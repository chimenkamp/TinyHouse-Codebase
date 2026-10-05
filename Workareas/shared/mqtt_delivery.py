"""Publish the durable outbox using authenticated TLS and MQTT QoS 1.

Paho API reference: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html
Only Paho's network loop uses a background thread; SQLite stays on the caller.
"""

from __future__ import annotations

import logging
import ssl
import time
from queue import SimpleQueue
from typing import TYPE_CHECKING
from uuid import uuid4

from Workareas.shared.configuration import BrokerConfig
from Workareas.shared.events import OUTBOX_BATCH_SIZE, EventService, encode
from Workareas.shared.models import JsonObject

if TYPE_CHECKING:
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import MQTTErrorCode
    from paho.mqtt.properties import Properties
    from paho.mqtt.reasoncodes import ReasonCode

LOGGER: logging.Logger = logging.getLogger(__name__)
CONNECT_TIMEOUT_SECONDS: float = 2.0
PUBACK_TIMEOUT_SECONDS: float = 5.0
KEEPALIVE_SECONDS: int = 30
MIN_RECONNECT_SECONDS: int = 1
MAX_RECONNECT_SECONDS: int = 30
CLIENT_ID_SUFFIX_LENGTH: int = 12
MQTT_SUCCESS_CODE: int = 0
MQTT_QUEUE_FULL_CODE: int = 15
EVENT_QOS: int = 1


def on_connect(
    client: mqtt.Client,
    userdata: SimpleQueue[int],
    flags: mqtt.ConnectFlags,
    reason_code: ReasonCode,
    properties: Properties | None,
) -> None:
    """Log the actual broker connection result without touching the database.

    :param client: Paho transport client.
    :param userdata: Unused callback context.
    :param flags: Broker session flags.
    :param reason_code: Broker acceptance or rejection reason.
    :param properties: MQTT callback properties.
    :return: None.
    """
    if reason_code.is_failure:
        LOGGER.warning("MQTT connection rejected by %s: %s", client.host, reason_code)
    else:
        LOGGER.info("MQTT connected to %s", client.host)


def on_disconnect(
    client: mqtt.Client,
    userdata: SimpleQueue[int],
    flags: mqtt.DisconnectFlags,
    reason_code: ReasonCode,
    properties: Properties | None,
) -> None:
    """Expose transport loss while leaving uncertain events in the outbox.

    :param client: Paho transport client.
    :param userdata: Unused callback context.
    :param flags: Broker disconnect flags.
    :param reason_code: Disconnect result supplied by Paho.
    :param properties: MQTT callback properties.
    :return: None.
    """
    if reason_code.is_failure:
        LOGGER.warning(
            "MQTT disconnected from %s: %s; outbox retained", client.host, reason_code
        )


def on_connect_fail(client: mqtt.Client, userdata: SimpleQueue[int]) -> None:
    """Expose a failed network attempt without accessing the durable store.

    :param client: Paho transport client attempting to connect.
    :param userdata: Unused callback context.
    :return: None.
    """
    LOGGER.warning("MQTT connection attempt to %s failed; outbox retained", client.host)


def on_publish(
    client: mqtt.Client,
    userdata: SimpleQueue[int],
    mid: int,
    reason_code: ReasonCode,
    properties: Properties | None,
) -> None:
    """Pass completed QoS 1 acknowledgments back to the server thread.

    :param client: Paho transport client.
    :param userdata: Thread-safe queue consumed only by the server thread.
    :param mid: Message identifier whose broker handshake completed.
    :param reason_code: Broker publish result.
    :param properties: MQTT callback properties.
    :return: None.
    """
    if reason_code.is_failure:
        LOGGER.warning(
            "MQTT PUBACK rejected message %s: %s; outbox retained", mid, reason_code
        )
        return
    userdata.put(mid)


