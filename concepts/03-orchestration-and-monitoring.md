# Orchestration and Live Monitoring

## Architecture Outcome

The recommended architecture uses federated orchestration. Each site owns local machine control and local safety. A collaboration coordinator owns only cross-site commitments, deadlines, object identity exchange, and shared process milestones.

The [orchestration architecture](orchestration-architecture.svg) shows the components. The architecture reuses the documented Raspberry Pis, MQTT services, management PC, Jetsons, and sensor adapters. The architecture adds software services before it adds new computers.

## Formal BPMN Model Set

The formal model set separates private orchestration from public choreography. The [orchestration source](bpmn/distributed-orchestration.bpmn) contains both participant processes and their message flows. The [choreography source](bpmn/distributed-choreography.bpmn) contains only the ordered interaction points.

![BPMN orchestration](distributed-process.svg)

![BPMN choreography](distributed-choreography.svg)

The two views use the same five message contracts. The contracts cover the lid request, commitment decision, lid dispatch, delivery decision, and minimized outcome. The [BPMN model guide](08-bpmn-models.md) defines the visual semantics, data guards, object-centric projection, and soundness assumptions.

## Control Boundaries

| Boundary | Owns | Must not own |
| --- | --- | --- |
| Machine controller | Motion, heater, print, stop, controller faults | Cross-site process state |
| Local safety layer | Interlocks, emergency stop, guarded-zone readiness | Research routing policy |
| Machine adapter | Vendor protocol, command idempotency, normalized state | Direct participant identity |
| Site orchestrator | Local tasks, resource allocation, retries, compensation | Remote robot motion |
| Collaboration coordinator | Commitments, deadlines, site handoffs, shared identifiers | Direct machine commands |
| Event pipeline | Validation, correlation, abstraction, OCEL projection | Safety decisions |
| Monitoring layer | State estimates, conformance, alerts, predictions | Autonomous safety bypasses |

## Local Orchestration

Each site orchestrator manages a durable task state machine. The required states are `requested`, `accepted`, `running`, `succeeded`, `failed`, `cancelled`, and `expired`. Each state change emits one immutable event.

Each command carries an idempotency key. A repeated command with the same key must return the earlier result. A repeated command must not start a second robot motion or print.

Each adapter translates a stable laboratory task into a vendor-specific call. Initial adapters can wrap printer job submission, printer state polling, robot program selection, robot state polling, QR scans, scale readings, and human-task forms. OPC UA can become an optional adapter when a controller supports the required information model.

## Cross-Site Choreography

The collaboration coordinator sends commitments instead of device commands. A commitment states the requested output, acceptance deadline, completion deadline, required evidence class, and disclosure policy. The pilot BPMN route supports acceptance and rejection. A later protocol can add a counter-offer interaction.

The coordinator uses a saga for cross-site recovery. The pilot BPMN route supports remote reprint and TinyHouse fallback after a rejected commitment. A later fault model can add design changes and work-order cancellation. Each compensation action must retain the original objects and reason codes.

The cross-site channel should use outbound mutually authenticated HTTPS through an approved gateway. The channel should exchange signed event and commitment envelopes. The channel should not expose either site's MQTT broker.

The current network documentation prohibits an external MQTT bridge. The proposed gateway respects that constraint because the gateway is an application endpoint rather than a broker bridge. The network and security owners must still approve the gateway before deployment.

## Store-and-Forward Behavior

Each site must continue safe local work during a temporary cross-site outage. The site records events in a local append-only outbox. The gateway sends the events after connectivity returns.

Every event carries `occurred_at` and `observed_at`. The shared store records `ingested_at`. The event also carries a source sequence number. The fields support late-event ordering and clock-quality analysis.

The event pipeline should assume at-least-once delivery. Deduplication uses the immutable event identifier. State changes use optimistic version checks to reject stale updates.

## TinyHouse Integration Path

