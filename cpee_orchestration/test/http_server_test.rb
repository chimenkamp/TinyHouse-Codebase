# frozen_string_literal: true

require_relative 'test_helper'

require 'json'
require 'net/http'
require 'uri'
require 'tinyhouse_cpee/http_server'

class FakeHttpCoordinator
  attr_reader :requests, :events

  # Initializes captured gateway calls.
  def initialize
    @requests = []
    @events = []
  end

  # Captures a parent activity and returns its child identity.
  def start_and_await(request)
    @requests << request
    TinyHouseCpee::DispatchRecord.new(
      key: TinyHouseCpee::DispatchKey.new(request.run_id, request.fragment_id, request.attempt),
      request: request,
      phase: TinyHouseCpee::DispatchPhase::RUNNING,
      event_token: 'token',
      child_instance_id: '17',
      child_instance_url: 'http://child/17/',
      child_instance_uuid: 'uuid-17'
    )
  end

  # Captures one CPEE state webhook.
  def handle_state_event(**event)
    @events << event
  end
end

class FakeHttpDeployer
  attr_reader :deployments

  # Initializes captured holistic deployments.
  def initialize
    @deployments = []
  end

  # Returns one running holistic run record.
  def deploy(run_id, work_order_id)
    @deployments << [run_id, work_order_id]
    TinyHouseCpee::RunRecord.new(
      run_id: run_id,
      work_order_id: work_order_id,
      phase: TinyHouseCpee::RunPhase::RUNNING,
      instance_id: '5',
      instance_url: 'http://coordinator/5/',
      instance_uuid: 'uuid-5'
    )
  end
end

class FakeHttpRegistry
  # Returns no persisted run for status-route tests.
  def fetch_run(_run_id)
    nil
  end

  # Returns no child records for status-route tests.
  def dispatches_for_run(_run_id)
    []
  end
end

class HttpServerTest < Minitest::Test
  # Starts the Ruby gateway on an isolated loopback port.
  def setup
    @coordinator = FakeHttpCoordinator.new
    @deployer = FakeHttpDeployer.new
    @server = TinyHouseCpee::HttpServer.new(
      host: '127.0.0.1',
      port: 0,
      coordinator: @coordinator,
      deployer: @deployer,
      registry: FakeHttpRegistry.new
    )
    @thread = Thread.new { @server.start }
    @base_uri = URI("http://127.0.0.1:#{@server.bound_port}")
  end

  # Stops the isolated Ruby gateway.
  def teardown
    @server.shutdown
    @thread.join
  end

  # Verifies a CPEE activity is held with asynchronous callback semantics.
  def test_fragment_route_returns_cpee_callback_headers_and_empty_body
    uri = URI.join(@base_uri.to_s, '/v1/fragments/start-and-await')
    request = Net::HTTP::Post.new(uri)
    request['Content-Type'] = 'application/x-www-form-urlencoded'
    request['CPEE-INSTANCE-UUID'] = 'parent-uuid'
    request['CPEE-INSTANCE-URL'] = 'http://parent/8/'
    request['CPEE-CALLBACK'] = 'http://parent/8/callbacks/cb/'
    request['CPEE-CALLBACK-ID'] = 'cb'
    request['CPEE-ACTIVITY'] = 'a_wa1'
    request.body = URI.encode_www_form(
      'run_id' => 'run-1',
      'work_order_id' => 'order-1',
      'fragment_id' => 'wa1',
      'attempt' => '1',
      'input_json' => '{"size":"large"}'
    )

    response = Net::HTTP.start(uri.host, uri.port) { |http| http.request(request) }

    assert_equal '202', response.code
    assert_equal 'true', response['cpee-callback']
    assert_equal '', response.body.to_s
    assert_includes response['cpee-instantiation'], 'uuid-17'
    assert_equal 'parent-uuid', @coordinator.requests.first.parent_instance_uuid
  end

  # Verifies a run API request deploys the executable holistic CPEE model.
  def test_run_route_returns_created_coordinator_identity
    uri = URI.join(@base_uri.to_s, '/v1/runs')
    request = Net::HTTP::Post.new(uri)
    request['Content-Type'] = 'application/json'
    request.body = JSON.generate('run_id' => 'run-2', 'work_order_id' => 'order-2')

    response = Net::HTTP.start(uri.host, uri.port) { |http| http.request(request) }
    body = JSON.parse(response.body)

    assert_equal '201', response.code
    assert_equal '5', body.fetch('instance_id')
    assert_equal [['run-2', 'order-2']], @deployer.deployments
  end

  # Verifies child state events retain CPEE identity and notification content.
  def test_event_route_passes_correlation_to_coordinator
    uri = URI.join(@base_uri.to_s, '/v1/cpee/events/token-1')
    request = Net::HTTP::Post.new(uri)
    request['Content-Type'] = 'application/x-www-form-urlencoded'
    request['CPEE-INSTANCE'] = '17'
    request['CPEE-INSTANCE-UUID'] = 'uuid-17'
    request.body = URI.encode_www_form(
      'topic' => 'state',
      'event' => 'change',
      'notification' => '{"content":{"state":"finished"}}'
    )

    response = Net::HTTP.start(uri.host, uri.port) { |http| http.request(request) }

    assert_equal '204', response.code
    assert_equal 'token-1', @coordinator.events.first.fetch(:event_token)
    assert_equal 'uuid-17', @coordinator.events.first.fetch(:child_instance_uuid)
  end

  # Verifies CPEE's multipart notification producer format is accepted.
  def test_event_route_accepts_multipart_cpee_notification
    uri = URI.join(@base_uri.to_s, '/v1/cpee/events/token-2')
    boundary = 'tinyhouse-cpee-boundary'
    request = Net::HTTP::Post.new(uri)
    request['Content-Type'] = "multipart/form-data; boundary=#{boundary}"
    request['CPEE-INSTANCE'] = '18'
    request['CPEE-INSTANCE-UUID'] = 'uuid-18'
    request.body = multipart_body(
      boundary,
      'topic' => ['text/plain', 'state'],
      'event' => ['text/plain', 'change'],
      'notification' => ['application/json', '{"content":{"state":"finished"}}']
    )

    response = Net::HTTP.start(uri.host, uri.port) { |http| http.request(request) }

    assert_equal '204', response.code
    assert_equal 'token-2', @coordinator.events.last.fetch(:event_token)
    assert_equal '{"content":{"state":"finished"}}', @coordinator.events.last.fetch(:notification_json)
  end

  private

  # Builds a minimal multipart body matching Riddl's named parameters.
  def multipart_body(boundary, fields)
    parts = fields.map do |name, (content_type, value)|
      [
        "--#{boundary}\r\n",
        "Content-Disposition: form-data; name=\"#{name}\"\r\n",
        "Content-Type: #{content_type}\r\n\r\n",
        "#{value}\r\n"
      ].join
    end
    "#{parts.join}--#{boundary}--\r\n"
  end
end
