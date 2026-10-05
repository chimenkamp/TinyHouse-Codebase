"""Outbox delivery contract checks with an explicitly mocked MQTT transport."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from Workareas.shared.configuration import BrokerConfig, StationConfig
from Workareas.shared.events import EventService, encode
from Workareas.shared.models import JsonObject
from Workareas.shared.mqtt_delivery import MqttDelivery


class MqttDeliveryTests(unittest.TestCase):
    """Keep durable events until a QoS 1 publish has been acknowledged."""

    directory: tempfile.TemporaryDirectory[str]
    service: EventService
    broker: BrokerConfig
    client: Mock
    info: Mock

    def setUp(self) -> None:
        """Prepare a real temporary SQLite outbox and a synthetic transport.

        :return: None.
        """
        self.directory = tempfile.TemporaryDirectory()
        root: Path = Path(self.directory.name)
        self.broker = BrokerConfig(
            "localhost", "test-user", root / "password", root / "ca.pem"
        )
        self.service = EventService(
            StationConfig("WA1", root / "events.sqlite3", broker=self.broker)
        )
        event: JsonObject = {"event_id": "fixture-1", "activity": "test fixture"}
        with self.service.database:
            self.service.database.execute(
                "INSERT INTO events(id,topic,data) VALUES(?,?,?)",
                ("fixture-1", "test/events", encode(event)),
            )
        self.client = Mock()
        self.client.is_connected.return_value = True
        self.info = Mock()
        self.info.rc = 0
        self.info.mid = 1
        self.client.publish.return_value = self.info

    def tearDown(self) -> None:
        """Close the real database before removing test files.

        :return: None.
        """
        self.service.close()
        self.directory.cleanup()

    def publisher(self) -> MqttDelivery:
        """Replace only network construction, retaining real delivery logic.

        :return: Delivery helper backed by the explicit unit-test mock.
        """
        with patch(
            "Workareas.shared.mqtt_delivery.create_client", return_value=self.client
        ):
            return MqttDelivery(self.broker, "WA1")

    def test_acks_only_after_puback_and_never_enqueues_twice(self) -> None:
        """Successful enqueue alone must not consume a durable event.

        :return: None.
        """
        delivery: MqttDelivery = self.publisher()
        self.assertEqual(delivery.publish_pending(self.service), 0)
        self.assertEqual(delivery.publish_pending(self.service), 0)
        self.assertEqual(len(self.service.pending()), 1)
        self.assertEqual(self.client.publish.call_count, 1)
        self.assertEqual(
            self.client.publish.call_args.kwargs, {"qos": 1, "retain": False}
        )
        delivery.acknowledged_mids.put(self.info.mid)
        self.assertEqual(delivery.publish_pending(self.service), 1)
        self.assertEqual(self.service.pending(), [])

    def test_disconnected_transport_keeps_outbox(self) -> None:
        """An offline broker must not enqueue or acknowledge anything.

        :return: None.
        """
        delivery: MqttDelivery = self.publisher()
        self.client.is_connected.return_value = False
        self.assertEqual(delivery.publish_pending(self.service), 0)
        self.client.publish.assert_not_called()
        self.assertEqual(len(self.service.pending()), 1)

    def test_publish_failure_keeps_outbox_and_retries(self) -> None:
        """A rejected enqueue remains available on a later connected attempt.

        :return: None.
        """
        delivery: MqttDelivery = self.publisher()
        self.info.rc = 15
        with self.assertLogs("Workareas.shared.mqtt_delivery", level="WARNING"):
            self.assertEqual(delivery.publish_pending(self.service), 0)
        self.assertEqual(len(self.service.pending()), 1)
        self.info.rc = 0
        self.assertEqual(delivery.publish_pending(self.service), 0)
        self.assertEqual(self.client.publish.call_count, 2)

    def test_ack_timeout_keeps_durable_and_client_queues(self) -> None:
        """Missing PUBACK must be visible while preserving restart recovery.

        :return: None.
        """
        delivery: MqttDelivery = self.publisher()
        with patch("Workareas.shared.mqtt_delivery.time.monotonic", return_value=0.0):
            delivery.publish_pending(self.service)
        with (
            patch("Workareas.shared.mqtt_delivery.time.monotonic", return_value=60.0),
            self.assertLogs("Workareas.shared.mqtt_delivery", level="WARNING"),
        ):
            self.assertEqual(delivery.publish_pending(self.service), 0)
        self.assertEqual(len(self.service.pending()), 1)
        self.assertEqual(self.client.publish.call_count, 1)

    def test_close_and_restart_leave_unacknowledged_event_durable(self) -> None:
        """Publisher lifetime must not delete an uncertain delivery.

        :return: None.
        """
        delivery: MqttDelivery = self.publisher()
        delivery.publish_pending(self.service)
        delivery.close()
        self.client.disconnect.assert_called_once()
        self.client.loop_stop.assert_called_once()
        replacement: MqttDelivery = self.publisher()
        replacement.publish_pending(self.service)
        self.assertEqual(self.client.publish.call_count, 2)
        self.assertEqual(len(self.service.pending()), 1)

    def test_disconnect_during_publish_never_enqueues_twice(self) -> None:
        """Paho retains QoS1 messages when a connection vanishes during publish.

        :return: None.
        """
        delivery: MqttDelivery = self.publisher()
        self.info.rc = 4
        with self.assertLogs("Workareas.shared.mqtt_delivery", level="WARNING"):
            self.assertEqual(delivery.publish_pending(self.service), 0)
        self.assertEqual(delivery.publish_pending(self.service), 0)
        self.assertEqual(len(self.service.pending()), 1)
        self.assertEqual(self.client.publish.call_count, 1)
        delivery.acknowledged_mids.put(self.info.mid)
        self.assertEqual(delivery.publish_pending(self.service), 1)


if __name__ == "__main__":
    unittest.main()
