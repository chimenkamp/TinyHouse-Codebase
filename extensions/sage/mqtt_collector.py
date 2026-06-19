"""
scale_serial_emulator.py

Subscribes to MQTT topics from scale sensors (esp32/drawerX/sensor),
maps drawer IDs to line prefixes (P1, P2, ...) dynamically,
and emulates serial output on a virtual serial port (socat).

Setup:
    socat PTY,link=/dev/ttyV0,rawer PTY,link=/dev/ttyV1,rawer &
    python scale_serial_emulator.py

MQTT payload expected:
    {
        "deviceID": "",
        "drawer": "drawer1",
        "timestamp": "...",
        "weight": 123.4,
        "batvoltage": 3.7,
        "wifi_connected": true,
        "mqtt_connected": true
    }

Serial output format:
    P1,<weight>

Drawer mapping is persisted in drawer_mapping.json.
Load environment variables before starting:
    export $(cat .env | xargs)
"""

import json
import logging
import os
import re
from pathlib import Path

import paho.mqtt.client as mqtt
import serial

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# === Configuration ===
BROKER_HOST = os.getenv("BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("BROKER_PORT", 1883))
SERIAL_PORT = os.getenv("EMULATOR_SERIAL_PORT", "/dev/ttyV0")
BAUDRATE = 9600
SUBSCRIBE_TOPIC = "esp32/+/sensor"
MAPPING_FILE = Path(os.getenv("DRAWER_MAPPING_FILE", "drawer_mapping.json"))

_drawer_to_prefix: dict[str, str] = {}
_next_index = 1


def load_mapping():
    """Load persisted drawer mapping from JSON if it exists."""
    global _next_index
    if MAPPING_FILE.exists():
        with open(MAPPING_FILE) as f:
            _drawer_to_prefix.update(json.load(f))
        # Set next index to avoid collisions with already assigned prefixes
        existing = [
            int(re.search(r"\d+", p).group())
            for p in _drawer_to_prefix.values()
            if re.search(r"\d+", p)
        ]
        if existing:
            _next_index = max(existing) + 1
        logger.info(f"Loaded drawer mapping: {_drawer_to_prefix}")


def save_mapping():
    """Persist current drawer mapping to JSON."""
    with open(MAPPING_FILE, "w") as f:
        json.dump(_drawer_to_prefix, f, indent=2)
    logger.debug(f"Mapping saved to {MAPPING_FILE}")


def get_or_assign_prefix(drawer_id: str) -> str:
    """
    Returns the line prefix for a drawer ID.
    Assigns and persists a new prefix if the drawer is seen for the first time.
    """
    global _next_index

    if drawer_id not in _drawer_to_prefix:
        match = re.search(r"\d+", drawer_id)
        prefix = f"P{match.group()}" if match else f"P{_next_index}"
        if not match:
            _next_index += 1

        _drawer_to_prefix[drawer_id] = prefix
        save_mapping()
        logger.info(f"New drawer registered: {drawer_id} -> {prefix}")

    return _drawer_to_prefix[drawer_id]


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(SUBSCRIBE_TOPIC)
        logger.info(f"Connected to broker, subscribed to '{SUBSCRIBE_TOPIC}'")
    else:
        logger.error(f"Connection failed: rc={rc}")


def on_message(client, userdata, msg):
    ser: serial.Serial = userdata["ser"]

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"Could not parse payload: {e}")
        return

    drawer = payload.get("drawer")
    weight = payload.get("weight")

    if not drawer:
        logger.warning(f"No drawer field in payload from {msg.topic}, skipping")
        return

    if weight is None:
        logger.warning(f"No weight field in payload from {msg.topic}, skipping")
        return

    prefix = get_or_assign_prefix(drawer)
    line = f"{prefix},{float(weight):.3f}\n"

    try:
        ser.write(line.encode("utf-8"))
        ser.flush()
        logger.debug(f"Serial write: {line.strip()}")
    except serial.SerialException as e:
        logger.error(f"Serial write failed: {e}")


def main():
    load_mapping()

    logger.info(f"Opening serial port {SERIAL_PORT} at {BAUDRATE} baud...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    except serial.SerialException as e:
        logger.error(
            f"Could not open serial port {SERIAL_PORT}: {e}\n"
            "Make sure socat is running:\n"
            "  socat PTY,link=/dev/ttyV0,rawer PTY,link=/dev/ttyV1,rawer &"
        )
        return

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="scale_serial_emulator",
        userdata={"ser": ser},
    )
    client.on_connect = on_connect
    client.on_message = on_message

    logger.info(f"Connecting to broker {BROKER_HOST}:{BROKER_PORT}...")
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        client.disconnect()
        ser.close()
        logger.info("Closed MQTT and serial port.")


if __name__ == "__main__":
    main()
