"""Evaluate the documented renewable-energy policy without controlling devices."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias

ENERGY_UNIT: str = "kWh"
POWER_UNIT: str = "kW"
STATE_OF_CHARGE_UNIT: str = "%"
MINIMUM_ENERGY_KWH: float = 0.0
MAXIMUM_STATE_OF_CHARGE_PERCENT: float = 100.0

Configuration: TypeAlias = Literal["large", "standard", "wait"]


@dataclass(frozen=True)
class EnergyPolicy:
    """Carry measured estimates and externally approved reserve references."""

    policy_version: str
    reserve_energy_kwh: float
    standard_container_energy_kwh: float
    large_container_energy_kwh: float
    reserve_approval_id: str
    energy_profile_id: str
    loss_model_id: str
    snapshot_max_age_seconds: float


@dataclass(frozen=True)
class EnergySnapshot:
    """Represent one complete read with forecast for its candidate window."""

    snapshot_id: str
    source_id: str
    source_time: datetime
    ingestion_time: datetime
    solar_power_kw: float
    battery_soc_percent: float
    usable_battery_energy_kwh: float
    forecast_solar_energy_kwh: float
    committed_print_energy_kwh: float
    forecast_starts_at: datetime
    forecast_ends_at: datetime
    energy_unit: str
    power_unit: str
    state_of_charge_unit: str
    healthy: bool
    resource_ready: bool


@dataclass(frozen=True)
class EnergyImpact:
    """Hold external loss-aware projections for one configuration and window."""

    expected_nonrenewable_energy_kwh: float
    expected_direct_solar_energy_kwh: float
    expected_finish_at: datetime


@dataclass(frozen=True)
class ProductionWindow:
    """Bind a candidate interval to its input read and configuration impacts."""

    window_id: str
    starts_at: datetime
    ends_at: datetime
    snapshot: EnergySnapshot
    standard_impact: EnergyImpact
    large_impact: EnergyImpact


@dataclass(frozen=True)
class WindowEvaluation:
    """Record ordered eligibility for replay and decision evidence."""

    window_id: str
    snapshot_id: str
    available_renewable_energy_kwh: float
    eligible_configurations: tuple[Configuration, ...]


@dataclass(frozen=True)
class ScheduleDecision:
    """Record a reproducible schedule or a wait for a supplied solar window."""

    schedule_id: str
    run_id: str
    work_order_id: str
    policy: EnergyPolicy
    evaluated_at: datetime
    configuration: Configuration
    window: ProductionWindow | None
    required_energy_kwh: float | None
    evaluations: tuple[WindowEvaluation, ...]
    next_solar_window_start: datetime | None


@dataclass(frozen=True)
class PrintAuthorization:
    """Record a fresh start check; this record never dispatches a printer."""

    authorization_id: str
    schedule_id: str
    previous_schedule_id: str | None
    run_id: str
    work_order_id: str
    print_job_id: str
    snapshot_id: str
    policy_version: str
    energy_profile_id: str
    reserve_approval_id: str
    loss_model_id: str
    checked_at: datetime
    configuration: Configuration
    available_renewable_energy_kwh: float
    required_energy_kwh: float
    reserve_energy_kwh: float
    authorized: bool
    reason: str


def _require_identifier(value: str, name: str) -> None:
    """Reject an absent evidence or correlation reference.

    :param value: Supplied identifier.
    :param name: Field name reported on failure.
    :return: None.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty identifier")


