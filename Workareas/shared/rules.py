"""Explicit evidence fusion for the activities printed on the four cards."""

from __future__ import annotations

from dataclasses import dataclass

from Workareas.shared.models import (
    Evidence,
    Scalar,
    ValidationError,
    identifier,
    number,
)

TRANSITIONS: tuple[str, ...] = ("start", "complete", "failed")


@dataclass(frozen=True)
class Rule:
    """Required object links and independent evidence roles for an activity."""

    objects: tuple[str, ...]
    kinds: tuple[str, ...]
    decisions: tuple[str, ...] = ()


RULES: dict[str, dict[str, Rule]] = {
    "WA1": {
        "Print base": Rule(
            (
                "print_job",
                "component",
                "authorization",
                "energy_schedule",
                "design_revision",
            ),
            ("printer", "meter", "thermal", "camera"),
        ),
        "Inspect base": Rule(
            ("component", "inspection"),
            ("inspection", "operator"),
            ("accepted", "rejected"),
        ),
        "Review base": Rule(
            ("component", "inspection", "human_task"),
            ("operator",),
            ("reprint", "release"),
        ),
        "Schedule reprint energy": Rule(
            ("component", "energy_schedule", "energy_snapshot", "print_job"),
            ("schedule",),
        ),
        "Release base": Rule(
            ("component", "inspection", "human_task"),
            ("inspection", "operator"),
            ("release",),
        ),
    },
    "WA2": {
        "Robot kit": Rule(
            ("robot_job", "kit"), ("controller", "kit_plan", "bins", "camera", "safety")
        ),
    },
    "WA3": {
        "Assemble node": Rule(
            ("product", "base", "lid", "kit", "design_revision"),
            ("identity", "assembly", "camera", "operator"),
            ("assembled",),
        ),
        "Test and calibrate": Rule(
            ("product", "test", "calibration"), ("test", "calibration", "scale")
        ),
        "Resolve failure": Rule(
            ("product", "test", "human_task"), ("operator",), ("rework",)
        ),
        "Rework sensor": Rule(("product", "human_task"), ("operator",), ("reworked",)),
        "Approve deployment": Rule(
            ("product", "test", "calibration", "human_task"),
            ("test", "calibration", "scale", "operator"),
            ("approve",),
        ),
    },
    "WA4": {
        "Register run": Rule(
            ("design_revision",), ("registration", "operator"), ("register",)
        ),
        "Select topology": Rule(("topology_decision",), ("topology",)),
        "Read solar and battery": Rule(("energy_snapshot",), ("energy",)),
        "Optimize energy-aware schedule": Rule(
            ("energy_schedule", "energy_snapshot"), ("schedule",)
        ),
        "Select standard container": Rule(
            ("energy_schedule", "design_revision"), ("schedule",)
        ),
        "Select large container": Rule(
            ("energy_schedule", "design_revision"), ("schedule",)
        ),
        "Request matching lid": Rule(
            ("commitment", "energy_schedule", "design_revision"), ("request",)
        ),
        "Evaluate decision": Rule(("commitment", "decision"), ("commitment",)),
        "Set local fallback": Rule(
            ("commitment", "topology_decision"), ("commitment", "topology")
        ),
        "Receive lid": Rule(
            ("shipment", "lid", "design_revision"), ("scale", "identity", "camera")
        ),
        "Verify lid": Rule(
            ("shipment", "lid", "inspection", "design_revision"),
            ("identity", "inspection", "operator"),
            ("accepted", "rejected"),
        ),
        "Accept delivery": Rule(
            ("shipment", "lid", "inspection", "design_revision"),
            ("identity", "inspection", "operator"),
            ("accept",),
        ),
        "Request replacement": Rule(
            ("commitment", "shipment", "lid", "inspection"),
            ("inspection", "operator"),
            ("replace",),
        ),
        "Apply disclosure": Rule(("disclosure_policy", "outcome"), ("disclosure",)),
        "Share outcome": Rule(
            ("disclosure_policy", "outcome", "commitment"), ("disclosure", "delivery")
        ),
    },
}


