from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect

from .ssh_backend import SSHBackend


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


async def stream_mqtt(
    websocket: WebSocket,
    config: Dict[str, Any],
    mode: str,
    target_id: Optional[str] = None,
) -> None:
    await websocket.accept()

    if target_id:
        try:
            target = _find_target(config, target_id)
            mqtt_config = _target_mqtt_config(config, target)
        except MqttTargetError as error:
            await websocket.send_json(
                {
                    "kind": "error",
                    "message": str(error),
                    "timestamp": _timestamp(),
                }
            )
            return

        await _stream_direct(websocket, mqtt_config)
        return

    if mode == "local":
        await _stream_direct(websocket, config.get("mqtt", {}))
        return

    await _stream_remote_command(websocket, config)


async def _stream_direct(websocket: WebSocket, mqtt_config: Dict[str, Any]) -> None:
    import paho.mqtt.client as mqtt

    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=500)
    loop = asyncio.get_running_loop()
    client_id = str(mqtt_config.get("client_id") or "")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    topics = _mqtt_topics(mqtt_config)
    host = str(mqtt_config.get("host") or "").strip()
    port = int(mqtt_config.get("port") or 1883)
    keepalive = int(mqtt_config.get("keepalive_seconds") or 30)
    label = str(mqtt_config.get("label") or host or "MQTT broker")

    if not host:
        await websocket.send_json(
            {
                "kind": "error",
                "message": "MQTT host is empty",
                "timestamp": _timestamp(),
            }
        )
        return

    username = str(mqtt_config.get("username") or "")
    password = str(mqtt_config.get("password") or "")

    if username or password:
        client.username_pw_set(username or None, password or None)

    if _truthy(mqtt_config.get("tls")):
        client.tls_set()

    def on_connect(client: mqtt.Client, _: Any, __: Any, reason_code: Any, ___: Any) -> None:
        loop.call_soon_threadsafe(
            _queue_put_latest,
            queue,
            {
                "kind": "status",
                "message": (
                    f"connected to {label} with reason {reason_code}; "
                    f"subscribed to {', '.join(topics)}"
                ),
                "timestamp": _timestamp(),
            },
        )

        for topic in topics:
            client.subscribe(topic)

    def on_message(_: mqtt.Client, __: Any, message: mqtt.MQTTMessage) -> None:
        payload = message.payload.decode("utf-8", errors="replace")
        item = {
            "kind": "message",
            "topic": message.topic,
            "payload": payload,
            "qos": message.qos,
            "retain": bool(message.retain),
            "timestamp": _timestamp(),
        }
        loop.call_soon_threadsafe(_queue_put_latest, queue, item)

    client.on_connect = on_connect
    client.on_message = on_message
    loop_started = False

    try:
        await asyncio.to_thread(client.connect, host, port, keepalive)
        client.loop_start()
        loop_started = True

        while True:
            item = await queue.get()
            await websocket.send_json(item)
    except WebSocketDisconnect:
        pass
    except Exception as error:
        await websocket.send_json(
            {
                "kind": "error",
                "message": str(error),
                "timestamp": _timestamp(),
            }
        )
    finally:
        if loop_started:
            client.loop_stop()

        try:
            client.disconnect()
        except Exception:
            pass


def _queue_put_latest(queue: asyncio.Queue[Dict[str, Any]], item: Dict[str, Any]) -> None:
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass

    queue.put_nowait(item)


async def _stream_remote_command(websocket: WebSocket, config: Dict[str, Any]) -> None:
    command = str(config.get("mqtt", {}).get("remote_subscribe_command") or "")

    if not command:
        await websocket.send_json(
            {
                "kind": "error",
                "message": "remote_subscribe_command is empty",
                "timestamp": _timestamp(),
            }
        )
        return

    ssh = SSHBackend(config)
    client = await asyncio.to_thread(ssh.connect)
    channel = client.get_transport().open_session()
    channel.get_pty()
    channel.exec_command(command)
    buffer = ""

    try:
        await websocket.send_json(
            {
                "kind": "status",
                "message": "remote MQTT subscription started",
                "timestamp": _timestamp(),
            }
        )

        while not channel.exit_status_ready():
            if not channel.recv_ready():
                await asyncio.sleep(0.05)
                continue

            data = channel.recv(4096).decode("utf-8", errors="replace")
            buffer += data
            lines = buffer.splitlines(keepends=True)
            buffer = ""

            if lines and not lines[-1].endswith(("\n", "\r")):
                buffer = lines.pop()

            for line in lines:
                text = line.strip()
                if text:
                    await websocket.send_json(_parse_mosquitto_line(text))
    except WebSocketDisconnect:
        pass
    finally:
        channel.close()
        client.close()


def _parse_mosquitto_line(line: str) -> Dict[str, Any]:
    if " " not in line:
        return {
            "kind": "message",
            "topic": line,
            "payload": "",
            "timestamp": _timestamp(),
        }

    topic, payload = line.split(" ", 1)
    return {
        "kind": "message",
        "topic": topic,
        "payload": payload,
        "timestamp": _timestamp(),
    }


class MqttTargetError(Exception):
    pass


def _target_mqtt_config(
    config: Dict[str, Any],
    target: Dict[str, Any],
) -> Dict[str, Any]:
    nested = target.get("mqtt") if isinstance(target.get("mqtt"), dict) else {}
    mqtt_config = {
        "host": nested.get("host") or target.get("mqtt_host"),
        "port": nested.get("port") or target.get("mqtt_port") or 1883,
        "keepalive_seconds": (
            nested.get("keepalive_seconds")
            or target.get("mqtt_keepalive_seconds")
            or config.get("mqtt", {}).get("keepalive_seconds")
            or 30
        ),
        "topics": _first_configured_topics(
            nested.get("topics"),
            nested.get("topic"),
            target.get("mqtt_topics"),
            target.get("mqtt_topic"),
        ),
        "client_id": nested.get("client_id") or target.get("mqtt_client_id") or "",
        "username": nested.get("username") or target.get("mqtt_username") or "",
        "password": nested.get("password") or target.get("mqtt_password") or "",
        "tls": nested.get("tls", target.get("mqtt_tls", False)),
        "label": target.get("mqtt_description") or target.get("name") or target.get("ip"),
    }

    if not mqtt_config["host"]:
        raise MqttTargetError(
            f"No MQTT broker is configured for {target.get('name') or target.get('ip') or 'target'}."
        )

    return mqtt_config


def _first_configured_topics(*candidates: Any) -> List[str]:
    for candidate in candidates:
        topics = _normalize_topics(candidate)

        if topics:
            return topics

    return ["#"]


def _mqtt_topics(mqtt_config: Dict[str, Any]) -> List[str]:
    return _normalize_topics(mqtt_config.get("topics")) or ["#"]


def _normalize_topics(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []

    if isinstance(value, (list, tuple, set)):
        return [str(topic).strip() for topic in value if str(topic).strip()]

    return [str(value).strip()] if str(value).strip() else []


def _find_target(config: Dict[str, Any], target_id: str) -> Dict[str, Any]:
    target_key = target_id.strip().lower()

    for target in config.get("targets", []):
        names = {
            str(target.get("ip") or "").lower(),
            str(target.get("name") or "").lower(),
            str(target.get("mqtt_target") or "").lower(),
            _slug(str(target.get("name") or "")),
            _slug(str(target.get("mqtt_target") or "")),
        }

        if target_key in names:
            return target

    raise MqttTargetError(f"No configured MQTT target matches {target_id}.")


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value.lower()).strip("-")


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    return str(value).strip().lower() in {"1", "true", "yes", "on"}
