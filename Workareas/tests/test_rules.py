"""Card coverage and negative evidence-fusion checks using synthetic records."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import TypeAlias

from Workareas.shared.models import Evidence, Scalar, ValidationError
from Workareas.shared.rules import RULES, validate_rule

NOW: datetime = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
EvidenceMap: TypeAlias = dict[str, Evidence]
Case: TypeAlias = tuple[str, str, tuple[str, ...], str]
HASH: str = "a" * 64
CASES: tuple[Case, ...] = (
    ("WA1", "Print base", ("printer", "meter", "thermal", "camera"), ""),
    ("WA1", "Inspect base", ("inspection", "operator"), "accepted"),
    ("WA1", "Review base", ("operator",), "reprint"),
    ("WA1", "Schedule reprint energy", ("schedule",), ""),
    ("WA1", "Release base", ("inspection", "operator"), "release"),
    ("WA2", "Robot kit", ("controller", "kit_plan", "bins", "camera", "safety"), ""),
    (
        "WA3",
        "Assemble node",
        ("identity", "assembly", "camera", "operator"),
        "assembled",
    ),
    ("WA3", "Test and calibrate", ("test", "calibration", "scale"), ""),
    ("WA3", "Resolve failure", ("operator",), "rework"),
    ("WA3", "Rework sensor", ("operator",), "reworked"),
    (
        "WA3",
        "Approve deployment",
        ("test", "calibration", "scale", "operator"),
        "approve",
    ),
    ("WA4", "Register run", ("registration", "operator"), "register"),
    ("WA4", "Select topology", ("topology",), ""),
    ("WA4", "Read solar and battery", ("energy",), ""),
    ("WA4", "Optimize energy-aware schedule", ("schedule",), ""),
    ("WA4", "Select standard container", ("schedule",), ""),
    ("WA4", "Select large container", ("schedule",), ""),
    ("WA4", "Request matching lid", ("request",), ""),
    ("WA4", "Evaluate decision", ("commitment",), ""),
    ("WA4", "Set local fallback", ("commitment", "topology"), ""),
    ("WA4", "Receive lid", ("scale", "identity", "camera"), ""),
    ("WA4", "Verify lid", ("identity", "inspection", "operator"), "accepted"),
    ("WA4", "Accept delivery", ("identity", "inspection", "operator"), "accept"),
    ("WA4", "Request replacement", ("inspection", "operator"), "replace"),
    ("WA4", "Apply disclosure", ("disclosure",), ""),
    ("WA4", "Share outcome", ("disclosure", "delivery"), ""),
)


def object_links() -> dict[str, str]:
    """
    Construct explicit synthetic identities for isolated rule checks.

    :return: Object identities with no connection to deployed equipment.
    """
    names: tuple[str, ...] = (
        "print_job",
        "component",
        "authorization",
        "energy_schedule",
        "design_revision",
        "inspection",
        "human_task",
        "energy_snapshot",
        "robot_job",
        "kit",
        "product",
        "base",
        "lid",
        "test",
        "calibration",
        "topology_decision",
        "commitment",
        "decision",
        "shipment",
        "disclosure_policy",
        "outcome",
    )
    return {name: name + "-1" for name in names}


def record(kind: str, values: dict[str, Scalar]) -> Evidence:
    """
    Create synthetic evidence for a validator, bypassing only transport parsing.

    :param kind: Independent evidence role.
    :param values: Synthetic observation values.
    :return: Evidence for software tests only.
    """
    return Evidence(
        kind + "-record",
        kind,
        kind + "-source",
        "test-session",
        1,
        NOW,
        1.0,
        values,
        {},
    )


def readings(decision: str) -> EvidenceMap:
    """
    Construct passing independent measurements for the card scenarios.

    :param decision: Explicit synthetic human decision.
    :return: Fresh test records to mutate within one test.
    """
    values: dict[str, dict[str, Scalar]] = {
        "printer": {"job_id": "print_job-1", "state": "completed"},
        "meter": {"job_id": "print_job-1", "energy_kwh": 0.3},
        "thermal": {"job_id": "print_job-1", "episode": "cooling"},
        "camera": {
            "component_id": "component-1",
            "kit_id": "kit-1",
            "product_id": "product-1",
            "lid_id": "lid-1",
            "present": True,
        },
        "operator": {
            "decision": decision,
            "actor": "operator-1",
            "record_id": "decision-record-1",
            "release_reason": "measured deviation accepted",
            "reason": "replace failed sensor",
            "record_uri": "local:rework-record",
        },
        "inspection": {
            "component_id": "component-1",
            "inspection_id": "inspection-1",
            "decision": "accepted",
            "procedure_version": "inspection-v1",
        },
        "schedule": {
            "schedule_id": "energy_schedule-1",
            "snapshot_id": "energy_snapshot-1",
            "policy_version": "energy-v1",
            "record_uri": "local:schedule",
            "selection": "standard",
            "purpose": "reprint",
            "job_id": "print_job-1",
        },
        "controller": {"job_id": "robot_job-1", "state": "success"},
        "safety": {"guard_closed": True, "estop_released": True},
        "kit_plan": {
            "kit_id": "kit-1",
            "plan_version": "kit-v1",
            "bin_count": 2,
            "bin1_part_id": "sensor",
            "bin1_expected_g": 12.0,
            "bin1_tolerance_g": 0.5,
            "bin2_part_id": "board",
            "bin2_expected_g": 20.0,
            "bin2_tolerance_g": 1.0,
        },
        "bins": {
            "job_id": "robot_job-1",
            "calibration_id": "bins-v1",
            "bin1_removed_g": 12.0,
            "bin2_removed_g": 20.0,
        },
        "identity": {
            "lid_id": "lid-1",
            "lid_revision": "design_revision-1",
            "expected_size": "standard",
            "lid_size": "standard",
            "base_id": "base-1",
            "kit_id": "kit-1",
            "base_size": "standard",
            "base_revision": "design_revision-1",
            "shipment_id": "shipment-1",
        },
        "assembly": {
            "product_id": "product-1",
            "first_transfer": True,
            "pattern_complete": True,
            "calibration_id": "mat-v1",
            "pattern_version": "assembly-v1",
        },
        "test": {
            "product_id": "product-1",
            "test_id": "test-1",
            "procedure_version": "test-v1",
            "record_uri": "local:test-1",
            "result": "passed",
        },
        "calibration": {
            "product_id": "product-1",
            "calibration_id": "calibration-1",
            "procedure_version": "test-v1",
            "record_uri": "local:calibration-1",
            "reference_id": "reference-1",
            "result": "passed",
        },
        "scale": {
            "product_id": "product-1",
            "lid_id": "lid-1",
            "stable": True,
            "tared": True,
            "calibration_id": "scale-v1",
            "weight_g": 180.0,
            "delta_g": 30.0,
        },
        "registration": {
            "design_revision": "design_revision-1",
            "due_start": "2026-09-29T12:00:00Z",
            "due_end": "2026-09-29T14:00:00Z",
            "policy_version": "registration-v1",
        },
        "topology": {
            "selection": "distributed",
            "decision_id": "topology_decision-1",
            "policy_version": "topology-v1",
            "requires_new_energy_schedule": True,
        },
        "energy": {
            "snapshot_id": "energy_snapshot-1",
            "solar_kw": 1.0,
            "usable_battery_kwh": 2.0,
            "forecast_solar_kwh": 0.2,
            "committed_print_kwh": 0.1,
            "battery_soc_percent": 80.0,
            "inverter_id": "inverter-1",
            "bms_id": "bms-1",
            "forecast_id": "forecast-1",
            "limits_version": "limits-v1",
        },
        "request": {
            "commitment_id": "commitment-1",
            "schedule_id": "energy_schedule-1",
            "design_revision": "design_revision-1",
            "size": "standard",
            "scheduled_size": "standard",
            "due_start": "2026-09-29T12:00:00Z",
            "due_end": "2026-09-29T14:00:00Z",
            "receipt_id": "request-receipt-1",
        },
        "commitment": {
            "commitment_id": "commitment-1",
            "decision": "accepted",
            "record_uri": "local:commitment",
        },
        "disclosure": {
            "policy_id": "disclosure_policy-1",
            "outcome_id": "outcome-1",
            "allowed": True,
            "policy_version": "privacy-v1",
            "minimized_payload_sha256": HASH,
            "record_uri": "local:disclosure",
        },
        "delivery": {
            "outcome_id": "outcome-1",
            "payload_sha256": HASH,
            "acknowledged": True,
            "receipt_id": "outcome-receipt-1",
        },
    }
    return {kind: record(kind, content) for kind, content in values.items()}


def scenario(station: str, activity: str) -> tuple[dict[str, str], EvidenceMap]:
    """
    Select only the independent evidence the source card requires.

    :param station: Station whose card is being tested.
    :param activity: Exact card label.
    :return: Synthetic object links and completion records.
    """
    case: Case = next(case for case in CASES if case[:2] == (station, activity))
    all_records: EvidenceMap = readings(case[3])
    evidence: EvidenceMap = {kind: all_records[kind] for kind in case[2]}
    if station == "WA4" and "inspection" in evidence:
        evidence["inspection"].values["component_id"] = "lid-1"
    if activity == "Request replacement":
        evidence["inspection"].values["decision"] = "rejected"
    if activity == "Select large container":
        evidence["schedule"].values["selection"] = "large"
    if activity == "Set local fallback":
        evidence["commitment"].values["decision"] = "rejected"
        evidence["topology"].values["selection"] = "local"
    return object_links(), evidence


class RuleTests(unittest.TestCase):
    """Validate distinct evidence sources rather than plausible activity names."""

    def test_every_exact_card_activity_has_a_passing_evidence_path(self) -> None:
        """
        Exercise every activity printed on all four source cards.

        :return: None.
        """
        expected: set[tuple[str, str]] = {
            (station, activity) for station, activity, _, _ in CASES
        }
        actual: set[tuple[str, str]] = {
            (station, activity)
            for station, rules in RULES.items()
            for activity in rules
        }
        self.assertEqual(actual, expected)
        for station, activity, _, _ in CASES:
            objects: dict[str, str]
            evidence: EvidenceMap
            objects, evidence = scenario(station, activity)
            with self.subTest(station=station, activity=activity):
                validate_rule(station, activity, "complete", objects, evidence)

    def test_missing_each_required_independent_source_blocks_completion(self) -> None:
        """
        Prevent every activity from silently dropping a required observation.

        :return: None.
        """
        for station, activity, kinds, _ in CASES:
            for kind in kinds:
                objects: dict[str, str]
                evidence: EvidenceMap
                objects, evidence = scenario(station, activity)
                del evidence[kind]
                with (
                    self.subTest(activity=activity, missing=kind),
                    self.assertRaises(ValidationError),
                ):
                    validate_rule(station, activity, "complete", objects, evidence)

    def test_kit_requires_each_delta_controller_success_and_presence(self) -> None:
        """
        Reject partial, conflicting and anonymous kit evidence.

        :return: None.
        """
        defects: tuple[tuple[str, str, Scalar], ...] = (
            ("bins", "bin1_removed_g", 11.49),
            ("bins", "bin2_removed_g", 18.9),
            ("bins", "bin2_removed_g", None),
            ("bins", "job_id", "another-job"),
            ("controller", "state", "fault"),
            ("controller", "job_id", "another-job"),
            ("camera", "present", False),
            ("camera", "kit_id", "another-kit"),
            ("safety", "guard_closed", False),
            ("safety", "estop_released", False),
            ("kit_plan", "bin1_tolerance_g", 12.0),
            ("kit_plan", "bin2_tolerance_g", -1.0),
        )
        for kind, field, value in defects:
            objects: dict[str, str]
            evidence: EvidenceMap
            objects, evidence = scenario("WA2", "Robot kit")
            evidence[kind].values[field] = value
            with (
                self.subTest(kind=kind, field=field),
                self.assertRaises(ValidationError),
            ):
                validate_rule("WA2", "Robot kit", "complete", objects, evidence)

    def test_kit_tolerance_boundaries_and_fault_are_explicit(self) -> None:
        """
        Accept measured boundaries while recording real faults separately.

        :return: None.
        """
        objects: dict[str, str]
        evidence: EvidenceMap
        objects, evidence = scenario("WA2", "Robot kit")
        evidence["bins"].values.update({"bin1_removed_g": 11.5, "bin2_removed_g": 21.0})
        validate_rule("WA2", "Robot kit", "complete", objects, evidence)
        evidence["controller"].values.update(
            {"state": "fault", "fault_code": "drive-error"}
        )
        evidence["safety"].values["estop_released"] = False
        validate_rule("WA2", "Robot kit", "failed", objects, evidence)
        del evidence["controller"].values["fault_code"]
        with self.assertRaises(ValidationError):
            validate_rule("WA2", "Robot kit", "failed", objects, evidence)

    def test_approved_bin_count_is_not_limited_by_printed_prototype_quantity(
        self,
    ) -> None:
        """
        Allow the approved BOM to define channels beyond four prototype bins.

        :return: None.
        """
        objects: dict[str, str]
        evidence: EvidenceMap
        objects, evidence = scenario("WA2", "Robot kit")
        evidence["kit_plan"].values["bin_count"] = 5
        for index in range(3, 6):
            prefix: str = f"bin{index}_"
            evidence["kit_plan"].values.update(
                {
                    prefix + "part_id": f"part-{index}",
                    prefix + "expected_g": 5.0,
                    prefix + "tolerance_g": 0.2,
                }
            )
            evidence["bins"].values[prefix + "removed_g"] = 5.0
        validate_rule("WA2", "Robot kit", "complete", objects, evidence)

    def test_approval_requires_matching_passed_test_calibration_and_weight(
        self,
    ) -> None:
        """
        Refuse incomplete, failed or mismatched scientific procedure evidence.

        :return: None.
        """
        defects: tuple[tuple[str, str, Scalar], ...] = (
            ("test", "result", "failed"),
            ("test", "result", "not_run"),
            ("calibration", "result", "failed"),
            ("calibration", "result", "not_run"),
            ("test", "product_id", "other-product"),
            ("calibration", "product_id", "other-product"),
            ("test", "test_id", "other-test"),
            ("calibration", "calibration_id", "other-calibration"),
            ("calibration", "procedure_version", "other-procedure"),
            ("calibration", "reference_id", ""),
            ("scale", "product_id", "other-product"),
            ("scale", "weight_g", 0.0),
            ("scale", "stable", False),
            ("operator", "decision", "assembled"),
            ("operator", "actor", ""),
        )
        for kind, field, value in defects:
            objects: dict[str, str]
            evidence: EvidenceMap
            objects, evidence = scenario("WA3", "Approve deployment")
            evidence[kind].values[field] = value
            with (
                self.subTest(kind=kind, field=field),
                self.assertRaises(ValidationError),
            ):
                validate_rule(
                    "WA3", "Approve deployment", "complete", objects, evidence
                )

    def test_assembly_identity_and_real_failed_test_record(self) -> None:
        """
        Preserve matching components and distinguish failure from missing work.

        :return: None.
        """
        for field in (
            "base_id",
            "lid_id",
            "kit_id",
            "base_revision",
            "lid_revision",
            "base_size",
            "lid_size",
        ):
            objects: dict[str, str]
            evidence: EvidenceMap
            objects, evidence = scenario("WA3", "Assemble node")
            evidence["identity"].values[field] = "wrong"
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_rule("WA3", "Assemble node", "complete", objects, evidence)
        objects, evidence = scenario("WA3", "Test and calibrate")
        evidence["test"].values["result"] = "failed"
        evidence["calibration"].values["result"] = "not_run"
        validate_rule("WA3", "Test and calibrate", "failed", objects, evidence)
        evidence["test"].values["result"] = "not_run"
        with self.assertRaises(ValidationError):
            validate_rule("WA3", "Test and calibrate", "failed", objects, evidence)

    def test_receiving_requires_tare_stability_presence_and_matching_identity(
        self,
    ) -> None:
        """
        Prevent unrelated objects and uncertain measurements proving receipt.

        :return: None.
        """
        defects: tuple[tuple[str, str, Scalar], ...] = (
            ("scale", "tared", False),
            ("scale", "stable", False),
            ("scale", "delta_g", 0.0),
            ("scale", "lid_id", "other-lid"),
            ("camera", "present", False),
            ("camera", "lid_id", "other-lid"),
            ("identity", "shipment_id", "other-shipment"),
            ("identity", "lid_id", "other-lid"),
            ("identity", "lid_revision", "other-revision"),
            ("identity", "lid_size", "large"),
        )
        for kind, field, value in defects:
            objects: dict[str, str]
            evidence: EvidenceMap
            objects, evidence = scenario("WA4", "Receive lid")
            evidence[kind].values[field] = value
            with (
                self.subTest(kind=kind, field=field),
                self.assertRaises(ValidationError),
            ):
                validate_rule("WA4", "Receive lid", "complete", objects, evidence)

    def test_delivery_acceptance_requires_matching_accepted_inspection(self) -> None:
        """
        Refuse acceptance for the wrong lid, failed inspection or other decision.

        :return: None.
        """
        defects: tuple[tuple[str, str, Scalar], ...] = (
            ("identity", "lid_revision", "other-revision"),
            ("identity", "lid_size", "large"),
            ("inspection", "component_id", "other-lid"),
            ("inspection", "inspection_id", "other-inspection"),
            ("inspection", "decision", "rejected"),
            ("operator", "decision", "replace"),
        )
        for kind, field, value in defects:
            objects: dict[str, str]
            evidence: EvidenceMap
            objects, evidence = scenario("WA4", "Accept delivery")
            evidence[kind].values[field] = value
            with (
                self.subTest(kind=kind, field=field),
                self.assertRaises(ValidationError),
            ):
                validate_rule("WA4", "Accept delivery", "complete", objects, evidence)

    def test_wrong_revision_can_be_recorded_as_rejected_verification(self) -> None:
        """
        Preserve a genuine failed verification so replacement remains possible.

        :return: None.
        """
        objects: dict[str, str]
        evidence: EvidenceMap
        objects, evidence = scenario("WA4", "Verify lid")
        evidence["identity"].values["lid_revision"] = "wrong-delivered-revision"
        evidence["inspection"].values["decision"] = "rejected"
        evidence["operator"].values["decision"] = "rejected"
        validate_rule("WA4", "Verify lid", "complete", objects, evidence)

    def test_shared_outcome_requires_disclosure_same_payload_and_acknowledgment(
        self,
    ) -> None:
        """
        Refuse undisclosed, altered or unacknowledged outcome transfers.

        :return: None.
        """
        defects: tuple[tuple[str, str, Scalar], ...] = (
            ("disclosure", "allowed", False),
            ("disclosure", "policy_id", "other-policy"),
            ("disclosure", "outcome_id", "other-outcome"),
            ("delivery", "outcome_id", "other-outcome"),
            ("delivery", "payload_sha256", "b" * 64),
            ("delivery", "acknowledged", False),
        )
        for kind, field, value in defects:
            objects: dict[str, str]
            evidence: EvidenceMap
            objects, evidence = scenario("WA4", "Share outcome")
            evidence[kind].values[field] = value
            with (
                self.subTest(kind=kind, field=field),
                self.assertRaises(ValidationError),
            ):
                validate_rule("WA4", "Share outcome", "complete", objects, evidence)


if __name__ == "__main__":
    unittest.main()
