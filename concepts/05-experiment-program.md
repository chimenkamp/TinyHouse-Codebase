# Experiment Program

## Scientific Aim

The experiment program should evaluate how object-centric methods represent and monitor distributed physical processes. The program should also evaluate the effects of abstraction, delayed events, privacy transformation, human work, and adaptive routing. Every finding must distinguish observed evidence from interpretation.

The initial studies should use controlled factors. The later studies can use adaptive policies after the baseline instrumentation is stable. The experiment design must preserve the assigned factor levels and every deviation.

## Proposed Research Questions

| ID | Research question | Main evidence |
| --- | --- | --- |
| RQ1 | How accurately can an object-centric model reconstruct cross-site component synchronization? | Ground-truth scans, OCEL relations, discovered model |
| RQ2 | How do event delay and clock error affect online object state and conformance alerts? | Occurrence time, ingestion time, sequence, injected delay |
| RQ3 | Which telemetry abstraction level preserves conformance findings while reducing event volume? | Linked L0 to L5 data and conformance results |
| RQ4 | How do distributed routing policies change throughput, waiting time, rework, and workload? | Decision events, object durations, resource states |
| RQ5 | How does privacy minimization change process-discovery and prediction utility? | Paired local and disclosed views with approved metrics |
| RQ6 | When do human reviews improve or reduce inspection decision accuracy? | Independent reference label, model decision, human decision |
| RQ7 | How well do object-centric models expose batching and many-to-many interactions? | Shipment batches, component sets, work orders |
| RQ8 | Can live conformance detect unsafe process requests before machine execution? | Rejected commands and rule violations above the safety layer |
| RQ9 | How does equipment or process drift affect discovered behavior over time? | Protocol phases, policy versions, resource health |
| RQ10 | Which cross-site information is necessary for useful monitoring? | Controlled disclosure profiles and monitoring outcomes |

## Experimental Units

The primary experimental unit should be an `experiment-run`. Each run contains one or more work orders. The analysis must account for dependence between objects that share equipment, participants, material batches, or shipments.

The process must not treat every component as an independent sample when several components share one run or shipment. The analysis plan should define the unit for every metric. The plan should record repeated measures by participant and resource.

## Controlled Factors

| Factor | Levels | Manipulation |
| --- | --- | --- |
| Production topology | Split across sites; all TinyHouse; all Munich | Routing policy |
| Shipment policy | Immediate; batch of two or more | Dispatch rule |
| Inspection mode | Rule-based; human; model plus human | Inspection assignment |
| Event delay | None; configured bounded delay; disconnection backlog | Gateway test control |
| Event loss | None; safe duplicate; noncritical event omission | Test harness above device control |
| Clock offset | Synchronized; recorded positive or negative offset | Test event timestamp adapter |
| Privacy profile | Local full; shared minimized; time-bucketed | Disclosure policy |
| Quality condition | Nominal; approved printable defect or parameter perturbation | Test geometry or slicer profile |
| Workload | One order; small concurrent batch; rolling stream | Experiment controller |
| Human availability | Immediate; delayed; reassigned | Human-task scheduler |
| Resource state | Available; planned unavailable; recoverable fault | Adapter test mode or maintenance window |
| Policy version | Baseline; revised threshold or routing weights | Versioned decision model |

## Data-Driven Conditions

Data-driven routing needs deterministic replay. Each decision must store the exact policy version and input snapshot. The replay service must reproduce the chosen route from the stored input when the policy is deterministic.

| Condition | Example measurement | Action class | Minimum provenance |
| --- | --- | --- | --- |
| Queue pressure | Number of accepted jobs and expected queue duration | Change print site | Queue snapshot and estimator version |
| Quality uncertainty | Inspection score inside review band | Create human review | Model and threshold version |
| Component mismatch | QR identity or mass outside expected set | Block assembly | Expected set and measurement evidence |
| Environmental state | Temperature or humidity outside protocol range | Delay print or flag run | Sensor identity and calibration state |
| Energy state | Measured local power or approved energy window | Delay nonurgent print | Meter identity and policy version |
| Network degradation | Gateway unavailable or backlog above threshold | Enter store-and-forward | Health event and backlog size |
| Human workload | Offered tasks above configured limit | Reassign or delay | Task counts and role capacity |
| Device drift | Calibration error or battery trend crosses threshold | Create maintenance | Model version and threshold |

## Safe Fault-Injection Catalog

Fault injection must never bypass local safety. The preferred faults alter orchestration messages, noncritical sensor evidence, or approved test artifacts.

