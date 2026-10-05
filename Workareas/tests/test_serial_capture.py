"""Checks for the deployed Nano CSV acquisition path."""

from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone

from Workareas.shared.serial_capture import (
    MAX_LINE_BYTES,
    CaptureSession,
    FsrReading,
    Record,
    SerialCaptureConfig,
    parse_sensor_line,
    write_record,
)

NOW: datetime = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)


class SerialCaptureTests(unittest.TestCase):
    """Exercise wire parsing, framing, and acquisition identity."""

    def test_deployed_sensor_values_and_invalid_resistance(self) -> None:
        """Preserve the firmware units and sentinel.

        :return: None.
        """
        reading: FsrReading = parse_sensor_line("P1,2.500,510.000")
        self.assertEqual(reading.sensor_id, "P1")
        self.assertEqual(reading.voltage_v, 2.5)
        self.assertEqual(reading.resistance_kohm, 510.0)
        self.assertIsNone(parse_sensor_line("P2,0.000,-1").resistance_kohm)

    def test_rejects_malformed_and_nonfinite_values(self) -> None:
        """Reject unsupported identities, structure, and electrical values.

        :return: None.
        """
        invalid: tuple[str, ...] = (
            "P3,1,2",
            "P1,1",
            "P1,1,2,3",
            "P1,nan,2",
            "P1,1,inf",
            "P1,-0.1,2",
            "P1,5.1,2",
            "P1,1,-2",
            "P1,volts,2",
        )
        value: str
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_sensor_line(value)

    def test_partial_line_timeout_and_next_sensor(self) -> None:
        """Retain partial frames across a read timeout.

        :return: None.
        """
        session: CaptureSession = CaptureSession(
            SerialCaptureConfig("/dev/test", "WA1")
        )
        self.assertEqual(session.feed(b"P1,2.5", NOW), [])
        self.assertEqual(session.feed(b"", NOW)[0]["status"], "serial_timeout")
        records: list[Record] = session.feed(b"00,510.000\r\nP2,0.000,-1\n", NOW)
        self.assertEqual([record["sensor_id"] for record in records], ["P1", "P2"])
        self.assertEqual(records[0]["sequence"], 2)
        self.assertEqual(records[0]["source_timestamp"], "2026-09-28T10:00:00Z")
        self.assertEqual(records[0]["timestamp_quality"], "edge_ingest")
        self.assertEqual(records[1]["status"], "resistance_unavailable")

    def test_malformed_bytes_are_recorded_and_oversize_frames_discarded(self) -> None:
        """Recover only at the next delimiter after a corrupt frame.

        :return: None.
        """
        session: CaptureSession = CaptureSession(
            SerialCaptureConfig("/dev/test", "WA1")
        )
        self.assertEqual(session.feed(b"\xff\n", NOW)[0]["status"], "invalid_encoding")
        self.assertEqual(
            session.feed(b"P1,nan,2\n", NOW)[0]["status"], "invalid_reading"
        )
        self.assertEqual(
            session.feed(b"x" * (MAX_LINE_BYTES + 1), NOW)[0]["status"], "line_too_long"
        )
        self.assertEqual(session.feed(b"P1,1,2\n", NOW), [])
        self.assertEqual(session.feed(b"P2,5.000,0.000\n", NOW)[0]["sensor_id"], "P2")

    def test_reconnection_starts_new_session_and_sequence(self) -> None:
        """Prevent old partial readings and identities from crossing reconnects.

        :return: None.
        """
        config: SerialCaptureConfig = SerialCaptureConfig("/dev/test", "WA2")
        first: CaptureSession = CaptureSession(config)
        second: CaptureSession = CaptureSession(config)
        first.feed(b"P1,2", NOW)
        before: Record = first.diagnostic("disconnected", NOW, "USB removed")
        after: Record = second.feed(b"P1,2.500,510.000\n", NOW)[0]
        self.assertNotEqual(before["session_id"], after["session_id"])
        self.assertEqual(after["sequence"], 1)
        self.assertEqual(before["record_type"], "diagnostic")
        self.assertNotIn("sensor_id", before)

    def test_jsonl_writer_appends_and_flushes(self) -> None:
        """Write individual valid JSON records without truncating prior output.

        :return: None.
        """
        output: io.StringIO = io.StringIO()
        session: CaptureSession = CaptureSession(
            SerialCaptureConfig("/dev/test", "WA4")
        )
        record: Record = session.feed(b"P2,0.000,-1\n", NOW)[0]
        write_record(output, record)
        write_record(output, record)
        lines: list[str] = output.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIsNone(json.loads(lines[0])["resistance_kohm"])

    def test_configuration_and_timestamp_boundaries(self) -> None:
        """Reject ambiguous station identities and unusable timing values.

        :return: None.
        """
        with self.assertRaises(ValueError):
            SerialCaptureConfig("", "WA1")
        with self.assertRaises(ValueError):
            SerialCaptureConfig("/dev/test", "WA5")
        with self.assertRaises(ValueError):
            SerialCaptureConfig("/dev/test", "WA1", read_timeout_seconds=0)
        with self.assertRaises(ValueError):
            SerialCaptureConfig("/dev/test", "WA1", reconnect_seconds=float("nan"))
        session: CaptureSession = CaptureSession(
            SerialCaptureConfig("/dev/test", "WA1")
        )
        with self.assertRaises(ValueError):
            session.feed(b"P1,0,-1\n", NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
