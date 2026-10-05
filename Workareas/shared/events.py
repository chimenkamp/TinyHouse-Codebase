"""Durable evidence, idempotent process events, and an acknowledged outbox."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from Workareas.shared.configuration import (
    MAX_CLOCK_OFFSET_SECONDS,
    MIN_MESSAGE_AVAILABILITY,
    MIN_VALIDATION_F1,
    Commissioning,
    StationConfig,
)
from Workareas.shared.models import (
    Evidence,
    JsonObject,
    JsonValue,
    ValidationError,
    identifier,
    mapping,
    parse_evidence,
)
from Workareas.shared.rules import RULES, validate_rule

SCHEMA: str = """
CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, digest TEXT NOT NULL, event TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, signature TEXT NOT NULL, event TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence (
 id TEXT PRIMARY KEY, source TEXT NOT NULL, session TEXT NOT NULL, sequence INTEGER NOT NULL,
 context TEXT NOT NULL, data TEXT NOT NULL, ingested_at TEXT NOT NULL,
 UNIQUE(source,session,sequence));
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, topic TEXT NOT NULL, data TEXT NOT NULL, delivered_at TEXT);
CREATE TABLE IF NOT EXISTS rejected (
 id INTEGER PRIMARY KEY, received_at TEXT NOT NULL, reason TEXT NOT NULL, data TEXT NOT NULL);
