# frozen_string_literal: true

require 'json'
require 'fileutils'
require 'pstore'
require 'thread'
require 'time'
require_relative 'domain'

module TinyHouseCpee
  class RegistryConflict < StandardError
  end

  class Registry
    TIMESTAMP_PRECISION = 6
    RECONCILABLE_PHASES = [
      DispatchPhase::READY,
      DispatchPhase::RUNNING,
      DispatchPhase::COMPLETION_PENDING,
      DispatchPhase::LOST
    ].freeze

    # Creates or opens one transactional local orchestration store.
    def initialize(path)
      directory = File.dirname(path)
      FileUtils.mkdir_p(directory)
      @store = PStore.new(path)
      @mutex = Mutex.new
      write_transaction do
        @store[:dispatches] ||= {}
        @store[:runs] ||= {}
      end
    end

    # Atomically claims one immutable fragment execution.
    def claim_dispatch(request, definition_sha256:, target_cpee_base:, deterministic_info:, event_token:)
      key = DispatchKey.new(request.run_id, request.fragment_id, request.attempt)
      write_transaction do
        dispatches = @store[:dispatches]
        stored = dispatches[dispatch_storage_key(key)]
        if stored
          record = dispatch_from_hash(stored)
          ensure_dispatch_matches!(
            record,
            request,
            definition_sha256,
            target_cpee_base,
            deterministic_info
          )
          DispatchClaim.new(record: record, new_record: false)
        else
          timestamp = current_timestamp
          record = DispatchRecord.new(
            key: key,
            request: request,
            definition_sha256: definition_sha256,
            target_cpee_base: target_cpee_base,
            deterministic_info: deterministic_info,
            event_token: event_token,
            phase: DispatchPhase::CLAIMED,
            created_at: timestamp,
            updated_at: timestamp,
            callback_salvage: false
          )
          dispatches[dispatch_storage_key(key)] = dispatch_to_hash(record)
          @store[:dispatches] = dispatches
          DispatchClaim.new(record: record, new_record: true)
        end
      end
    end

    # Persists a created child identity before any start command.
    def attach_child(key, identity)
      update_dispatch(key) do |record|
        record.phase = DispatchPhase::READY
        record.child_instance_id = identity.instance_id
        record.child_instance_url = identity.instance_url
        record.child_instance_uuid = identity.instance_uuid
        record.last_error = nil
      end
    end

    # Marks a known child as running without changing its identity.
    def mark_running(key)
      update_dispatch(key) do |record|
        record.phase = DispatchPhase::RUNNING
        record.last_error = nil
      end
    end

    # Stores a terminal outcome before attempting its parent callback.
    def mark_terminal(key, state:, result_json:, error:, salvage:)
      update_dispatch(key) do |record|
        record.phase = DispatchPhase::COMPLETION_PENDING
        record.terminal_state = state
        record.result_json = result_json
        record.last_error = error
        record.callback_salvage = salvage
      end
    end

    # Marks an irrecoverably missing known child for a salvage callback.
    def mark_lost(key, error)
      update_dispatch(key) do |record|
        record.phase = DispatchPhase::LOST
        record.terminal_state = 'lost'
        record.result_json = '{}'
        record.last_error = error
        record.callback_salvage = true
      end
    end

    # Records that CPEE accepted the stored terminal callback payload.
    def mark_callback_delivered(key)
      update_dispatch(key) do |record|
        record.phase = DispatchPhase::COMPLETED
        record.last_error = nil
      end
    end

    # Preserves a lifecycle phase while attaching a diagnostic failure.
    def set_dispatch_error(key, phase, error)
      update_dispatch(key) do |record|
        record.phase = phase
        record.last_error = error
      end
    end

    # Reads one dispatch or raises when its correlation key is unknown.
    def fetch_dispatch(key)
      read_transaction do
        stored = @store[:dispatches][dispatch_storage_key(key)]
        raise KeyError, "unknown dispatch #{dispatch_storage_key(key)}" unless stored

        dispatch_from_hash(stored)
      end
    end

    # Finds the dispatch assigned to an unguessable event token.
    def find_dispatch_by_event_token(event_token)
      read_transaction do
        stored = @store[:dispatches].values.find do |candidate|
          candidate.fetch(:event_token) == event_token
        end
        stored ? dispatch_from_hash(stored) : nil
      end
    end

    # Lists active or callback-pending child executions for reconciliation.
    def reconcilable_dispatches
      read_transaction do
        @store[:dispatches].values.map { |value| dispatch_from_hash(value) }.select do |record|
          RECONCILABLE_PHASES.include?(record.phase)
        end
      end
    end

    # Lists all child records correlated with one holistic run.
    def dispatches_for_run(run_id)
      read_transaction do
        @store[:dispatches].values.map { |value| dispatch_from_hash(value) }.select do |record|
          record.key.run_id == run_id
        end
      end
    end

    # Atomically claims one rendered holistic coordinator deployment.
    def claim_run(run_id, work_order_id, model_sha256)
      write_transaction do
        runs = @store[:runs]
        stored = runs[run_id]
        if stored
          record = run_from_hash(stored)
          ensure_run_matches!(record, work_order_id, model_sha256)
          RunClaim.new(record: record, new_record: false)
        else
          timestamp = current_timestamp
          record = RunRecord.new(
            run_id: run_id,
            work_order_id: work_order_id,
            model_sha256: model_sha256,
            phase: RunPhase::CLAIMED,
            created_at: timestamp,
            updated_at: timestamp
          )
          runs[run_id] = run_to_hash(record)
          @store[:runs] = runs
          RunClaim.new(record: record, new_record: true)
        end
      end
    end

    # Persists the holistic CPEE identity before starting it.
    def attach_run(run_id, identity)
      update_run(run_id) do |record|
        record.phase = RunPhase::READY
        record.instance_id = identity.instance_id
        record.instance_url = identity.instance_url
        record.instance_uuid = identity.instance_uuid
        record.last_error = nil
      end
    end

    # Records that the holistic coordinator is running.
    def mark_run_running(run_id)
      update_run(run_id) do |record|
        record.phase = RunPhase::RUNNING
        record.last_error = nil
      end
    end

    # Blocks blind parent recreation after an ambiguous create request.
    def mark_run_create_unknown(run_id, error)
      update_run(run_id) do |record|
        record.phase = RunPhase::CREATE_UNKNOWN
        record.last_error = error
      end
    end

    # Retains a known ready parent after a failed start request.
    def set_run_ready_error(run_id, error)
      update_run(run_id) do |record|
        record.phase = RunPhase::READY
        record.last_error = error
      end
    end

    # Reads one holistic run deployment when present.
    def fetch_run(run_id)
      read_transaction do
        stored = @store[:runs][run_id]
        stored ? run_from_hash(stored) : nil
      end
    end

    private

    # Applies an atomic mutation to one dispatch record.
    def update_dispatch(key)
      write_transaction do
        dispatches = @store[:dispatches]
        storage_key = dispatch_storage_key(key)
        stored = dispatches[storage_key]
        raise KeyError, "unknown dispatch #{storage_key}" unless stored

        record = dispatch_from_hash(stored)
        yield record
        record.updated_at = current_timestamp
        dispatches[storage_key] = dispatch_to_hash(record)
        @store[:dispatches] = dispatches
        record
      end
    end

    # Applies an atomic mutation to one holistic run record.
    def update_run(run_id)
      write_transaction do
        runs = @store[:runs]
        stored = runs[run_id]
        raise KeyError, "unknown holistic run #{run_id}" unless stored

        record = run_from_hash(stored)
        yield record
        record.updated_at = current_timestamp
        runs[run_id] = run_to_hash(record)
        @store[:runs] = runs
        record
      end
    end

    # Rejects reuse of a dispatch key with changed physical-work input.
    def ensure_dispatch_matches!(record, request, definition_sha256, target_cpee_base, deterministic_info)
      matching = record.request.to_h == request.to_h &&
                 record.definition_sha256 == definition_sha256 &&
                 record.target_cpee_base == target_cpee_base &&
                 record.deterministic_info == deterministic_info
      return if matching

      raise RegistryConflict, "dispatch #{dispatch_storage_key(record.key)} has different immutable input"
    end

    # Rejects reuse of a run ID with changed coordinator input.
    def ensure_run_matches!(record, work_order_id, model_sha256)
      return if record.work_order_id == work_order_id && record.model_sha256 == model_sha256

      raise RegistryConflict, "holistic run #{record.run_id} has different immutable input"
    end

    # Encodes an unambiguous dispatch key for persistent hash storage.
    def dispatch_storage_key(key)
      JSON.generate([key.run_id, key.fragment_id, key.attempt])
    end

    # Converts a typed dispatch into primitive PStore data.
    def dispatch_to_hash(record)
      {
        key: record.key.to_h,
        request: record.request.to_h,
        definition_sha256: record.definition_sha256,
        target_cpee_base: record.target_cpee_base,
        deterministic_info: record.deterministic_info,
        event_token: record.event_token,
        phase: record.phase,
        child_instance_id: record.child_instance_id,
        child_instance_url: record.child_instance_url,
        child_instance_uuid: record.child_instance_uuid,
        terminal_state: record.terminal_state,
        result_json: record.result_json,
        last_error: record.last_error,
        callback_salvage: record.callback_salvage,
        created_at: record.created_at,
        updated_at: record.updated_at
      }
    end

    # Reconstructs a typed dispatch from primitive PStore data.
    def dispatch_from_hash(value)
      DispatchRecord.new(
        key: DispatchKey.new(*value.fetch(:key).values_at(:run_id, :fragment_id, :attempt)),
        request: DispatchRequest.new(**value.fetch(:request)),
        definition_sha256: value.fetch(:definition_sha256),
        target_cpee_base: value.fetch(:target_cpee_base),
        deterministic_info: value.fetch(:deterministic_info),
        event_token: value.fetch(:event_token),
        phase: value.fetch(:phase),
        child_instance_id: value[:child_instance_id],
        child_instance_url: value[:child_instance_url],
        child_instance_uuid: value[:child_instance_uuid],
        terminal_state: value[:terminal_state],
        result_json: value[:result_json],
        last_error: value[:last_error],
        callback_salvage: value.fetch(:callback_salvage, false),
        created_at: value.fetch(:created_at),
        updated_at: value.fetch(:updated_at)
      )
    end

    # Converts a typed run into primitive PStore data.
    def run_to_hash(record)
      record.to_h
    end

    # Reconstructs a typed holistic run from primitive PStore data.
    def run_from_hash(value)
      RunRecord.new(**value)
    end

    # Returns one UTC audit timestamp.
    def current_timestamp
      Time.now.utc.iso8601(TIMESTAMP_PRECISION)
    end

    # Runs a synchronized read-only PStore transaction.
    def read_transaction(&block)
      @mutex.synchronize { @store.transaction(true, &block) }
    end

    # Runs a synchronized write PStore transaction.
    def write_transaction(&block)
      @mutex.synchronize { @store.transaction(false, &block) }
    end
  end
end
