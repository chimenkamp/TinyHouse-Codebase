"""Capture real Nano P1/P2 readings without assigning process meaning."""

from __future__ import annotations

import json
import math
import sys
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, TextIO, TypeAlias
from uuid import UUID, uuid4

if TYPE_CHECKING:
    import serial

NANO_BAUD_RATE: int = 9600
NANO_SUPPLY_VOLTS: float = 5.0
CSV_FIELD_COUNT: int = 3
RESISTANCE_UNAVAILABLE: float = -1.0
DEFAULT_READ_TIMEOUT_SECONDS: float = 2.0
DEFAULT_RECONNECT_SECONDS: float = 2.0
MAX_LINE_BYTES: int = 128
LINE_FEED: int = 10
SUPPORTED_SENSOR_IDS: tuple[str, ...] = ("P1", "P2")
SUPPORTED_WORKSTATIONS: tuple[str, ...] = ("WA1", "WA2", "WA3", "WA4")
Record: TypeAlias = dict[str, str | int | float | None]


@dataclass(frozen=True)
class SerialCaptureConfig:
    """Configure one explicitly identified Nano serial connection."""

    port: str
    workstation: str
    source_id: str = "nano-fsr"
    output_path: Path | None = None
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS
    reconnect_seconds: float = DEFAULT_RECONNECT_SECONDS

    def __post_init__(self) -> None:
        """Reject incomplete identity and unbounded serial timing.

        :return: None.
        """
        if not self.port.strip() or not self.source_id.strip():
            raise ValueError("port and source_id must be nonempty")
        if self.workstation not in SUPPORTED_WORKSTATIONS:
            raise ValueError("workstation must be WA1, WA2, WA3, or WA4")
        duration: float
        for duration in (self.read_timeout_seconds, self.reconnect_seconds):
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError(
                    "serial timeout and reconnect delay must be positive and finite"
                )


@dataclass(frozen=True)
class FsrReading:
    """Preserve the firmware voltage and resistance units."""

    sensor_id: str
    voltage_v: float
    resistance_kohm: float | None


def parse_sensor_line(raw_line: str) -> FsrReading:
    """Validate one deployed P1/P2 CSV frame.

    :param raw_line: ASCII CSV payload without its newline delimiter.
    :return: Reading with the firmware's -1 resistance represented by None.
    """
    parts: list[str] = raw_line.strip().split(",")
    if len(parts) != CSV_FIELD_COUNT or parts[0] not in SUPPORTED_SENSOR_IDS:
        raise ValueError("expected P1 or P2 followed by voltage and resistance")
    voltage: float = float(parts[1])
    resistance: float = float(parts[2])
    if not math.isfinite(voltage) or not 0 <= voltage <= NANO_SUPPLY_VOLTS:
        raise ValueError("voltage must be finite and within 0..5 V")
    if not math.isfinite(resistance) or (
        resistance < 0 and resistance != RESISTANCE_UNAVAILABLE
    ):
        raise ValueError("resistance must be nonnegative or the firmware sentinel -1")
    return FsrReading(
        parts[0], voltage, None if resistance == RESISTANCE_UNAVAILABLE else resistance
    )


