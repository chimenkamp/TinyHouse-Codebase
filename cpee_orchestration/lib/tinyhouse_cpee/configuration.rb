# frozen_string_literal: true

require 'uri'
require_relative 'domain'

module TinyHouseCpee
  class Configuration
    FRAGMENT_IDS = %w[wa1 wa2 wa3 wa4 munich].freeze
    DEFAULT_HOST = '127.0.0.1'
    DEFAULT_PORT = 8400
    DEFAULT_CPEE_URL = 'http://127.0.0.1:8298/'
    DEFAULT_TIMEOUT_SECONDS = 10.0
    DEFAULT_POLL_SECONDS = 2.0
    MAX_TCP_PORT = 65_535
    ENV_PREFIX = 'TINYHOUSE_CPEE_'

    attr_reader :listen_host,
                :listen_port,
                :public_base_url,
                :coordinator_cpee_base_url,
                :registry_path,
                :holistic_model_path,
                :fragments,
                :request_timeout_seconds,
                :poll_interval_seconds

    # Stores all explicit deployment settings.
    def initialize(listen_host:, listen_port:, public_base_url:, coordinator_cpee_base_url:,
                   registry_path:, holistic_model_path:, fragments:, request_timeout_seconds:,
                   poll_interval_seconds:)
      @listen_host = listen_host
      @listen_port = listen_port
      @public_base_url = normalize_url(public_base_url, 'public gateway URL')
      @coordinator_cpee_base_url = normalize_url(
        coordinator_cpee_base_url,
        'coordinator CPEE URL'
      )
      @registry_path = registry_path
      @holistic_model_path = holistic_model_path
      @fragments = fragments.freeze
      @request_timeout_seconds = positive_number!(request_timeout_seconds, 'request timeout')
      @poll_interval_seconds = positive_number!(poll_interval_seconds, 'poll interval')
      validate!
    end

    # Builds a local-development configuration with environment overrides.
    def self.from_environment
      application_root = File.expand_path('../..', __dir__)
      listen_host = ENV.fetch("#{ENV_PREFIX}HOST", DEFAULT_HOST)
      listen_port = Integer(ENV.fetch("#{ENV_PREFIX}PORT", DEFAULT_PORT.to_s), 10)
      public_url = ENV.fetch(
        "#{ENV_PREFIX}PUBLIC_URL",
        "http://#{listen_host}:#{listen_port}/"
      )
      coordinator_url = ENV.fetch(
        "#{ENV_PREFIX}COORDINATOR_URL",
        DEFAULT_CPEE_URL
      )
      fragments = build_fragments(application_root, coordinator_url)
      new(
        listen_host: listen_host,
        listen_port: listen_port,
        public_base_url: public_url,
        coordinator_cpee_base_url: coordinator_url,
        registry_path: ENV.fetch(
          "#{ENV_PREFIX}REGISTRY",
          File.join(application_root, 'runtime', 'orchestration.pstore')
        ),
        holistic_model_path: ENV.fetch(
          "#{ENV_PREFIX}HOLISTIC_MODEL",
          File.join(application_root, 'models', 'holistic_coordinator.xml')
        ),
        fragments: fragments,
        request_timeout_seconds: Float(
          ENV.fetch("#{ENV_PREFIX}REQUEST_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS.to_s)
        ),
        poll_interval_seconds: Float(
          ENV.fetch("#{ENV_PREFIX}POLL_INTERVAL_SECONDS", DEFAULT_POLL_SECONDS.to_s)
        )
      )
    end

    # Returns one whitelisted fragment configuration.
    def fragment(fragment_id)
      fragment = @fragments.find { |candidate| candidate.fragment_id == fragment_id }
      raise KeyError, "unknown fragment #{fragment_id}" unless fragment

      fragment
    end

    # Returns a lookup map for lifecycle coordination.
    def fragment_map
      @fragments.each_with_object({}) do |fragment, values|
        values[fragment.fragment_id] = fragment
      end.freeze
    end

    # Returns the CPEE-callable asynchronous fragment endpoint.
    def fragment_gateway_url
      URI.join(@public_base_url, 'v1/fragments/start-and-await').to_s
    end

    private

    # Builds the exact five static child target mappings.
    def self.build_fragments(application_root, coordinator_url)
      FRAGMENT_IDS.map do |fragment_id|
        environment_id = fragment_id.upcase
        FragmentConfig.new(
          fragment_id,
          normalize_class_url(
            ENV.fetch("#{ENV_PREFIX}#{environment_id}_URL", coordinator_url)
          ),
          ENV.fetch(
            "#{ENV_PREFIX}#{environment_id}_MODEL",
            File.join(application_root, 'models', 'fragments', "#{fragment_id}.xml")
          )
        )
      end
    end

    # Normalizes a class-level URL without constructing a partial configuration.
    def self.normalize_class_url(value)
      uri = URI.parse(value)
      unless %w[http https].include?(uri.scheme) && uri.host && !uri.query && !uri.fragment
        raise ArgumentError, "invalid absolute HTTP(S) URL: #{value}"
      end
      "#{value.sub(%r{/+\z}, '')}/"
    rescue URI::InvalidURIError => error
      raise ArgumentError, "invalid URL: #{error.message}"
    end

    # Validates invariants spanning all application settings.
    def validate!
      ids = @fragments.map(&:fragment_id)
      raise ArgumentError, "fragments must be #{FRAGMENT_IDS.join(', ')}" unless ids == FRAGMENT_IDS
      raise ArgumentError, 'listen host must not be empty' if @listen_host.to_s.strip.empty?
      unless @listen_port.between?(1, MAX_TCP_PORT)
        raise ArgumentError, 'listen port must be between 1 and 65535'
      end
    end

    # Normalizes an HTTP URL and reports the owning setting.
    def normalize_url(value, label)
      uri = URI.parse(value)
      unless %w[http https].include?(uri.scheme) && uri.host && !uri.query && !uri.fragment
        raise ArgumentError, "#{label} must be an absolute HTTP(S) URL"
      end
      "#{value.sub(%r{/+\z}, '')}/"
    rescue URI::InvalidURIError => error
      raise ArgumentError, "#{label} is invalid: #{error.message}"
    end

    # Validates one positive timing value.
    def positive_number!(value, label)
      number = Float(value)
      raise ArgumentError, "#{label} must be positive" unless number.positive?

      number
    end
  end
end
