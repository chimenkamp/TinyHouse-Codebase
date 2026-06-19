"""
Module running on Main PC to receive Event jsons from Pis
"""

import json
from datetime import datetime
from pathlib import Path

SUBSCRIBE_TOPIC = "events/#"


def make_on_message(events_file: Path):
    """Factory: returns on_message callback with events_file path baked in."""

    def on_message(client, userdata, msg):
        try:
            event = json.loads(msg.payload.decode("utf-8"))
            event["_received_at"] = datetime.now().isoformat()
            event["_mqtt_topic"] = msg.topic

            with open(events_file, "a") as f:
                f.write(json.dumps(event) + "\n")

            activity = event.get("event_type", "?")
            sensor = event.get("sensor_id", "?")
            case = event.get("case_id", "?")
            print(f"  [{sensor}] {activity} (case={case})")

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"error while parsing: {e}")

    return on_message


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"connected to broker, subscribe '{SUBSCRIBE_TOPIC}'")
        client.subscribe(SUBSCRIBE_TOPIC)
    else:
        print(f"connection unsuccessful: rc={rc}")


def on_disconnect(client, userdata, flags, rc, properties=None):
    print(f"disconnected (rc={rc})")
