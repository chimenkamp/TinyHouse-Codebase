# Distributed Adaptive Sensor Node Demonstrator

## Demonstrator Goal

The demonstrator manufactures one configurable sensor node across two laboratories. The TinyHouse prints the enclosure base and integrates the electronics. The Munich laboratory prints the lid or application-specific mount. Both laboratories use a robot arm for at least one handling or inspection activity.

The product remains useful after process completion. The sensor node can monitor a drawer, storage bin, machine area, or environmental zone in the TinyHouse. The device lifecycle extends the process from order creation through manufacturing, deployment, maintenance, and decommissioning.

## Why This Product Fits the Research Goal

The product creates natural distributed complexity. The enclosure base and lid can be produced concurrently. The parts can follow different routes. The parts synchronize before assembly. Each failed part can create a new print job without replacing the complete work order.

The product also creates data-driven decisions. Configuration can select a weight sensor, temperature sensor, motion sensor, camera-free presence sensor, or mixed sensor set. Machine state, material stock, queue length, print quality, due date, privacy policy, and network state can change the route.

The product supports controlled repetition. A short standardized print can support many experimental runs. Replaceable mounts create variants without changing the complete product. QR labels provide inexpensive object identity.

## Physical Product

| Element | Default site | Identity | Main evidence |
| --- | --- | --- | --- |
| Enclosure base | TinyHouse | `component:<uuid>` | QR scan, print telemetry, image, weight |
| Lid or mount | Munich | `component:<uuid>` | QR scan, print telemetry, image, shipment scan |
| Electronics kit | TinyHouse | `component:<uuid>` | Kit scan, weight, human confirmation |
| Sensor module | TinyHouse | `component:<uuid>` | Device identifier, calibration reading |
| Completed sensor node | TinyHouse | `product-unit:<uuid>` | Assembly event, test result, deployment telemetry |
| Shipping container | Munich and TinyHouse | `shipment:<uuid>` | Seal identifier, departure and receipt scans |

## End-to-End Process

The [BPMN orchestration](distributed-process.svg) shows both local processes and their message flows. The [BPMN choreography](distributed-choreography.svg) isolates the public interaction order. The editable sources and formal semantics are documented in [08-bpmn-models.md](08-bpmn-models.md).

| Phase | TinyHouse | Munich laboratory | Human role | Main objects |
| --- | --- | --- | --- | --- |
| 1. Initiate | Register experiment and work order | Receive collaboration notice | Select configuration and privacy profile | Experiment run, work order, consent record |
| 2. Plan | Freeze product configuration | Accept assigned component | Approve safety-sensitive route | Work order, design revision, task commitment |
| 3. Produce | Print enclosure base | Print lid or mount | Load material or recover a failed print | Print jobs, components, material batches, equipment |
| 4. Inspect | Robot or camera inspects base | Robot or camera inspects lid | Review uncertain inspection | Inspections, components, robot jobs, human tasks |
| 5. Transfer | Prepare receiving slot | Label and dispatch component | Pack, hand over, and scan | Shipment, component, handover task |
| 6. Integrate | Receive part and assemble node | Observe receipt acknowledgement | Install electronics or supervise robot | Product unit, components, human task, robot job |
| 7. Validate | Test and calibrate sensor node | Receive outcome milestone | Approve calibration exception | Inspection, calibration, product unit |
| 8. Operate | Deploy node and monitor telemetry | Receive minimized research milestone | Maintain or replace node | Sensor node, deployment, incident, data asset |
| 9. Close | Decommission or refurbish node | Close collaboration commitment | Confirm return or disposal | Product unit, experiment run, data asset |

## Default Happy Path

1. A researcher creates an experiment run.
2. A participant selects a sensor-node configuration.
3. The orchestration service creates one work order and two print jobs.
4. The TinyHouse prints the base.
5. The Munich laboratory prints the lid.
6. Each site performs local quality inspection.
7. The Munich laboratory labels and ships the lid.
8. The TinyHouse receives the lid and reconciles the component identity.
9. The TinyHouse robot prepares the kit.
10. A human installs the electronics and closes the enclosure.
11. The TinyHouse tests and calibrates the node.
12. A human approves deployment.
13. The node produces operational telemetry.
14. The experiment closes after the configured observation window.

## Data-Driven Variant Rules

The variant policy must emit a `Decision evaluated` event before the selected action. The event records the input values, policy version, eligible options, chosen option, and reason code. The policy must never override a safety interlock.

