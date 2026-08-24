# frozen_string_literal: true

module TinyHouseCpee
  class SignalRelay
    SIGNAL_BYTE_COUNT = 1
    # Configures a self-pipe relay from Ruby traps to a normal worker thread.
    def initialize(target, signals: %w[INT TERM])
      @target = target
      @signals = signals
      @reader, @writer = IO.pipe
      @previous_handlers = {}
      @worker = nil
      @installed = false
      @closed = false
    end

    # Installs minimal traps and starts the shutdown worker.
    def install
      return if @installed

      @worker = Thread.new do
        @reader.read(SIGNAL_BYTE_COUNT)
        @target.shutdown
      end
      @signals.each do |signal|
        @previous_handlers[signal] = Signal.trap(signal) { notify_worker }
      end
      @installed = true
      nil
    end

    # Restores prior handlers and closes the relay resources.
    def close
      return if @closed

      restore_handlers
      notify_worker if @worker&.alive?
      @worker&.join
      @reader.close unless @reader.closed?
      @writer.close unless @writer.closed?
      @closed = true
      nil
    end

    private

    # Performs the only trap-context action: one nonblocking pipe byte.
    def notify_worker
      @writer.write_nonblock('.')
    rescue IO::WaitWritable, Errno::EINTR, Errno::EPIPE, IOError
      nil
    end

    # Restores every signal handler replaced during installation.
    def restore_handlers
      return unless @installed

      @previous_handlers.each do |signal, handler|
        Signal.trap(signal, handler)
      end
      @installed = false
    end
  end
end