| Existing capability | Proposed role | Required work |
| --- | --- | --- |
| Arduino and Nano boards | Sensor acquisition | Complete the serial framing and receiver contract |
| Raspberry Pis | Edge adapters, MQTT, local outbox, health services | Standardize operating system and broker roles |
| EMQX or Mosquitto | Local telemetry and task-event transport | Select one supported broker topology and add authentication |
| Jetson devices | Optional local vision inference | Inventory hardware and services before use |
| Management PC and WSL | Site orchestration, administration, experiment control | Harden exposed services and deploy reproducibly |
| Network scale | Mass evidence and calibration reference | Verify connectivity, units, protocol, and tare procedure |
| Cameras | Workcell evidence and derived inspection features | Define camera zones and retention policy |
| Robot arm | Handling, kitting, or inspection motion | Record controller protocol, safe programs, and interlocks |
| 3D printer | Base production and controlled faults | Record interface, telemetry, and repeatable test geometry |

## Current Network Constraints

The current network has a public university side and a private TinyHouse side. The private subnet uses `192.168.1.0/24` behind the TP-Link router. The 2026-06-15 inspection found no direct route from the management PC to the private subnet while Wi-Fi was disconnected.

| Documented condition | Architectural consequence |
| --- | --- |
| The management PC is the WSL and administration entry point. | The pilot can host the local orchestrator on the management PC after capacity and hardening checks. |
| Raspberry Pis and the network scale use the private subnet. | Local adapters should run inside the private boundary or through an approved route. |
| Router DNAT rules expose selected SSH endpoints. | The collaboration design should not add direct public broker or machine exposure. |
| Mosquitto allows anonymous access on several reachable Pis. | Authentication and topic authorization must precede expanded student or partner access. |
| EMQX and Mosquitto currently serve different nodes. | Broker standardization must precede high-reliability experiment claims. |
| An EMQX dashboard listener was observed on one private node. | The service owner and access policy require review before use. |
| External MQTT bridges are prohibited by the current project constraint. | Cross-site exchange should use an approved application gateway with minimized messages. |
| Router firewall rules lack documented source restrictions for DNAT. | No new cross-site service should rely on broad inbound DNAT. |

## Recommended Services

The first implementation can run as containers on the management PC and reachable Raspberry Pis. The concept does not require Kubernetes. Docker Compose or system services provide enough repeatability for the pilot.

| Service | Responsibility | Input | Output |
| --- | --- | --- | --- |
| Device registry | Stable asset and capability identifiers | Admin changes | Versioned equipment metadata |
| Schema registry | Event and payload versions | Reviewed schemas | Validation artifacts |
| Serial receiver | Arduino framing and validation | USB serial or RX/TX | MQTT sensor messages |
| Machine adapter | Vendor-specific control and state | Durable task | Normalized job events |
| Human-task service | Forms, QR scans, task claims | Offered task | Human-task events |
| Site orchestrator | Local workflow state | Process request and events | Local tasks and compensation |
| Event normalizer | Canonical event envelope | MQTT and adapter data | Validated domain events |
| Event correlator | Object resolution and deduplication | Domain events | Object-centric events |
| Abstraction service | Episode and milestone extraction | Raw telemetry | Higher-level activities |
| OCEL projector | OCEL 2.0 export | Correlated events and objects | JSON or SQLite OCEL |
| Live monitor | State, conformance, SLA, and quality views | Event stream | Dashboards and alerts |
| Disclosure gateway | Policy-based cross-site sharing | Local shared-view events | Signed minimized events |

## Telemetry-to-Process Abstraction

The [monitoring abstraction model](monitoring-abstraction.svg) defines six levels from L0 through L5. The pipeline must retain the mapping between each higher-level event and its source evidence.

