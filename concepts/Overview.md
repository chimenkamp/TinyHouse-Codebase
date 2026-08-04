# Sustainable Distributed Process Laboratory

## Goal

The primary operational goal is sustainability. The TinyHouse in Bayreuth and a research laboratory in Munich execute one physical production process. The process uses the TinyHouse solar roof and battery state to decide when Bayreuth may print. The process also uses the renewable-energy budget to select the product configuration.

The primary research goal is a reproducible real-world process laboratory. The laboratory generates distributed and object-centric process data. The process combines local orchestration with a cross-site choreography. The resulting data supports process mining and online monitoring research.

## Demonstrator

The demonstrator produces a configurable sensor node. Bayreuth prints the enclosure base and integrates the electronics. Munich produces a utility lid that matches the selected enclosure configuration. Each site keeps local control of its printer and robot arm.

The product contains the following physical parts.

| Part | Default site | Configuration rule | Evidence |
| --- | --- | --- | --- |
| Enclosure base | TinyHouse in Bayreuth | `large` or `standard` from the energy schedule | Print job telemetry and component inspection |
| Utility lid | Munich laboratory | Must equal the requested base size and design revision | Print job telemetry and component inspection |
| Electronics kit | TinyHouse in Bayreuth | Selected sensor configuration | Kit scan and human confirmation |
| Completed sensor node | TinyHouse in Bayreuth | Base and lid must match | Assembly and calibration events |
| Shipping container | Munich and Bayreuth | Contains one or more accepted lids | Dispatch and receipt scans |

The completed sensor node remains useful after production. The node can monitor a storage bin or another TinyHouse area. The product lifecycle can therefore include deployment and maintenance events.

## Energy-Aware Scheduling Concept

The optimization concept is **renewable-energy-aware production scheduling**. The scheduler creates a production plan from measured energy state and predicted solar supply. The scheduler also couples the Bayreuth container size to the Munich lid configuration. The BPMN model represents the schedule evaluation and the resulting wait or production route.

The scheduler uses the following inputs.

| Input | Unit | Meaning |
| --- | --- | --- |
| Solar power | kW | Current photovoltaic output from the TinyHouse roof |
| Forecast solar energy | kWh | Expected photovoltaic energy within a candidate production window |
| Battery state of charge | % | Current battery charge state |
| Usable battery energy | kWh | Stored energy within battery operating limits before the protected process reserve |
| Committed print energy | kWh | Renewable energy already allocated to accepted print jobs |
| Estimated job energy | kWh | Measured estimate for one printer and configuration |
| Due window | ISO 8601 interval | Earliest and latest allowed production time |
| Resource state | categorical | Printer availability and local safety readiness |

The scheduler computes one renewable-energy budget for each candidate window. The formula is:

```text
availableRenewableEnergyKWh = max(
  0 kWh,
  usableBatteryEnergyKWh
  + forecastSolarEnergyKWhWithinCandidateWindow
  - committedPrintEnergyKWh
)
```

The protected reserve remains unavailable to printing. The variable `reserveEnergyKWh` represents the energy required for protected TinyHouse loads. The reserve value must come from the approved site configuration. The current repository does not provide a verified reserve value.

The configuration policy uses ordered rules. The scheduler evaluates the large option first. The scheduler evaluates the standard option only when the large option is not eligible. The process waits when neither option is eligible.

| Priority | Formal condition | Result |
| --- | --- | --- |
| 1 | `availableRenewableEnergyKWh >= largeContainerEnergyKWh + reserveEnergyKWh` | Select a large base and request a large Munich lid |
| 2 | `availableRenewableEnergyKWh >= standardContainerEnergyKWh + reserveEnergyKWh` and `< largeContainerEnergyKWh + reserveEnergyKWh` | Select a standard base and request a standard Munich lid |
| 3 | Default | Wait until `nextSolarWindowStart` and evaluate a new energy snapshot |

The print adapter enforces a second authorization at the scheduled start. A print may start only when the renewable-energy budget still covers the selected job and reserve. A failed authorization returns the job to the scheduler. A Bayreuth reprint uses the same rule with `reprintEnergyKWh`.

