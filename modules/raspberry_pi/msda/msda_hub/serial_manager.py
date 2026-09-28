"""
msda_hub.serial_manager — Serial Communication Manager
Handles GPIO UART communication with Arduino Nano Every over /dev/ttyAMA0.

Protocol: newline-terminated JSON messages (SensorHub firmware)
  Arduino → Pi:  {"type":"DATA","ts":...,"sensor":"...","values":{...}}
                 {"type":"HEARTBEAT","ts":...,"interval_ms":...,"mode":"..."}
                 {"type":"INVENTORY","ts":...,"sensors":{...}}
                 {"type":"LOG","ts":...,"message":"..."}
                 {"type":"ERROR","ts":...,"message":"..."}

  Pi → Arduino:  PING\\n  INVENTORY\\n  START\\n  STOP\\n
                 SET_RATE <ms>\\n  STATUS\\n  RESET\\n
"""

import json
import logging
import threading
import time
from collections import deque
from datetime import datetime

import serial

from .config import ConfigManager
from .database import DatabaseManager


class SerialManager:
    def __init__(self, config: ConfigManager, db: DatabaseManager):
        self.config = config
        self.db = db
        self.port = config.get('SERIAL', 'port', '/dev/ttyAMA0')
        self.baudrate = config.getint('SERIAL', 'baudrate', 115200)
        self.timeout = config.getint('SERIAL', 'timeout', 1)
        self.serial_conn = None
        self.running = False
        self.read_thread = None
        self.last_heartbeat = time.time()
        self.sensor_inventory = {}
        self.message_queue = deque(maxlen=100)

    # ── Connection ────────────────────────────────────────────────────

    def connect(self) -> bool:
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            time.sleep(2)  # Allow Arduino to initialise after port open

            if not self._perform_handshake():
                raise IOError("No JSON response from Arduino during handshake")

            logging.info(f"Connected to Arduino on {self.port}")
            self.db.add_event("SERIAL", "INFO", f"Connected to {self.port}")
            self.last_heartbeat = time.time()
            return True

        except Exception as e:
            logging.error(f"Failed to connect: {e}")
            self.db.add_event("SERIAL", "ERROR", f"Connection failed: {e}")
            if self.serial_conn:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
                self.serial_conn = None
            return False

    def _perform_handshake(self, timeout: float = 8.0) -> bool:
        """Send STATUS and wait for any valid JSON message from Arduino."""
        if not self.serial_conn:
            return False
        try:
            self.serial_conn.reset_input_buffer()
        except Exception:
            pass

        # Ask Arduino for its status — it will reply with INVENTORY + HEARTBEAT
        self.send_command("STATUS")

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                raw = self.serial_conn.readline()
                if not raw:
                    continue
                line = raw.decode('utf-8', errors='replace').strip()
                if not line:
                    continue
                obj = json.loads(line)
                msg_type = obj.get("type", "")
                if msg_type in ("INVENTORY", "HEARTBEAT", "LOG", "DATA"):
                    self.process_json(obj)   # handle the first message
                    return True
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass   # ignore non-JSON lines during handshake
            except Exception:
                time.sleep(0.05)

        return False

    # ── Start / Stop ──────────────────────────────────────────────────

    def start(self):
        if not self.serial_conn:
            if not self.connect():
                return False
        self.running = True
        self.read_thread = threading.Thread(target=self.read_loop, daemon=True)
        self.read_thread.start()
        time.sleep(0.5)
        self.send_command("STATUS")
        return True

    def stop(self):
        self.running = False
        if self.read_thread:
            self.read_thread.join(timeout=2)
        if self.serial_conn:
            self.serial_conn.close()

    # ── Read Loop ─────────────────────────────────────────────────────

    def read_loop(self):
        """Continuously read newline-delimited JSON from the Arduino."""
        while self.running:
            try:
                raw = self.serial_conn.readline() if self.serial_conn else b''
                if raw:
                    line = raw.decode('utf-8', errors='replace').strip()
                    if line:
                        self._dispatch_line(line)

                # Heartbeat timeout check
                hb_timeout = self.config.getint('MONITORING', 'heartbeat_timeout', 30)
                if time.time() - self.last_heartbeat > hb_timeout:
                    logging.warning("Heartbeat timeout — Arduino may be disconnected")
                    self.db.add_event("HEARTBEAT", "WARNING", "Heartbeat timeout")
                    if self.config.getboolean('MONITORING', 'auto_reconnect'):
                        self.reconnect()

            except Exception as e:
                logging.error(f"Read error: {e}")
                if self.config.getboolean('MONITORING', 'auto_reconnect'):
                    self.reconnect()
                time.sleep(1)

    def _dispatch_line(self, line: str):
        """Try to parse line as JSON and dispatch; log raw line on failure."""
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            logging.debug(f"Non-JSON line: {line!r}")
            return
        self.message_queue.append({
            'type': obj.get('type'),
            'raw': line,
            'received': datetime.now()
        })
        self.process_json(obj)

    # ── Message Processing ────────────────────────────────────────────

    def process_json(self, obj: dict):
        """Dispatch a parsed JSON message to the appropriate handler."""
        msg_type = obj.get("type", "")
        try:
            if msg_type == "DATA":
                self.process_data(obj)
            elif msg_type == "INVENTORY":
                self.process_inventory(obj)
            elif msg_type == "HEARTBEAT":
                self.process_heartbeat(obj)
            elif msg_type == "LOG":
                message = obj.get("message", "")
                logging.info(f"Arduino LOG: {message}")
                self.db.add_event("ARDUINO", "INFO", message)
            elif msg_type == "ERROR":
                message = obj.get("message", "")
                logging.warning(f"Arduino ERROR: {message}")
                self.db.add_event("ARDUINO", "ERROR", message)
        except Exception as e:
            logging.error(f"Error processing {msg_type} message: {e}")

    def process_data(self, obj: dict):
        """
        Handle DATA messages from SensorHub.
        JSON format: {"type":"DATA","ts":...,"sensor":"HC_SR04","values":{"distance_cm":3.38}}
        """
        sensor_id = obj.get("sensor", "UNKNOWN")
        values_dict: dict = obj.get("values", {})

        # Extract ordered values and their field names as units
        values = [float(v) for v in values_dict.values()]
        units  = list(values_dict.keys())

        self.db.add_sensor_data(sensor_id, values, units, json.dumps(obj))

        if self.config.get('LOGGING', 'level') == 'DEBUG':
            logging.debug(f"Data from {sensor_id}: {values_dict}")

    def process_inventory(self, obj: dict):
        """
        Handle INVENTORY messages from SensorHub.
        JSON format: {"type":"INVENTORY","ts":...,"sensors":{"HC_SR04":{"pins":"..."},...}}
        """
        sensors_dict: dict = obj.get("sensors", {})
        for sensor_id, meta in sensors_dict.items():
            self.sensor_inventory[sensor_id] = sensor_id
            self.db.add_sensor(sensor_id, sensor_id, 0, meta)

        count = len(sensors_dict)
        logging.info(f"Sensor inventory updated: {count} sensor(s) — {list(sensors_dict.keys())}")
        self.db.add_event("INVENTORY", "INFO", f"Updated: {count} sensors", self.sensor_inventory)

    def process_heartbeat(self, obj: dict):
        """
        Handle HEARTBEAT messages from SensorHub.
        JSON format: {"type":"HEARTBEAT","ts":...,"interval_ms":1000,"mode":"STREAMING"}
        """
        self.last_heartbeat = time.time()
        mode = obj.get("mode", "UNKNOWN")
        if mode == "PAUSED":
            logging.warning("Arduino streaming is PAUSED — send START to resume")
            self.db.add_event("HEARTBEAT", "WARNING", "Streaming paused")

    # ── Commands (Pi → Arduino) ───────────────────────────────────────

    def send_command(self, command: str, *args) -> bool:
        """
        Send a command to the Arduino over serial.

        Supported commands (case-insensitive, passed to firmware as uppercase):
            PING, INVENTORY, START, STOP, STATUS, RESET
            SET_RATE <ms>          — sets the sensor sample interval
            CONFIG INTERVAL <ms>   — alias for SET_RATE (backwards compat)
        """
        if not self.serial_conn:
            return False

        try:
            cmd = command.upper()

            # Backwards-compatibility aliases from old CONFIG sub-command style
            if cmd == "CONFIG":
                sub = args[0].upper() if args else ""
                if sub == "INTERVAL" and len(args) >= 2:
                    cmd = "SET_RATE"
                    args = (args[1],)
                else:
                    # CONFIG AUTODETECT / CONFIG DEBUG are not supported in firmware
                    logging.debug(f"CONFIG {sub} not supported by firmware — skipped")
                    return True

            # DETECT is an alias for INVENTORY
            if cmd == "DETECT":
                cmd = "INVENTORY"

            # Build the plain-text command line
            if args:
                line = f"{cmd} {' '.join(str(a) for a in args)}\n"
            else:
                line = f"{cmd}\n"

            self.serial_conn.write(line.encode())
            logging.debug(f"Sent command: {line.strip()!r}")
            return True

        except Exception as e:
            logging.error(f"Error sending command: {e}")
            return False

    # ── Reconnection ──────────────────────────────────────────────────

    def reconnect(self) -> bool:
        logging.info("Attempting to reconnect...")
        max_attempts = self.config.getint('MONITORING', 'max_reconnect_attempts', 10)

        for attempt in range(max_attempts):
            if self.serial_conn:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
                self.serial_conn = None

            time.sleep(2)

            if self.connect():
                self.last_heartbeat = time.time()
                logging.info(f"Reconnected after {attempt + 1} attempt(s)")
                self.db.add_event("SERIAL", "INFO", f"Reconnected after {attempt + 1} attempts")
                return True

            time.sleep(5)

        logging.error("Failed to reconnect")
        self.db.add_event("SERIAL", "ERROR", "Reconnection failed")
        return False

    # Keep old method name as alias for backwards compatibility
    def process_message(self, raw_line: str):
        """Alias kept for backwards compatibility — routes to _dispatch_line."""
        self._dispatch_line(raw_line)
