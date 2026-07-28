from __future__ import annotations

import argparse
import json
import logging
import os
import ssl
import sys
import uuid
from typing import Any

import paho.mqtt.client as mqtt

DEFAULT_HOST = "192.168.1.100"
DEFAULT_PORT = 8883
DEFAULT_USERNAME = "bblp"
DEFAULT_ACCESS_CODE = os.getenv("BAMBU_ACCESS_CODE", "")
DEFAULT_TOPICS = ["device/+/report"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Connect to a Bambu Lab printer over local MQTT and print messages."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Printer IP or hostname")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="MQTT port")
    parser.add_argument(
        "--username",
        default=DEFAULT_USERNAME,
        help="MQTT username. Bambu local MQTT normally uses 'bblp'.",
    )
    parser.add_argument(
        "--access-code",
        default=DEFAULT_ACCESS_CODE,
        help="Printer LAN access code used as the MQTT password. Defaults to BAMBU_ACCESS_CODE if set.",
    )
    parser.add_argument(
        "--topic",
        action="append",
        dest="topics",
        help="Topic filter to subscribe to. Repeat to subscribe to multiple topics.",
    )
    parser.add_argument(
        "--client-id",
        default=f"tinyhouse-bambu-{uuid.uuid4().hex[:8]}",
        help="MQTT client id",
    )
    parser.add_argument(
        "--keepalive",
        type=int,
        default=30,
        help="MQTT keepalive interval in seconds",
    )
    parser.add_argument(
        "--qos",
        type=int,
        choices=(0, 1, 2),
        default=0,
        help="Subscription QoS",
    )
    parser.add_argument(
        "--no-tls",
        action="store_true",
        help="Disable TLS. Use this only if your printer exposes plain MQTT.",
    )
    parser.add_argument(
        "--verify-tls",
        action="store_true",
        help="Verify the server certificate. Off by default because printers use local certs.",
    )
    parser.add_argument(
        "--publish-topic",
        help="Optional topic to publish to immediately after connecting",
    )
    parser.add_argument(
        "--publish-payload",
        help="Payload for --publish-topic. If valid JSON, it is normalized before publishing.",
    )
    parser.add_argument(
        "--serial",
        help="Printer serial. Enables --request shortcuts for device/<serial>/request.",
    )
    parser.add_argument(
        "--request",
        action="append",
        choices=("get_version", "pushall", "start_push"),
        help="Convenience request to publish after connect. Repeat as needed.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging level",
    )
    return parser.parse_args()


def build_request_payload(name: str) -> dict[str, Any]:
    sequence_id = "0"
    if name == "get_version":
        return {"info": {"command": "get_version", "sequence_id": sequence_id}}
    if name == "pushall":
        return {"pushing": {"command": "pushall", "sequence_id": sequence_id}}
    if name == "start_push":
        return {"pushing": {"command": "start", "sequence_id": sequence_id}}
    raise ValueError(f"Unsupported request: {name}")


def normalize_payload(payload: str) -> str:
    try:
        return json.dumps(json.loads(payload), separators=(",", ":"))
    except json.JSONDecodeError:
        return payload


def configure_tls(client: mqtt.Client, verify_tls: bool) -> None:
    context = ssl.create_default_context()
    if not verify_tls:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    client.tls_set_context(context)
    if not verify_tls:
        client.tls_insecure_set(True)


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger(__name__)

    if not args.access_code:
        logger.error("No access code provided. Set --access-code or BAMBU_ACCESS_CODE.")
        return 1

    topics = args.topics or list(DEFAULT_TOPICS)
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=args.client_id,
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(args.username, args.access_code)

    if not args.no_tls:
        configure_tls(client, args.verify_tls)

    def on_connect(
        mqtt_client: mqtt.Client,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any = None,
    ) -> None:
        logger.info("Connected to %s:%s with reason=%s", args.host, args.port, reason_code)
        for topic in topics:
            mqtt_client.subscribe(topic, qos=args.qos)
            logger.info("Subscribed to %s", topic)

        if args.publish_topic and args.publish_payload is not None:
            payload = normalize_payload(args.publish_payload)
            mqtt_client.publish(args.publish_topic, payload, qos=args.qos)
            logger.info("Published to %s", args.publish_topic)

        if args.request:
            if not args.serial:
                logger.error("--request requires --serial")
                mqtt_client.disconnect()
                return

            request_topic = f"device/{args.serial}/request"
            for request_name in args.request:
                payload = json.dumps(build_request_payload(request_name), separators=(",", ":"))
                mqtt_client.publish(request_topic, payload, qos=args.qos)
                logger.info("Published %s to %s", request_name, request_topic)

    def on_message(
        _mqtt_client: mqtt.Client,
        _userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        payload = message.payload.decode("utf-8", errors="replace")
        print(json.dumps({
            "topic": message.topic,
            "qos": message.qos,
            "retain": bool(message.retain),
            "payload": payload,
        }, ensure_ascii=True))

    def on_disconnect(
        _mqtt_client: mqtt.Client,
        _userdata: Any,
        disconnect_flags: Any,
        reason_code: Any,
        _properties: Any = None,
    ) -> None:
        logger.info("Disconnected with reason=%s flags=%s", reason_code, disconnect_flags)

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    logger.info(
        "Connecting to Bambu printer MQTT at %s:%s using %s topics=%s tls=%s",
        args.host,
        args.port,
        args.username,
        ",".join(topics),
        not args.no_tls,
    )

    try:
        client.connect(args.host, args.port, keepalive=args.keepalive)
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Interrupted, shutting down")
    except Exception as error:
        logger.error("MQTT session failed: %s", error)
        return 1
    finally:
        try:
            client.disconnect()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())