The energy estimates follow one configuration invariant. `largeContainerEnergyKWh` must be greater than `standardContainerEnergyKWh`. The mutually exclusive gateway conditions make the large and standard routes deterministic.

The scheduler treats energy eligibility as a hard constraint. The scheduler then minimizes expected non-renewable energy use among eligible windows. The scheduler next minimizes due-window lateness. The scheduler finally prefers direct solar consumption over battery discharge when the preceding criteria are equal.

The configuration thresholds require measurement. The project must measure `largeContainerEnergyKWh` and `standardContainerEnergyKWh` for the actual printer and material. The project must also measure conversion losses and battery limits. The concept does not invent those values.

## End-to-End Process

The current production activities remain part of the process. The energy scheduler adds decisions before Bayreuth production and before every Bayreuth reprint.

1. A researcher registers an experiment and work order.
2. Bayreuth selects a local or distributed production topology.
3. Bayreuth reads the solar roof and battery state.
4. The scheduler evaluates candidate production windows.
5. The scheduler selects a large or standard container when enough renewable energy is available.
6. The scheduler waits and evaluates again when the renewable-energy budget is insufficient.
7. Bayreuth requests the matching utility lid for a distributed run.
8. Munich evaluates the commitment and applies the requested lid configuration.
9. Bayreuth prints the base while Munich prints the lid.
10. Each site inspects its component and handles review or reprint paths.
11. Munich packs and dispatches the accepted lid.
12. Bayreuth receives the lid and verifies its identity and configuration.
13. The robot prepares the assembly kit.
14. A human assembles the sensor node.
15. Bayreuth tests and calibrates the sensor node.
16. A human approves deployment.
17. Bayreuth shares a minimized outcome for a joint run.

A rejected Munich commitment changes the topology to local fallback. Bayreuth then creates a new energy schedule for the extra local lid print. The process does not start the larger local workload under the earlier distributed energy budget.

## BPMN Orchestration

The orchestration model contains both private site processes. Human work uses user and manual tasks. Machine work uses service tasks. Policy decisions use business rule tasks. Exclusive gateways use formal conditions and default routes.

![Current energy-aware BPMN orchestration rendered from the editable source](distributed-process.svg)

The figure reflects the current `distributed-orchestration.bpmn` flow. The distributed branch continues through synchronized production and final assembly. The current local branch stops after `Produce locally` because that task has no outgoing sequence flow.

The Bayreuth energy loop reads the solar and battery state. The loop calculates the schedule and selects the product size. The default path waits for `nextSolarWindowStart`. A timer event then triggers a new energy evaluation.

The distributed route contains one matched parallel region. Base production and remote lid delivery run concurrently. The accepted base and accepted lid synchronize before assembly. Existing quality and calibration loops remain available.

The editable source is [distributed-orchestration.bpmn](bpmn/distributed-orchestration.bpmn). The stored Diagram Interchange coordinates define the rendered layout. Both participant swimlanes use white backgrounds.

## BPMN Choreography

The choreography model contains only cross-site contracts. The first interaction transmits the scheduled lid specification. The specification includes the selected size and design revision. Munich returns a commitment decision before production begins.

![Energy-aware BPMN choreography](distributed-choreography.svg)

| Interaction | Initiator | Required content | Result |
| --- | --- | --- | --- |
| Request scheduled lid configuration | TinyHouse in Bayreuth | Work order ID, energy schedule ID, size, design revision, and due window | Accepted or rejected commitment |
| Dispatch lid | Munich laboratory | Shipment ID, component ID, size, and design revision | Lid becomes in transit |
| Confirm delivery | TinyHouse in Bayreuth | Accepted or replacement-required decision | Delivery closes or Munich reprints |
| Share outcome | TinyHouse in Bayreuth | Privacy-minimized completion and sustainability measures | Collaboration completes |

The replacement route returns to the dispatch interaction. A replacement creates a new print-job identity and component identity. The work-order identity and commitment identity remain stable.

The editable source is [distributed-choreography.bpmn](bpmn/distributed-choreography.bpmn). The two BPMN sources use the same five message contract names.

## Gateway Conditions

Every exclusive split reads a versioned decision result. Every decision emits a `Decision evaluated` event before the selected flow fires.

