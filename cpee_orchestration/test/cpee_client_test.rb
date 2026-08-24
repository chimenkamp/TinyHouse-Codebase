# frozen_string_literal: true

require_relative 'test_helper'

require 'webrick'
require 'tinyhouse_cpee/cpee_client'

class CpeeTestServlet < WEBrick::HTTPServlet::AbstractServlet
  # Retains the test case that owns the deterministic routes.
  def initialize(server, owner)
    super(server)
    @owner = owner
  end

  # Handles every HTTP method through the same test route table.
  def service(request, response)
    @owner.send(:capture_request, request)
    @owner.send(:route_request, request, response)
  end
end

class CpeeClientTest < Minitest::Test
  # Starts a deterministic HTTP double for the CPEE wire contract.
  def setup
    @requests = []
    @omit_identity = false
    @server = WEBrick::HTTPServer.new(
      BindAddress: '127.0.0.1',
      Port: 0,
      Logger: WEBrick::Log.new(File::NULL),
      AccessLog: []
    )
    mount_routes
    @thread = Thread.new { @server.start }
    port = @server.listeners.first.addr[1]
    @base_url = "http://127.0.0.1:#{port}/"
    @client = TinyHouseCpee::CpeeClient.new(timeout_seconds: 1.0)
  end

  # Stops the local HTTP double.
  def teardown
    @server&.shutdown
    @thread&.join
  end

  # Verifies the exact Cockpit-compatible full-instance POST contract.
  def test_create_instance_posts_raw_xml_and_parses_identity
    model = '<testset xmlns="http://cpee.org/ns/properties/2.0"/>'

    instance = @client.create_instance(@base_url, model)
    request = @requests.first

    assert_equal 'POST', request.fetch(:method)
    assert_equal '/', request.fetch(:path)
    assert_equal 'application/xml', request.fetch(:content_type)
    assert_equal 'xml', request.fetch(:content_id)
    assert_equal model, request.fetch(:body)
    assert_equal '23', instance.instance_id
    assert_equal "#{@base_url}23/", instance.instance_url
    assert_equal 'uuid-23', instance.instance_uuid
  end

  # Verifies ready instances are started through the state property.
  def test_start_instance_puts_url_encoded_running_state
    @client.start_instance("#{@base_url}23/")
    request = @requests.last

    assert_equal 'PUT', request.fetch(:method)
    assert_equal '/23/properties/state/', request.fetch(:path)
    assert_equal 'value=running', request.fetch(:body)
  end

  # Verifies polling and callback delivery use the CPEE resources.
  def test_state_data_and_salvage_callback_contracts
    state = @client.get_state("#{@base_url}23/")
    data = @client.get_data_elements("#{@base_url}23/")
    pending = @client.callback_pending?("#{@base_url}23/callbacks/cb/")
    @client.deliver_callback(
      "#{@base_url}23/callbacks/cb/",
      { 'state' => 'abandoned', 'run_id' => 'run-1' },
      salvage: true
    )

    assert_equal 'finished', state
    assert_includes data, '<component_id>base-7</component_id>'
    assert pending
    callback = @requests.last
    assert_equal 'true', callback.fetch(:salvage)
    assert_includes callback.fetch(:body), 'state=abandoned'
  end

  # Verifies an ambiguous create response is rejected instead of fabricated.
  def test_create_requires_complete_instance_identity
    @omit_identity = true

    assert_raises(TinyHouseCpee::CpeeProtocolError) do
      @client.create_instance(@base_url, '<testset/>')
    end
  end

  private

  # Mounts the fake CPEE lifecycle and callback resources.
  def mount_routes
    @server.mount('/', CpeeTestServlet, self)
  end

  # Records relevant request details for assertions.
  def capture_request(request)
    @requests << {
      method: request.request_method,
      path: request.path,
      content_type: request['content-type'],
      content_id: request['content-id'],
      salvage: request['cpee-salvage'],
      body: request.body.to_s
    }
  end

  # Returns deterministic CPEE responses for each resource.
  def route_request(request, response)
    case [request.request_method, request.path]
    when ['POST', '/']
      response.status = 200
      response.body = '23'
      unless @omit_identity
        response['CPEE-INSTANCE'] = '23'
        response['CPEE-INSTANCE-URL'] = "#{@base_url}23/"
        response['CPEE-INSTANCE-UUID'] = 'uuid-23'
      end
    when ['PUT', '/23/properties/state/']
      response.status = 200
      response.body = ''
    when ['GET', '/23/properties/state/']
      response.status = 200
      response.body = 'finished'
    when ['GET', '/23/properties/dataelements/']
      response.status = 200
      response.body = '<dataelements><component_id>base-7</component_id></dataelements>'
    when ['GET', '/23/callbacks/cb/']
      response.status = 200
      response.body = '{}'
    when ['PUT', '/23/callbacks/cb/']
      response.status = 200
      response.body = ''
    else
      response.status = 404
      response.body = 'missing'
    end
  end
end