def require(record: Evidence, field: str, expected: Scalar) -> None:
    """
    Require an exact observation, including its primitive type.

    :param record: Validated evidence.
    :param field: Value field.
    :param expected: Expected value.
    :return: None.
    """
    actual: Scalar = record.values.get(field)
    if type(actual) is not type(expected) or actual != expected:
        raise ValidationError(
            f"{record.kind}.{field}: expected {expected!r}, received {actual!r}"
        )


def text_fields(record: Evidence, *fields: str) -> None:
    """
    Require traceable identifiers rather than anonymous booleans.

    :param record: Evidence with string metadata.
    :param fields: Required field names.
    :return: None.
    """
    for field in fields:
        identifier(record.values.get(field), f"{record.kind}.{field}")


def positive(record: Evidence, field: str) -> float:
    """
    Read a strictly positive finite measurement.

    :param record: Measurement source.
    :param field: Unit-bearing field name.
    :return: Positive measurement.
    """
    result: float = number(record.values.get(field), f"{record.kind}.{field}")
    if result <= 0:
        raise ValidationError(f"{record.kind}.{field} must be positive")
    return result


def validate_rule(
    station: str,
    activity: str,
    transition: str,
    objects: dict[str, str],
    evidence: dict[str, Evidence],
) -> None:
    """
    Fuse all required records; a missing or conflicting source cannot complete.

    :param station: Physical WA identifier.
    :param activity: Exact card activity label.
    :param transition: Activity lifecycle.
    :param objects: Correlated physical and execution identifiers.
    :param evidence: One current record per source role.
    :return: None when evidence satisfies the rule.
    """
    if activity not in RULES.get(station, {}) or transition not in TRANSITIONS:
        raise ValidationError("unknown station/activity/transition")
    rule: Rule = RULES[station][activity]
    for key in rule.objects:
        identifier(objects.get(key), f"objects.{key}")
    kinds: tuple[str, ...] = required_kinds(activity, transition, rule)
    unrelated: set[str] = evidence.keys() - (set(rule.kinds) | set(kinds))
    if unrelated:
        raise ValidationError(f"unrelated evidence roles: {', '.join(sorted(unrelated))}")
    missing: set[str] = set(kinds) - evidence.keys()
    if missing:
        raise ValidationError(f"missing evidence: {', '.join(sorted(missing))}")
    if transition == "complete" and rule.decisions:
        decision: Scalar = evidence["operator"].values.get("decision")
        if decision not in rule.decisions:
            raise ValidationError("operator decision does not match this activity")
        text_fields(evidence["operator"], "actor", "record_id")
    if station == "WA1":
        validate_print(activity, transition, objects, evidence)
    elif station == "WA2":
        validate_robot(transition, objects, evidence)
    elif station == "WA3":
        validate_assembly(activity, transition, objects, evidence)
    else:
        validate_control(activity, objects, evidence)


def required_kinds(activity: str, transition: str, rule: Rule) -> tuple[str, ...]:
    """
    Select actual lifecycle evidence rather than completing from a start signal.

    :param activity: Card label.
    :param transition: Lifecycle state.
    :param rule: Completion requirements.
    :return: Evidence roles for the transition.
    """
    if transition == "complete":
        return rule.kinds
    if activity == "Print base":
        return ("printer", "authorization") if transition == "start" else ("printer",)
    if activity == "Robot kit":
        return ("controller", "safety")
    if activity == "Assemble node" and transition == "start":
        return ("identity", "assembly", "camera")
    if activity == "Test and calibrate" and transition == "failed":
        return ("test", "calibration")
    raise ValidationError("this activity accepts only a completed decision record")


