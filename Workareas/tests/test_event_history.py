"""Regression checks for durable authority, causal history and operation replay."""

from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from Workareas.shared.configuration import StationConfig
from Workareas.shared.events import EventService
from Workareas.shared.models import (
    Evidence,
    JsonObject,
    JsonValue,
    ValidationError,
    mapping,
)
from Workareas.shared.rules import RULES
from Workareas.tests.test_rules import NOW, readings, scenario

SECOND: timedelta = timedelta(seconds=1)


def history_request(
    activity: str,
    sequence: int,
    *,
    station: str = "WA3",
    run_id: str = "run-1",
    work_order_id: str = "order-1",
    source_time: datetime = NOW,
) -> JsonObject:
    """Wrap synthetic rule fixtures in the real event-ingress contract.

    :param activity: Exact card activity under test.
    :param sequence: Monotonic source sequence and unique fixture ID suffix.
    :param station: Station owning the activity.
    :param run_id: Experiment-run correlation.
    :param work_order_id: Work-order correlation.
    :param source_time: Realistic source occurrence time for this synthetic record.
    :return: Complete synthetic ingress request, never production data.
    """
    objects: dict[str, str]
    records: dict[str, Evidence]
    objects, records = scenario(station, activity)
    observations: list[JsonValue] = []
    kind: str
    record: Evidence
    for kind, record in records.items():
        values: JsonObject = {key: value for key, value in record.values.items()}
        observations.append(
            {
                "id": f"{kind}-{sequence}",
                "kind": kind,
                "source_id": kind + "-source",
                "session_id": "test-session",
                "sequence": sequence,
                "source_time": source_time.isoformat(),
                "confidence": 1.0,
                "health": "ok",
                "quality": "valid",
                "values": values,
            }
        )
    return {
        "request_id": f"request-{sequence}",
        "activity": activity,
        "transition": "complete",
        "run_id": run_id,
        "work_order_id": work_order_id,
        "operation_id": f"operation-{sequence}",
        "objects": {key: objects[key] for key in RULES[station][activity].objects},
        "evidence": observations,
    }


def observation(request: JsonObject, kind: str) -> JsonObject:
    """Find one mutable synthetic source record in an ingress bundle.

    :param request: Synthetic ingress request.
    :param kind: Evidence kind to select.
    :return: Matching source record.
    """
    item: JsonValue
    for item in cast(list[JsonValue], request["evidence"]):
        record: JsonObject = mapping(item, "test observation")
        if record["kind"] == kind:
            return record
    raise AssertionError(f"missing synthetic role {kind}")


def bind_attempt(request: JsonObject, attempt: str) -> None:
    """Bind synthetic test/calibration records to one new actual attempt.

    :param request: Test or approval request to update.
    :param attempt: Distinct attempt suffix.
    :return: None.
    """
    kind: str
    for kind in ("test", "calibration"):
        identity: str = kind + "-" + attempt
        mapping(request["objects"], "objects")[kind] = identity
        values: JsonObject = mapping(observation(request, kind)["values"], "values")
        values[kind + "_id"] = identity
        values["record_uri"] = "local:" + identity


