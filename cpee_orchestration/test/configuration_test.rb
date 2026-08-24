# frozen_string_literal: true

require_relative 'test_helper'

require 'tinyhouse_cpee/configuration'

class ConfigurationTest < Minitest::Test
  # Preserves any caller deployment configuration.
  def setup
    @saved_environment = ENV.to_h.select do |key, _value|
      key.start_with?(TinyHouseCpee::Configuration::ENV_PREFIX)
    end
    ENV.delete_if do |key, _value|
      key.start_with?(TinyHouseCpee::Configuration::ENV_PREFIX)
    end
  end

  # Restores caller deployment configuration after each test.
  def teardown
    ENV.delete_if do |key, _value|
      key.start_with?(TinyHouseCpee::Configuration::ENV_PREFIX)
    end
    @saved_environment.each { |key, value| ENV[key] = value }
  end

  # Verifies the default application has exactly five static fragment targets.
  def test_defaults_define_five_fragments_and_loopback_service
    config = TinyHouseCpee::Configuration.from_environment

    assert_equal %w[wa1 wa2 wa3 wa4 munich], config.fragments.map(&:fragment_id)
    assert_equal '127.0.0.1', config.listen_host
    assert_equal 8400, config.listen_port
    assert_equal 'http://127.0.0.1:8400/', config.public_base_url
  end

  # Verifies physical-node URLs and definitions are explicit overrides.
  def test_fragment_environment_overrides_are_applied
    ENV['TINYHOUSE_CPEE_WA1_URL'] = 'http://pi-wa1.example:8298'
    ENV['TINYHOUSE_CPEE_WA1_MODEL'] = '/srv/cpee/wa1.xml'

    config = TinyHouseCpee::Configuration.from_environment
    fragment = config.fragment('wa1')

    assert_equal 'http://pi-wa1.example:8298/', fragment.cpee_base_url
    assert_equal '/srv/cpee/wa1.xml', fragment.model_path
  end

  # Verifies non-HTTP callback bases are rejected during startup.
  def test_invalid_public_url_is_rejected
    ENV['TINYHOUSE_CPEE_PUBLIC_URL'] = 'file:///tmp/gateway'

    assert_raises(ArgumentError) do
      TinyHouseCpee::Configuration.from_environment
    end
  end
end