def create_client(
    config: BrokerConfig, station: str, acknowledgments: SimpleQueue[int]
) -> mqtt.Client:
    """Start an authenticated TLS transport without blocking HTTP on DNS.

    :param config: Broker address and local credential/certificate paths.
    :param station: Station label included in the unique MQTT client ID.
    :param acknowledgments: Queue carrying broker acknowledgments to the server.
    :return: Paho client whose daemon network thread owns no database state.
    """
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import CallbackAPIVersion

    password: str = config.password_file.read_text(encoding="utf-8").rstrip("\r\n")
    if not password or not config.username.strip() or not config.host.strip():
        raise ValueError(
            "MQTT requires a broker host, username, and nonempty password file"
        )
    context: ssl.SSLContext = ssl.create_default_context(cafile=str(config.ca_file))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    client_id: str = f"tinyhouse-{station}-{uuid4().hex[:CLIENT_ID_SUFFIX_LENGTH]}"
    client: mqtt.Client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=client_id,
        clean_session=True,
        protocol=mqtt.MQTTv311,
        reconnect_on_failure=True,
        userdata=acknowledgments,
    )
    client.connect_timeout = CONNECT_TIMEOUT_SECONDS
    client.username_pw_set(config.username, password)
    client.tls_set_context(context)
    client.max_queued_messages_set(OUTBOX_BATCH_SIZE)
    client.reconnect_delay_set(MIN_RECONNECT_SECONDS, MAX_RECONNECT_SECONDS)
    client.on_connect = on_connect
    client.on_connect_fail = on_connect_fail
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish
    client.enable_logger(LOGGER)
    client.connect_async(config.host, config.port, keepalive=KEEPALIVE_SECONDS)
    result: MQTTErrorCode = client.loop_start()
    if result != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(
            f"Cannot start MQTT network loop: {mqtt.error_string(result)}"
        )
    return client


class MqttDelivery:
    """Track PUBACKs while keeping all durable-store access on the server thread."""

    client: mqtt.Client
    station: str
    inflight: dict[int, tuple[str, float]]
    queued_ids: set[str]
    acknowledged_mids: SimpleQueue[int]
    timed_out: set[str]

    def __init__(self, config: BrokerConfig, station: str) -> None:
        """Construct the optional broker integration once per HTTP server.

        :param config: Explicit authenticated TLS broker configuration.
        :param station: Owning station label.
        :return: None.
        """
        self.station = station
        self.inflight = {}
        self.queued_ids = set()
        self.acknowledged_mids = SimpleQueue()
        self.timed_out = set()
        self.client = create_client(config, station, self.acknowledged_mids)

    def acknowledge_received(self, service: EventService) -> int:
        """Persist delivery only after Paho reports completed QoS 1 handshake.

        :param service: Durable event store owned by the calling server thread.
        :return: Number of newly acknowledged outbox entries.
        """
        delivered: int = 0
        # Only this server thread consumes the queue; the network thread adds IDs.
        while not self.acknowledged_mids.empty():
            mid: int = self.acknowledged_mids.get_nowait()
            pending: tuple[str, float] | None = self.inflight.get(mid)
            if pending is None:
                LOGGER.warning("MQTT received untracked PUBACK %s", mid)
                continue
            event_id: str = pending[0]
            service.acknowledge(event_id)
            del self.inflight[mid]
            self.queued_ids.remove(event_id)
            self.timed_out.discard(event_id)
            delivered += 1
        return delivered

    def report_overdue(self) -> None:
        """Report missing acknowledgments once while preserving queued sends.

        :return: None.
        """
        now: float = time.monotonic()
        event_id: str
        queued_at: float
        for event_id, queued_at in self.inflight.values():
            if (
                now - queued_at >= PUBACK_TIMEOUT_SECONDS
                and event_id not in self.timed_out
            ):
                LOGGER.warning(
                    "MQTT PUBACK overdue for %s; durable event and client queue retained",
                    event_id,
                )
                self.timed_out.add(event_id)

    def publish_pending(self, service: EventService) -> int:
        """Queue each pending event once without waiting on network operations.

        :param service: Server-thread event store with pending topic/event pairs.
        :return: Number acknowledged during this invocation.
        """
        if service.config.station != self.station:
            raise ValueError(
                "MQTT publisher and event store must belong to the same station"
            )
        delivered: int = self.acknowledge_received(service)
        self.report_overdue()
        if not self.client.is_connected():
            return delivered
        topic: str
        event: JsonObject
        for topic, event in service.pending():
            event_id: str = str(event["event_id"])
            if event_id in self.queued_ids:
                continue
            info: mqtt.MQTTMessageInfo = self.client.publish(
                topic, encode(event), qos=EVENT_QOS, retain=False
            )
            if info.rc == MQTT_QUEUE_FULL_CODE:
                LOGGER.warning(
                    "MQTT enqueue failed for %s with code %s; outbox retained",
                    event_id,
                    info.rc,
                )
                break
            self.inflight[info.mid] = (event_id, time.monotonic())
            self.queued_ids.add(event_id)
            if info.rc != MQTT_SUCCESS_CODE:
                LOGGER.warning(
                    "MQTT send deferred for %s with code %s; client queue and outbox retained",
                    event_id,
                    info.rc,
                )
        return delivered

    def close(self) -> None:
        """Stop Paho while leaving every unacknowledged event in SQLite.

        :return: None.
        """
        self.client.disconnect()
        self.client.loop_stop()
