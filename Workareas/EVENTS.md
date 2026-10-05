# Process-event and normalized evidence contract

`shared/rules.py` is the executable card contract; `shared/events.py` validates source provenance/freshness, evaluates the rule and commits its event. Records must come from real commissioned adapters or explicit operator decisions. JSON examples in tests are synthetic test inputs only.

## Submission envelope

POST one JSON object to the local `POST /v1/events` endpoint with the station's bearer token:

| Field | Type | Meaning |
| --- | --- | --- |
| `request_id` | nonempty string | Stable delivery idempotency key. Retry the same content with the same key. |
| `activity` | string | Exact card label in the station tables below. |
| `transition` | `start`, `complete`, `failed` | Only lifecycles listed below are supported. A decision record normally has only `complete`. |
| `run_id`, `work_order_id` | nonempty strings | Experiment and work-order correlation. |
| `operation_id` | nonempty string | Unique activity attempt, e.g. a print job or test attempt. Use a new ID for a real retry/rework attempt. |
| `objects` | string-to-string object | Required physical/execution/control IDs listed by the rule. |
| `evidence` | array of records | One current record per required kind, all acquired for this envelope's actual run/order/operation. |

The adapter owns binding raw observations to a run/order/operation before submission. The server cannot establish that an uncorrelated camera frame depicts a particular work order. Once recorded, an evidence ID cannot be reassigned to another operation or edited. Source identity plus source session/sequence prevents replay. Unrelated evidence roles are rejected; supplemental records may only belong to the requested activity's completion or selected lifecycle contract. One event is recorded per `(run, order, operation, activity, transition)`. Repeating the original request returns its stable event even after restart; changing an already-recorded lifecycle's content is rejected.

Each evidence record has:

| Field | Constraint |
| --- | --- |
| `id` | Globally unique evidence ID, reused unchanged on retries |
| `kind` | Role such as `printer`, `bins`, `operator`; matched against station configuration |
| `source_id` | Exact configured role identity from `SOURCE_IDS` |
| `session_id` | Adapter boot/acquisition-session ID; renew on reconnect/restart |
| `sequence` | Monotonically increasing integer ≥ 0 for that source/session |
| `source_time` | Timezone-aware ISO 8601; preserve actual occurrence time, never rewrite a late event as current |
| `health`, `quality` | Exactly `ok` and `valid` to support a process event; other values become unknown |
| `confidence` | Finite 0..1, at least the commissioned station threshold |
| `values` | Flat object of string/number/boolean/null fields described below; NaN/infinity forbidden |

The server records its own ingestion time, rejects timestamps older than configured freshness or more than the allowed clock offset ahead, and keeps full accepted evidence locally. For Nano CSV, source time is unavailable: raw capture explicitly labels the time `edge_ingest`. A calibrated normalizer must retain that acquisition limitation in its local evidence lineage; no hardware RTC is assumed.

## Activity requirements

All events additionally link their run, work order, operation, station and abstraction-policy version. The `objects` keys below are required; their values are actual IDs, not the key names.

| WA1 activity | Lifecycle | Required objects | Required evidence |
| --- | --- | --- | --- |
| Print base | start | print_job, component, authorization, energy_schedule, design_revision | printer running for job; matching allowed authorization |
| Print base | complete | same as start | printer completed for job; measured job energy >0; same-job cooling episode; component present |
| Print base | failed | same as start | printer fault for job with fault code |
| Inspect base | complete | component, inspection | versioned inspection; matching explicit accepted/rejected operator decision |
| Review base | complete | component, inspection, human_task | explicit reprint/release decision |
| Schedule reprint energy | complete | component, energy_schedule, energy_snapshot, print_job | versioned reprint schedule and snapshot; new job linked |
| Release base | complete | component, inspection, human_task | inspection record; explicit release and release reason |

| WA2 activity | Lifecycle | Required objects | Required evidence |
| --- | --- | --- | --- |
| Robot kit | start | robot_job, kit | controller running for job; guard/E-stop observation ready |
| Robot kit | complete | robot_job, kit | controller success; approved kit plan; every measured bin delta within its tolerance; kit camera presence; safety observation |
| Robot kit | failed | robot_job, kit | controller fault and fault code; safety-state record still required but never overrides fault |