@dataclass
class CaptureSession:
    """Frame one connection and identify its emitted records."""

    config: SerialCaptureConfig
    session_id: UUID = field(default_factory=uuid4)
    sequence: int = 0
    pending: bytearray = field(default_factory=bytearray)
    discarding: bool = False

    def record(self, record_type: str, status: str, at: datetime) -> Record:
        """Allocate a session-local identity and UTC ingestion timestamp.

        :param record_type: Observation or diagnostic classification.
        :param status: Acquisition result, never a process-event name.
        :param at: Timezone-aware time when the edge received the record.
        :return: Common JSON fields for an acquisition record.
        """
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("ingestion timestamp must be timezone-aware")
        self.sequence += 1
        return {
            "record_type": record_type,
            "status": status,
            "workstation": self.config.workstation,
            "source_id": self.config.source_id,
            "session_id": str(self.session_id),
            "sequence": self.sequence,
            "source_timestamp": at.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "timestamp_quality": "edge_ingest",
        }

    def diagnostic(self, status: str, at: datetime, detail: str = "") -> Record:
        """Describe a transport condition without claiming sensor health.

        :param status: Specific acquisition condition.
        :param at: Timezone-aware edge timestamp.
        :param detail: Error context suitable for the acquisition log.
        :return: Diagnostic record with no inferred process state.
        """
        result: Record = self.record("diagnostic", status, at)
        result["detail"] = detail
        return result

    def decode(self, raw: bytes, at: datetime) -> Record:
        """Preserve malformed frames or decode a valid reading.

        :param raw: Complete frame without its line-feed delimiter.
        :param at: Timezone-aware edge timestamp.
        :return: An observation or an explicit malformed-frame diagnostic.
        """
        raw_line: str
        result: Record
        try:
            raw_line = raw.decode("ascii").rstrip("\r")
        except UnicodeDecodeError as error:
            result = self.diagnostic("invalid_encoding", at, str(error))
            result["raw_hex"] = raw.hex()
            return result
        reading: FsrReading
        try:
            reading = parse_sensor_line(raw_line)
        except ValueError as error:
            result = self.diagnostic("invalid_reading", at, str(error))
            result["raw_line"] = raw_line
            return result
        status: str = (
            "valid" if reading.resistance_kohm is not None else "resistance_unavailable"
        )
        result = self.record("observation", status, at)
        result.update(
            sensor_id=reading.sensor_id,
            voltage_v=reading.voltage_v,
            resistance_kohm=reading.resistance_kohm,
            raw_line=raw_line,
        )
        return result

    def feed(self, chunk: bytes, at: datetime) -> list[Record]:
        """Retain partial lines across timeouts and bound malformed frames.

        :param chunk: Bytes returned by a bounded serial read; empty means timeout.
        :param at: Timezone-aware time when the read completed.
        :return: Records completed by this read, including explicit diagnostics.
        """
        if not chunk:
            return [
                self.diagnostic(
                    "serial_timeout", at, "No bytes received before read timeout"
                )
            ]
        records: list[Record] = []
        byte: int
        for byte in chunk:
            if self.discarding:
                self.discarding = byte != LINE_FEED
            elif byte == LINE_FEED:
                records.append(self.decode(bytes(self.pending), at))
                self.pending.clear()
            elif len(self.pending) == MAX_LINE_BYTES:
                records.append(
                    self.diagnostic(
                        "line_too_long", at, "Discarding frame through next newline"
                    )
                )
                self.pending.clear()
                self.discarding = True
            else:
                self.pending.append(byte)
        return records


def write_record(output: TextIO, record: Record) -> None:
    """Append and flush one strict JSONL record.

    :param output: Open text stream owned by the caller.
    :param record: Acquisition observation or diagnostic.
    :return: None.
    """
    output.write(json.dumps(record, allow_nan=False) + "\n")
    output.flush()


def capture_connection(
    connection: serial.Serial, session: CaptureSession, output: TextIO
) -> None:
    """Read one serial connection until it fails or the operator interrupts.

    :param connection: Open pyserial device configured with a finite timeout.
    :param session: State scoped to this connection only.
    :param output: JSONL destination; output errors propagate to the caller.
    :return: None after a transport failure has been recorded.
    """
    import serial

    write_record(output, session.diagnostic("connected", datetime.now(timezone.utc)))
    while True:
        chunk: bytes
        try:
            chunk = connection.read_until(b"\n", size=MAX_LINE_BYTES + 1)
        except (serial.SerialException, OSError) as error:
            write_record(
                output,
                session.diagnostic(
                    "disconnected", datetime.now(timezone.utc), str(error)
                ),
            )
            return
        record: Record
        for record in session.feed(chunk, datetime.now(timezone.utc)):
            write_record(output, record)


def capture_forever(config: SerialCaptureConfig, output: TextIO) -> None:
    """Reconnect only the configured device and reset acquisition identity.

    :param config: Explicit device, workstation, and timing configuration.
    :param output: JSONL destination; failed writes stop capture visibly.
    :return: None after a keyboard interruption.
    """
    import serial

    session: CaptureSession = CaptureSession(config)
    try:
        while True:
            session = CaptureSession(config)
            connection: serial.Serial
            try:
                connection = serial.Serial(
                    config.port, NANO_BAUD_RATE, timeout=config.read_timeout_seconds
                )
            except (serial.SerialException, OSError) as error:
                write_record(
                    output,
                    session.diagnostic(
                        "connection_failed", datetime.now(timezone.utc), str(error)
                    ),
                )
                time.sleep(config.reconnect_seconds)
                continue
            try:
                capture_connection(connection, session, output)
            finally:
                try:
                    connection.close()
                except (serial.SerialException, OSError) as error:
                    write_record(
                        output,
                        session.diagnostic(
                            "close_failed", datetime.now(timezone.utc), str(error)
                        ),
                    )
            time.sleep(config.reconnect_seconds)
    except KeyboardInterrupt:
        write_record(
            output,
            session.diagnostic(
                "stopped", datetime.now(timezone.utc), "Operator interrupted capture"
            ),
        )


def run_capture(config: SerialCaptureConfig) -> None:
    """Run acquisition to stdout or append an existing JSONL file.

    :param config: Serial capture configuration instantiated by the entry point.
    :return: None after capture stops.
    """
    if config.output_path is not None:
        config.output_path.parent.mkdir(parents=True, exist_ok=True)
    output_context: TextIO | nullcontext[TextIO] = (
        config.output_path.open("a", encoding="utf-8")
        if config.output_path is not None
        else nullcontext(sys.stdout)
    )
    output: TextIO
    with output_context as output:
        capture_forever(config, output)
