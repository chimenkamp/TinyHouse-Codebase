# frozen_string_literal: true

$LOAD_PATH.unshift File.expand_path('lib', __dir__)

require 'tinyhouse_cpee/application'
require 'tinyhouse_cpee/configuration'
require 'tinyhouse_cpee/signal_relay'

# Constructs configuration and starts the Ruby CPEE orchestration service.
def main
  config = TinyHouseCpee::Configuration.from_environment
  application = TinyHouseCpee::Application.new(config)
  signal_relay = TinyHouseCpee::SignalRelay.new(application)
  signal_relay.install
  application.run
ensure
  signal_relay&.close
end

main if $PROGRAM_NAME == __FILE__