Guard/E-stop evidence is observation only. Neither this API nor a record with `guard_closed: true` energizes a robot or replaces an independent safety circuit.

| WA3 activity | Lifecycle | Required objects | Required evidence |
| --- | --- | --- | --- |
| Assemble node | start | product, base, lid, kit, design_revision | matching identities; first confirmed assembly transfer; product camera presence |
| Assemble node | complete | same as start | calibrated complete part-state pattern; matching identities and camera; explicit assembled decision |
| Test and calibrate | complete | product, test, calibration | both versioned records passed; same procedure/product; stable positive final weight |
| Test and calibrate | failed | product, test, calibration | actual failed test or calibration; other procedure outcome may be not_run |
| Resolve failure | complete | product, test, human_task | explicit rework decision, reason and record URI |
| Rework sensor | complete | product, human_task | explicit reworked decision, reason and record URI |
| Approve deployment | complete | product, test, calibration, human_task | latest recorded passing test/calibration for this run/order/product; same immutable procedure/reference records; final weight; explicit approval after passing result |

Rework or failed test invalidates an earlier pass. Late pre-rework evidence cannot restore approval. The API verifies the existence and consistency of procedure records; it does not execute the missing physical DUT procedure or infer scientific pass/fail from a pressure reading.

| WA4 activity | Lifecycle | Required objects | Required evidence |
| --- | --- | --- | --- |
| Register run | complete | design_revision | registration with due window/policy; explicit register decision |
| Select topology | complete | topology_decision | versioned local/distributed selection |
| Read solar and battery | complete | energy_snapshot | complete finite energy snapshot and source/forecast/limits references |
| Optimize energy-aware schedule | complete | energy_schedule, energy_snapshot | actual versioned scheduler output; selection large/standard/wait |
| Select standard container | complete | energy_schedule, design_revision | scheduler selected standard |
| Select large container | complete | energy_schedule, design_revision | scheduler selected large |
| Request matching lid | complete | commitment, energy_schedule, design_revision | sent request receipt; size equals scheduled size; due window |
| Evaluate decision | complete | commitment, decision | actual accepted/rejected commitment record |
| Set local fallback | complete | commitment, topology_decision | rejected commitment; local selection requiring a new energy schedule |
| Receive lid | complete | shipment, lid, design_revision | matching captured identity; tared stable positive weight delta; camera presence |
| Verify lid | complete | shipment, lid, inspection, design_revision | identity and versioned inspection; explicit accepted/rejected decision; wrong size/revision may be recorded as rejected |
| Accept delivery | complete | shipment, lid, inspection, design_revision | matching identity and accepted inspection; explicit accept |
| Request replacement | complete | commitment, shipment, lid, inspection | rejected inspection; explicit replace |
| Apply disclosure | complete | disclosure_policy, outcome | allowed policy record tied to minimized-payload digest |
| Share outcome | complete | disclosure_policy, outcome, commitment | same allowed digest and actual recipient acknowledgment |

The card activity names are canonical. Older concept narrative names such as `Energy snapshot read` and `Schedule evaluated` correspond to the complete transitions of `Read solar and battery` and `Optimize energy-aware schedule`. `Print authorized` is the external start-authorization record from the energy helper/print adapter and is included in `Print base/start` evidence; the service does not invent or issue a physical permit from power readings.

## Required role values

Field names encode numeric units. All numeric fields must be finite. IDs must match the envelope's `objects` wherever indicated by the rule. This table is the adapter implementation checklist; `rules.py` and the all-activity test fixtures specify each exact combination.

