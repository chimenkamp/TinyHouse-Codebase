# frozen_string_literal: true

require_relative 'test_helper'

require 'timeout'
require 'tinyhouse_cpee/signal_relay'

class FakeShutdownTarget
  # Creates a thread-safe shutdown notification.
  def initialize
    @notifications = Queue.new
  end

  # Records shutdown from the relay's normal worker thread.
  def shutdown
    @notifications << true
  end

  # Waits for shutdown without allowing a hanging test.
  def wait
    Timeout.timeout(1.0) { @notifications.pop }
  end
end

class SignalRelayTest < Minitest::Test
  # Verifies the signal trap relays shutdown outside trap context.
  def test_signal_is_relayed_to_normal_worker_thread
    target = FakeShutdownTarget.new
    relay = TinyHouseCpee::SignalRelay.new(target, signals: ['USR1'])
    relay.install

    Process.kill('USR1', Process.pid)

    assert target.wait
  ensure
    relay&.close
  end
end
