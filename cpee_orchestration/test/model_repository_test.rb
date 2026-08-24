# frozen_string_literal: true

require_relative 'test_helper'

require 'rexml/document'
require 'tinyhouse_cpee/model_repository'

class ModelRepositoryTest < Minitest::Test
  PROPERTIES_NAMESPACE = 'http://cpee.org/ns/properties/2.0'
  DESCRIPTION_NAMESPACE = 'http://cpee.org/ns/description/1.0'

  # Verifies the coordinator owns exactly the required five fragment calls.
  def test_holistic_model_has_process_aware_five_fragment_topology
    path = File.expand_path('../models/holistic_coordinator.xml', __dir__)
    content = File.binread(path)

    TinyHouseCpee::ModelRepository.validate_holistic(content)
    document = REXML::Document.new(content)
    calls = REXML::XPath.match(
      document,
      '//d:call',
      'd' => DESCRIPTION_NAMESPACE
    )
    fragments = calls.map do |call|
      REXML::XPath.first(call, 'd:parameters/d:arguments/d:fragment_id', 'd' => DESCRIPTION_NAMESPACE).text
    end

    assert_equal %w[wa4 wa1 munich wa2 wa3], fragments
    assert_equal 5, calls.map { |call| call.attributes['id'] }.uniq.length
    calls.each do |call|
      assert_equal 'fragment_gateway', call.attributes['endpoint']
      assert_equal '!data.run_id', REXML::XPath.first(call, './/d:run_id', 'd' => DESCRIPTION_NAMESPACE).text
      assert_equal '!data.work_order_id', REXML::XPath.first(call, './/d:work_order_id', 'd' => DESCRIPTION_NAMESPACE).text
    end
  end

  # Verifies deployment values are inserted as escaped XML data, not string templates.
  def test_render_holistic_sets_correlation_and_gateway_endpoint
    path = File.expand_path('../models/holistic_coordinator.xml', __dir__)

    content = TinyHouseCpee::ModelRepository.render_holistic(
      path: path,
      run_id: 'run<&>7',
      work_order_id: 'order-9',
      gateway_url: 'http://gateway:8400/v1/fragments/start-and-await'
    )
    document = REXML::Document.new(content)

    assert_equal 'run<&>7', REXML::XPath.first(document, '//p:dataelements/p:run_id', 'p' => PROPERTIES_NAMESPACE).text
    assert_equal 'order-9', REXML::XPath.first(document, '//p:dataelements/p:work_order_id', 'p' => PROPERTIES_NAMESPACE).text
    assert_equal 'http://gateway:8400/v1/fragments/start-and-await', REXML::XPath.first(document, '//p:endpoints/p:fragment_gateway', 'p' => PROPERTIES_NAMESPACE).text
    assert_equal 'ready', REXML::XPath.first(document, '//p:state', 'p' => PROPERTIES_NAMESPACE).text
  end

  # Verifies a fragment receives durable correlation and a state webhook subscription.
  def test_render_fragment_injects_ready_state_inputs_attributes_and_subscription
    Dir.mktmpdir do |directory|
      path = File.join(directory, 'wa1.xml')
      File.write(path, minimal_fragment_model)

      rendered = TinyHouseCpee::ModelRepository.render_fragment(
        path: path,
        run_id: 'run-1',
        work_order_id: 'order-1',
        fragment_id: 'wa1',
        attempt: 2,
        input_json: '{"size":"large"}',
        event_url: 'http://gateway/events/token'
      )
      document = REXML::Document.new(rendered.content)

      assert_equal 'ready', REXML::XPath.first(document, '//p:state', 'p' => PROPERTIES_NAMESPACE).text
      assert_equal 'run-1', REXML::XPath.first(document, '//p:dataelements/p:run_id', 'p' => PROPERTIES_NAMESPACE).text
      assert_equal 'tinyhouse:run-1:wa1:2', REXML::XPath.first(document, '//p:attributes/p:info', 'p' => PROPERTIES_NAMESPACE).text
      subscription = REXML::XPath.first(document, '//*[local-name()="subscription"]')
      assert_equal 'http://gateway/events/token', subscription.attributes['url']
      assert_match(/\A[0-9a-f]{64}\z/, rendered.definition_sha256)
    end
  end

  # Builds a valid minimal child definition for rendering tests.
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