| Fault | Injection layer | Expected process effect | Prohibited implementation |
| --- | --- | --- | --- |
| Duplicate event | Test event gateway | Deduplication without duplicate state change | Duplicate robot command |
| Delayed event | Outbox or network emulator | Late correction of live state | Delay of emergency-stop signal |
| Reordered event | Test event gateway | Sequence or causal repair | Reordered controller safety messages |
| Missing optional evidence | Abstraction pipeline | Lower confidence and human review | Removal of mandatory safety evidence |
| QR read failure | Test label or scanner mode | Manual dual confirmation | Silent guessed correlation |
| Printer unavailable | Adapter test state | Route negotiation or fallback | Unsafe power interruption |
| Recoverable print defect | Approved test geometry or parameter profile | Reprint loop | Thermal protection change |
| Shipment delay | Coordinator schedule | Waiting and escalation path | Untracked physical item movement |
| Human-task timeout | Task service | Reassignment or escalation | Coercive participant behavior |
| Consent withdrawal | Governance test record | Stop nonessential collection | Continued hidden collection |

## Ground Truth

Ground truth needs independent evidence sources. The sources should include object scans, machine-controller states, scale measurements, and human confirmations. A process event must not serve as its own independent ground truth. The protocol should define the trusted source for each activity.

| Activity | Primary ground truth | Secondary evidence |
| --- | --- | --- |
| Print start and end | Printer controller state | Power signature or camera-derived state |
| Component identity | QR scan at controlled station | Expected mass and design revision |
| Shipment dispatch and receipt | Two endpoint scans | Seal and package mass |
| Robot job | Controller program state | Workcell camera-derived motion episode |
| Human task | Task start and completion confirmation | Workstation button or QR scan |
| Inspection result | Independent reference label or measurement | Model and reviewer decision |
| Calibration | Reference measurement procedure | Network-scale or load-cell trace |
| Deployment | Location scan and device heartbeat | Human confirmation |

## Evaluation Metrics

| Dimension | Metric | Unit and scope |
| --- | --- | --- |
| Event completeness | Required events observed divided by required events | Proportion per run |
| Relation completeness | Required qualified relations observed divided by required relations | Proportion per run |
| Timestamp error | Absolute occurrence-time error against ground truth | Milliseconds per event when measurable |
| Online state accuracy | Correct object-state duration divided by observed duration | Proportion per object |
| Detection delay | Alert time minus ground-truth deviation time | Seconds per deviation |
| False-alert rate | Incorrect alerts divided by monitored object-hours | Alerts per object-hour |
| Throughput time | Close or deploy time minus order creation time | Minutes per work order |
| Cross-site waiting | Receive time minus remote acceptance time after local processing | Minutes per component |
| Rework rate | Reworked or reprinted components divided by produced components | Proportion per run |
| Human touch time | Sum of active human-task durations | Minutes per product |
| Event reduction | L2 event count divided by L0 sample count | Ratio per run |
| Conformance fitness | Selected object-centric conformance measure | Score with method version |
| Conformance precision | Selected object-centric conformance measure | Score with method version |
| Privacy reduction | Removed or generalized fields divided by candidate fields | Proportion per disclosure profile |
| Prediction error | Absolute error for remaining-time prediction | Minutes per prediction horizon |

Every metric requires an explicit denominator and scope. Aggregate results should report variation and sample size. A statistical analysis plan should precede confirmatory experiments.

## Run Protocol

1. Register the protocol version and assigned factors.
2. Verify equipment readiness and clock status.
3. Verify schema and adapter versions.
4. Verify participant notice and consent state.
5. Create the experiment run and work orders.
6. Execute the assigned process without hidden manual corrections.
7. Record every authorized deviation and reason code.
8. Close physical objects and reconcile expected identities.
9. Validate event and relation completeness.
10. Produce local and approved shared OCEL views.
11. Freeze the dataset manifest and software versions.
12. Review unresolved safety, privacy, and data-quality issues.

## Run Manifest

| Field | Purpose |
| --- | --- |
| `experiment_run_id` | Stable scope identifier |
| `protocol_version` | Exact run procedure |
| `factor_assignment` | Planned conditions |
| `actual_conditions` | Observed conditions and deviations |
| `schema_versions` | Event and payload interpretation |
| `policy_versions` | Routing, privacy, and thresholds |
| `adapter_versions` | Machine and sensor behavior |
| `design_hashes` | Printed artifact reproducibility |
| `equipment_aliases` | Stable resource mapping |
| `clock_quality` | Synchronization source and offset estimate |
| `dataset_assets` | Raw, derived, and disclosed data references |
| `completeness_results` | Missing required events or relations |
| `closure_status` | Complete, complete with deviations, or invalid |

## Collaboration Study Design

The two laboratories should agree on the shared object identifiers and milestone semantics before live runs. Each laboratory can retain a richer local event log. The shared view should contain enough data to reconstruct commitments, component state, shipment state, and final integration.

The first joint study should use the nominal split route. The second joint study should introduce one planned delay. The third joint study should compare the full local view against the privacy-minimized shared view.

The laboratories should exchange nonparticipant artifacts first. The artifacts should include protocol files, schemas, synthetic examples, and validation reports. A public benchmark should use synthetic or strongly de-identified data until disclosure review is complete.
