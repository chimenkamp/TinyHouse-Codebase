from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from .color_camera import COLOR_LABELS, CameraColorReader
from .runtime_common import ensure_pipeline_config, host_slug, utc_now

from mqtt.case_receiver import Case_Receiver
from mqtt.sensor_publisher import create_mqtt_client
from pipeline import SensorPipeline
from sensors.adapter import PressureAdapter
from sensors.serial_reader import SerialReader


DEFAULT_DATA_DIR = Path("./data")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a TinyHouse SAGE sensor node.")
    parser.add_argument(
        "--role",
        choices=["arduino", "camera"],
        required=True,
        help="Hardware role for this node.",
    )
    parser.add_argument("--broker-host", default=os.getenv("BROKER_HOST", "132.180.196.164"))
    parser.add_argument("--broker-port", type=int, default=int(os.getenv("BROKER_PORT", "1883")))
    parser.add_argument("--data-dir", default=os.getenv("OUTPUT_DIR", str(DEFAULT_DATA_DIR)))
    parser.add_argument("--window-size", type=float, default=float(os.getenv("WINDOW_SIZE", "2.0")))
    parser.add_argument("--serial-port", default=os.getenv("SERIAL_PORT", ""))
    parser.add_argument("--baudrate", type=int, default=int(os.getenv("BAUDRATE", "9600")))
    parser.add_argument(
        "--prefixes",
        default=os.getenv("ARDUINO_PREFIXES", "P1,P2"),
        help="Comma-separated Arduino serial prefixes.",
    )
    parser.add_argument("--camera-index", type=int, default=int(os.getenv("CAMERA_INDEX", "0")))
    parser.add_argument("--camera-interval", type=float, default=float(os.getenv("CAMERA_INTERVAL", "0.5")))
    parser.add_argument("--auto-case", action="store_true", default=os.getenv("AUTO_CASE", "0") == "1")
    return parser.parse_args()


def publish_status(client, node_id: str, state: str, **extra: object) -> None:
    payload = {
        "node_id": node_id,
        "state": state,
        "timestamp": utc_now(),
        **extra,
    }
    client.publish(f"sage/status/{node_id}", json.dumps(payload), retain=True)


def find_serial_port() -> str:
    candidates = [
        "/dev/ttyACM0",
        "/dev/ttyACM1",
        "/dev/ttyUSB0",
        "/dev/ttyUSB1",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    raise RuntimeError("No serial port found. Set SERIAL_PORT or pass --serial-port.")


def make_pipeline(sensor_id: str, sensor_kind: str, args: argparse.Namespace, mqtt_client) -> SensorPipeline:
    data_dir = Path(args.data_dir)
    ensure_pipeline_config(
        data_dir,
        sensor_id,
        sensor_kind,
        color_labels=COLOR_LABELS if sensor_kind == "color" else None,
    )
    return SensorPipeline(
        sensor_id=sensor_id,
        data_dir=str(data_dir),
        window_size=args.window_size,
        mqtt_client=mqtt_client,
        mqtt_topic=f"events/{sensor_id}",
        on_event_ready=lambda event: print(f"[event] {json.dumps(event)}", flush=True),
    )


def run_arduino(args: argparse.Namespace, mqtt_client, node_id: str) -> None:
    prefixes = [prefix.strip() for prefix in args.prefixes.split(",") if prefix.strip()]
    if not prefixes:
        prefixes = ["P1"]

    adapters = [
        PressureAdapter(sensor_id=f"{node_id}_{prefix.lower()}", line_prefix=prefix)
        for prefix in prefixes
    ]
    pipelines = {
        adapter.sensor_id: make_pipeline(adapter.sensor_id, "pressure", args, mqtt_client)
        for adapter in adapters
    }

    serial_port = args.serial_port or find_serial_port()
    reader = SerialReader(
        port=serial_port,
        baudrate=args.baudrate,
        adapters=adapters,
        on_reading=lambda reading: route_reading(reading, pipelines),
    )

    print(f"Arduino node {node_id}: {serial_port}, sensors={list(pipelines)}", flush=True)
    publish_status(mqtt_client, node_id, "running", role="arduino", serial_port=serial_port)
    run_until_interrupted(args, mqtt_client, pipelines, reader.run, node_id)
    reader.close()


def run_camera(args: argparse.Namespace, mqtt_client, node_id: str) -> None:
    sensor_id = f"{node_id}_usb_camera_color"
    pipelines = {
        sensor_id: make_pipeline(sensor_id, "color", args, mqtt_client)
    }
    reader = CameraColorReader(
        sensor_id=sensor_id,
        camera_index=args.camera_index,
        interval_seconds=args.camera_interval,
    )
    print(f"Camera node {node_id}: camera_index={args.camera_index}", flush=True)
    publish_status(mqtt_client, node_id, "running", role="camera", camera_index=args.camera_index)
    run_until_interrupted(args, mqtt_client, pipelines, lambda: reader.run(lambda r: route_reading(r, pipelines)), node_id)
    reader.close()


def route_reading(reading: dict, pipelines: dict[str, SensorPipeline]) -> None:
    pipeline = pipelines.get(reading["sensor_id"])
    if pipeline is None:
        return
    pipeline.process_reading(reading)


def run_until_interrupted(
    args: argparse.Namespace,
    mqtt_client,
    pipelines: dict[str, SensorPipeline],
    runner,
    node_id: str,
) -> None:
    current_case = {"id": None}

    def start_case(case_id: str) -> None:
        current_case["id"] = case_id
        for pipeline in pipelines.values():
            pipeline.start_case(case_id)
        publish_status(mqtt_client, node_id, "case_started", case_id=case_id)

    def stop_case() -> None:
        for pipeline in pipelines.values():
            pipeline.stop_case()
        publish_status(mqtt_client, node_id, "case_stopped", case_id=current_case["id"])
        current_case["id"] = None

    Case_Receiver(client=mqtt_client, on_case_start=start_case, on_case_stop=stop_case)

    if args.auto_case:
        start_case(f"{node_id}-{utc_now()}")

    should_stop = {"value": False}

    def handle_signal(signum, frame) -> None:
        should_stop["value"] = True
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handle_signal)

    try:
        runner()
    except KeyboardInterrupt:
        print("Stopping node...", flush=True)
    finally:
        if current_case["id"]:
            stop_case()
        for pipeline in pipelines.values():
            pipeline.close()
        publish_status(mqtt_client, node_id, "stopped")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        time.sleep(0.2)


def main() -> int:
    load_dotenv()
    args = parse_args()
    node_id = f"{host_slug()}_{args.role}"
    mqtt_client = create_mqtt_client(
        args.broker_host,
        broker_port=args.broker_port,
        client_id=f"sage_{node_id}",
    )

    if args.role == "arduino":
        run_arduino(args, mqtt_client, node_id)
    else:
        run_camera(args, mqtt_client, node_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

