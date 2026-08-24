# frozen_string_literal: true

require 'json'
require 'webrick'
require_relative 'deployer'
require_relative 'domain'
require_relative 'fragment_coordinator'
require_relative 'model_repository'
require_relative 'registry'

module TinyHouseCpee
  class GatewayServlet < WEBrick::HTTPServlet::AbstractServlet
    # Retains the routing service for every HTTP method.
    def initialize(server, router)
      super(server)
      @router = router
    end

    # Delegates every request method to one focused router.
    def service(request, response)
      @router.handle(request, response)
    end
  end

  class HttpRouter
    MAX_REQUEST_BYTES = 1_048_576
    HTTP_OK = 200
    HTTP_CREATED = 201
    HTTP_ACCEPTED = 202
    HTTP_NO_CONTENT = 204
    HTTP_FORBIDDEN = 403
    HTTP_NOT_FOUND = 404
    HTTP_CONFLICT = 409
    HTTP_UNPROCESSABLE_ENTITY = 422
    HTTP_BAD_GATEWAY = 502

    # Configures route dependencies without lifecycle logic in the HTTP layer.
    def initialize(coordinator:, deployer:, registry:)
      @coordinator = coordinator
      @deployer = deployer
      @registry = registry
    end

    # Routes one request and translates domain failures into HTTP responses.
    def handle(request, response)
      enforce_body_limit!(request)
      route(request, response)
    rescue FragmentEventError => error
      json_error(response, HTTP_FORBIDDEN, error.message)
    rescue UnknownFragmentError, KeyError => error
      json_error(response, HTTP_NOT_FOUND, error.message)
    rescue RegistryConflict => error
      json_error(response, HTTP_CONFLICT, error.message)
    rescue ModelError, ArgumentError, JSON::ParserError => error
      json_error(response, HTTP_UNPROCESSABLE_ENTITY, error.message)
    rescue FragmentStartError, HolisticDeploymentError, CpeeError => error
      json_error(response, HTTP_BAD_GATEWAY, error.message)
    end

    private

    # Selects a supported endpoint from method and path.
    def route(request, response)
      method = request.request_method
      path = request.path
      if method == 'GET' && path == '/health'
        json_response(response, HTTP_OK, 'status' => 'ok')
      elsif method == 'POST' && path == '/v1/runs'
        deploy_run(request, response)
      elsif method == 'GET' && path.match?(%r{\A/v1/runs/[^/]+\z})
        show_run(path.split('/').last, response)
      elsif method == 'POST' && path == '/v1/fragments/start-and-await'
        start_fragment(request, response)
      elsif method == 'POST' && path.match?(%r{\A/v1/cpee/events/[^/]+\z})
        accept_event(path.split('/').last, request, response)
      else
        json_error(response, HTTP_NOT_FOUND, 'route not found')
      end
    end

    # Deploys one correlated holistic CPEE parent.
    def deploy_run(request, response)
      body = parse_json_object(request.body.to_s)
      record = @deployer.deploy(
        required_value(body, 'run_id'),
        required_value(body, 'work_order_id')
      )
      json_response(response, HTTP_CREATED, run_hash(record))
    end

    # Returns parent and child lifecycle state for one run.
    def show_run(run_id, response)
      run = @registry.fetch_run(run_id)
      raise KeyError, "unknown run #{run_id}" unless run

      dispatches = @registry.dispatches_for_run(run_id).map do |record|
        dispatch_hash(record)
      end
      json_response(
        response,
        HTTP_OK,
        'run' => run_hash(run),
        'fragments' => dispatches
      )
    end

    # Starts a statically configured child and holds the CPEE parent callback.
    def start_fragment(request, response)
      values = request.query
      dispatch = DispatchRequest.new(
        run_id: required_value(values, 'run_id'),
        work_order_id: required_value(values, 'work_order_id'),
        fragment_id: required_value(values, 'fragment_id'),
        attempt: Integer(values.fetch('attempt', '1').to_s, 10),
        input_json: values.fetch('input_json', '{}').to_s,
        parent_instance_uuid: required_header(request, 'cpee-instance-uuid'),
        parent_instance_url: required_header(request, 'cpee-instance-url'),
        parent_callback_url: required_header(request, 'cpee-callback'),
        parent_callback_id: required_header(request, 'cpee-callback-id'),
        parent_activity: required_header(request, 'cpee-activity')
      )
      record = @coordinator.start_and_await(dispatch)
      response.status = HTTP_ACCEPTED
      response['CPEE-CALLBACK'] = 'true'
      response['CPEE-INSTANTIATION'] = JSON.generate(
        'id' => record.child_instance_id,
        'url' => record.child_instance_url,
        'uuid' => record.child_instance_uuid
      )
      response.body = ''
    end

    # Accepts one state notification emitted by a child CPEE subscription.
    def accept_event(token, request, response)
      values = request.query
      @coordinator.handle_state_event(
        event_token: token,
        child_instance_id: required_header(request, 'cpee-instance'),
        child_instance_uuid: required_header(request, 'cpee-instance-uuid'),
        topic: required_value(values, 'topic'),
        event: required_value(values, 'event'),
        notification_json: required_value(values, 'notification')
      )
      response.status = HTTP_NO_CONTENT
      response.body = ''
    end

    # Rejects oversized inbound model-control messages.
    def enforce_body_limit!(request)
      length = request['content-length'].to_i
      raise ArgumentError, 'request body exceeds 1 MiB' if length > MAX_REQUEST_BYTES
    end

    # Parses a JSON object for the user-facing run endpoint.
    def parse_json_object(content)
      value = JSON.parse(content)
      raise ArgumentError, 'request JSON must be an object' unless value.is_a?(Hash)

      value
    end

    # Returns one required form or JSON value as text.
    def required_value(values, name)
      value = values[name]
      raise ArgumentError, "missing required field #{name}" if value.nil? || value.to_s.empty?

      value.to_s
    end

    # Returns one required CPEE correlation header.
    def required_header(request, name)
      value = request[name]
      raise ArgumentError, "missing required header #{name}" if value.nil? || value.empty?

      value
    end

    # Converts a holistic deployment into a stable JSON representation.
    def run_hash(record)
      {
        'run_id' => record.run_id,
        'work_order_id' => record.work_order_id,
        'phase' => record.phase,
        'instance_id' => record.instance_id,
        'instance_url' => record.instance_url,
        'instance_uuid' => record.instance_uuid,
        'last_error' => record.last_error
      }
    end

    # Converts one fragment dispatch into a stable JSON representation.
    def dispatch_hash(record)
      {
        'fragment_id' => record.key.fragment_id,
        'attempt' => record.key.attempt,
        'phase' => record.phase,
        'instance_id' => record.child_instance_id,
        'instance_url' => record.child_instance_url,
        'instance_uuid' => record.child_instance_uuid,
        'terminal_state' => record.terminal_state,
        'last_error' => record.last_error
      }
    end

    # Writes one JSON success response.
    def json_response(response, status, value)
      response.status = status
      response['Content-Type'] = 'application/json'
      response.body = JSON.generate(value)
    end

    # Writes one bounded JSON error response.
    def json_error(response, status, message)
      json_response(response, status, 'error' => message)
    end
  end

  class HttpServer
    # Binds the Ruby gateway and installs all routes.
    def initialize(host:, port:, coordinator:, deployer:, registry:, logger: nil)
      router = HttpRouter.new(
        coordinator: coordinator,
        deployer: deployer,
        registry: registry
      )
      @server = WEBrick::HTTPServer.new(
        BindAddress: host,
        Port: port,
        Logger: logger || WEBrick::Log.new($stderr, WEBrick::Log::WARN),
        AccessLog: []
      )
      @server.mount('/', GatewayServlet, router)
    end

    # Starts serving until shutdown is requested.
    def start
      @server.start
    end

    # Stops accepting new HTTP requests.
    def shutdown
      @server.shutdown
    end

    # Returns the actual bound port, including when configured with zero.
    def bound_port
      @server.listeners.first.addr[1]
    end
  end
end