def _require_nonnegative(value: float, name: str) -> None:
    """Reject nonfinite, negative, boolean or incomplete numerical inputs.

    :param value: Supplied quantity.
    :param name: Field name reported on failure.
    :return: None.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    if not math.isfinite(value) or value < MINIMUM_ENERGY_KWH:
        raise ValueError(f"{name} must be finite and nonnegative")


def _require_timestamp(value: datetime, name: str) -> None:
    """Require a timezone-aware timestamp so freshness has one meaning.

    :param value: Supplied timestamp.
    :param name: Field name reported on failure.
    :return: None.
    """
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _validate_policy(policy: EnergyPolicy) -> None:
    """Validate references and the exact large-greater-than-standard invariant.

    :param policy: Externally commissioned energy policy.
    :return: None.
    """
    name: str
    for name in (
        "policy_version",
        "reserve_approval_id",
        "energy_profile_id",
        "loss_model_id",
    ):
        _require_identifier(getattr(policy, name), name)
    for name in (
        "reserve_energy_kwh",
        "standard_container_energy_kwh",
        "large_container_energy_kwh",
        "snapshot_max_age_seconds",
    ):
        _require_nonnegative(getattr(policy, name), name)
    if policy.standard_container_energy_kwh <= MINIMUM_ENERGY_KWH:
        raise ValueError("standard container energy must be positive")
    if policy.large_container_energy_kwh <= policy.standard_container_energy_kwh:
        raise ValueError("large container energy must exceed standard container energy")
    if policy.snapshot_max_age_seconds <= 0:
        raise ValueError("snapshot freshness limit must be positive")


def _validate_energy_values(snapshot: EnergySnapshot) -> None:
    """Check dimensional consistency and all numeric energy-read fields.

    :param snapshot: Complete energy evidence.
    :return: None.
    """
    if (snapshot.energy_unit, snapshot.power_unit, snapshot.state_of_charge_unit) != (
        ENERGY_UNIT,
        POWER_UNIT,
        STATE_OF_CHARGE_UNIT,
    ):
        raise ValueError("snapshot units must be kWh, kW and % respectively")
    name: str
    for name in (
        "solar_power_kw",
        "battery_soc_percent",
        "usable_battery_energy_kwh",
        "forecast_solar_energy_kwh",
        "committed_print_energy_kwh",
    ):
        _require_nonnegative(getattr(snapshot, name), name)
    if snapshot.battery_soc_percent > MAXIMUM_STATE_OF_CHARGE_PERCENT:
        raise ValueError("battery state of charge must not exceed 100%")


def _validate_snapshot(
    snapshot: EnergySnapshot, policy: EnergyPolicy, now: datetime
) -> None:
    """Reject incomplete, stale, unhealthy or temporally inconsistent evidence.

    :param snapshot: Complete energy evidence.
    :param policy: Policy containing the accepted freshness bound.
    :param now: Current synchronized evaluation time.
    :return: None.
    """
    _require_identifier(snapshot.snapshot_id, "snapshot_id")
    _require_identifier(snapshot.source_id, "source_id")
    _require_timestamp(now, "now")
    _require_timestamp(snapshot.source_time, "source_time")
    _require_timestamp(snapshot.ingestion_time, "ingestion_time")
    _validate_energy_values(snapshot)
    _validate_interval(snapshot.forecast_starts_at, snapshot.forecast_ends_at)
    if not snapshot.source_time <= snapshot.ingestion_time <= now:
        raise ValueError("snapshot timestamps must satisfy source <= ingestion <= now")
    age_seconds: float = (now - snapshot.source_time).total_seconds()
    if age_seconds > policy.snapshot_max_age_seconds:
        raise ValueError("energy snapshot is stale")
    if snapshot.healthy is not True or not isinstance(snapshot.resource_ready, bool):
        raise ValueError("snapshot health and resource readiness must be explicit")


def available_renewable_energy(snapshot: EnergySnapshot) -> float:
    """Return max(0, usable battery + candidate forecast - committed energy).

    :param snapshot: Explicit kWh quantities; freshness is checked by callers.
    :return: Renewable budget in kWh before the protected reserve gate.
    """
    _validate_energy_values(snapshot)
    raw_budget: float = (
        snapshot.usable_battery_energy_kwh
        + snapshot.forecast_solar_energy_kwh
        - snapshot.committed_print_energy_kwh
    )
    if not math.isfinite(raw_budget):
        raise ValueError("renewable energy calculation overflowed")
    return max(MINIMUM_ENERGY_KWH, raw_budget)


def _validate_interval(starts_at: datetime, ends_at: datetime) -> None:
    """Require a positive timezone-aware production interval.

    :param starts_at: Inclusive interval start.
    :param ends_at: Exclusive interval end.
    :return: None.
    """
    _require_timestamp(starts_at, "starts_at")
    _require_timestamp(ends_at, "ends_at")
    if starts_at >= ends_at:
        raise ValueError("production interval must have starts_at < ends_at")


def _validate_impact(
    impact: EnergyImpact, required: float, window: ProductionWindow
) -> None:
    """Check an externally projected impact without inventing a loss model.

    :param impact: Configuration-specific projected consumption and finish.
    :param required: Measured job-energy estimate in kWh.
    :param window: Interval covered by the projection.
    :return: None.
    """
    _require_nonnegative(
        impact.expected_nonrenewable_energy_kwh, "expected nonrenewable energy"
    )
    _require_nonnegative(
        impact.expected_direct_solar_energy_kwh, "expected direct solar energy"
    )
    _require_timestamp(impact.expected_finish_at, "expected_finish_at")
    if (
        impact.expected_nonrenewable_energy_kwh
        + impact.expected_direct_solar_energy_kwh
        > required
    ):
        raise ValueError(
            "projected nonrenewable plus direct solar energy exceeds job energy"
        )
    if not window.starts_at <= impact.expected_finish_at <= window.ends_at:
        raise ValueError("projected finish must lie within the candidate window")


def _evaluate_window(
    window: ProductionWindow, policy: EnergyPolicy, now: datetime
) -> WindowEvaluation:
    """Apply hard energy and resource constraints before ordered size selection.

    :param window: Complete candidate with matching forecast interval.
    :param policy: Approved energy estimates and reserve.
    :param now: Current synchronized evaluation time.
    :return: Available energy and ordered eligible configurations.
    """
    _require_identifier(window.window_id, "window_id")
    _validate_interval(window.starts_at, window.ends_at)
    if window.starts_at < now:
        raise ValueError("candidate production window has already started")
    _validate_snapshot(window.snapshot, policy, now)
    if (window.snapshot.forecast_starts_at, window.snapshot.forecast_ends_at) != (
        window.starts_at,
        window.ends_at,
    ):
        raise ValueError("forecast must cover exactly the candidate production window")
    _validate_impact(
        window.standard_impact, policy.standard_container_energy_kwh, window
    )
    _validate_impact(window.large_impact, policy.large_container_energy_kwh, window)
    available: float = available_renewable_energy(window.snapshot)
    eligible: tuple[Configuration, ...] = ()
    if window.snapshot.resource_ready:
        if available >= policy.large_container_energy_kwh + policy.reserve_energy_kwh:
            eligible = ("large",)
        elif (
            available
            >= policy.standard_container_energy_kwh + policy.reserve_energy_kwh
        ):
            eligible = ("standard",)
    return WindowEvaluation(
        window.window_id, window.snapshot.snapshot_id, available, eligible
    )


def _window_rank(
    window: ProductionWindow, configuration: Configuration, due_end: datetime
) -> tuple[float, float, float]:
    """Rank by nonrenewable energy, due lateness, then negative direct solar use.

    :param window: Candidate production interval and projections.
    :param configuration: Selected large or standard configuration.
    :param due_end: Latest desired completion time.
    :return: Lexicographic objective tuple.
    """
    impact: EnergyImpact = (
        window.large_impact if configuration == "large" else window.standard_impact
    )
    lateness_seconds: float = max(
        0.0, (impact.expected_finish_at - due_end).total_seconds()
    )
    return (
        impact.expected_nonrenewable_energy_kwh,
        lateness_seconds,
        -impact.expected_direct_solar_energy_kwh,
    )


def evaluate_schedule(
    policy: EnergyPolicy,
    windows: tuple[ProductionWindow, ...],
    *,
    schedule_id: str,
    run_id: str,
    work_order_id: str,
    now: datetime,
    due_window_start: datetime,
    due_window_end: datetime,
    next_solar_window_start: datetime,
) -> ScheduleDecision:
    """Choose among complete supplied windows, preserving exact ordered rules.

    :param policy: Commissioned energy estimates, reserve and evidence references.
    :param windows: Explicit candidate intervals with configuration projections.
    :param schedule_id: New schedule identity.
    :param run_id: Experiment-run identity.
    :param work_order_id: Work-order identity.
    :param now: Current synchronized evaluation time.
    :param due_window_start: Earliest permitted production time.
    :param due_window_end: Completion deadline used to measure lateness.
    :param next_solar_window_start: Supplied future retry time when ineligible.
    :return: Correlated schedule or wait decision with all input references.
    """
    _validate_schedule_inputs(
        policy,
        windows,
        schedule_id,
        run_id,
        work_order_id,
        now,
        due_window_start,
        due_window_end,
        next_solar_window_start,
    )
    evaluations: tuple[WindowEvaluation, ...] = tuple(
        _evaluate_window(window, policy, now) for window in windows
    )
    selected: ProductionWindow | None = None
    configuration: Configuration = "wait"
    best_rank: tuple[float, float, float] | None = None
    candidate: ProductionWindow
    evaluation: WindowEvaluation
    for candidate, evaluation in zip(windows, evaluations):
        if not evaluation.eligible_configurations:
            continue
        option: Configuration = evaluation.eligible_configurations[0]
        rank: tuple[float, float, float] = _window_rank(
            candidate, option, due_window_end
        )
        if best_rank is None or rank < best_rank:
            selected, configuration, best_rank = candidate, option, rank
    required: float | None = None
    if selected is not None:
        required = (
            policy.large_container_energy_kwh
            if configuration == "large"
            else policy.standard_container_energy_kwh
        )
    return ScheduleDecision(
        schedule_id,
        run_id,
        work_order_id,
        policy,
        now,
        configuration,
        selected,
        required,
        evaluations,
        next_solar_window_start if selected is None else None,
    )


def _validate_schedule_inputs(
    policy: EnergyPolicy,
    windows: tuple[ProductionWindow, ...],
    schedule_id: str,
    run_id: str,
    work_order_id: str,
    now: datetime,
    due_start: datetime,
    due_end: datetime,
    next_start: datetime,
) -> None:
    """Validate complete scheduling context before evaluating any candidates.

    :param policy: Commissioned energy policy.
    :param windows: Candidate production records.
    :param schedule_id: New schedule identity.
    :param run_id: Experiment-run identity.
    :param work_order_id: Work-order identity.
    :param now: Current synchronized evaluation time.
    :param due_start: Earliest permitted production time.
    :param due_end: Completion deadline.
    :param next_start: Future retry time.
    :return: None.
    """
    _validate_policy(policy)
    _require_identifier(schedule_id, "schedule_id")
    _require_identifier(run_id, "run_id")
    _require_identifier(work_order_id, "work_order_id")
    _require_timestamp(now, "now")
    _validate_interval(due_start, due_end)
    _require_timestamp(next_start, "next_solar_window_start")
    if next_start <= now:
        raise ValueError("next solar window must be in the future")
    if not windows or len({window.window_id for window in windows}) != len(windows):
        raise ValueError("provide at least one candidate with unique window IDs")
    if any(window.starts_at < due_start for window in windows):
        raise ValueError("candidate window precedes earliest allowed production time")


def _validate_existing_schedule(
    policy: EnergyPolicy, decision: ScheduleDecision
) -> None:
    """Require an eligible existing schedule under the identical approved policy.

    :param policy: Current commissioned policy.
    :param decision: Previously evaluated eligible schedule.
    :return: None.
    """
    _validate_policy(policy)
    if decision.policy != policy:
        raise ValueError("authorization policy differs from the scheduling policy")
    if (
        decision.configuration == "wait"
        or decision.window is None
        or decision.required_energy_kwh is None
    ):
        raise ValueError("a wait decision cannot authorize a print")
    if decision.configuration not in ("large", "standard"):
        raise ValueError("schedule configuration is invalid")
    expected: float = (
        policy.large_container_energy_kwh
        if decision.configuration == "large"
        else policy.standard_container_energy_kwh
    )
    if decision.required_energy_kwh != expected:
        raise ValueError(
            "scheduled energy differs from the approved configuration estimate"
        )
    _require_identifier(decision.schedule_id, "schedule_id")
    _require_identifier(decision.run_id, "run_id")
    _require_identifier(decision.work_order_id, "work_order_id")


def _authorization_reason(
    snapshot: EnergySnapshot,
    available: float,
    required: float,
    reserve: float,
    now: datetime,
    starts_at: datetime,
    ends_at: datetime,
) -> str:
    """Return a denial reason or authorized without changing physical state.

    :param snapshot: Fresh resource-readiness evidence.
    :param available: Renewable budget in kWh.
    :param required: Job energy in kWh.
    :param reserve: Protected reserve in kWh.
    :param now: Actual start-check time.
    :param starts_at: Inclusive scheduled start.
    :param ends_at: Exclusive scheduled end.
    :return: Decision reason.
    """
    if not starts_at <= now < ends_at:
        return "outside scheduled window"
    if not snapshot.resource_ready:
        return "resource unavailable"
    if available < required + reserve:
        return "insufficient renewable energy; reschedule"
    return "authorized"


def _check_start(
    policy: EnergyPolicy,
    decision: ScheduleDecision,
    snapshot: EnergySnapshot,
    *,
    now: datetime,
    authorization_id: str,
    print_job_id: str,
    schedule_id: str,
    previous_schedule_id: str | None,
    required: float,
    energy_profile_id: str,
    starts_at: datetime,
    ends_at: datetime,
) -> PrintAuthorization:
    """Create correlated authorization evidence from one fresh start snapshot.

    :param policy: Commissioned energy policy.
    :param decision: Original configuration and run correlation.
    :param snapshot: Fresh start energy and resource evidence.
    :param now: Actual start-check time.
    :param authorization_id: New authorization-check identity.
    :param print_job_id: Target print-job identity.
    :param schedule_id: Schedule for this attempt.
    :param previous_schedule_id: Prior schedule reference for reprints.
    :param required: Measured energy estimate for this attempt in kWh.
    :param energy_profile_id: Measurement reference for this estimate.
    :param starts_at: Inclusive scheduled start.
    :param ends_at: Exclusive scheduled end.
    :return: Authorization or denial evidence; no physical command.
    """
    _validate_existing_schedule(policy, decision)
    _validate_snapshot(snapshot, policy, now)
    _validate_interval(starts_at, ends_at)
    _require_identifier(authorization_id, "authorization_id")
    _require_identifier(print_job_id, "print_job_id")
    _require_identifier(schedule_id, "schedule_id")
    _require_identifier(energy_profile_id, "energy_profile_id")
    _require_nonnegative(required, "required print energy")
    if required <= MINIMUM_ENERGY_KWH:
        raise ValueError("required print energy must be positive")
    if starts_at <= now < ends_at and (
        snapshot.forecast_starts_at,
        snapshot.forecast_ends_at,
    ) != (now, ends_at):
        raise ValueError(
            "start forecast must cover exactly the remaining production window"
        )
    available: float = available_renewable_energy(snapshot)
    reason: str = _authorization_reason(
        snapshot,
        available,
        required,
        policy.reserve_energy_kwh,
        now,
        starts_at,
        ends_at,
    )
    return PrintAuthorization(
        authorization_id,
        schedule_id,
        previous_schedule_id,
        decision.run_id,
        decision.work_order_id,
        print_job_id,
        snapshot.snapshot_id,
        policy.policy_version,
        energy_profile_id,
        policy.reserve_approval_id,
        policy.loss_model_id,
        now,
        decision.configuration,
        available,
        required,
        policy.reserve_energy_kwh,
        reason == "authorized",
        reason,
    )


def authorize_print(
    policy: EnergyPolicy,
    decision: ScheduleDecision,
    snapshot: EnergySnapshot,
    *,
    now: datetime,
    authorization_id: str,
    print_job_id: str,
) -> PrintAuthorization:
    """Recheck the selected job and reserve at its actual scheduled start.

    :param policy: Identical commissioned policy used by the schedule.
    :param decision: Eligible selected schedule.
    :param snapshot: Fresh start energy and resource evidence.
    :param now: Actual start-check time.
    :param authorization_id: New authorization-check identity.
    :param print_job_id: Target print-job identity.
    :return: Authorization or denial evidence; no physical command.
    """
    _validate_existing_schedule(policy, decision)
    assert decision.window is not None and decision.required_energy_kwh is not None
    return _check_start(
        policy,
        decision,
        snapshot,
        now=now,
        authorization_id=authorization_id,
        print_job_id=print_job_id,
        schedule_id=decision.schedule_id,
        previous_schedule_id=None,
        required=decision.required_energy_kwh,
        energy_profile_id=policy.energy_profile_id,
        starts_at=decision.window.starts_at,
        ends_at=decision.window.ends_at,
    )


def authorize_reprint(
    policy: EnergyPolicy,
    previous_decision: ScheduleDecision,
    snapshot: EnergySnapshot,
    *,
    now: datetime,
    authorization_id: str,
    print_job_id: str,
    reprint_schedule_id: str,
    reprint_energy_kwh: float,
    energy_profile_id: str,
    starts_at: datetime,
    ends_at: datetime,
) -> PrintAuthorization:
    """Check a separately scheduled measured reprint against fresh energy and reserve.

    :param policy: Commissioned policy retaining the original configuration.
    :param previous_decision: Original schedule and run/work-order correlation.
    :param snapshot: Fresh start energy and resource evidence.
    :param now: Actual start-check time.
    :param authorization_id: New authorization-check identity.
    :param print_job_id: New reprint-job identity.
    :param reprint_schedule_id: New schedule identity distinct from the original.
    :param reprint_energy_kwh: Measured reprint-energy estimate in kWh.
    :param energy_profile_id: Measurement reference for the reprint estimate.
    :param starts_at: Inclusive separately scheduled start.
    :param ends_at: Exclusive separately scheduled end.
    :return: Reprint authorization or denial evidence; no physical command.
    """
    if reprint_schedule_id == previous_decision.schedule_id:
        raise ValueError("a reprint requires a new energy schedule identity")
    return _check_start(
        policy,
        previous_decision,
        snapshot,
        now=now,
        authorization_id=authorization_id,
        print_job_id=print_job_id,
        schedule_id=reprint_schedule_id,
        previous_schedule_id=previous_decision.schedule_id,
        required=reprint_energy_kwh,
        energy_profile_id=energy_profile_id,
        starts_at=starts_at,
        ends_at=ends_at,
    )
