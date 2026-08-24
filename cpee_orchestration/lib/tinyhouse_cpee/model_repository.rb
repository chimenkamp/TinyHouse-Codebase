# frozen_string_literal: true

require 'digest'
require 'json'
require 'rexml/document'
require 'rexml/formatters/default'
require 'rexml/xpath'

module TinyHouseCpee
  RenderedFragment = Struct.new(
    :content,
    :definition_sha256,
    :deterministic_info,
    keyword_init: true
  )

  class ModelError < StandardError
  end

  module ModelRepository
    PROPERTIES_NAMESPACE = 'http://cpee.org/ns/properties/2.0'
    DESCRIPTION_NAMESPACE = 'http://cpee.org/ns/description/1.0'
    NOTIFICATIONS_NAMESPACE = 'http://riddl.org/ns/common-patterns/notifications-producer/2.0'
    EXPECTED_FRAGMENTS = %w[wa4 wa1 munich wa2 wa3].freeze
    NAMESPACES = {
      'p' => PROPERTIES_NAMESPACE,
      'd' => DESCRIPTION_NAMESPACE,
      'n' => NOTIFICATIONS_NAMESPACE
    }.freeze

    module_function

    # Renders the run-specific holistic full-instance document.
    def render_holistic(path:, run_id:, work_order_id:, gateway_url:)
      content = read_model(path)
      validate_holistic(content)
      document = parse_document(content)
      set_property_text(document, 'state', 'ready')
      set_data_text(document, 'run_id', run_id)
      set_data_text(document, 'work_order_id', work_order_id)
      set_property_child_text(document, 'endpoints', 'fragment_gateway', gateway_url)
      set_property_child_text(
        document,
        'attributes',
        'info',
        "TinyHouse holistic #{run_id}"
      )
      serialize(document)
    end

    # Renders one correlated child definition with a state webhook.
    def render_fragment(path:, run_id:, work_order_id:, fragment_id:, attempt:, input_json:, event_url:)
      content = read_model(path)
      JSON.parse(input_json)
      document = parse_document(content)
      ensure_testset!(document)
      definition_sha256 = Digest::SHA256.hexdigest(content)
      deterministic_info = "tinyhouse:#{run_id}:#{fragment_id}:#{attempt}"
      set_property_text(document, 'state', 'ready')
      set_data_text(document, 'run_id', run_id)
      set_data_text(document, 'work_order_id', work_order_id)
      set_data_text(document, 'fragment_id', fragment_id)
      set_data_text(document, 'attempt', attempt.to_s)
      set_data_text(document, 'input_json', input_json)
      set_property_child_text(document, 'attributes', 'info', deterministic_info)
      set_property_child_text(document, 'attributes', 'run_id', run_id)
      set_property_child_text(document, 'attributes', 'work_order_id', work_order_id)
      set_property_child_text(document, 'attributes', 'fragment_id', fragment_id)
      set_property_child_text(document, 'attributes', 'attempt', attempt.to_s)
      set_property_child_text(
        document,
        'attributes',
        'definition_sha256',
        definition_sha256
      )
      replace_state_subscription(document, event_url)
      RenderedFragment.new(
        content: serialize(document),
        definition_sha256: definition_sha256,
        deterministic_info: deterministic_info
      )
    rescue JSON::ParserError => error
      raise ModelError, "fragment input_json is invalid: #{error.message}"
    end

    # Converts a CPEE dataelements document into a simple result hash.
    def parse_data_elements(content)
      document = parse_document(content)
      root = document.root
      raise ModelError, 'CPEE dataelements response has no root element' unless root

      root.elements.each_with_object({}) do |element, values|
        values[element.name] = element.has_elements? ? serialize_element(element) : element.text.to_s
      end
    end

    # Enforces the coordinator's five-fragment topology and correlation contract.
    def validate_holistic(content)
      document = parse_document(content)
      ensure_testset!(document)
      state = xpath_first(document, '/p:testset/p:state')
      handler = xpath_first(document, '/p:testset/p:executionhandler')
      raise ModelError, 'holistic model must declare state ready' unless state && state.text == 'ready'
      raise ModelError, 'holistic model must use the ruby execution handler' unless handler && handler.text == 'ruby'

      calls = REXML::XPath.match(document, '//d:call', NAMESPACES)
      fragments = calls.map do |call|
        fragment = REXML::XPath.first(
          call,
          'd:parameters/d:arguments/d:fragment_id',
          NAMESPACES
        )
        fragment&.text
      end
      raise ModelError, 'holistic model must call wa4, wa1, munich, wa2, and wa3 exactly once' unless fragments == EXPECTED_FRAGMENTS

      ids = calls.map { |call| call.attributes['id'] }
      raise ModelError, 'holistic call activity IDs must be unique' unless ids.uniq.length == ids.length
      calls.each { |call| validate_gateway_call!(call) }
      validate_parallel_shape!(document)
      true
    end

    # Reads one model without substituting absent definitions.
    def read_model(path)
      File.binread(path)
    rescue Errno::ENOENT
      raise ModelError, "CPEE model does not exist: #{path}"
    end

    # Checks the fixed arguments and handlers on one gateway activity.
    def validate_gateway_call!(call)
      raise ModelError, 'all fragment calls must use fragment_gateway' unless call.attributes['endpoint'] == 'fragment_gateway'
      run_id = REXML::XPath.first(call, './/d:run_id', NAMESPACES)
      order_id = REXML::XPath.first(call, './/d:work_order_id', NAMESPACES)
      finalize = REXML::XPath.first(call, 'd:code/d:finalize', NAMESPACES)
      rescue_code = REXML::XPath.first(call, 'd:code/d:rescue', NAMESPACES)
      unless run_id&.text == '!data.run_id' && order_id&.text == '!data.work_order_id'
        raise ModelError, 'every fragment call must pass dynamic run and work-order correlation'
      end
      if finalize.nil? || finalize.text.to_s.strip.empty? || rescue_code.nil? || rescue_code.text.to_s.strip.empty?
        raise ModelError, 'every fragment call must finalize output and raise on salvage'
      end
    end
    private_class_method :validate_gateway_call!

    # Checks WA4 spans the case while production follows WA1/Munich, WA2, WA3.
    def validate_parallel_shape!(document)
      outer = REXML::XPath.first(
        document,
        '/p:testset/p:description/d:description/d:parallel',
        NAMESPACES
      )
      branches = outer ? REXML::XPath.match(outer, 'd:parallel_branch', NAMESPACES) : []
      raise ModelError, 'holistic model requires two outer parallel branches' unless branches.length == 2
      first_fragment = REXML::XPath.first(branches[0], './/d:fragment_id', NAMESPACES)
      nested = REXML::XPath.first(branches[1], 'd:parallel', NAMESPACES)
      nested_fragments = nested ? REXML::XPath.match(nested, './/d:fragment_id', NAMESPACES).map(&:text) : []
      sequential = REXML::XPath.match(branches[1], 'd:call/d:parameters/d:arguments/d:fragment_id', NAMESPACES).map(&:text)
      waits_for_all = outer.attributes['wait'] == '-1' &&
                      outer.attributes['cancel'] == 'last' &&
                      nested && nested.attributes['wait'] == '-1' &&
                      nested.attributes['cancel'] == 'last'
      valid = waits_for_all && first_fragment&.text == 'wa4' &&
              nested_fragments == %w[wa1 munich] && sequential == %w[wa2 wa3]
      raise ModelError, 'holistic parallel topology does not match the distributed process' unless valid
    end
    private_class_method :validate_parallel_shape!

    # Parses XML and reports malformed models with one domain exception.
    def parse_document(content)
      REXML::Document.new(content)
    rescue REXML::ParseException => error
      raise ModelError, "invalid CPEE XML: #{error.message}"
    end
    private_class_method :parse_document

    # Ensures a full-instance document uses the CPEE properties namespace.
    def ensure_testset!(document)
      root = document.root
      unless root && root.name == 'testset' && root.namespace == PROPERTIES_NAMESPACE
        raise ModelError, 'model root must be a CPEE properties 2.0 testset'
      end
    end
    private_class_method :ensure_testset!

    # Updates one direct property element.
    def set_property_text(document, name, value)
      root = document.root
      element = xpath_first(document, "/p:testset/p:#{name}")
      unless element
        element = REXML::Element.new(name)
        reference = root.elements['executionhandler']
        reference ? root.insert_before(reference, element) : root.add_element(element)
      end
      element.text = value
    end
    private_class_method :set_property_text

    # Updates or creates one data element.
    def set_data_text(document, name, value)
      set_property_child_text(document, 'dataelements', name, value)
    end
    private_class_method :set_data_text

    # Updates or creates a child inside one required property container.
    def set_property_child_text(document, container_name, child_name, value)
      container = xpath_first(document, "/p:testset/p:#{container_name}")
      raise ModelError, "model has no #{container_name} property" unless container

      child = container.elements[child_name] || container.add_element(child_name)
      child.text = value
    end
    private_class_method :set_property_child_text

    # Replaces this gateway's subscription without touching unrelated subscribers.
    def replace_state_subscription(document, event_url)
      root = document.root
      subscriptions = REXML::XPath.first(document, '/p:testset/n:subscriptions', NAMESPACES)
      unless subscriptions
        subscriptions = root.add_element(
          'subscriptions',
          'xmlns' => NOTIFICATIONS_NAMESPACE
        )
      end
      previous = REXML::XPath.first(
        subscriptions,
        'n:subscription[@id="tinyhouse_holistic"]',
        NAMESPACES
      )
      subscriptions.delete_element(previous) if previous
      subscription = subscriptions.add_element(
        'subscription',
        'id' => 'tinyhouse_holistic',
        'url' => event_url
      )
      topic = subscription.add_element('topic', 'id' => 'state')
      topic.add_element('event').text = 'change'
    end
    private_class_method :replace_state_subscription

    # Selects one element with the module namespace map.
    def xpath_first(node, path)
      REXML::XPath.first(node, path, NAMESPACES)
    end
    private_class_method :xpath_first

    # Serializes a complete XML document.
    def serialize(document)
      output = String.new
      REXML::Formatters::Default.new.write(document, output)
      output
    end
    private_class_method :serialize

    # Serializes a nested data element when it is not scalar.
    def serialize_element(element)
      output = String.new
      REXML::Formatters::Default.new.write(element, output)
      output
    end
    private_class_method :serialize_element
  end
end