def validate_print(
    activity: str,
    transition: str,
    objects: dict[str, str],
    evidence: dict[str, Evidence],
) -> None:
    """
    Require job identity, actual printer lifecycle, and supporting completion data.

    :param activity: WA1 activity.
    :param transition: Lifecycle state.
    :param objects: Object links.
    :param evidence: Current records.
    :return: None.
    """
    if activity == "Print base":
        printer: Evidence = evidence["printer"]
        require(printer, "job_id", objects["print_job"])
        expected: str = {
            "start": "running",
            "complete": "completed",
            "failed": "fault",
        }[transition]
        require(printer, "state", expected)
        if transition == "start":
            permit: Evidence = evidence["authorization"]
            require(permit, "allowed", True)
            require(permit, "authorization_id", objects["authorization"])
            require(permit, "schedule_id", objects["energy_schedule"])
            require(permit, "job_id", objects["print_job"])
        elif transition == "complete":
            require(evidence["meter"], "job_id", objects["print_job"])
            positive(evidence["meter"], "energy_kwh")
            require(evidence["thermal"], "job_id", objects["print_job"])
            require(evidence["thermal"], "episode", "cooling")
            require(evidence["camera"], "component_id", objects["component"])
            require(evidence["camera"], "present", True)
        else:
            text_fields(printer, "fault_code")
    elif activity == "Schedule reprint energy":
        validate_schedule(evidence["schedule"], objects)
        require(evidence["schedule"], "purpose", "reprint")
        require(evidence["schedule"], "job_id", objects["print_job"])
    elif "inspection" in evidence:
        require(evidence["inspection"], "component_id", objects["component"])
        require(evidence["inspection"], "inspection_id", objects["inspection"])
        text_fields(evidence["inspection"], "decision", "procedure_version")
        if activity == "Inspect base":
            require(
                evidence["inspection"],
                "decision",
                evidence["operator"].values["decision"],
            )
        elif activity == "Release base":
            text_fields(evidence["operator"], "release_reason")


def validate_robot(
    transition: str, objects: dict[str, str], evidence: dict[str, Evidence]
) -> None:
    """
    Keep controller truth primary and compare every expected bin removal.

    :param transition: Controller lifecycle.
    :param objects: Job and kit links.
    :param evidence: Controller, bins, kit plan and observational safety records.
    :return: None.
    """
    controller: Evidence = evidence["controller"]
    require(controller, "job_id", objects["robot_job"])
    require(
        controller,
        "state",
        {"start": "running", "complete": "success", "failed": "fault"}[transition],
    )
    if transition == "failed":
        text_fields(controller, "fault_code")
        return
    require(evidence["safety"], "guard_closed", True)
    require(evidence["safety"], "estop_released", True)
    if transition == "start":
        return
    plan: Evidence = evidence["kit_plan"]
    bins: Evidence = evidence["bins"]
    require(plan, "kit_id", objects["kit"])
    require(bins, "job_id", objects["robot_job"])
    text_fields(plan, "plan_version")
    text_fields(bins, "calibration_id")
    count: Scalar = plan.values.get("bin_count")
    if type(count) is not int or count < 1:
        raise ValidationError(
            "bin_count must be a positive integer from the approved kit plan"
        )
    for index in range(1, count + 1):
        prefix: str = f"bin{index}_"
        text_fields(plan, prefix + "part_id")
        expected: float = positive(plan, prefix + "expected_g")
        measured: float = number(
            bins.values.get(prefix + "removed_g"), prefix + "removed_g"
        )
        tolerance: float = number(
            plan.values.get(prefix + "tolerance_g"), prefix + "tolerance_g"
        )
        if tolerance >= expected or abs(measured - expected) > tolerance:
            raise ValidationError(
                f"bin {index} removal conflicts with the expected kit"
            )
    require(evidence["camera"], "kit_id", objects["kit"])
    require(evidence["camera"], "present", True)


def validate_identity(
    record: Evidence, objects: dict[str, str], assembly: bool = False
) -> None:
    """
    Match scanned component identity, size, and revision to the work order.

    :param record: Bound identity record.
    :param objects: Expected identities.
    :param assembly: Whether base and kit also need matching.
    :return: None.
    """
    require(record, "lid_id", objects["lid"])
    require(record, "lid_revision", objects["design_revision"])
    size: str = identifier(record.values.get("expected_size"), "expected_size")
    if size not in ("standard", "large"):
        raise ValidationError("expected_size must be standard or large")
    require(record, "lid_size", size)
    if assembly:
        require(record, "base_id", objects["base"])
        require(record, "kit_id", objects["kit"])
        require(record, "base_size", size)
        require(record, "base_revision", objects["design_revision"])


