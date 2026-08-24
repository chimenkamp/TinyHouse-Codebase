# frozen_string_literal: true

require_relative 'test_helper'

require 'tinyhouse_cpee/configuration'
require 'tinyhouse_cpee/fragment_coordinator'

class FakeCpeeClient
  attr_accessor :state, :create_error, :start_error
  attr_reader :create_count, :start_count, :callbacks, :models

  # Initializes observable fake CPEE state.
  def initialize
    @create_count = 0
    @start_count = 0
    @state = 'running'
    @create_error = nil
    @start_error = nil
    @callbacks = []
    @models = []
  end

  # Returns one deterministic child identity.
  def create_instance(base_url, model)
    @create_count += 1
    raise @create_error if @create_error

    @models << model
    TinyHouseCpee::InstanceIdentity.new('17', "#{base_url}17/", 'child-uuid')
  end

  # Records the child start request.
  def start_instance(_instance_url)
    @start_count += 1
    if @start_error
      error = @start_error
      @start_error = nil
      raise error
    end
  end

  # Returns the configured child state.
  def get_state(_instance_url)
    @state
  end

  # Returns deterministic terminal data.
  def get_data_elements(_instance_url)
    '<dataelements><component_id>base-7</component_id></dataelements>'
  end

  # Reports that the parent callback remains pending.
  def callback_pending?(_callback_url)
    true
  end

  # Captures a parent callback delivery.
  def deliver_callback(url, fields, salvage:)
    @callbacks << [url, fields, salvage]
  end
end

