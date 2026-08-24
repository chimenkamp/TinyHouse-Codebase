# frozen_string_literal: true

require 'thread'
require 'webrick'
require_relative 'configuration'
require_relative 'cpee_client'
require_relative 'deployer'
require_relative 'fragment_coordinator'
require_relative 'http_server'
require_relative 'registry'

module TinyHouseCpee
  class Application
    # Constructs the complete Ruby orchestration service from configuration.
    def initialize(config, logger: WEBrick::Log.new($stderr, WEBrick::Log::INFO))
      @config = config
      @logger = logger
      @registry = Registry.new(config.registry_path)
      @client = CpeeClient.new(timeout_seconds: config.request_timeout_seconds)
      @coordinator = FragmentCoordinator.new(
        fragments: config.fragment_map,
        registry: @registry,
        client: @client,
        public_base_url: config.public_base_url
      )
      @deployer = HolisticDeployer.new(
        coordinator_cpee_base_url: config.coordinator_cpee_base_url,
        holistic_model_path: config.holistic_model_path,
        fragment_gateway_url: config.fragment_gateway_url,
        registry: @registry,
        client: @client
      )
      @server = HttpServer.new(
        host: config.listen_host,
        port: config.listen_port,
        coordinator: @coordinator,
        deployer: @deployer,
        registry: @registry,
        logger: logger
      )
      @stop_mutex = Mutex.new
      @stop_condition = ConditionVariable.new
      @stopping = false
      @reconciler = nil
    end

    # Starts background reconciliation and the blocking HTTP server.
    def run
      @reconciler = Thread.new { reconciliation_loop }
      @server.start
    ensure
      shutdown
    end

    # Stops the HTTP server and wakes the reconciliation thread.
    def shutdown
      @stop_mutex.synchronize do
        unless @stopping
          @stopping = true
          @stop_condition.broadcast
        end
      end
      @server.shutdown
      @reconciler&.join
      nil
    end

    private

    # Reconciles missed events and retries pending callbacks until shutdown.
    def reconciliation_loop
      loop do
        break if stopping?

        begin
          @coordinator.reconcile
        rescue StandardError => error
          @logger.error("fragment reconciliation failed: #{error.class}: #{error.message}")
        end
        wait_for_next_poll
      end
    end

    # Reads the coordinated shutdown flag.
    def stopping?
      @stop_mutex.synchronize { @stopping }
    end

    # Sleeps interruptibly between reconciliation passes.
    def wait_for_next_poll
      @stop_mutex.synchronize do
        @stop_condition.wait(@stop_mutex, @config.poll_interval_seconds) unless @stopping
      end
    end
  end
end

