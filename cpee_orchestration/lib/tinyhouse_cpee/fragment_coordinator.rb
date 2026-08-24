# frozen_string_literal: true

require 'json'
require 'securerandom'
require 'thread'
require 'uri'
require_relative 'cpee_client'
require_relative 'domain'
require_relative 'model_repository'
require_relative 'registry'

module TinyHouseCpee
  class UnknownFragmentError < StandardError
  end

  class FragmentStartError < StandardError
  end

  class FragmentEventError < StandardError
  end

  class FragmentCoordinator
    IDENTIFIER_PATTERN = /\A[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\z/.freeze
    MAX_ATTEMPT = 100
    EVENT_TOKEN_BYTES = 24

    # Configures durable child lifecycle orchestration.
    def initialize(fragments:, registry:, client:, public_base_url:)
      @fragments = fragments.freeze
      @registry = registry
      @client = client
      @public_base_url = ensure_trailing_slash(public_base_url)
      @locks = {}
      @locks_mutex = Mutex.new
    end

    # Idempotently creates a child and leaves the parent activity waiting.
    def start_and_await(request)
      validate_request!(request)
      fragment = @fragments[request.fragment_id]
      raise UnknownFragmentError, "unknown fragment #{request.fragment_id}" unless fragment

      key = DispatchKey.new(request.run_id, request.fragment_id, request.attempt)
      dispatch_lock(key).synchronize do
        token = SecureRandom.urlsafe_base64(EVENT_TOKEN_BYTES)
        rendered = ModelRepository.render_fragment(
          path: fragment.model_path,
          run_id: request.run_id,
          work_order_id: request.work_order_id,
          fragment_id: request.fragment_id,
          attempt: request.attempt,
          input_json: request.input_json,
          event_url: event_url(token)
        )
        claim = @registry.claim_dispatch(
          request,
          definition_sha256: rendered.definition_sha256,
          target_cpee_base: fragment.cpee_base_url,
          deterministic_info: rendered.deterministic_info,
          event_token: token
        )
        return resume_existing_dispatch(claim.record) unless claim.new_record

        create_and_start(claim.record, fragment, rendered.content)
      end
    end

    # Reconciles every active child and pending parent callback once.
    def reconcile
      @registry.reconcilable_dispatches.each do |record|
        reconcile_record(record)
      end
      nil
    end

    # Accepts one authenticated-by-token CPEE state notification.
    def handle_state_event(event_token:, child_instance_id:, child_instance_uuid:,
                           topic:, event:, notification_json:)
      record = @registry.find_dispatch_by_event_token(event_token)
      raise FragmentEventError, 'unknown event token' unless record
      unless record.child_instance_id == child_instance_id &&
             record.child_instance_uuid == child_instance_uuid
        raise FragmentEventError, 'event child identity does not match dispatch'
      end
      unless topic == 'state' && event == 'change'
        raise FragmentEventError, 'only state/change events are accepted'
      end

      notification = JSON.parse(notification_json)
      content = notification['content']
      state = content.is_a?(Hash) ? content['state'].to_s : ''
      raise FragmentEventError, 'state event has no content.state' if state.empty?

      observe_state(record, state)
    rescue JSON::ParserError => error
      raise FragmentEventError, "invalid notification JSON: #{error.message}"
    end

    private

    # Reuses known lifecycle state but refuses an ambiguous create replay.
    def resume_existing_dispatch(record)
      ambiguous = [DispatchPhase::CLAIMED, DispatchPhase::CREATE_UNKNOWN]
      if ambiguous.include?(record.phase)
        raise FragmentStartError,
              'child create outcome is unknown; operator reconciliation is required'
      end

      record
    end

    # Creates ready, persists identity, and only then issues running.
    def create_and_start(record, fragment, model)
      identity = @client.create_instance(fragment.cpee_base_url, model)
      ready = @registry.attach_child(record.key, identity)
      begin
        @client.start_instance(identity.instance_url)
        @registry.mark_running(record.key)
      rescue CpeeError => error
        @registry.set_dispatch_error(record.key, DispatchPhase::READY, error.message)
        ready
      end
    rescue CpeeError => error
      @registry.set_dispatch_error(
        record.key,
        DispatchPhase::CREATE_UNKNOWN,
        error.message
      )
      raise FragmentStartError,
            'child create outcome is unknown; automatic recreation is disabled'
    end

    # Reconciles one stored lifecycle phase.
    def reconcile_record(record)
      if [DispatchPhase::COMPLETION_PENDING, DispatchPhase::LOST].include?(record.phase)
        deliver_pending(record)
        return
      end
      return unless record.child_instance_url

      state = @client.get_state(record.child_instance_url)
      observe_state(record, state)
    rescue CpeeHttpError => error
      if error.status_code == 404
        lost = @registry.mark_lost(record.key, 'known CPEE child is missing')
        deliver_pending(lost)
      else
        @registry.set_dispatch_error(record.key, record.phase, error.message)
      end
    rescue CpeeError => error
      @registry.set_dispatch_error(record.key, record.phase, error.message)
    end

    # Applies one monotonic observed child state.
    def observe_state(record, state)
      case state
      when 'ready'
        start_known_ready(record)
      when 'running', 'stopping', 'stopped'
        @registry.mark_running(record.key) if state == 'running'
      when 'finished'
        complete_finished(record)
      when 'abandoned'
        terminal = @registry.mark_terminal(
          record.key,
          state: state,
          result_json: '{}',
          error: 'child CPEE instance was abandoned',
          salvage: true
        )
        deliver_pending(terminal)
      else
        @registry.set_dispatch_error(record.key, record.phase, "unknown child state #{state.inspect}")
      end
      @registry.fetch_dispatch(record.key)
    end

    # Retries a start only while the observed child is still ready.
    def start_known_ready(record)
      return unless record.child_instance_url

      @client.start_instance(record.child_instance_url)
      @registry.mark_running(record.key)
    end

    # Reads final data and stages a successful parent callback.
    def complete_finished(record)
      data_xml = @client.get_data_elements(record.child_instance_url)
      result_json = JSON.generate(ModelRepository.parse_data_elements(data_xml))
      terminal = @registry.mark_terminal(
        record.key,
        state: 'finished',
        result_json: result_json,
        error: nil,
        salvage: false
      )
      deliver_pending(terminal)
    end

    # Delivers the exact stored terminal payload to the waiting parent activity.
    def deliver_pending(record)
      callback_url = record.request.parent_callback_url
      unless @client.callback_pending?(callback_url)
        @registry.set_dispatch_error(
          record.key,
          record.phase,
          'parent callback is not currently registered'
        )
        return
      end
      fields = {
        'run_id' => record.key.run_id,
        'fragment_id' => record.key.fragment_id,
        'attempt' => record.key.attempt.to_s,
        'child_instance_id' => record.child_instance_id.to_s,
        'child_instance_uuid' => record.child_instance_uuid.to_s,
        'state' => record.terminal_state.to_s,
        'output_json' => record.result_json.to_s
      }
      @client.deliver_callback(
        callback_url,
        fields,
        salvage: record.callback_salvage
      )
      @registry.mark_callback_delivered(record.key)
    rescue CpeeError => error
      @registry.set_dispatch_error(record.key, record.phase, error.message)
    end

    # Enforces bounded, correlated input before reading a model or calling CPEE.
    def validate_request!(request)
      validate_identifier!(request.run_id, 'run_id')
      validate_identifier!(request.work_order_id, 'work_order_id')
      validate_identifier!(request.fragment_id, 'fragment_id')
      unless request.attempt.is_a?(Integer) && request.attempt.between?(1, MAX_ATTEMPT)
        raise ArgumentError, "attempt must be an integer between 1 and #{MAX_ATTEMPT}"
      end
      JSON.parse(request.input_json)
      validate_identifier!(request.parent_instance_uuid, 'parent_instance_uuid')
      validate_identifier!(request.parent_callback_id, 'parent_callback_id')
      validate_identifier!(request.parent_activity, 'parent_activity')
      validate_http_url!(request.parent_instance_url, 'parent instance URL')
      validate_http_url!(request.parent_callback_url, 'parent callback URL')
      validate_callback_owner!(request)
    rescue JSON::ParserError => error
      raise ArgumentError, "input_json is invalid: #{error.message}"
    end

    # Validates one correlation identifier.
    def validate_identifier!(value, label)
      return if IDENTIFIER_PATTERN.match?(value.to_s)

      raise ArgumentError, "#{label} must match #{IDENTIFIER_PATTERN.inspect}"
    end

    # Validates a callback destination from CPEE metadata.
    def validate_http_url!(value, label)
      uri = URI.parse(value)
      return if %w[http https].include?(uri.scheme) && uri.host

      raise ArgumentError, "#{label} must be an absolute HTTP(S) URL"
    rescue URI::InvalidURIError => error
      raise ArgumentError, "#{label} is invalid: #{error.message}"
    end

    # Ensures the callback resource is below the supplying parent instance URL.
    def validate_callback_owner!(request)
      parent_uri = URI.parse(ensure_trailing_slash(request.parent_instance_url))
      callback_uri = URI.parse(request.parent_callback_url)
      expected_path = "#{parent_uri.path}callbacks/#{request.parent_callback_id}/"
      same_origin = parent_uri.scheme == callback_uri.scheme &&
                    parent_uri.host == callback_uri.host &&
                    parent_uri.port == callback_uri.port
      valid = same_origin && callback_uri.path == expected_path &&
              callback_uri.query.nil? && callback_uri.fragment.nil?
      raise ArgumentError, 'parent callback URL does not belong to parent instance' unless valid
    end

    # Returns a stable per-dispatch in-process critical section.
    def dispatch_lock(key)
      storage_key = [key.run_id, key.fragment_id, key.attempt]
      @locks_mutex.synchronize { @locks[storage_key] ||= Mutex.new }
    end

    # Builds the token-bearing child state event target.
    def event_url(token)
      URI.join(@public_base_url, "v1/cpee/events/#{token}").to_s
    end

    # Normalizes a base URL for relative path resolution.
    def ensure_trailing_slash(value)
      "#{value.sub(%r{/+\z}, '')}/"
    end
  end
end