class EventHistoryTests(unittest.TestCase):
    """Require the latest applicable passing test and one event per operation."""

    directory: tempfile.TemporaryDirectory[str]
    service: EventService

    def setUp(self) -> None:
        """Create an isolated candidate station with explicitly assigned sources.

        :return: None.
        """
        self.directory = tempfile.TemporaryDirectory()
        self.service = EventService(self.station_config("WA3"))

    def tearDown(self) -> None:
        """Close the isolated event store and remove test data.

        :return: None.
        """
        self.service.close()
        self.directory.cleanup()

    def station_config(self, station: str) -> StationConfig:
        """Assign only synthetic source identities for a requested station.

        :param station: Station identifier.
        :return: Temporary candidate-mode station configuration.
        """
        return StationConfig(
            station=station,
            database=Path(self.directory.name) / f"{station}.sqlite3",
            sources={kind: kind + "-source" for kind in readings("")},
        )

    def test_passing_test_and_same_context_approval_succeed(self) -> None:
        """Establish the valid path before testing history restrictions.

        :return: None.
        """
        self.service.submit(history_request("Test and calibrate", 1), NOW)
        result: JsonObject = self.service.submit(
            history_request("Approve deployment", 2), NOW
        )
        self.assertEqual(result["activity"], "Approve deployment")

    def test_approval_cannot_borrow_another_run_passing_test(self) -> None:
        """Keep identical product/test labels from importing another run's pass.

        :return: None.
        """
        self.service.submit(
            history_request("Test and calibrate", 1, run_id="run-other"), NOW
        )
        with self.assertRaises(ValidationError):
            self.service.submit(history_request("Approve deployment", 2), NOW)

    def test_approval_cannot_borrow_another_order_passing_test(self) -> None:
        """Require the passing record to belong to the current work order.

        :return: None.
        """
        self.service.submit(
            history_request("Test and calibrate", 1, work_order_id="order-other"), NOW
        )
        with self.assertRaises(ValidationError):
            self.service.submit(history_request("Approve deployment", 2), NOW)

    def test_rework_invalidates_prior_passing_test(self) -> None:
        """Never approve after rework using only the earlier passing values.

        :return: None.
        """
        self.service.submit(history_request("Test and calibrate", 1), NOW)
        self.service.submit(
            history_request("Rework sensor", 2, source_time=NOW + SECOND), NOW + SECOND
        )
        with self.assertRaises(ValidationError):
            self.service.submit(
                history_request("Approve deployment", 3, source_time=NOW + 2 * SECOND),
                NOW + 2 * SECOND,
            )

    def test_later_failed_attempt_invalidates_prior_pass(self) -> None:
        """Require the latest attempt instead of searching backward for any pass.

        :return: None.
        """
        self.service.submit(history_request("Test and calibrate", 1), NOW)
        failed: JsonObject = history_request(
            "Test and calibrate", 2, source_time=NOW + SECOND
        )
        bind_attempt(failed, "failed-attempt")
        failed["transition"] = "failed"
        mapping(observation(failed, "test")["values"], "values")["result"] = "failed"
        mapping(observation(failed, "calibration")["values"], "values")["result"] = (
            "not_run"
        )
        self.service.submit(failed, NOW + SECOND)
        with self.assertRaises(ValidationError):
            self.service.submit(
                history_request("Approve deployment", 3, source_time=NOW + 2 * SECOND),
                NOW + 2 * SECOND,
            )

    def test_new_passing_attempt_after_rework_allows_approval(self) -> None:
        """Retest and explicitly approve the same latest valid attempt.

        :return: None.
        """
        self.service.submit(history_request("Test and calibrate", 1), NOW)
        self.service.submit(
            history_request("Rework sensor", 2, source_time=NOW + SECOND), NOW + SECOND
        )
        retest: JsonObject = history_request(
            "Test and calibrate", 3, source_time=NOW + 2 * SECOND
        )
        bind_attempt(retest, "retest")
        self.service.submit(retest, NOW + 2 * SECOND)
        approval: JsonObject = history_request(
            "Approve deployment", 4, source_time=NOW + 3 * SECOND
        )
        bind_attempt(approval, "retest")
        result: JsonObject = self.service.submit(approval, NOW + 3 * SECOND)
        self.assertEqual(mapping(result["objects"], "objects")["test"], "test-retest")

    def test_late_pre_rework_pass_does_not_restore_approval(self) -> None:
        """Retain occurrence ordering when old passing evidence arrives late.

        :return: None.
        """
        self.service.submit(
            history_request("Rework sensor", 1, source_time=NOW + SECOND), NOW + SECOND
        )
        late: JsonObject = history_request("Test and calibrate", 2, source_time=NOW)
        try:
            self.service.submit(late, NOW + 2 * SECOND)
        except ValidationError:
            return
        with self.assertRaises(ValidationError):
            self.service.submit(
                history_request("Approve deployment", 3, source_time=NOW + 3 * SECOND),
                NOW + 3 * SECOND,
            )

    def test_approval_cannot_replace_procedure_under_existing_test_ids(self) -> None:
        """Bind approval to the passing procedure records, not just their labels.

        :return: None.
        """
        self.service.submit(history_request("Test and calibrate", 1), NOW)
        request: JsonObject = history_request("Approve deployment", 2)
        kind: str
        for kind in ("test", "calibration"):
            mapping(observation(request, kind)["values"], "values")[
                "procedure_version"
            ] = "different-procedure"
        with self.assertRaises(ValidationError):
            self.service.submit(request, NOW)

    def test_approval_cannot_replace_calibration_reference(self) -> None:
        """Preserve the reference that justified the recorded calibration pass.

        :return: None.
        """
        self.service.submit(history_request("Test and calibrate", 1), NOW)
        request: JsonObject = history_request("Approve deployment", 2)
        mapping(observation(request, "calibration")["values"], "values")[
            "reference_id"
        ] = "unrelated-reference"
        with self.assertRaises(ValidationError):
            self.service.submit(request, NOW)

    def test_changed_request_id_cannot_emit_duplicate_operation_event(self) -> None:
        """Preserve event uniqueness when a producer retries with a new request ID.

        :return: None.
        """
        request: JsonObject = history_request("Test and calibrate", 1)
        self.service.submit(request, NOW)
        retry: JsonObject = copy.deepcopy(request)
        retry["request_id"] = "different-request-id"
        try:
            self.service.submit(retry, NOW)
        except ValidationError:
            pass
        completions: list[JsonObject] = [
            event
            for _, event in self.service.pending()
            if event.get("activity") == "Test and calibrate"
            and event.get("transition") == "complete"
        ]
        self.assertEqual(len(completions), 1)

    def test_new_samples_do_not_repeat_same_operation_completion(self) -> None:
        """Avoid a second completion from later samples of the same finished job.

        :return: None.
        """
        self.service.submit(history_request("Test and calibrate", 1), NOW)
        repeat: JsonObject = history_request("Test and calibrate", 2)
        repeat["operation_id"] = "operation-1"
        try:
            self.service.submit(repeat, NOW)
        except ValidationError:
            pass
        completions: list[JsonObject] = [
            event
            for _, event in self.service.pending()
            if event.get("activity") == "Test and calibrate"
            and event.get("transition") == "complete"
        ]
        self.assertEqual(len(completions), 1)

    def test_reused_evidence_cannot_change_run_context(self) -> None:
        """Keep durable evidence ownership immutable across runs.

        :return: None.
        """
        request: JsonObject = history_request("Test and calibrate", 1)
        self.service.submit(request, NOW)
        other: JsonObject = copy.deepcopy(request)
        other.update({"request_id": "other-request", "run_id": "other-run"})
        with self.assertRaises(ValidationError):
            self.service.submit(other, NOW)

    def test_extra_schedule_evidence_cannot_bypass_energy_validation(self) -> None:
        """Dispatch by requested activity even when an unrelated record is present.

        :return: None.
        """
        self.service.close()
        self.service = EventService(self.station_config("WA4"))
        request: JsonObject = history_request(
            "Read solar and battery", 1, station="WA4"
        )
        mapping(observation(request, "energy")["values"], "values")["solar_kw"] = -1.0
        schedule: JsonObject = history_request(
            "Optimize energy-aware schedule", 2, station="WA4"
        )
        mapping(request["objects"], "objects")["energy_schedule"] = "energy_schedule-1"
        cast(list[JsonValue], request["evidence"]).append(
            observation(schedule, "schedule")
        )
        with self.assertRaises(ValidationError):
            self.service.submit(request, NOW)

    def test_unrelated_role_is_rejected_before_activity_specific_access(self) -> None:
        """Reject unrelated input as unknown instead of an unhandled field error.

        :return: None.
        """
        self.service.close()
        self.service = EventService(self.station_config("WA4"))
        request: JsonObject = history_request("Register run", 1, station="WA4")
        topology: JsonObject = history_request("Select topology", 2, station="WA4")
        cast(list[JsonValue], request["evidence"]).append(observation(topology, "topology"))
        with self.assertRaises(ValidationError):
            self.service.submit(request, NOW)


if __name__ == "__main__":
    unittest.main()
