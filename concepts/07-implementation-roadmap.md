# Implementation Roadmap

## Delivery Strategy

The roadmap starts with identity and event quality. Physical automation follows after the process can be executed manually with complete object relations. Cross-site operation follows after both sites pass the same local acceptance tests.

The roadmap uses gates instead of calendar promises. Each gate has observable evidence. A phase cannot claim completion when the required evidence is missing.

## Phase 0: Joint Scope and Inventory

**Goal:** Establish one shared vocabulary and a verified hardware baseline.

### Work

- Confirm the demonstrator product and mandatory component roles.
- Inventory both robot arms and both printers.
- Inventory TinyHouse sensor modules and adapter hosts.
- Assign site, equipment, station, and object identifier conventions.
- Agree on OCEL 2.0 as the pilot exchange profile.
- Approve the initial privacy and safety boundaries.
- Define the Munich data-sharing and operational agreement.

### Gate

- Every required machine has an acceptance record.
- Both sites approve the object types and activity names.
- The process can be performed manually on paper.
- Safety and privacy owners identify the required review path.

## Phase 1: Manual Digital Thread

**Goal:** Produce a valid object-centric log without machine control.

### Work

- Create QR identities for orders, components, products, shipments, and stations.
- Build the experiment registration and human-task forms.
- Implement the canonical event envelope.
- Implement object and relation validation.
- Export one synthetic and one manual-run OCEL 2.0 log.
- Build the object tracker and completeness dashboard.

### Gate

- One local run includes every mandatory object relation.
- Duplicate events do not create duplicate state changes.
- An invalid lifecycle transition is rejected and logged.
- The OCEL export passes structural validation.
- The disclosed view contains no direct participant identity.

## Phase 2: TinyHouse Instrumentation

**Goal:** Replace manual machine-state events with observed events.

### Work

- Complete the Arduino-to-Pi receiver.
- Standardize the application topic namespace and payload types.
- Select the supported local broker topology.
- Add printer, robot, scale, camera, and station adapters.
- Add source sequence numbers and clock-quality fields.
- Implement L0 to L2 abstraction rules.

### Gate

- A printer run emits start, completion, and fault events from the controller or approved adapter.
- A robot job emits accepted, running, and terminal events.
- A component scan resolves one expected object without manual database edits.
- A network interruption preserves and later delivers ordered source events.
- Sensor and task events meet the configured completeness target.

## Phase 3: Closed-Loop Local Orchestration

**Goal:** Execute one safe TinyHouse process with live conformance.

### Work

- Implement the durable task state machine.
- Implement idempotent machine commands.
- Implement local decision events and versioned policies.
- Implement reprint, review, and manual-fallback paths.
- Connect the live object tracker and conformance rules.
- Run approved logical fault injections.

### Gate

- A duplicate command does not start a duplicate physical job.
- A rejected component cannot be packed or assembled.
- A failed print creates a traceable replacement component.
- A safety-not-ready state blocks machine-job acceptance.
- Each route change has a preceding decision event.

## Phase 4: Munich Choreography

**Goal:** Execute the nominal split process across both sites.

### Work

- Deploy the same event and commitment contracts at Munich.
- Configure mutually authenticated site gateways.
- Implement commitment accept, reject, counter, complete, and cancel events.
- Implement shipment packing, dispatch, receipt, and reconciliation.
- Implement the privacy-minimized shared OCEL view.
- Test store-and-forward across a planned disconnection.

### Gate

- The coordinator never sends direct robot or printer commands across sites.
- One remote component completes the full custody chain.
- Late events reconcile without duplicate state changes.
- Both sites reconstruct the same shared object state.
- The shared dataset passes the disclosure-policy test.

## Phase 5: Controlled Experiment Campaign

**Goal:** Generate analyzable distributed-process datasets.

### Work