| Gateway | Positive condition | Default route |
| --- | --- | --- |
| Renewable energy available? | Large condition or standard condition from the energy policy | Wait for the next solar window |
| Distributed? | `topology = 'distributed'` | Local production |
| Commitment accepted? | `commitmentStatus = 'accepted'` | Set local fallback and reschedule energy |
| Base passed? | `baseQuality = 'accepted'` | Human review |
| Base reprint? | `baseDisposition = 'reprint'` | Human release |
| Reprint energy available? | `availableRenewableEnergyKWh >= reprintEnergyKWh + reserveEnergyKWh` | Wait for the next solar window |
| Lid passed? | `lidQuality = 'accepted'` | Request replacement |
| Calibration passed? | `calibrationStatus = 'passed'` | Human resolution and rework |
| Shared run? | `collaborationStatus = 'active'` | Complete without remote outcome |

The BPMN models are descriptive. Both processes use `isExecutable="false"`. The actual printer APIs and robot APIs remain unverified.

## Object-Centric Research Model

The canonical research log follows OCEL 2.0 concepts. Events link to several typed objects through explicit qualifiers. The model avoids forcing every event into one case identifier.

| Object group | Main object types |
| --- | --- |
| Control | Experiment run, work order, commitment, and incident |
| Sustainability | Energy snapshot and energy schedule |
| Physical | Product unit, component, and material batch |
| Execution | Print job, robot job, and human task |
| Quality | Inspection and calibration |
| Logistics | Shipment |
| Resources | Equipment, station, and participant |
| Information | Design revision, data asset, and dataset manifest |
| Governance | Consent record and disclosure policy |

The energy snapshot records source time and ingestion time. The energy schedule records input object identifiers and policy version. The schedule also records eligible configurations and the selected production window. Every print job references the schedule that authorized the job.

![Energy-aware object-centric model](object-centric-model.svg)

The [example OCEL 2.0 log](example-ocel20.json) shows one large split-production run. The example includes the energy snapshot and schedule that authorize the Bayreuth print. The Munich lid uses the same configuration value.

## Federated Architecture

Machine control remains local to each laboratory. The Bayreuth energy adapter reads the solar roof and battery interface. The site scheduler produces energy permits and product configurations. The site orchestrator executes only locally authorized tasks.

Each site keeps an append-only event outbox. Local work can continue during a cross-site interruption when the local schedule and safety policy allow the work. Late events retain occurrence time and ingestion time.

The cross-site coordinator exchanges commitments and milestones. The coordinator never sends direct robot motion or printer heater commands. An approved disclosure gateway filters every shared event.

![Federated energy-aware orchestration architecture](orchestration-architecture.svg)

## Monitoring

The monitoring pipeline separates process events from high-volume telemetry. Raw solar and battery samples remain local evidence. Higher levels represent energy windows and schedule decisions. Collaboration views receive only the summary required for lid production and research.

| Level | Meaning | Energy-aware example |
| --- | --- | --- |
| L0 | Raw signal | Solar power or battery state of charge |
| L1 | State episode | Renewable-energy window available |
| L2 | Activity instance | Schedule evaluated or print authorized |
| L3 | Site milestone | Container configuration fixed |
| L4 | Collaboration milestone | Matching lid committed |
| L5 | Experiment outcome | Product completed with measured renewable-energy share |

![Energy-aware monitoring abstraction](monitoring-abstraction.svg)

Every derived state records confidence and freshness. Every derived state also records source time and policy version. A missing event must remain visible as uncertainty.

## Privacy and Safety

Raw energy telemetry remains at the TinyHouse by default. Munich receives the selected configuration and due window. Munich does not need the complete battery history or household load profile. A shared research view may include aggregated renewable-energy measures under the approved disclosure policy.

Human events use a role or study pseudonym in the shared view. Direct identity remains in a separate local identity vault. Raw video remains local by default. Workpiece cameras should exclude faces and unrelated areas.

Safety functions remain local and independent from research orchestration. No experiment may disable emergency stops or guards. No schedule may override thermal limits or manufacturer safety checks. The protected battery reserve also remains a local hard constraint.

![Privacy and safety boundaries](privacy-boundaries.svg)