| Level | Name | Example | Storage rule | Process-mining role |
| --- | --- | --- | --- | --- |
| L0 | Raw signal | Nozzle temperature sample or scale reading | Local time-series store | Evidence and feature computation |
| L1 | State episode | Printer heating or robot blocked | Local episode store | Operational diagnosis |
| L2 | Activity instance | Start print or complete inspection | Canonical event store | Main OCEL event |
| L3 | Site milestone | Remote component accepted | Local and shared event store | Site-level monitoring |
| L4 | Collaboration milestone | Shipment received or commitment breached | Shared event store | Distributed conformance |
| L5 | Experiment outcome | Run complete with data-quality score | Research dataset | Evaluation and comparison |

The abstraction service should use explicit rules before learned models. A rule can require a state transition, a stable duration, and one confirming signal. A learned model can later propose an activity label. A learned result must record its model version and confidence.

The pipeline should avoid converting every sensor sample into an OCEL event. Raw samples remain evidence. Process events represent meaningful state changes or completed activities.

## Live Monitoring Views

| View | Main question | Required objects | Example alert |
| --- | --- | --- | --- |
| Object tracker | Where is each required object? | Product, component, shipment | Component has no valid location |
| Collaboration board | Which commitments wait across sites? | Work order, commitment, shipment | Munich acceptance deadline missed |
| Resource board | Which resources are ready or blocked? | Equipment, print job, robot job | Printer queue exceeds policy threshold |
| Human-task board | Which tasks require a participant? | Human task, participant role | Review task is unclaimed |
| Conformance board | Which lifecycle or relation rule failed? | All operational objects | Rejected component was packed |
| Data-quality board | Are events complete and timely? | Event source, data asset | Source sequence gap detected |
| Privacy board | Which disclosure policy applies? | Consent record, data asset | Shared event contains prohibited field |
| Prediction board | Which deadlines or failures are at risk? | Work order, equipment, model version | Completion risk exceeds configured threshold |

## Process Abstractions

The monitor should support several abstraction lenses. Each lens derives from the same object-centric event graph.

| Lens | Included activities | Hidden detail | Intended audience |
| --- | --- | --- | --- |
| Executive | Create, dispatch, receive, assemble, deploy | Device and retry detail | Laboratory leadership |
| Collaboration | Commit, accept, deliver, acknowledge | Local machine steps | Cross-site coordinators |
| Manufacturing | Print, inspect, rework, assemble, test | Participant identity | Process engineers |
| Resource | Queue, start, stop, fail, maintain | Product configuration detail | Equipment operators |
| Human interaction | Offer, claim, start, complete, override | Direct identity in shared view | Human-factors researchers |
| Privacy | Collect, transform, disclose, delete | Manufacturing details | Data-protection reviewers |
| Scientific | Factor assignment, execution, deviation, outcome | Unneeded operational samples | Researchers |

## Digital Twin Scope

The digital twin should model object state and resource capability. The twin should not claim physical truth when an event is missing. Every displayed state must include source time, ingestion time, confidence, and freshness.

The first twin can use a state projection. Later versions can add remaining-time prediction, counterfactual route evaluation, and simulation. Every prediction must record the model version, features, output time, and eventual outcome.

## Operational Failure Handling

| Failure | Local response | Cross-site response | Required evidence |
| --- | --- | --- | --- |
| Printer failure | Stop job and preserve controller status | Re-negotiate print commitment | Fault code and last stable state |
| Robot failure | Enter safe state and open human task | Report milestone delay | Safety state and program version |
| QR failure | Use dual-confirmed manual selection | Mark correlation quality as manual | Two confirmations and candidate set |
| Scale failure | Use approved alternate inspection | Mark evidence class as degraded | Device health and alternate method |
| MQTT outage | Buffer at adapter and local outbox | Report after restoration | Sequence continuity and backlog duration |
| Cross-site outage | Continue authorized local tasks | Reconcile late events | Occurrence and ingestion timestamps |
| Privacy-policy failure | Block disclosure | Notify collaboration coordinator without payload | Policy identifier and rejected field list |
| Clock drift | Preserve source time and mark quality | Order by causal and sequence evidence | Offset estimate and synchronization source |
