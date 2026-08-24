# frozen_string_literal: true

require_relative 'test_helper'

require 'tinyhouse_cpee/registry'

class RegistryTest < Minitest::Test
  # Verifies duplicate dispatch claims reuse one durable record.
  def test_dispatch_claim_is_idempotent_across_registry_instances
    Dir.mktmpdir do |directory|
      path = File.join(directory, 'registry.pstore')
      request = dispatch_request
      first = TinyHouseCpee::Registry.new(path).claim_dispatch(
        request,
        definition_sha256: 'digest-a',
        target_cpee_base: 'http://wa1/',
        deterministic_info: 'tinyhouse:run-1:wa1:1',
        event_token: 'token-a'
      )
      second = TinyHouseCpee::Registry.new(path).claim_dispatch(
        request,
        definition_sha256: 'digest-a',
        target_cpee_base: 'http://wa1/',
        deterministic_info: 'tinyhouse:run-1:wa1:1',
        event_token: 'different-unused-token'
      )

      assert first.new_record
      refute second.new_record
      assert_equal first.record.event_token, second.record.event_token
    end
  end

  # Verifies changed immutable input cannot reuse an existing dispatch key.
  def test_changed_dispatch_input_is_a_conflict
    Dir.mktmpdir do |directory|
      registry = TinyHouseCpee::Registry.new(File.join(directory, 'registry.pstore'))
      registry.claim_dispatch(
        dispatch_request,
        definition_sha256: 'digest-a',
        target_cpee_base: 'http://wa1/',
        deterministic_info: 'tinyhouse:run-1:wa1:1',
        event_token: 'token-a'
      )
      changed = dispatch_request(input_json: '{"size":"standard"}')

      assert_raises(TinyHouseCpee::RegistryConflict) do
        registry.claim_dispatch(
          changed,
          definition_sha256: 'digest-a',
          target_cpee_base: 'http://wa1/',
          deterministic_info: 'tinyhouse:run-1:wa1:1',
          event_token: 'token-b'
        )
      end
    end
  end

  # Verifies lifecycle transitions and terminal callback state are persistent.
  def test_dispatch_lifecycle_is_persisted
    Dir.mktmpdir do |directory|
      registry = TinyHouseCpee::Registry.new(File.join(directory, 'registry.pstore'))
      claim = registry.claim_dispatch(
        dispatch_request,
        definition_sha256: 'digest-a',
        target_cpee_base: 'http://wa1/',
        deterministic_info: 'tinyhouse:run-1:wa1:1',
        event_token: 'token-a'
      )
      identity = TinyHouseCpee::InstanceIdentity.new('17', 'http://wa1/17/', 'uuid-17')
      registry.attach_child(claim.record.key, identity)
      registry.mark_running(claim.record.key)
      registry.mark_terminal(
        claim.record.key,
        state: 'finished',
        result_json: '{"component_id":"base-7"}',
        error: nil,
        salvage: false
      )
      registry.mark_callback_delivered(claim.record.key)
      record = registry.fetch_dispatch(claim.record.key)

      assert_equal TinyHouseCpee::DispatchPhase::COMPLETED, record.phase
      assert_equal 'uuid-17', record.child_instance_uuid
      assert_equal 'finished', record.terminal_state
    end
  end

  # Builds a valid dispatch request and applies selected overrides.
  def dispatch_request(overrides = {})
    values = {
      run_id: 'run-1',
      work_order_id: 'order-1',
      fragment_id: 'wa1',
      attempt: 1,
      input_json: '{"size":"large"}',
      parent_instance_uuid: 'parent-uuid',
      parent_instance_url: 'http://parent/8/',
      parent_callback_url: 'http://parent/callbacks/cb/',
      parent_callback_id: 'cb',
      parent_activity: 'a_wa1'
    }.merge(overrides)
    TinyHouseCpee::DispatchRequest.new(**values)
  end
end
