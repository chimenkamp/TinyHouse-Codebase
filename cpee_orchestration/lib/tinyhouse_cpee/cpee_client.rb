# frozen_string_literal: true

require 'net/http'
require 'openssl'
require 'uri'
require_relative 'domain'

module TinyHouseCpee
  class CpeeError < StandardError
  end

  class CpeeHttpError < CpeeError
    attr_reader :status_code, :response_body

    # Captures the failed CPEE status and response body.
    def initialize(message, status_code:, response_body:)
      super(message)
      @status_code = status_code
      @response_body = response_body
    end
  end

  class CpeeProtocolError < CpeeError
  end

  class CpeeClient
    CREATE_CONTENT_TYPE = 'application/xml'
    CREATE_CONTENT_ID = 'xml'
    ABSENT_CALLBACK_STATUSES = [404, 410].freeze
    SUCCESS_STATUS_RANGE = (200..299)

    # Configures bounded CPEE network operations.
    def initialize(timeout_seconds:)
      @timeout_seconds = timeout_seconds
    end

    # Creates a complete CPEE instance in its model-declared state.
    def create_instance(base_url, model)
      uri = normalized_uri(base_url)
      request = Net::HTTP::Post.new(uri)
      request['Content-Type'] = CREATE_CONTENT_TYPE
      request['Content-ID'] = CREATE_CONTENT_ID
      request.body = model
      response = perform(uri, request)
      ensure_success!(response, 'create CPEE instance')
      parse_instance_identity(response)
    end

    # Starts a previously persisted ready CPEE instance.
    def start_instance(instance_url)
      uri = resource_uri(instance_url, 'properties/state/')
      request = Net::HTTP::Put.new(uri)
      request['Content-Type'] = 'application/x-www-form-urlencoded'
      request.body = URI.encode_www_form('value' => 'running')
      response = perform(uri, request)
      ensure_success!(response, 'start CPEE instance')
      nil
    end

    # Reads the current CPEE state property.
    def get_state(instance_url)
      uri = resource_uri(instance_url, 'properties/state/')
      response = perform(uri, Net::HTTP::Get.new(uri))
      ensure_success!(response, 'read CPEE state')
      response.body.to_s.strip
    end

    # Reads final child data elements as the engine returns them.
    def get_data_elements(instance_url)
      uri = resource_uri(instance_url, 'properties/dataelements/')
      response = perform(uri, Net::HTTP::Get.new(uri))
      ensure_success!(response, 'read CPEE data elements')
      response.body.to_s
    end

    # Checks whether a parent activity callback is still registered.
    def callback_pending?(callback_url)
      uri = normalized_uri(callback_url)
      response = perform(uri, Net::HTTP::Get.new(uri))
      return true if successful?(response)
      return false if ABSENT_CALLBACK_STATUSES.include?(response.code.to_i)

      raise_http_error(response, 'inspect parent CPEE callback')
    end

    # Completes a parent activity with normal or WEEL-salvage semantics.
    def deliver_callback(callback_url, fields, salvage:)
      uri = normalized_uri(callback_url)
      request = Net::HTTP::Put.new(uri)
      request['Content-Type'] = 'application/x-www-form-urlencoded'
      request['CPEE-SALVAGE'] = 'true' if salvage
      request.body = URI.encode_www_form(fields)
      response = perform(uri, request)
      ensure_success!(response, 'deliver parent CPEE callback')
      nil
    end

    private

    # Executes one request with explicit connection and read timeouts.
    def perform(uri, request)
      http = Net::HTTP.new(uri.host, uri.port)
      http.use_ssl = uri.scheme == 'https'
      http.verify_mode = OpenSSL::SSL::VERIFY_PEER if http.use_ssl?
      http.open_timeout = @timeout_seconds
      http.read_timeout = @timeout_seconds
      http.request(request)
    rescue Net::OpenTimeout, Net::ReadTimeout, SocketError, SystemCallError => error
      raise CpeeError, "CPEE request to #{uri} failed: #{error.message}"
    end

    # Parses the identity headers emitted by full-instance creation.
    def parse_instance_identity(response)
      instance_id = response['cpee-instance'].to_s.strip
      instance_id = response.body.to_s.strip if instance_id.empty?
      instance_url = response['cpee-instance-url'].to_s.strip
      instance_uuid = response['cpee-instance-uuid'].to_s.strip
      if [instance_id, instance_url, instance_uuid].any?(&:empty?)
        raise CpeeProtocolError, 'CPEE create response omitted instance identity headers'
      end

      InstanceIdentity.new(instance_id, ensure_trailing_slash(instance_url), instance_uuid)
    end

    # Raises a contextual exception for a non-success response.
    def ensure_success!(response, action)
      return if successful?(response)

      raise_http_error(response, action)
    end

    # Identifies a successful HTTP response without relying on response subclasses.
    def successful?(response)
      SUCCESS_STATUS_RANGE.cover?(response.code.to_i)
    end

    # Raises a typed HTTP error with response evidence.
    def raise_http_error(response, action)
      status_code = response.code.to_i
      raise CpeeHttpError.new(
        "#{action} failed with HTTP #{status_code}",
        status_code: status_code,
        response_body: response.body.to_s
      )
    end

    # Resolves a property path below one canonical instance URL.
    def resource_uri(instance_url, relative_path)
      URI.join(ensure_trailing_slash(instance_url), relative_path)
    rescue URI::InvalidURIError => error
      raise CpeeProtocolError, "invalid CPEE instance URL: #{error.message}"
    end

    # Parses and validates an absolute HTTP endpoint.
    def normalized_uri(value)
      uri = URI.parse(value)
      unless %w[http https].include?(uri.scheme) && uri.host
        raise CpeeProtocolError, "invalid absolute HTTP(S) URL: #{value}"
      end
      uri
    rescue URI::InvalidURIError => error
      raise CpeeProtocolError, "invalid URL: #{error.message}"
    end

    # Normalizes a URL for safe relative resource resolution.
    def ensure_trailing_slash(value)
      "#{value.to_s.sub(%r{/+\z}, '')}/"
    end
  end
end