class FragmentCoordinatorTest < Minitest::Test
  DESCRIPTION_NAMESPACE = 'http://cpee.org/ns/description/1.0'
  PROPERTIES_NAMESPACE = 'http://cpee.org/ns/properties/2.0'

  # Creates an isolated coordinator and real fragment definition.
  def setup
    @directory = Dir.mktmpdir
    @model_path = File.join(@directory, 'wa1.xml')
    File.write(@model_path, minimal_fragment_model)
    fragment = TinyHouseCpee::FragmentConfig.new(
      'wa1', 'http://wa1-cpee:8298/', @model_path
    )
    @registry = TinyHouseCpee::Registry.new(File.join(@directory, 'registry.pstore'))
    @client = FakeCpeeClient.new
    @coordinator = TinyHouseCpee::FragmentCoordinator.new(
      fragments: { 'wa1' => fragment },
      registry: @registry,
      client: @client,
      public_base_url: 'http://gateway:8400/'
    )
  end

  # Removes the isolated registry and model.
  def teardown
    FileUtils.remove_entry(@directory)
  end

  # Verifies repeated parent delivery creates and starts only one child.
  def test_duplicate_dispatch_creates_one_child
    first = @coordinator.start_and_await(dispatch_request)
    second = @coordinator.start_and_await(dispatch_request)

    assert_equal 1, @client.create_count
    assert_equal 1, @client.start_count
    assert_equal first.key, second.key
    assert_equal TinyHouseCpee::DispatchPhase::RUNNING, second.phase
  end

  # Verifies concurrent duplicate HTTP deliveries cannot create two children.
  def test_concurrent_duplicate_dispatch_creates_one_child
    threads = Array.new(8) do
      Thread.new { @coordinator.start_and_await(dispatch_request) }
    end
    records = threads.map(&:value)

    assert_equal 1, @client.create_count
    assert_equal 1, @client.start_count
    assert_equal 1, records.map(&:child_instance_uuid).uniq.length
  end

  # Verifies finished data is returned through the asynchronous parent callback.
  def test_finished_child_delivers_output
    record = @coordinator.start_and_await(dispatch_request)
    @client.state = 'finished'

    @coordinator.reconcile
    stored = @registry.fetch_dispatch(record.key)

    assert_equal TinyHouseCpee::DispatchPhase::COMPLETED, stored.phase
    assert_equal 1, @client.callbacks.length
    callback = @client.callbacks.first
    assert_equal 'http://parent/8/callbacks/cb/', callback[0]
    refute callback[2]
    assert_includes callback[1].fetch('output_json'), 'base-7'
  end

  # Verifies abnormal child termination raises WEEL salvage in the parent.
  def test_abandoned_child_delivers_salvage
    @coordinator.start_and_await(dispatch_request)
    @client.state = 'abandoned'

    @coordinator.reconcile

    assert @client.callbacks.first[2]
    assert_equal 'abandoned', @client.callbacks.first[1].fetch('state')
  end

  # Verifies arbitrary model paths and target URLs cannot come from a parent call.
  def test_unknown_fragment_is_rejected_before_create
    request = dispatch_request(fragment_id: 'arbitrary')

    assert_raises(TinyHouseCpee::UnknownFragmentError) do
      @coordinator.start_and_await(request)
    end
    assert_equal 0, @client.create_count
  end

  # Verifies the callback URL belongs to the CPEE parent instance that supplied it.
  def test_callback_outside_parent_instance_is_rejected
    request = dispatch_request(
      parent_instance_url: 'http://parent/8/',
      parent_callback_url: 'http://attacker/callbacks/cb/'
    )

    assert_raises(ArgumentError) do
      @coordinator.start_and_await(request)
    end
    assert_equal 0, @client.create_count
  end

  # Verifies webhook correlation checks reject a spoofed child UUID.
  def test_state_event_must_match_child_identity
    record = @coordinator.start_and_await(dispatch_request)

    assert_raises(TinyHouseCpee::FragmentEventError) do
      @coordinator.handle_state_event(
        event_token: record.event_token,
        child_instance_id: '17',
        child_instance_uuid: 'spoofed',
        topic: 'state',
        event: 'change',
        notification_json: '{"content":{"state":"finished"}}'
      )
    end
  end

  # Verifies a correlated state event completes without waiting for the poller.
  def test_finished_state_event_delivers_parent_callback
    record = @coordinator.start_and_await(dispatch_request)

    @coordinator.handle_state_event(
      event_token: record.event_token,
      child_instance_id: '17',
      child_instance_uuid: 'child-uuid',
      topic: 'state',
      event: 'change',
      notification_json: '{"content":{"state":"finished"}}'
    )

    assert_equal 1, @client.callbacks.length
    assert_equal TinyHouseCpee::DispatchPhase::COMPLETED,
                 @registry.fetch_dispatch(record.key).phase
  end

  # Verifies an ambiguous create is never retried as duplicate physical work.
  def test_ambiguous_create_is_persisted_and_not_reissued
    @client.create_error = TinyHouseCpee::CpeeError.new('create timed out')

    assert_raises(TinyHouseCpee::FragmentStartError) do
      @coordinator.start_and_await(dispatch_request)
    end
    assert_raises(TinyHouseCpee::FragmentStartError) do
      @coordinator.start_and_await(dispatch_request)
    end
    assert_equal 1, @client.create_count
  end

  # Verifies a timed-out start is resolved by observing state before more work.
  def test_start_timeout_is_reconciled_from_child_state
    @client.start_error = TinyHouseCpee::CpeeError.new('start timed out')
    record = @coordinator.start_and_await(dispatch_request)
    @client.state = 'running'

    @coordinator.reconcile
    stored = @registry.fetch_dispatch(record.key)

    assert_equal TinyHouseCpee::DispatchPhase::READY, record.phase
    assert_equal TinyHouseCpee::DispatchPhase::RUNNING, stored.phase
    assert_equal 1, @client.create_count
    assert_equal 1, @client.start_count
  end

  # Builds a valid parent activity request with selected overrides.
  def dispatch_request(overrides = {})
    values = {
      run_id: 'run-7',
      work_order_id: 'order-9',
      fragment_id: 'wa1',
      attempt: 1,
      input_json: '{"size":"large"}',
      parent_instance_uuid: 'parent-uuid',
      parent_instance_url: 'http://parent/8/',
      parent_callback_url: 'http://parent/8/callbacks/cb/',
      parent_callback_id: 'cb',
      parent_activity: 'a_wa1'
    }.merge(overrides)
    TinyHouseCpee::DispatchRequest.new(**values)
  end

  # Returns a valid executable fragment envelope for gateway tests.
  def minimal_fragment_model
    <<~XML
      <?xml version="1.0"?>
      <testset xmlns="#{PROPERTIES_NAMESPACE}">
        <state>ready</state>
        <executionhandler>ruby</executionhandler>
        <dataelements/>
        <endpoints/>
        <attributes><info>Child</info></attributes>
        <description>
          <description xmlns="#{DESCRIPTION_NAMESPACE}">
            <manipulate id="a1">data.run_id = data.run_id</manipulate>
          </description>
        </description>
        <transformation>
          <description type="copy"/>
          <dataelements type="none"/>
          <endpoints type="none"/>
        </transformation>
      </testset>
    XML
  end
end
