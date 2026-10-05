"""Behavioral checks for the card-derived process-event boundary."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

from Workareas.shared.configuration import Commissioning, StationConfig
from Workareas.shared.events import EventService, validate_config
from Workareas.shared.models import JsonObject, JsonValue, ValidationError, mapping

NOW: datetime = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)


def print_request() -> JsonObject:
    """
    Construct explicitly synthetic test evidence, never deployment data.

    :return: A complete print observation for isolated software tests.
    """
    values: dict[str, JsonObject] = {
        "printer": {"job_id": "job-1", "state": "completed"},
        "meter": {"job_id": "job-1", "energy_kwh": 0.3},
        "thermal": {"job_id": "job-1", "episode": "cooling"},
        "camera": {"component_id": "base-1", "present": True},
    }
    evidence: list[JsonObject] = [
        {
            "id": kind + "-1",
            "kind": kind,
            "source_id": kind,
            "source_time": NOW.isoformat(),
            "sequence": 1,
            "session_id": "boot-1",
            "health": "ok",
            "quality": "valid",
            "confidence": 1.0,
            "values": reading,
        }
        for kind, reading in values.items()
    ]
    return {
        "request_id": "request-1",
        "activity": "Print base",
        "transition": "complete",
        "run_id": "run-1",
        "work_order_id": "order-1",
        "operation_id": "job-1",
        "objects": {
            "print_job": "job-1",
            "component": "base-1",
            "authorization": "permit-1",
            "energy_schedule": "schedule-1",
            "design_revision": "rev-1",
        },
        "evidence": cast(list[JsonValue], evidence),
    }


class EventTests(unittest.TestCase):
    """Require actual corroboration, persistence, and fail-closed validation."""

    directory: tempfile.TemporaryDirectory[str]
    service: EventService

    def setUp(self) -> None:
        """
        Create an isolated candidate-mode station store.

        :return: None.
        """
        self.directory = tempfile.TemporaryDirectory()
        config: StationConfig = StationConfig(
            station="WA1",
            database=Path(self.directory.name) / "events.sqlite3",
            sources={kind: kind for kind in ("printer", "meter", "thermal", "camera")},
        )
        self.service = EventService(config)

    def tearDown(self) -> None:
        """
        Close files before deleting the temporary station.

        :return: None.
        """
        self.service.close()
        self.directory.cleanup()

    def test_complete_print_is_durable_candidate_until_commissioned(self) -> None:
        """
        Preserve event identity and evidence through retries and restart.

        :return: None.
        """
        event: JsonObject = self.service.submit(print_request(), NOW)
        self.assertEqual(event["authority"], "candidate")
        self.assertEqual(event["activity"], "Print base")
        self.assertEqual(len(cast(list[JsonValue], event["evidence_ids"])), 4)
        self.assertEqual(
            event, self.service.submit(print_request(), NOW + timedelta(seconds=1))
        )
        self.assertEqual(len(self.service.pending()), 1)
        config: StationConfig = self.service.config
        self.service.close()
        self.service = EventService(config)
        self.assertEqual(event, self.service.submit(print_request(), NOW))
        self.assertEqual(self.service.pending()[0][1]["event_id"], event["event_id"])

    def test_missing_disconnected_stale_and_wrong_job_never_complete(self) -> None:
        """
        Reject invalid supporting evidence rather than infer completion.

        :return: None.
        """
        for defect in (
            "missing",
            "disconnected",
            "stale",
            "wrong_job",
            "future",
            "nan",
        ):
            request: JsonObject = print_request()
            evidence: list[JsonObject] = cast(list[JsonObject], request["evidence"])
            if defect == "missing":
                evidence.pop()
            elif defect == "disconnected":
                evidence[0]["health"] = "offline"
            elif defect == "stale":
                evidence[0]["source_time"] = (NOW - timedelta(hours=1)).isoformat()
            elif defect == "wrong_job":
                mapping(evidence[0]["values"], "values")["job_id"] = "different-job"
            elif defect == "future":
                evidence[0]["source_time"] = (NOW + timedelta(seconds=1)).isoformat()
            else:
                mapping(evidence[1]["values"], "values")["energy_kwh"] = float("nan")
            with self.subTest(defect=defect), self.assertRaises(ValidationError):
                self.service.submit(request, NOW)
        self.assertFalse(
            any(
                event.get("transition") == "complete"
                for _, event in self.service.pending()
            )
        )

    def test_conflict_has_durable_diagnostic_and_success_has_measurement(self) -> None:
        """
        Make disagreements observable without losing usable event outcomes.

        :return: None.
        """
        request: JsonObject = print_request()
        records: list[JsonObject] = cast(list[JsonObject], request["evidence"])
        mapping(records[0]["values"], "values")["state"] = "running"
        with self.assertRaises(ValidationError):
            self.service.submit(request, NOW)
        diagnostics: list[tuple[str, JsonObject]] = self.service.pending()
        self.assertEqual(diagnostics[0][1]["activity"], "Print evidence conflict")
        self.assertEqual(diagnostics[0][1]["authority"], "diagnostic")
        event: JsonObject = self.service.submit(print_request(), NOW)
        self.assertEqual(mapping(event["outcome"], "outcome")["meter.energy_kwh"], 0.3)

    def test_changed_retry_and_replayed_source_are_rejected(self) -> None:
        """
        Prevent idempotency keys and source sequences being repurposed.

        :return: None.
        """
        request: JsonObject = print_request()
        self.service.submit(request, NOW)
        changed: JsonObject = copy.deepcopy(request)
        mapping(changed["objects"], "objects")["component"] = "base-2"
        with self.assertRaises(ValidationError):
            self.service.submit(changed, NOW)
        changed = copy.deepcopy(request)
        changed["request_id"] = "request-2"
        cast(list[JsonObject], changed["evidence"])[0]["id"] = (
            "changed-id-same-sequence"
        )
        with self.assertRaises(ValidationError):
            self.service.submit(changed, NOW)

    def test_topic_and_delivery_ack(self) -> None:
        """
        Keep candidates away from authoritative topics and retain until ACK.

        :return: None.
        """
        event: JsonObject = self.service.submit(print_request(), NOW)
        topic: str = self.service.pending()[0][0]
        self.assertEqual(topic, "tinyhouse/bayreuth/candidate/WA1/print-base")
        self.service.acknowledge(str(event["event_id"]))
        self.assertEqual(self.service.pending(), [])
        self.assertEqual(
            json.loads(self.service.get_event(str(event["event_id"])))["activity"],
            "Print base",
        )

    def test_authority_requires_every_commissioning_gate(self) -> None:
        """
        Check exact acceptance boundaries without claiming empirical validation.

        :return: None.
        """
        report: Path = Path(self.directory.name) / "synthetic-test-report.txt"
        report.write_text("Synthetic configuration-test fixture, not field validation.")
        approval: Commissioning = Commissioning(
            report, "test-approver", 0.90, 0.99, 0.250, 1.0, 0, True, True
        )
        invalid: tuple[Commissioning, ...] = (
            replace(approval, report=report.with_name("missing")),
            replace(approval, approved_by=""),
            replace(approval, macro_f1=0.899),
            replace(approval, message_availability=0.989),
            replace(approval, clock_offset_seconds=0.251),
            replace(approval, mandatory_lifecycle_coverage=0.999),
            replace(approval, false_completions=1),
            replace(approval, safety_approved=False),
            replace(approval, privacy_approved=False),
        )
        for failed in invalid:
            with self.subTest(approval=failed), self.assertRaises(ValidationError):
                validate_config(replace(self.service.config, commissioning=failed))
        config: StationConfig = replace(self.service.config, commissioning=approval)
        self.service.close()
        self.service = EventService(config)
        event: JsonObject = self.service.submit(print_request(), NOW)
        self.assertEqual(event["authority"], "authoritative")
        self.assertEqual(
            self.service.pending()[0][0], "tinyhouse/bayreuth/activity/WA1/print-base"
        )


if __name__ == "__main__":
    unittest.main()