| Rule | Measured inputs | Decision | Research value |
| --- | --- | --- | --- |
| Print routing | Queue duration, printer health, material availability, due time | Select TinyHouse, Munich, or approved fallback | Distributed resource allocation |
| Split production | Experiment factor and site availability | Split components or produce all components at one site | Inter-site versus local comparison |
| Quality route | Image score, measured mass, dimensional check | Pass, human review, rework, or reprint | Hybrid AI and human decision analysis |
| Assembly mode | Robot availability, participant skill class, task risk | Robot, human, or collaborative assembly | Human-automation interaction |
| Shipping mode | Due time, batch size, dispatch schedule | Immediate shipment or batch consolidation | Batching and waiting behavior |
| Privacy mode | Consent scope and experiment protocol | Derived features only or approved image retention | Privacy-utility evaluation |
| Network mode | Gateway reachability and event backlog | Online coordination or local store-and-forward | Resilience and late-event analysis |
| Calibration depth | Sensor type, initial error, prior failures | Standard or extended calibration | Adaptive quality control |
| Maintenance route | Drift score, battery voltage, device age | Continue, recalibrate, repair, or replace | Product-lifecycle mining |

## Planned Process Variants

| Variant | Trigger | Changed path | Required marker |
| --- | --- | --- | --- |
| `V0_split_nominal` | Baseline allocation | Each site prints one component | `variant_id=V0_split_nominal` |
| `V1_local_fallback` | Partner site unavailable | TinyHouse prints both components | Recorded unavailability evidence |
| `V2_remote_fallback` | TinyHouse printer unavailable | Munich prints both components | Recorded unavailability evidence |
| `V3_quality_reprint` | Inspection fails | New print job supersedes failed component | `replaces` object relation |
| `V4_human_review` | Inspection confidence enters review band | Human accepts or rejects part | Human-task and rationale events |
| `V5_batch_shipping` | At least two accepted remote components wait | One shipment contains several components | Qualified `contains` relations |
| `V6_offline_sync` | Cross-site link unavailable | Local execution continues and events arrive late | Occurrence and ingestion timestamps |
| `V7_manual_identity` | QR scan fails | Human selects component with dual confirmation | Manual-correlation quality flag |
| `V8_privacy_minimal` | Participant selects minimal sharing | Only role and derived timing leave the site | Disclosure-policy identifier |
| `V9_predictive_maintenance` | Drift threshold is reached | Maintenance precedes final failure | Model version and threshold evidence |

## Complexity Controls

The experiment controller should vary one factor at a time during early validation. Later factorial experiments can combine factors after instrumentation reaches the required data quality.

| Level | Objects per work order | Variants | Cross-site behavior | Recommended use |
| --- | --- | --- | --- | --- |
| 0 | One product and two components | Nominal only | Simulated commitment with real local work | Instrumentation checkout |
| 1 | One product and three components | One controlled deviation | Real two-site transfer | Initial process discovery |
| 2 | Two products and shared shipment | Reprint or human-review loop | Batching and late events | Object interaction analysis |
| 3 | Three to five products | Concurrent routing and maintenance | Store-and-forward and rescheduling | Online conformance evaluation |
| 4 | Rolling product stream | Policy change during the run | Concept drift across both sites | Adaptive monitoring research |

## Human Interaction Points

| Interaction | Research role | Safety role | Privacy treatment |
| --- | --- | --- | --- |
| Configuration choice | Introduces product variants | Confirms allowed configuration | Store choice with pseudonymous participant ID |
| Material loading | Creates resource and skill effects | Confirms machine-ready state | Record role and task result by default |
| Quality review | Creates human-AI disagreement cases | Rejects unsafe or damaged parts | Store decision and reason code |
| Electronics installation | Adds manual duration and rework | Prevents unsafe robotic dexterity task | Avoid continuous video by default |
| Handover scan | Creates cross-organizational evidence | Confirms custody transfer | Store participant role instead of name |
| Exception resolution | Creates adaptive paths | Authorizes recovery action | Apply local-only identity mapping |
| Deployment approval | Extends process into operation | Confirms electrical and placement checks | Record approval scope and protocol version |

## Completion Definition

A manufacturing run completes when every mandatory product component has passed inspection. The completed product must pass the configured functional and calibration checks. The event log must contain every required object relation. The privacy pipeline must produce the approved disclosure view. The process must record unresolved deviations before experiment closure.
