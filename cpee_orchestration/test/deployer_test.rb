# frozen_string_literal: true

require_relative 'test_helper'

require 'tinyhouse_cpee/deployer'

class FakeDeploymentClient
  attr_reader :models, :starts

  # Initializes captured deployment calls.
  def initialize
    @models = []
    @starts = []
  end

  # Returns one deterministic coordinator identity.
  def create_instance(base_url, model)
    @models << model
    TinyHouseCpee::InstanceIdentity.new('5', "#{base_url}5/", 'coordinator-uuid')
  end

  # Records the start request.
  def start_instance(instance_url)
    @starts << instance_url
  end
end

class DeployerTest < Minitest::Test
  # Verifies a repeated run request deploys one correlated CPEE parent.
  def test_deploy_is_idempotent_and_starts_after_identity_is_persisted
    Dir.mktmpdir do |directory|
      registry = TinyHouseCpee::Registry.new(File.join(directory, 'registry.pstore'))
      client = FakeDeploymentClient.new
      model_path = File.expand_path('../models/holistic_coordinator.xml', __dir__)
      deployer = TinyHouseCpee::HolisticDeployer.new(
        coordinator_cpee_base_url: 'http://munich-cpee:8298/',
        holistic_model_path: model_path,
        fragment_gateway_url: 'http://gateway:8400/v1/fragments/start-and-await',
        registry: registry,
        client: client
      )

      first = deployer.deploy('run-42', 'order-42')
      second = deployer.deploy('run-42', 'order-42')

      assert_equal 1, client.models.length
      assert_equal ['http://munich-cpee:8298/5/'], client.starts
      assert_equal first, second
      assert_equal TinyHouseCpee::RunPhase::RUNNING, first.phase
      assert_includes client.models.first, 'run-42'
      assert_includes client.models.first, 'order-42'
    end
  end
end

