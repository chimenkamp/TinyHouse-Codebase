"""Verify the exact concept energy policy with deterministic synthetic inputs."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from Workareas.shared.energy import (
    EnergyImpact,
    EnergyPolicy,
    EnergySnapshot,
    PrintAuthorization,
    ProductionWindow,
    ScheduleDecision,
    authorize_print,
    authorize_reprint,
    available_renewable_energy,
    evaluate_schedule,
)

NOW: datetime = datetime(2026, 9, 28, 10, tzinfo=timezone.utc)
SECOND: timedelta = timedelta(seconds=1)


def policy() -> EnergyPolicy:
    """Return explicit test-only measured/approved references and values.

    :return: Synthetic policy with no deployment defaults.
    """
    return EnergyPolicy(
        "test-policy", 0.4, 1.0, 2.0, "test-reserve", "test-profile", "test-loss", 60.0
    )


def snapshot(available: float = 2.4) -> EnergySnapshot:
    """Return a fresh synthetic snapshot whose budget equals available.

    :param available: Synthetic battery energy in kWh.
    :return: Complete synthetic snapshot.
    """
    return EnergySnapshot(
        snapshot_id="test-snapshot",
        source_id="test-adapter",
        source_time=NOW,
        ingestion_time=NOW,
        solar_power_kw=0.0,
        battery_soc_percent=75.0,
        usable_battery_energy_kwh=available,
        forecast_solar_energy_kwh=0.0,
        committed_print_energy_kwh=0.0,
        energy_unit="kWh",
        power_unit="kW",
        forecast_starts_at=NOW,
        forecast_ends_at=NOW + 40 * SECOND,
        state_of_charge_unit="%",
        healthy=True,
        resource_ready=True,
    )


def window(available: float = 2.4, identifier: str = "test-window") -> ProductionWindow:
    """Return a candidate with explicit impacts for both configurations.

    :param available: Synthetic candidate energy in kWh.
    :param identifier: Candidate identity.
    :return: Complete synthetic production window.
    """
    impact: EnergyImpact = EnergyImpact(0.0, 0.0, NOW + 30 * SECOND)
    return ProductionWindow(
        identifier, NOW, NOW + 40 * SECOND, snapshot(available), impact, impact
    )


def schedule(windows: tuple[ProductionWindow, ...]) -> ScheduleDecision:
    """Evaluate supplied candidates against one synthetic due window.

    :param windows: Candidate windows under test.
    :return: Evaluated schedule decision.
    """
    return evaluate_schedule(
        policy(),
        windows,
        schedule_id="test-schedule",
        run_id="test-run",
        work_order_id="test-order",
        now=NOW,
        due_window_start=NOW,
        due_window_end=NOW + 40 * SECOND,
        next_solar_window_start=NOW + 100 * SECOND,
    )


def reprint(
    decision: ScheduleDecision, budget: float, schedule_id: str = "new-schedule"
) -> PrintAuthorization:
    """Check a synthetic measured reprint with an explicitly new schedule.

    :param decision: Previous schedule under test.
    :param budget: Fresh synthetic energy budget in kWh.
    :param schedule_id: New reprint schedule identity.
    :return: Evaluated start authorization.
    """
    return authorize_reprint(
        policy(),
        decision,
        snapshot(budget),
        now=NOW,
        authorization_id="auth",
        print_job_id="reprint-job",
        reprint_schedule_id=schedule_id,
        reprint_energy_kwh=2.5,
        energy_profile_id="measured-reprint",
        starts_at=NOW,
        ends_at=NOW + 40 * SECOND,
    )


class EnergyPolicyTests(unittest.TestCase):
    """Exercise boundaries, optimization, validation and repeat authorization."""

    def test_formula_and_zero_floor(self) -> None:
        """Use the exact sum-minus-commitments formula with a zero floor.

        :return: None.
        """
        reading: EnergySnapshot = replace(
            snapshot(1.4), forecast_solar_energy_kwh=1.3, committed_print_energy_kwh=0.2
        )
        self.assertAlmostEqual(available_renewable_energy(reading), 2.5)
        self.assertEqual(
            available_renewable_energy(
                replace(reading, committed_print_energy_kwh=3.0)
            ),
            0.0,
        )

    def test_ordered_configuration_boundaries(self) -> None:
        """Select large first, standard second, and wait below reserve coverage.

        :return: None.
        """
        budget: float
        expected: str
        for budget, expected in (
            (2.4, "large"),
            (2.399, "standard"),
            (1.4, "standard"),
            (1.399, "wait"),
        ):
            with self.subTest(budget=budget):
                self.assertEqual(schedule((window(budget),)).configuration, expected)

    def test_large_threshold_does_not_enable_standard_gateway(self) -> None:
        """Keep the source standard route's strict upper bound.

        :return: None.
        """
        decision: ScheduleDecision = schedule((window(),))
        self.assertEqual(decision.evaluations[0].eligible_configurations, ("large",))

    def test_lexicographic_nonrenewable_precedes_lateness(self) -> None:
        """Prefer less nonrenewable energy even when that window is later.

        :return: None.
        """
        dirty: ProductionWindow = replace(
            window(identifier="dirty"),
            large_impact=EnergyImpact(0.1, 1.0, NOW + 30 * SECOND),
        )
        clean: ProductionWindow = replace(
            window(identifier="clean"),
            ends_at=NOW + 80 * SECOND,
            snapshot=replace(snapshot(), forecast_ends_at=NOW + 80 * SECOND),
            large_impact=EnergyImpact(0.0, 0.0, NOW + 70 * SECOND),
        )
        decision: ScheduleDecision = schedule((dirty, clean))
        self.assertIsNotNone(decision.window)
        assert decision.window is not None
        self.assertEqual(decision.window.window_id, "clean")

    def test_lexicographic_lateness_precedes_direct_solar(self) -> None:
        """Prefer on-time work when nonrenewable energy is tied.

        :return: None.
        """
        late: ProductionWindow = replace(
            window(identifier="late"),
            ends_at=NOW + 80 * SECOND,
            snapshot=replace(snapshot(), forecast_ends_at=NOW + 80 * SECOND),
            large_impact=EnergyImpact(0.0, 2.0, NOW + 70 * SECOND),
        )
        early: ProductionWindow = window(identifier="early")
        decision: ScheduleDecision = schedule((late, early))
        assert decision.window is not None
        self.assertEqual(decision.window.window_id, "early")

    def test_direct_solar_breaks_equal_cost_and_lateness(self) -> None:
        """Prefer direct solar consumption as the final stated objective.

        :return: None.
        """
        solar: ProductionWindow = replace(
            window(identifier="solar"),
            large_impact=EnergyImpact(0.0, 1.0, NOW + 30 * SECOND),
        )
        decision: ScheduleDecision = schedule((window(), solar))
        assert decision.window is not None
        self.assertEqual(decision.window.window_id, "solar")

    def test_standard_impact_used_for_standard_selection(self) -> None:
        """Rank each chosen configuration using that configuration's forecast.

        :return: None.
        """
        first: ProductionWindow = replace(
            window(1.4, "first"),
            standard_impact=EnergyImpact(0.2, 0.0, NOW + 30 * SECOND),
        )
        second: ProductionWindow = window(1.4, "second")
        decision: ScheduleDecision = schedule((first, second))
        assert decision.window is not None
        self.assertEqual(decision.window.window_id, "second")

    def test_unavailable_resource_waits(self) -> None:
        """Do not schedule a resource that is unavailable or locally unready.

        :return: None.
        """
        candidate: ProductionWindow = replace(
            window(), snapshot=replace(snapshot(), resource_ready=False)
        )
        decision: ScheduleDecision = schedule((candidate,))
        self.assertEqual(decision.configuration, "wait")
        self.assertEqual(decision.next_solar_window_start, NOW + 100 * SECOND)

    def test_policy_requires_measured_order_and_approval_references(self) -> None:
        """Reject invalid estimates, nonfinite values and missing references.

        :return: None.
        """
        invalid: tuple[EnergyPolicy, ...] = (
            replace(policy(), large_container_energy_kwh=1.0),
            replace(policy(), reserve_energy_kwh=-1.0),
            replace(policy(), standard_container_energy_kwh=float("nan")),
            replace(policy(), large_container_energy_kwh=float("inf")),
            replace(policy(), reserve_approval_id=""),
            replace(policy(), energy_profile_id=""),
            replace(policy(), loss_model_id=""),
            replace(policy(), snapshot_max_age_seconds=0.0),
        )
        candidate: EnergyPolicy
        for candidate in invalid:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                evaluate_schedule(
                    candidate,
                    (window(),),
                    schedule_id="s",
                    run_id="r",
                    work_order_id="o",
                    now=NOW,
                    due_window_start=NOW,
                    due_window_end=NOW + SECOND,
                    next_solar_window_start=NOW + SECOND,
                )

    def test_bad_snapshot_never_schedules(self) -> None:
        """Reject stale, future, unhealthy, incomplete or incompatible evidence.

        :return: None.
        """
        invalid: tuple[EnergySnapshot, ...] = (
            replace(snapshot(), source_time=NOW - 61 * SECOND),
            replace(snapshot(), source_time=NOW + SECOND),
            replace(snapshot(), ingestion_time=NOW - SECOND),
            replace(snapshot(), source_time=NOW.replace(tzinfo=None)),
            replace(snapshot(), energy_unit="Wh"),
            replace(snapshot(), battery_soc_percent=101.0),
            replace(snapshot(), healthy=False),
            replace(snapshot(), source_id=""),
            replace(snapshot(), usable_battery_energy_kwh=float("nan")),
            replace(snapshot(), forecast_solar_energy_kwh=-1.0),
        )
        reading: EnergySnapshot
        for reading in invalid:
            with self.subTest(reading=reading), self.assertRaises(ValueError):
                schedule((replace(window(), snapshot=reading),))

    def test_empty_and_invalid_candidate_sets_rejected(self) -> None:
        """Reject absent or contradictory candidate records.

        :return: None.
        """
        invalid: tuple[tuple[ProductionWindow, ...], ...] = (
            (),
            (replace(window(), ends_at=NOW),),
            (replace(window(), large_impact=EnergyImpact(-1.0, 0.0, NOW)),),
            (replace(window(), large_impact=EnergyImpact(0.0, 3.0, NOW)),),
            (window(), window()),
        )
        candidates: tuple[ProductionWindow, ...]
        for candidates in invalid:
            with self.subTest(candidates=candidates), self.assertRaises(ValueError):
                schedule(candidates)

    def test_scheduled_start_rechecks_actual_budget_and_identity(self) -> None:
        """A prior eligible schedule cannot authorize a now-depleted snapshot.

        :return: None.
        """
        decision: ScheduleDecision = schedule((window(),))
        permit: PrintAuthorization = authorize_print(
            policy(),
            decision,
            snapshot(2.399),
            now=NOW,
            authorization_id="auth",
            print_job_id="job",
        )
        self.assertFalse(permit.authorized)
        self.assertEqual(permit.schedule_id, "test-schedule")
        self.assertEqual(permit.snapshot_id, "test-snapshot")
        allowed: PrintAuthorization = authorize_print(
            policy(),
            decision,
            snapshot(),
            now=NOW,
            authorization_id="auth",
            print_job_id="job",
        )
        self.assertTrue(allowed.authorized)

    def test_print_not_authorized_outside_window_or_on_wait(self) -> None:
        """Reject premature, expired and unscheduled starts.

        :return: None.
        """
        decision: ScheduleDecision = schedule((window(),))
        current: datetime
        for current in (NOW - SECOND, NOW + 40 * SECOND):
            with self.subTest(current=current):
                reading: EnergySnapshot = replace(
                    snapshot(), source_time=current, ingestion_time=current
                )
                permit: PrintAuthorization = authorize_print(
                    policy(),
                    decision,
                    reading,
                    now=current,
                    authorization_id="auth",
                    print_job_id="job",
                )
                self.assertFalse(permit.authorized)
        with self.assertRaises(ValueError):
            authorize_print(
                policy(),
                schedule((window(0.0),)),
                snapshot(),
                now=NOW,
                authorization_id="auth",
                print_job_id="job",
            )

    def test_reprint_uses_new_schedule_and_its_measured_energy(self) -> None:
        """Reprints require a fresh schedule identity and reserve coverage.

        :return: None.
        """
        decision: ScheduleDecision = schedule((window(),))
        denied: PrintAuthorization = reprint(decision, 2.8)
        allowed: PrintAuthorization = reprint(decision, 2.9)
        self.assertFalse(denied.authorized)
        self.assertTrue(allowed.authorized)
        self.assertEqual(allowed.schedule_id, "new-schedule")
        self.assertEqual(allowed.previous_schedule_id, "test-schedule")
        self.assertEqual(allowed.required_energy_kwh, 2.5)
        with self.assertRaises(ValueError):
            reprint(decision, 2.9, "test-schedule")

    def test_freshness_boundary_and_forecast_interval(self) -> None:
        """Accept the freshness limit and reject mismatched forecast intervals.

        :return: None.
        """
        reading: EnergySnapshot = replace(snapshot(), source_time=NOW - 60 * SECOND)
        self.assertEqual(
            schedule((replace(window(), snapshot=reading),)).configuration, "large"
        )
        with self.assertRaises(ValueError):
            schedule(
                (
                    replace(
                        window(),
                        snapshot=replace(reading, forecast_ends_at=NOW + 41 * SECOND),
                    ),
                )
            )
        decision: ScheduleDecision = schedule((window(),))
        later: datetime = NOW + SECOND
        with self.assertRaises(ValueError):
            authorize_print(
                policy(),
                decision,
                replace(snapshot(), source_time=later, ingestion_time=later),
                now=later,
                authorization_id="auth",
                print_job_id="job",
            )
        refreshed: EnergySnapshot = replace(
            snapshot(),
            source_time=later,
            ingestion_time=later,
            forecast_starts_at=later,
        )
        self.assertTrue(
            authorize_print(
                policy(),
                decision,
                refreshed,
                now=later,
                authorization_id="auth",
                print_job_id="job",
            ).authorized
        )

    def test_overflow_and_invalid_authorization_rejected(self) -> None:
        """Reject arithmetic overflow, altered estimates and changed policies.

        :return: None.
        """
        with self.assertRaises(ValueError):
            available_renewable_energy(
                replace(snapshot(1e308), forecast_solar_energy_kwh=1e308)
            )
        decision: ScheduleDecision = schedule((window(),))
        with self.assertRaises(ValueError):
            authorize_print(
                policy(),
                replace(decision, required_energy_kwh=0.1),
                snapshot(),
                now=NOW,
                authorization_id="auth",
                print_job_id="job",
            )
        with self.assertRaises(ValueError):
            authorize_print(
                replace(policy(), policy_version="other"),
                decision,
                snapshot(),
                now=NOW,
                authorization_id="auth",
                print_job_id="job",
            )
        unready: EnergySnapshot = replace(snapshot(), resource_ready=False)
        self.assertFalse(
            authorize_print(
                policy(),
                decision,
                unready,
                now=NOW,
                authorization_id="auth",
                print_job_id="job",
            ).authorized
        )

    def test_earliest_due_time_and_missing_correlation_rejected(self) -> None:
        """Require full correlation and prevent a start before the due interval.

        :return: None.
        """
        with self.assertRaises(ValueError):
            evaluate_schedule(
                policy(),
                (window(),),
                schedule_id="s",
                run_id="",
                work_order_id="o",
                now=NOW,
                due_window_start=NOW,
                due_window_end=NOW + 60 * SECOND,
                next_solar_window_start=NOW + 90 * SECOND,
            )
        with self.assertRaises(ValueError):
            evaluate_schedule(
                policy(),
                (window(),),
                schedule_id="s",
                run_id="r",
                work_order_id="o",
                now=NOW,
                due_window_start=NOW + SECOND,
                due_window_end=NOW + 60 * SECOND,
                next_solar_window_start=NOW + 90 * SECOND,
            )


if __name__ == "__main__":
    unittest.main()