- Execute the nominal route until instrumentation reaches the quality target.
- Introduce one controlled factor per initial campaign.
- Freeze run manifests and data lineage.
- Compare local and shared process views.
- Evaluate object-centric discovery and conformance.
- Publish a synthetic or approved de-identified benchmark.

### Gate

- Every analyzed run has a frozen protocol and factor assignment.
- Every metric has an explicit unit, denominator, and scope.
- Every excluded run has a recorded exclusion reason.
- Every reported result traces to a frozen dataset manifest.
- The release review approves every shared or public artifact.

## Phase 6: Adaptive Monitoring

**Goal:** Evaluate online predictions and adaptive policies.

### Work

- Add remaining-time and failure-risk predictions.
- Add model and feature provenance to prediction events.
- Add policy shadow mode before automated routing.
- Compare proposed and executed decisions.
- Add concept-drift detection across protocol phases.
- Add product maintenance and decommissioning processes.

### Gate

- Every prediction records a model version and evaluation outcome.
- Shadow-mode evaluation precedes automated policy use.
- The adaptive policy cannot override safety or privacy rules.
- A policy rollback restores the prior version without object-state loss.

## First Four Demonstrations

| Demonstration | Physical scope | Data scope | Success evidence |
| --- | --- | --- | --- |
| D1 Manual local thread | QR-labeled components and human tasks | OCEL objects, relations, lifecycles | Complete valid log and object tracker |
| D2 Instrumented local print | TinyHouse printer and inspection | Telemetry abstraction and print objects | Controller evidence linked to component |
| D3 Local robot handoff | Robot moves accepted part to kit | Robot job and safety readiness | Idempotent job and physical identity continuity |
| D4 Joint split build | Munich lid, shipment, TinyHouse assembly | Commitments and shared OCEL view | Reconciled product with both site histories |

## Key Decisions Before Implementation

| Decision | Options | Recommended pilot choice | Reason |
| --- | --- | --- | --- |
| Product geometry | Sensor enclosure; cocktail accessory; generic assembly | Sensor enclosure | The product reuses documented sensors and supports lifecycle data |
| Broker topology | Mixed services; standardized Mosquitto; standardized EMQX | Select one supported site baseline after inventory | The current mixed state creates ambiguous service ownership |
| Cross-site channel | MQTT bridge; application gateway; manual file exchange | Application gateway after approval | The current constraint prohibits external MQTT bridges |
| Identity technology | QR; NFC; computer vision only | QR | QR is visible, inexpensive, and auditable |
| Camera retention | Continuous; event frames; derived features | Derived features with short review window | The choice supports minimization |
| Automation level | Full robotic assembly; hybrid; manual | Hybrid | The choice provides human interaction and safe fallback |
| Machine interface | Vendor API; OPC UA; UI automation | Vendor API behind a stable adapter | The choice minimizes unsupported assumptions |
| OCEL storage | JSON; SQLite; both | JSON exchange and query store after validation | JSON supports review and interchange |

## Definition of Ready for a Joint Run

- Both site orchestrators report healthy state.
- Both gateways report valid certificates and synchronized clocks.
- Every required machine adapter reports a version and readiness state.
- Every required material and component role is available.
- The assigned participants have valid task authorization.
- The consent and disclosure policies match the experiment protocol.
- The event schema and decision-policy versions match the run manifest.
- The local safety checks pass at each workcell.
- The offline recovery procedure has been tested.
- The physical shipment and custody procedure is available.

## Definition of Done for a Joint Run

- The physical product reaches the planned terminal state.
- Every mandatory component has a valid identity and disposition.
- Every cross-site commitment reaches a terminal state.
- Every shipment component is reconciled.
- Every required event and qualified relation is present or marked missing.
- Every deviation and manual correction has a reason code.
- The local and shared event views are generated.
- The privacy-policy check passes.
- The dataset manifest records software, hardware, design, schema, and policy versions.
- The run receives `complete`, `complete-with-deviations`, or `invalid` status.