| Kind | Required values for relevant activity |
| --- | --- |
| printer | `job_id`, `state` = running/completed/fault; `fault_code` for fault |
| authorization | `authorization_id`, `schedule_id`, `job_id`, `allowed: true` from fresh scheduled-start check |
| meter | `job_id`, `energy_kwh` >0 from a calibrated job counter delta; counter/calibration lineage stays in source evidence |
| thermal | `job_id`, `episode: cooling` from a commissioned episode detector |
| camera | relevant `component_id`, `kit_id`, `product_id`, or `lid_id`; `present: true` from the validated workpiece ROI |
| operator | `actor` (local role/pseudonym), `record_id`, `decision`; release adds `release_reason`; rework/resolution adds `reason`, `record_uri` |
| inspection | `component_id`, `inspection_id`, `procedure_version`, `decision` accepted/rejected |
| schedule | `schedule_id`, `snapshot_id`, `policy_version`, `record_uri`, `selection` large/standard/wait; reprint adds `purpose: reprint`, `job_id` |
| controller | `job_id`, `state` running/success/fault; `fault_code` for fault |
| safety | `guard_closed`, `estop_released` as booleans from an independent observation interface |
| kit_plan | `kit_id`, `plan_version`, positive integer `bin_count`; for each i in 1..count: `bin<i>_part_id`, positive `bin<i>_expected_g`, nonnegative `bin<i>_tolerance_g` smaller than expected removal |
| bins | `job_id`, `calibration_id`, nonnegative `bin<i>_removed_g` for every expected bin; each absolute difference must be ≤ plan tolerance |
| identity | `lid_id`, `lid_revision`, `lid_size`, `expected_size` standard/large; receiving adds `shipment_id`; assembly adds `base_id`, `kit_id`, `base_revision`, `base_size` |
| assembly | `product_id`, `calibration_id`, `pattern_version`; `first_transfer: true` for start or `pattern_complete: true` for completion |
| test | `product_id`, `test_id`, `procedure_version`, `record_uri`, `result` passed/failed/not_run |
| calibration | `product_id`, `calibration_id`, `procedure_version` matching test, `record_uri`, `reference_id`, `result` passed/failed/not_run |
| scale | `calibration_id`, `stable: true`; final test adds `product_id`, positive `weight_g`; receiving adds `lid_id`, `tared: true`, positive `delta_g` |
| registration | `design_revision`, `due_start`, `due_end`, `policy_version` |
| topology | `decision_id`, `selection` local/distributed, `policy_version`; fallback adds `requires_new_energy_schedule: true` |
| energy | `snapshot_id`, `inverter_id`, `bms_id`, `forecast_id`, `limits_version`, nonnegative `solar_kw`, `usable_battery_kwh`, `forecast_solar_kwh`, `committed_print_kwh`, `battery_soc_percent` in 0..100 |
| request | `commitment_id`, `schedule_id`, `design_revision`, `size` and equal `scheduled_size`, `due_start`, `due_end`, `receipt_id` |
| commitment | `commitment_id`, `decision` accepted/rejected, `record_uri` |
| disclosure | `policy_id`, `outcome_id`, `allowed: true`, `policy_version`, `minimized_payload_sha256`, `record_uri` |
| delivery | `outcome_id`, `payload_sha256` equal to disclosure digest, `acknowledged: true`, `receipt_id` |

Schedule/disclosure records are issued by trusted services. The event API validates their contract; it does not independently repeat energy forecasting, verify the contents of `record_uri`, hash a payload it never received, or execute remote delivery. Use [energy.py](shared/energy.py) for the actual specified scheduling calculation and retain its full typed output as the referenced record.

## Output and delivery

Accepted events contain a UUID `event_id`, exact `activity`, `transition`, station, run/order/operation links, `objects`, authority, abstraction-policy version, source and ingestion times, confidence, freshness, health, quality, evidence IDs and source IDs. `outcome` carries only selected normalized result fields with role prefixes, e.g. `inspection.decision`, `schedule.selection`, `meter.energy_kwh`, `test.result`. Raw samples, frames, operator identity and procedure files remain in local evidence, not the process-event payload.

An event's source time is the latest source occurrence needed for its rule; the original per-source timestamps remain in SQLite. The event payload is an internal L2 envelope, **not an OCEL 2.0 file**. An OCEL exporter must map `objects` to the concept's typed objects/qualifiers and preserve relationships; no exporter is claimed here.

Conflicting valid JSON submissions additionally create a durable diagnostic on `tinyhouse/bayreuth/diagnostic/<WA>`. The diagnostic includes attempted activity, context, reason and evidence IDs. Its `authority: diagnostic` and `transition: unknown` can never resume a completion. Printer disagreements use `Print evidence conflict`; other invalid/missing cases use `Evidence unknown`. Full rejected payloads remain local for manual review. Nonfinite/invalid JSON fails before diagnostic persistence.

Use QoS1/nonretained local MQTT events and deduplicate by event UUID. Monitor diagnostics as well as accepted events. A downstream CPEE observer must check authority, exact run/order/operation, activity and transition; neither a candidate nor an arbitrary event on the same station topic is sufficient.