def validate_test(
    objects: dict[str, str], evidence: dict[str, Evidence], passed: bool
) -> None:
    """
    Require separate versioned test and calibration results on the same product.

    :param objects: Product, test and calibration IDs.
    :param evidence: Serial records and final weight.
    :param passed: Whether both results must pass.
    :return: None.
    """
    test: Evidence = evidence["test"]
    calibration: Evidence = evidence["calibration"]
    for kind in ("test", "calibration"):
        record: Evidence = evidence[kind]
        require(record, "product_id", objects["product"])
        require(record, kind + "_id", objects[kind])
        text_fields(record, "procedure_version", "record_uri")
        if record.values.get("result") not in ("passed", "failed", "not_run"):
            raise ValidationError(f"invalid {kind} result")
        if passed:
            require(record, "result", "passed")
    require(calibration, "procedure_version", test.values["procedure_version"])
    text_fields(calibration, "reference_id")
    if passed:
        require(evidence["scale"], "product_id", objects["product"])
        require(evidence["scale"], "stable", True)
        text_fields(evidence["scale"], "calibration_id")
        positive(evidence["scale"], "weight_g")
    elif test.values["result"] != "failed" and calibration.values["result"] != "failed":
        raise ValidationError("a failure event needs a failed test or calibration")


def validate_assembly(
    activity: str,
    transition: str,
    objects: dict[str, str],
    evidence: dict[str, Evidence],
) -> None:
    """
    Separate physical assembly, actual procedure results, and human approval.

    :param activity: WA3 activity.
    :param transition: Lifecycle state.
    :param objects: Component and test identities.
    :param evidence: Corroborating records.
    :return: None.
    """
    if activity == "Assemble node":
        validate_identity(evidence["identity"], objects, assembly=True)
        require(evidence["assembly"], "product_id", objects["product"])
        require(
            evidence["assembly"],
            "first_transfer" if transition == "start" else "pattern_complete",
            True,
        )
        text_fields(evidence["assembly"], "calibration_id", "pattern_version")
        require(evidence["camera"], "product_id", objects["product"])
        require(evidence["camera"], "present", True)
    elif activity in ("Test and calibrate", "Approve deployment"):
        validate_test(objects, evidence, passed=transition == "complete")
    elif activity in ("Resolve failure", "Rework sensor"):
        text_fields(evidence["operator"], "reason", "record_uri")


def validate_schedule(record: Evidence, objects: dict[str, str]) -> None:
    """
    Require a versioned scheduler record referencing its actual input snapshot.

    :param record: Output of the energy scheduler adapter.
    :param objects: Bound schedule and optional input snapshot.
    :return: None.
    """
    require(record, "schedule_id", objects["energy_schedule"])
    if "energy_snapshot" in objects:
        require(record, "snapshot_id", objects["energy_snapshot"])
    text_fields(record, "snapshot_id", "policy_version", "record_uri")
    if record.values.get("selection") not in ("large", "standard", "wait"):
        raise ValidationError("schedule selection must be large, standard, or wait")


def validate_control(
    activity: str, objects: dict[str, str], evidence: dict[str, Evidence]
) -> None:
    """
    Validate WA4 control decisions and route physical receipt separately.

    :param activity: WA4 activity label.
    :param objects: Control/logistics links.
    :param evidence: Actual decisions or device observations.
    :return: None.
    """
    if activity in (
        "Receive lid",
        "Verify lid",
        "Accept delivery",
        "Request replacement",
    ):
        validate_receipt(activity, objects, evidence)
    elif activity in (
        "Optimize energy-aware schedule",
        "Select standard container",
        "Select large container",
    ):
        validate_schedule(evidence["schedule"], objects)
        if activity.startswith("Select "):
            require(
                evidence["schedule"],
                "selection",
                "large" if activity == "Select large container" else "standard",
            )
    elif activity == "Read solar and battery":
        energy: Evidence = evidence["energy"]
        require(energy, "snapshot_id", objects["energy_snapshot"])
        for field in (
            "solar_kw",
            "usable_battery_kwh",
            "forecast_solar_kwh",
            "committed_print_kwh",
            "battery_soc_percent",
        ):
            number(energy.values.get(field), field)
        if number(energy.values["battery_soc_percent"], "battery_soc_percent") > 100:
            raise ValidationError("battery state of charge exceeds 100 percent")
        text_fields(energy, "inverter_id", "bms_id", "forecast_id", "limits_version")
    elif activity in ("Apply disclosure", "Share outcome"):
        disclosure: Evidence = evidence["disclosure"]
        require(disclosure, "policy_id", objects["disclosure_policy"])
        require(disclosure, "outcome_id", objects["outcome"])
        require(disclosure, "allowed", True)
        text_fields(
            disclosure, "policy_version", "minimized_payload_sha256", "record_uri"
        )
        if activity == "Share outcome":
            require(evidence["delivery"], "outcome_id", objects["outcome"])
            require(
                evidence["delivery"],
                "payload_sha256",
                disclosure.values["minimized_payload_sha256"],
            )
            require(evidence["delivery"], "acknowledged", True)
            text_fields(evidence["delivery"], "receipt_id")
    else:
        validate_management(activity, objects, evidence)


