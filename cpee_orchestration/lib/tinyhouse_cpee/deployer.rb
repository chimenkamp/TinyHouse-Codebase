# frozen_string_literal: true

require 'digest'
require_relative 'cpee_client'
require_relative 'model_repository'
require_relative 'registry'

module TinyHouseCpee
  class HolisticDeploymentError < StandardError
  end

  class HolisticDeployer
    IDENTIFIER_PATTERN = /\A[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\z/.freeze

    # Configures safe holistic instance deployment.
    def initialize(coordinator_cpee_base_url:, holistic_model_path:, fragment_gateway_url:,
                   registry:, client:)
      @coordinator_cpee_base_url = coordinator_cpee_base_url
      @holistic_model_path = holistic_model_path
      @fragment_gateway_url = fragment_gateway_url
      @registry = registry
      @client = client
      @mutex = Mutex.new
    end

    # Idempotently renders, creates, persists, and starts one parent instance.
    def deploy(run_id, work_order_id)
      validate_identifier!(run_id, 'run_id')
      validate_identifier!(work_order_id, 'work_order_id')
      model = ModelRepository.render_holistic(
        path: @holistic_model_path,
        run_id: run_id,
        work_order_id: work_order_id,
        gateway_url: @fragment_gateway_url
      )
      digest = Digest::SHA256.hexdigest(model)
      @mutex.synchronize do
        claim = @registry.claim_run(run_id, work_order_id, digest)
        return resume_known(claim.record) unless claim.new_record

        create_and_start(claim.record, model)
      end
    end

    private

    # Creates the ready parent, stores identity, and then starts it.
    def create_and_start(record, model)
      identity = @client.create_instance(@coordinator_cpee_base_url, model)
      ready = @registry.attach_run(record.run_id, identity)
      start_ready(ready)
    rescue CpeeError => error
      @registry.mark_run_create_unknown(record.run_id, error.message)
      raise HolisticDeploymentError,
            'coordinator create outcome is unknown; automatic recreation is disabled'
    end

    # Resumes only a known ready parent and never recreates unknown work.
    def resume_known(record)
      return record if record.phase == RunPhase::RUNNING
      return start_ready(record) if record.phase == RunPhase::READY

      raise HolisticDeploymentError,
            "coordinator run is #{record.phase}; operator reconciliation is required"
    end

    # Starts a parent whose complete CPEE identity is already durable.
    def start_ready(record)
      raise HolisticDeploymentError, 'ready coordinator has no instance URL' unless record.instance_url

      @client.start_instance(record.instance_url)
      @registry.mark_run_running(record.run_id)
    rescue CpeeError => error
      @registry.set_run_ready_error(record.run_id, error.message)
      raise HolisticDeploymentError,
            'coordinator exists but could not be confirmed running'
    end

    # Validates one bounded run correlation identifier.
    def validate_identifier!(value, label)
      return if IDENTIFIER_PATTERN.match?(value.to_s)

      raise ArgumentError, "#{label} must match #{IDENTIFIER_PATTERN.inspect}"
    end
  end
end

