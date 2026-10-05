# WA4 energy scheduling and start authorization

**Feasible with limitations.** [The implementation](../shared/energy.py) evaluates supplied, complete energy evidence and produces typed decision records. It does not acquire inverter/BMS data, produce a weather forecast, estimate losses, reserve energy across concurrent callers, start equipment, or establish that a reference ID is approved. Those are external commissioning/integration responsibilities. No deployment energy constants are invented.

## Exact policy

The policy follows [Overview.md](../../concepts/Overview.md). All energy quantities use **kWh**, solar power uses **kW**, and battery state of charge uses **%**. Usable battery energy is measured within accepted battery operating limits **before subtracting the protected process reserve**. Do not subtract the same reserve in the adapter and again in this gate.

```text
availableRenewableEnergyKWh = max(
  0,
  usableBatteryEnergyKWh
  + forecastSolarEnergyKWhWithinCandidateWindow
  - committedPrintEnergyKWh
)
```

For each candidate window, evaluate these rules in order:

1. Select `large` when available energy is at least large-job energy plus reserve.
2. Otherwise select `standard` when available energy is at least standard-job energy plus reserve.
3. Otherwise return `wait` and the supplied next solar-window start.

The implementation rejects policies unless `large_container_energy_kwh > standard_container_energy_kwh > 0`. The reserve is nonnegative and requires an external approval reference. Resource readiness is a hard constraint; an unavailable resource is ineligible even with sufficient energy.

After this ordered size selection **within each candidate**, eligible candidates are ranked lexicographically by:

1. Lowest projected nonrenewable energy.
2. Lowest projected lateness after the due-window end, in seconds.
3. Highest projected direct-solar consumption.

Large and standard impacts are supplied separately, so each candidate is ranked using its selected configuration. An exact objective tie keeps input order; this tie-break has no effect on the specified objectives. Candidate generation, battery/loss modelling and forecasting are caller responsibilities. A due window's earliest start is enforced; lateness beyond its latest time is measured rather than silently forbidden, as required by the source's lateness objective.

## Input and output records

All record classes are frozen dataclasses. Instantiate them in configuration/integration code; there is no CLI and no hidden global configuration.

| Record/function | Required meaning |
| --- | --- |
| `EnergyPolicy` | Policy version; measured standard/large energy; approved reserve; reserve approval, measured-profile and loss-model references; approved freshness limit. No default values. |
| `EnergySnapshot` | Snapshot/source identity; timezone-aware source and ingestion times; current solar/SoC/usable battery; committed energy; candidate forecast with explicit interval; explicit units, health and resource readiness. |
| `EnergyImpact` | Expected nonrenewable and direct-solar energy and completion time for one configuration, from the referenced validated model. |
| `ProductionWindow` | Window identity and interval, matching forecast snapshot and separate standard/large impacts. |
| `evaluate_schedule(...)` | Requires schedule/run/work-order IDs, current time, full due window and future retry time. Returns chosen configuration/window or `wait`, all candidate eligibility records, policy and source snapshot links. |
| `authorize_print(...)` | Requires the selected schedule, fresh snapshot, authorization ID, actual print-job ID and actual start time. Returns an authorization or a denial record. |
| `authorize_reprint(...)` | Also requires a new schedule ID, measured reprint estimate/profile and separately scheduled interval. Checks `available >= reprintEnergyKWh + reserveEnergyKWh`. Retains the original configuration and prior schedule reference. |

`available_renewable_energy` is a dimensional/numeric calculation helper. Call `evaluate_schedule` or an authorization function to enforce health, correlation and freshness; the arithmetic helper alone is not authorization.

The scheduler rejects missing references, wrong units, NaN/infinity, overflow, negative energy, impossible SoC, naive/future/reversed timestamps, stale/unhealthy reads, invalid intervals and inconsistent forecasts. A supplied invalid candidate rejects the evaluation rather than disappearing from the audit trail. Source time must be no later than ingestion, and ingestion no later than evaluation. Synchronize clocks before use.

Schedule forecasts must cover exactly their candidate interval. At actual print/reprint start, the fresh forecast must cover exactly **now through that scheduled interval's end**; an old forecast must not count sunlight from an elapsed portion. Start checks use a half-open interval: the start is included; the end is excluded. A denied start must return to scheduling; it must not silently downgrade an already agreed large base/lid configuration.

## Commissioned integration sequence

1. Supply the identified read-only inverter/BMS adapter, correct battery operating limits and an approved protected reserve. Measure standard, large and reprint energy at the same energy boundary used by available-energy calculations; record material/printer/configuration and loss-model versions.
2. Maintain an authoritative, transactional reservation ledger. Calculate `committed_print_energy_kwh` consistently: a job must not be subtracted as committed and then charged again as the candidate under evaluation. These pure functions do not lock or mutate that ledger; serialize concurrent authorization and reservation in the integration layer.
3. Acquire a complete fresh source snapshot. Generate candidate windows and candidate-specific forecasts/impacts using the approved forecast/loss method. Invoke `evaluate_schedule` and persist its inputs and decision.
4. For `wait`, persist the decision and wake at its retry time to read fresh state. For a selected configuration, send the matching size and design revision through the existing choreography contract.
5. At actual start, acquire a fresh snapshot and invoke `authorize_print`. Persist and publish `Print authorized` only when `authorized` is true, binding the record to the target job. A denial is evidence for rescheduling, never permission to start.
6. For reprint, create new print-job/component identities and a new schedule identity, acquire fresh energy evidence and invoke `authorize_reprint` at the separately scheduled start. A failed check returns to the source reprint wait/reschedule loop. Never reuse the original job's energy authorization.

These calculations are read-only. Local machine protection and the eventual commissioned print adapter still enforce the independent start boundary. The incomplete direct-local/fallback BPMN route is not repaired by this module.

## Verification and remaining evidence

Run from the repository root:

```bash
python3 -m unittest discover -s Workareas/tests -p test_energy.py -v
```

Tests use explicitly synthetic values solely to establish arithmetic, ordered thresholds, optimization priority, input rejection and repeat authorization. They do not establish measured print energy, forecast accuracy, reserve approval, live adapter operation, concurrent reservation correctness or physical printing. Those remain commissioning gates.
