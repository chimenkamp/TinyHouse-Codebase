from __future__ import annotations

import argparse
import json
import os
import signal
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import paho.mqtt.client as mqtt

from .runtime_common import ensure_pipeline_config, normalize_sensor_id, utc_now

from broker.mqtt.broker_publisher import PUBLISH_TOPIC, case_ID, publish_case_stop
from broker.mqtt.broker_subscriber import make_on_message
from pipeline import SensorPipeline


SCALE_TOPICS = ["esp32/+/sensor", "tinyhouse/scale/#"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the TinyHouse SAGE orchestrator.")
    parser.add_argument("--broker-host", default=os.getenv("BROKER_HOST", "localhost"))
    parser.add_argument("--broker-port", type=int, default=int(os.getenv("BROKER_PORT", "1883")))
    parser.add_argument("--data-dir", default=os.getenv("BROKER_OUTPUT_DIR", "./received_data"))
    parser.add_argument("--scale-delta", type=float, default=float(os.getenv("SCALE_DELTA", "5.0")))
    parser.add_argument("--no-auto-case", action="store_true", help="Do not publish a case start at launch.")
    return parser.parse_args()


class ScaleRuntime:
    def __init__(self, data_dir: Path, mqtt_client: mqtt.Client, delta: float) -> None:
        self.data_dir = data_dir
        self.mqtt_client = mqtt_client
        self.delta = delta
        self.case_id: str | None = None
        self.pipelines: dict[str, SensorPipeline] = {}

    def start_case(self, case_id: str) -> None:
        self.case_id = case_id
        for pipeline in self.pipelines.values():
            pipeline.start_case(case_id)

    def stop_case(self) -> None:
        for pipeline in self.pipelines.values():
            pipeline.stop_case()
        self.case_id = None

    def process_payload(self, topic: str, payload: bytes) -> None:
        reading = self._reading_from_payload(topic, payload)
        if reading is None:
            return

        sensor_id = reading["sensor_id"]
        pipeline = self.pipelines.get(sensor_id)
        if pipeline is None:
            ensure_pipeline_config(self.data_dir, sensor_id, "scale", delta_per_unit=self.delta)
            pipeline = SensorPipeline(
                sensor_id=sensor_id,
                data_dir=str(self.data_dir),
                window_size=2.0,
                mqtt_client=self.mqtt_client,
                mqtt_topic=f"events/{sensor_id}",
                on_event_ready=lambda event: print(f"[scale-event] {json.dumps(event)}", flush=True),
            )
            if self.case_id:
                pipeline.start_case(self.case_id)
            self.pipelines[sensor_id] = pipeline

        if self.case_id is None:
            return

        pipeline.process_reading(reading)

    def _reading_from_payload(self, topic: str, payload: bytes) -> dict[str, Any] | None:
        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        value = data.get("weight", data.get("value"))
        if value is None:
            return None

        try:
            weight = float(value)
        except (TypeError, ValueError):
            return None

        drawer = str(
            data.get("drawer")
            or data.get("deviceID")
            or data.get("device")
            or data.get("sensor")
            or topic
        )
        sensor_id = f"scale_{normalize_sensor_id(drawer)}"
        timestamp = str(data.get("timestamp") or utc_now())

        return {
            "sensor_id": sensor_id,
            "sensor_type": "scale",
            "value": weight,
            "unit": str(data.get("unit") or "g"),
            "timestamp": timestamp,
            "raw": data,
        }

    def close(self) -> None:
        for pipeline in self.pipelines.values():
            pipeline.close()


def main() -> int:
    load_dotenv()
    args = parse_args()
    data_dir = Path(args.data_dir)
    events_file = data_dir / "events" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)

    scale_runtime: ScaleRuntime
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="tinyhouse_sage_orchestrator")
    event_handler = make_on_message(events_file)
    scale_runtime = ScaleRuntime(data_dir=data_dir, mqtt_client=client, delta=args.scale_delta)

    def on_connect(client, userdata, flags, reason_code, properties=None):
        print(f"Connected to MQTT broker {args.broker_host}:{args.broker_port}: {reason_code}", flush=True)
        client.subscribe("events/#")
        client.subscribe("sage/status/#")
        for topic in SCALE_TOPICS:
            client.subscribe(topic)

    def on_message(client, userdata, msg):
        if msg.topic.startswith("events/"):
            event_handler(client, userdata, msg)
        elif any(_topic_matches(pattern, msg.topic) for pattern in SCALE_TOPICS):
            scale_runtime.process_payload(msg.topic, msg.payload)
        elif msg.topic.startswith("sage/status/"):
            print(f"[status] {msg.topic}: {msg.payload.decode('utf-8', errors='replace')}", flush=True)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker_host, args.broker_port, keepalive=60)
    client.loop_start()

    time.sleep(1.0)
    active_case = None
    if not args.no_auto_case:
        case = case_ID()
        client.publish(PUBLISH_TOPIC, json.dumps(case))
        active_case = case["case_id"]
        scale_runtime.start_case(active_case)
        print(f"Published case/control start: {active_case}", flush=True)

    stopping = {"value": False}

    def stop(signum=None, frame=None) -> None:
        stopping["value"] = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        while not stopping["value"]:
            time.sleep(1.0)
    finally:
        if active_case:
            publish_case_stop(client)
            scale_runtime.stop_case()
        scale_runtime.close()
        client.loop_stop()
        client.disconnect()
        print(f"Events written to {events_file}", flush=True)
    return 0


def _topic_matches(pattern: str, topic: str) -> bool:
    pattern_parts = pattern.split("/")
    topic_parts = topic.split("/")
    for index, part in enumerate(pattern_parts):
        if part == "#":
            return True
        if index >= len(topic_parts):
            return False
        if part != "+" and part != topic_parts[index]:
            return False
    return len(pattern_parts) == len(topic_parts)


if __name__ == "__main__":
    raise SystemExit(main())