"""
OUTBOX_BATCH_SIZE: int = 100
OUTCOME_FIELDS: frozenset[str] = frozenset(
    {
        "decision",
        "state",
        "result",
        "selection",
        "energy_kwh",
        "weight_g",
        "delta_g",
        "purpose",
        "allowed",
    }
)


def encode(value: JsonValue) -> str:
    """
    Serialize deterministically and reject JSON's nonstandard NaN extension.

    :param value: JSON-compatible value.
    :return: Canonical JSON text.
    """
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as error:
        raise ValidationError("input must contain only finite JSON values") from error


def event_source_time(event: JsonObject) -> datetime:
    """
    Compare event occurrence instants independently of timezone formatting.

    :param event: Persisted, validated activity event.
    :return: Timezone-aware occurrence time.
    """
    return datetime.fromisoformat(str(event["source_time"]))


def validate_config(config: StationConfig) -> None:
    """
    Enforce the concept's measured authority gates before accepting evidence.

    :param config: Explicit station configuration.
    :return: None.
    """
    if config.station not in RULES:
        raise ValidationError("station must be WA1, WA2, WA3, or WA4")
    if not math.isfinite(config.max_age_seconds) or config.max_age_seconds <= 0:
        raise ValidationError("max_age_seconds must be finite and positive")
    if not 0 <= config.max_clock_offset_seconds <= MAX_CLOCK_OFFSET_SECONDS:
        raise ValidationError("clock allowance cannot exceed the concept's 250 ms")
    if not 0 <= config.minimum_confidence <= 1:
        raise ValidationError("minimum_confidence must be within 0..1")
    if config.commissioning is None:
        return
    approval: Commissioning = config.commissioning
    if (
        not approval.report.is_file()
        or not approval.approved_by.strip()
        or not MIN_VALIDATION_F1 <= approval.macro_f1 <= 1
        or not MIN_MESSAGE_AVAILABILITY <= approval.message_availability <= 1
        or not 0 <= approval.clock_offset_seconds <= MAX_CLOCK_OFFSET_SECONDS
        or approval.mandatory_lifecycle_coverage != 1
        or approval.false_completions != 0
        or not approval.safety_approved
        or not approval.privacy_approved
    ):
        raise ValidationError(
            "authoritative mode requires a real report and every commissioning gate"
        )


class EventService:
    """One serially accessed SQLite station store and deterministic rule boundary."""

    config: StationConfig
    database: sqlite3.Connection

    def __init__(self, config: StationConfig) -> None:
        """
        Open the durable local station store.

        :param config: Station and authority settings.
        :return: None.
        """
        validate_config(config)
        self.config = config
        config.database.parent.mkdir(parents=True, exist_ok=True)
        self.database = sqlite3.connect(config.database)
        self.database.executescript(SCHEMA)

    def close(self) -> None:
        """
        Release the SQLite connection.

        :return: None.
        """
        self.database.close()

    def submit(self, request: JsonObject, now: datetime | None = None) -> JsonObject:
        """
        Persist either a validated event transaction or an explicit rejection.

        :param request: Correlated evidence bundle from local trusted adapters.
        :param now: Edge clock, injectable only for deterministic tests.
        :return: Existing or newly committed event.
        """
        received: datetime = now if now is not None else datetime.now(timezone.utc)
        if received.tzinfo is None:
            raise ValidationError("ingestion time must have a timezone")
        body: str = encode(request)
        try:
            return self._submit(request, body, received)
        except ValidationError as error:
            self._reject(request, body, received, str(error))
            raise

    def _reject(
        self, request: JsonObject, body: str, received: datetime, reason: str
    ) -> None:
        """
        Preserve disagreement references and publish uncertainty, never completion.

        :param request: Invalid or conflicting correlated evidence.
        :param body: Original canonical payload.
        :param received: Edge receipt time.
        :param reason: Explicit failed condition.
        :return: None.
        """
        raw: JsonValue = request.get("evidence")
        ids: list[JsonValue] = (
            [item.get("id") for item in raw if isinstance(item, dict)]
            if isinstance(raw, list)
            else []
        )
        conflict: bool = "expected " in reason or "conflict" in reason
        activity: str = (
            "Print evidence conflict"
            if request.get("activity") == "Print base" and conflict
            else "Evidence unknown"
        )
        diagnostic: JsonObject = {
            "schema_version": "1.0",
            "event_id": str(uuid4()),
            "station": self.config.station,
            "activity": activity,
            "attempted_activity": request.get("activity"),
            "transition": "unknown",
            "authority": "diagnostic",
            "ingestion_time": received.isoformat(),
            "run_id": request.get("run_id"),
            "work_order_id": request.get("work_order_id"),
            "operation_id": request.get("operation_id"),
            "evidence_ids": ids,
            "reason": reason,
        }
        with self.database:
            self.database.execute(
                "INSERT INTO rejected(received_at,reason,data) VALUES(?,?,?)",
                (received.isoformat(), reason, body),
            )
            self.database.execute(
                "INSERT INTO events(id,topic,data) VALUES(?,?,?)",
                (
                    diagnostic["event_id"],
                    f"tinyhouse/bayreuth/diagnostic/{self.config.station}",
                    encode(diagnostic),
                ),
            )

    def _submit(self, request: JsonObject, body: str, now: datetime) -> JsonObject:
        """
        Atomically validate context, fuse records, and commit the outbox event.

        :param request: Decoded submission.
        :param body: Canonical request for idempotency comparison.
        :param now: Edge ingestion time.
        :return: Committed event.
        """
        request_id: str = identifier(request.get("request_id"), "request_id")
        digest: str = hashlib.sha256(body.encode()).hexdigest()
        previous: tuple[str, str] | None = self.database.execute(
            "SELECT digest,event FROM requests WHERE id=?", (request_id,)
        ).fetchone()
        if previous is not None:
            if previous[0] != digest:
                raise ValidationError(
                    "request_id was already used for different content"
                )
            return mapping(json.loads(previous[1]), "stored event")
        objects: dict[str, str] = self._objects(request)
        activity: str = identifier(request.get("activity"), "activity")
        transition: str = identifier(request.get("transition"), "transition")
        operation_key: str = encode(
            {
                key: request[key]
                for key in (
                    "run_id",
                    "work_order_id",
                    "operation_id",
                    "activity",
                    "transition",
                )
            }
        )
        signature: str = encode(
            {key: value for key, value in request.items() if key != "request_id"}
        )
        operation: tuple[str, str] | None = self.database.execute(
            "SELECT signature,event FROM operations WHERE id=?", (operation_key,)
        ).fetchone()
        if operation is not None:
            if operation[0] != signature:
                raise ValidationError(
                    "operation lifecycle already recorded; changed evidence requires a new operation"
                )
            with self.database:
                self.database.execute(
                    "INSERT INTO requests VALUES(?,?,?)",
                    (request_id, digest, operation[1]),
                )
            return mapping(json.loads(operation[1]), "stored event")
        records: dict[str, Evidence] = self._evidence(request, now)
        validate_rule(self.config.station, activity, transition, objects, records)
        with self.database:
            self._store_evidence(request, records, now)
            self._check_approval(request, activity, objects, records)
            event: JsonObject = self._make_event(
                request, activity, transition, objects, records, now
            )
            data: str = encode(event)
            topic: str = self._topic(activity)
            self.database.execute(
                "INSERT INTO events(id,topic,data) VALUES(?,?,?)",
                (event["event_id"], topic, data),
            )
            self.database.execute(
                "INSERT INTO requests VALUES(?,?,?)", (request_id, digest, data)
            )
            self.database.execute(
                "INSERT INTO operations VALUES(?,?,?)", (operation_key, signature, data)
            )
        return event

    def _objects(self, request: JsonObject) -> dict[str, str]:
        """
        Bind every event to its experiment, work order, operation and objects.

        :param request: Submission envelope.
        :return: Validated typed identifier mapping.
        """
        objects: dict[str, str] = {
            key: identifier(value, "objects." + key)
            for key, value in mapping(request.get("objects"), "objects").items()
        }
        for key in ("run_id", "work_order_id", "operation_id"):
            identifier(request.get(key), key)
        return objects

    def _evidence(self, request: JsonObject, now: datetime) -> dict[str, Evidence]:
        """
        Bind source roles to commissioned adapter identities and validate quality.

        :param request: Submission envelope.
        :param now: Ingestion timestamp.
        :return: One valid record per kind.
        """
        raw: JsonValue = request.get("evidence")
        if not isinstance(raw, list) or not raw:
            raise ValidationError("evidence must be a nonempty list")
        records: dict[str, Evidence] = {}
        for item in raw:
            record: Evidence = parse_evidence(
                mapping(item, "evidence item"),
                now,
                self.config.max_age_seconds,
                self.config.max_clock_offset_seconds,
            )
            if self.config.sources.get(record.kind) != record.source_id:
                raise ValidationError(
                    f"unassigned source for {record.kind}: {record.source_id}"
                )
            if record.kind in records:
                raise ValidationError(
                    f"duplicate/conflicting evidence kind: {record.kind}"
                )
            if record.confidence < self.config.minimum_confidence:
                raise ValidationError(f"insufficient confidence for {record.kind}")
            records[record.kind] = record
        return records

    def _store_evidence(
        self, request: JsonObject, records: dict[str, Evidence], now: datetime
    ) -> None:
        """
        Reject evidence reuse across runs and source replay within a boot session.

        :param request: Correlation envelope.
        :param records: Parsed records.
        :param now: Ingestion time.
        :return: None.
        """
        context: str = encode(
            {key: request[key] for key in ("run_id", "work_order_id", "operation_id")}
        )
        for record in records.values():
            data: str = encode(record.raw)
            existing: tuple[str, str] | None = self.database.execute(
                "SELECT context,data FROM evidence WHERE id=?", (record.id,)
            ).fetchone()
            latest: tuple[int | None] = self.database.execute(
                "SELECT MAX(sequence) FROM evidence WHERE source=? AND session=?",
                (record.source_id, record.session_id),
            ).fetchone()
            if existing is not None:
                if existing != (context, data):
                    raise ValidationError(
                        "evidence ID reused with changed data or operation context"
                    )
                if latest[0] is not None and record.sequence < latest[0]:
                    raise ValidationError(
                        "evidence was superseded by a newer source record"
                    )
                continue
            if latest[0] is not None and record.sequence <= latest[0]:
                raise ValidationError("out-of-order or replayed source sequence")
            self.database.execute(
                "INSERT INTO evidence VALUES(?,?,?,?,?,?,?)",
                (
                    record.id,
                    record.source_id,
                    record.session_id,
                    record.sequence,
                    context,
                    data,
                    now.isoformat(),
                ),
            )

    def _check_approval(
        self,
        request: JsonObject,
        activity: str,
        objects: dict[str, str],
        records: dict[str, Evidence],
    ) -> None:
        """
        Prevent an old passing test from approving a subsequently reworked product.

        :param request: Current run and order context.
        :param activity: Requested activity.
        :param objects: Product/test links.
        :param records: Actual records submitted for approval.
        :return: None.
        """
        if activity != "Approve deployment":
            return
        history: list[JsonObject] = self._product_history(request, objects["product"])
        passes: list[JsonObject] = [
            event
            for event in history
            if event["activity"] == "Test and calibrate"
            and event["transition"] == "complete"
        ]
        if not passes:
            raise ValidationError(
                "record Test and calibrate completion in this run/order before approval"
            )
        passed: JsonObject = max(passes, key=event_source_time)
        links: JsonObject = mapping(passed["objects"], "stored objects")
        if (
            links.get("test") != objects["test"]
            or links.get("calibration") != objects["calibration"]
        ):
            raise ValidationError(
                "approval must reference the latest passing test and calibration"
            )
        barriers: list[datetime] = [
            datetime.fromisoformat(str(event["source_time"]))
            for event in history
            if event["activity"] != "Test and calibrate"
            or event["transition"] == "failed"
        ]
        self._compare_test_records(passed, records, max(barriers) if barriers else None)

    def _product_history(self, request: JsonObject, product: str) -> list[JsonObject]:
        """
        Select actual test/rework history only within the current run and order.

        :param request: Current correlation envelope.
        :param product: Product identity.
        :return: Relevant local lifecycle events with occurrence times.
        """
        history: list[JsonObject] = []
        rows: list[tuple[str]] = self.database.execute(
            "SELECT data FROM events ORDER BY rowid DESC"
        ).fetchall()
        authority: str = "authoritative" if self.config.commissioning else "candidate"
        for row in rows:
            event: JsonObject = mapping(json.loads(row[0]), "stored event")
            if (
                event.get("authority") != authority
                or event.get("run_id") != request["run_id"]
                or event.get("work_order_id") != request["work_order_id"]
                or event.get("activity")
                not in ("Rework sensor", "Resolve failure", "Test and calibrate")
            ):
                continue
            if mapping(event["objects"], "stored objects").get("product") == product:
                history.append(event)
        return history

    def _compare_test_records(
        self, passed: JsonObject, records: dict[str, Evidence], barrier: datetime | None
    ) -> None:
        """
        Bind approval to immutable procedure records newer than any failed work.

        :param passed: Recorded successful test event.
        :param records: Proposed approval evidence.
        :param barrier: Most recent failure/rework occurrence time.
        :return: None.
        """
        ids: JsonValue = passed["evidence_ids"]
        assert isinstance(ids, list)
        for evidence_id in ids:
            row: tuple[str] = self.database.execute(
                "SELECT data FROM evidence WHERE id=?", (evidence_id,)
            ).fetchone()
            original: JsonObject = mapping(json.loads(row[0]), "stored evidence")
            kind: str = str(original["kind"])
            if kind not in ("test", "calibration"):
                continue
            source_time: datetime = datetime.fromisoformat(str(original["source_time"]))
            if barrier is not None and source_time <= barrier:
                raise ValidationError(
                    "approval needs a new passing test after failure/rework"
                )
            if records[kind].values != original["values"]:
                raise ValidationError(
                    "approval changed the immutable passing procedure record"
                )
            if records["operator"].source_time < source_time:
                raise ValidationError(
                    "approval occurred before the passing test/calibration"
                )

    def _make_event(
        self,
        request: JsonObject,
        activity: str,
        transition: str,
        objects: dict[str, str],
        records: dict[str, Evidence],
        now: datetime,
    ) -> JsonObject:
        """
        Create the local L2 event without embedding raw measurements or identities.

        :param request: Submission context.
        :param activity: Exact card label.
        :param transition: Lifecycle label.
        :param objects: Typed object links.
        :param records: Validated evidence references.
        :param now: Edge ingestion time.
        :return: JSON event envelope.
        """
        event: JsonObject = {
            "schema_version": "1.0",
            "event_id": str(uuid4()),
            "activity": activity,
            "transition": transition,
            "station": self.config.station,
            "authority": "authoritative" if self.config.commissioning else "candidate",
            "policy_version": self.config.policy_version,
            "objects": dict(objects),
            "source_time": max(
                record.source_time for record in records.values()
            ).isoformat(),
            "ingestion_time": now.isoformat(),
            "confidence": min(record.confidence for record in records.values()),
            "freshness_seconds": max(
                0.0,
                max(
                    (now - record.source_time).total_seconds()
                    for record in records.values()
                ),
            ),
            "health": "ok",
            "quality": "valid",
            "evidence_ids": [record.id for record in records.values()],
            "source_ids": [record.source_id for record in records.values()],
            "outcome": {
                f"{record.kind}.{key}": value
                for record in records.values()
                for key, value in record.values.items()
                if key in OUTCOME_FIELDS
            },
        }
        for key in ("run_id", "work_order_id", "operation_id"):
            event[key] = request[key]
        return event

    def _topic(self, activity: str) -> str:
        """
        Isolate unvalidated candidates from the concept's authoritative topic.

        :param activity: Card label.
        :return: Local MQTT topic.
        """
        category: str = "activity" if self.config.commissioning else "candidate"
        slug: str = activity.lower().replace(" ", "-")
        return f"tinyhouse/bayreuth/{category}/{self.config.station}/{slug}"

    def pending(self) -> list[tuple[str, JsonObject]]:
        """
        Read an ordered bounded outbox batch without consuming it.

        :return: Topic and event pairs awaiting broker acknowledgment.
        """
        rows: list[tuple[str, str]] = self.database.execute(
            "SELECT topic,data FROM events WHERE delivered_at IS NULL ORDER BY rowid LIMIT ?",
            (OUTBOX_BATCH_SIZE,),
        ).fetchall()
        return [
            (topic, mapping(json.loads(data), "stored event")) for topic, data in rows
        ]

    def acknowledge(self, event_id: str) -> None:
        """
        Mark delivery only after a real broker PUBACK; retain the audit event.

        :param event_id: Acknowledged event ID.
        :return: None.
        """
        with self.database:
            self.database.execute(
                "UPDATE events SET delivered_at=? WHERE id=? AND delivered_at IS NULL",
                (datetime.now(timezone.utc).isoformat(), event_id),
            )

    def get_event(self, event_id: str) -> str:
        """
        Retrieve a durable local event independently of delivery status.

        :param event_id: Event UUID.
        :return: Serialized event.
        """
        row: tuple[str] | None = self.database.execute(
            "SELECT data FROM events WHERE id=?", (event_id,)
        ).fetchone()
        if row is None:
            raise KeyError(event_id)
        return row[0]