def validate_receipt(
    activity: str, objects: dict[str, str], evidence: dict[str, Evidence]
) -> None:
    """
    Require stable positive receipt, matching identity, and explicit decisions.

    :param activity: Lid logistics activity.
    :param objects: Shipment, lid, inspection, and revision links.
    :param evidence: Receiving evidence.
    :return: None.
    """
    if "identity" in evidence:
        rejected: bool = (
            activity == "Verify lid"
            and evidence["operator"].values.get("decision") == "rejected"
        )
        if rejected:
            require(evidence["identity"], "lid_id", objects["lid"])
            text_fields(
                evidence["identity"], "lid_revision", "lid_size", "expected_size"
            )
        else:
            validate_identity(evidence["identity"], objects)
        require(evidence["identity"], "shipment_id", objects["shipment"])
    if activity == "Receive lid":
        scale: Evidence = evidence["scale"]
        require(scale, "stable", True)
        require(scale, "tared", True)
        require(scale, "lid_id", objects["lid"])
        positive(scale, "delta_g")
        text_fields(scale, "calibration_id")
        require(evidence["camera"], "lid_id", objects["lid"])
        require(evidence["camera"], "present", True)
    else:
        inspection: Evidence = evidence["inspection"]
        require(inspection, "component_id", objects["lid"])
        require(inspection, "inspection_id", objects["inspection"])
        text_fields(inspection, "procedure_version")
        expected: Scalar = (
            evidence["operator"].values["decision"]
            if activity == "Verify lid"
            else "accepted"
            if activity == "Accept delivery"
            else "rejected"
        )
        require(inspection, "decision", expected)


def validate_management(
    activity: str, objects: dict[str, str], evidence: dict[str, Evidence]
) -> None:
    """
    Validate registration, topology, commitment and fallback records.

    :param activity: Management activity.
    :param objects: Correlated control objects.
    :param evidence: Versioned records from the management interface.
    :return: None.
    """
    if activity == "Register run":
        require(evidence["registration"], "design_revision", objects["design_revision"])
        text_fields(evidence["registration"], "due_start", "due_end", "policy_version")
    if "topology" in evidence:
        topology: Evidence = evidence["topology"]
        if topology.values.get("selection") not in ("local", "distributed"):
            raise ValidationError("topology must be local or distributed")
        require(topology, "decision_id", objects["topology_decision"])
        text_fields(topology, "policy_version")
    if "commitment" in evidence:
        commitment: Evidence = evidence["commitment"]
        require(commitment, "commitment_id", objects["commitment"])
        if commitment.values.get("decision") not in ("accepted", "rejected"):
            raise ValidationError("commitment requires an accepted/rejected decision")
        text_fields(commitment, "record_uri")
    if activity == "Set local fallback":
        require(evidence["commitment"], "decision", "rejected")
        require(evidence["topology"], "selection", "local")
        require(evidence["topology"], "requires_new_energy_schedule", True)
    if activity == "Request matching lid":
        request: Evidence = evidence["request"]
        for field, key in (
            ("commitment_id", "commitment"),
            ("schedule_id", "energy_schedule"),
            ("design_revision", "design_revision"),
        ):
            require(request, field, objects[key])
        require(request, "size", request.values.get("scheduled_size"))
        if request.values.get("size") not in ("large", "standard"):
            raise ValidationError("lid request must match a selected size")
        text_fields(request, "due_start", "due_end", "receipt_id")
