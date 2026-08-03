# Object-Centric Process Model

## Modeling Principle

The laboratory should use OCEL 2.0 as the canonical research exchange format. OCEL 2.0 represents events, objects, object changes, object-to-object relations, and qualified event-to-object relations. The format avoids forcing every event into one case identifier.

The process model should use an object-centric Petri net for discovery and conformance. The implementation should also retain explicit lifecycle models. The lifecycle models provide simpler runtime checks than a single large discovered model.

The [object-centric model](object-centric-model.svg) shows the main object types and relations.

## Object Types

| Object type | Category | Identity rule | Selected attributes | Retention role |
| --- | --- | --- | --- | --- |
| `experiment-run` | Control | UUID created before execution | protocol version, factor levels, planned start, status | Research scope |
| `work-order` | Control | UUID created at request | configuration, priority, due time, route policy | Main business request |
| `commitment` | Control | Site-prefixed UUID created for each cross-site request | provider site, requested output, decision, deadlines, state | Choreography state |
| `product-unit` | Physical | UUID encoded in QR label | configuration, status, deployment location class | Finished unit |
| `component` | Physical | UUID encoded in QR label | part role, revision, disposition, measured mass | Printed or purchased part |
| `design-revision` | Information | Content hash plus revision label | file hash, slicer profile hash, compatibility set | Reproducibility |
| `print-job` | Execution | Site-prefixed UUID | site, machine adapter, planned parameters, state | Additive-manufacturing execution |
| `robot-job` | Execution | Site-prefixed UUID | program version, safety mode, state | Robot execution |
| `human-task` | Execution | Site-prefixed UUID | task type, role, skill class, state | Manual execution |
| `inspection` | Quality | UUID created per inspection | method, threshold version, result, confidence | Quality decision |
| `calibration` | Quality | UUID created per calibration | sensor type, reference, error, result | Measurement quality |
| `shipment` | Logistics | UUID encoded in shipment label | origin, destination, seal, state | Cross-site transfer |
| `material-batch` | Physical | Supplier or local batch identifier | material, color, received time, storage state | Traceability |
| `equipment` | Resource | Stable site asset identifier | equipment type, adapter version, capability state | Resource behavior |
| `station` | Resource | Stable site and workstation identifier | station type, fixture set, readiness state | Location and fixture context |
| `participant` | Governance | Local pseudonym | role, skill class, consent pointer | Human behavior |
| `consent-record` | Governance | Immutable versioned identifier | allowed purposes, allowed fields, expiry, withdrawal time | Lawful-use evidence |
| `disclosure-policy` | Governance | Immutable versioned identifier | purpose, destination, field allowlist, transformations | Cross-site data control |
| `incident` | Control | Site-prefixed UUID | category, severity class, resolution | Exception trace |
| `data-asset` | Information | Content hash or dataset UUID | class, storage zone, retention deadline | Evidence lineage |
| `dataset-manifest` | Information | Dataset UUID plus manifest version | asset hashes, protocol, software, closure state | Reproducibility and release |

## Primary Object Relations

| Source | Qualifier | Target | Cardinality rule | Creation event |
| --- | --- | --- | --- | --- |
| `experiment-run` | `scopes` | `work-order` | One run scopes one or more orders | Register work order |
| `work-order` | `requests` | `product-unit` | One order requests one or more units | Configure product |
| `work-order` | `requests` | `commitment` | A distributed order requests one remote commitment | Request commitment |
| `commitment` | `promises` | `component` | An accepted commitment promises one component role | Accept commitment |
| `product-unit` | `composed-of` | `component` | One unit needs one component per mandatory role | Reserve component |
| `component` | `realizes` | `design-revision` | Each printed component realizes one revision | Freeze design |
| `print-job` | `produces` | `component` | One job produces one or more same-revision components | Start print |
| `print-job` | `consumes` | `material-batch` | A job consumes at least one batch | Start print |
| `print-job` | `executes-on` | `equipment` | Each job executes on exactly one printer | Accept print job |
| `robot-job` | `executes-on` | `equipment` | Each job executes on exactly one robot | Accept robot job |
| `equipment` | `located-at` | `station` | Each installed resource has one active station location | Register equipment state |
| `inspection` | `evaluates` | `component` | One inspection evaluates one or more components | Start inspection |
| `shipment` | `contains` | `component` | A shipment contains one or more accepted components | Pack shipment |
| `human-task` | `performed-by` | `participant` | One task has one accountable participant | Claim human task |
| `consent-record` | `authorizes` | `participant` | A participant can have versioned records | Capture consent |
| `data-asset` | `evidence-for` | `inspection` | Zero or more assets support an inspection | Capture evidence |
| `disclosure-policy` | `governs` | `data-asset` | Every disclosed asset has one applied policy version | Apply disclosure policy |
| `dataset-manifest` | `lists` | `data-asset` | A frozen manifest lists every included asset | Freeze dataset manifest |
| `component` | `replaces` | `component` | A reprint replaces one failed component | Authorize reprint |
| `incident` | `affects` | Any operational object | One incident affects at least one object | Raise incident |

## Event-to-Object Qualifiers

Qualifiers must describe the role of each object in the event. Generic qualifiers such as `related` should be rejected when a precise role exists.

| Qualifier | Meaning | Example activity |
| --- | --- | --- |
| `scope` | The object defines the experiment scope. | Register work order |
| `request` | The object requests the activity. | Schedule print |
| `target` | The object identifies the requested result. | Request commitment |
| `input` | The activity consumes or evaluates the object. | Assemble product |
| `output` | The activity creates or changes the object. | Complete print |
| `resource` | The object executes or supports the activity. | Start robot job |
| `actor` | The participant performs the activity. | Complete human review |
| `container` | The object groups transported items. | Pack shipment |
| `evidence` | The object stores supporting data. | Decide inspection |
| `policy` | The object or revision governs the decision. | Evaluate route |
| `cause` | The object or incident caused the activity. | Authorize reprint |

## Activity Catalog

| Domain | Activity | Required object roles | Main attributes |
| --- | --- | --- | --- |
| Experiment | `Register experiment` | experiment run as `output` | protocol version, planned factors |
| Order | `Configure product` | work order as `output`, product as `output` | configuration, requested due time |
| Decision | `Evaluate route` | work order as `request`, equipment as `resource` | policy version, inputs, eligible routes, choice |
| Collaboration | `Request commitment` | work order as `request`, commitment as `output`, component as `target` | provider site, deadline, evidence class |
| Collaboration | `Decide commitment` | commitment as `input`, equipment as `resource` | accepted or rejected, reason code, policy version |
| Design | `Freeze design` | design revision as `output`, work order as `request` | file hash, slicer profile hash |
| Printing | `Accept print job` | print job as `output`, printer as `resource` | site, queue estimate |
| Printing | `Start print` | print job as `input`, material as `input`, printer as `resource` | parameters, start sequence |
| Printing | `Complete print` | print job as `input`, component as `output`, printer as `resource` | result, duration, material estimate |
| Inspection | `Capture inspection evidence` | component as `input`, data asset as `output`, equipment as `resource` | method, feature set, quality class |
| Inspection | `Decide inspection` | inspection as `output`, component as `input` | threshold version, score, decision |
| Rework | `Authorize reprint` | failed component as `cause`, new print job as `output` | reason code, approver role |
| Logistics | `Pack shipment` | shipment as `container`, components as `input` | seal, package mass |
| Logistics | `Dispatch shipment` | shipment as `input`, participant as `actor` | handover channel, planned arrival |
| Logistics | `Receive shipment` | shipment as `input`, components as `output`, participant as `actor` | seal state, measured mass |
| Assembly | `Prepare assembly kit` | components as `input`, robot job as `output` | completeness result |
| Assembly | `Assemble product` | components as `input`, product as `output`, actor or robot as `resource` | mode, program or instruction version |
| Test | `Run functional test` | product as `input`, inspection as `output`, equipment as `resource` | test profile, result |
| Calibration | `Calibrate sensor` | product as `input`, calibration as `output`, participant as `actor` | reference, initial error, final error |
| Deployment | `Deploy sensor node` | product as `input`, participant as `actor` | location class, policy version |
| Operation | `Detect operational drift` | product as `input`, data asset as `evidence` | model version, drift score, threshold |
| Maintenance | `Complete maintenance` | product as `input`, human task as `input` | action, replaced component roles |
| Governance | `Apply disclosure policy` | data asset as `input`, disclosure policy as `policy`, consent record as `policy` | policy version, removed fields |
| Closure | `Close experiment` | experiment run as `input` | completeness result, unresolved deviations |

## Object Lifecycles

The lifecycle states provide runtime invariants. The event log should store every state change as an event or a timed object attribute change.

### Work Order

`created → configured → planned → in-production → awaiting-integration → testing → deployed → closed`

The lifecycle also permits `planned → cancelled` and `in-production → suspended`. A cancelled work order must not create new machine commands.

### Component

`planned → printing → produced → inspection-pending → accepted → packed → in-transit → received → consumed-in-assembly`

The lifecycle also permits `inspection-pending → rejected → rework` and `rework → inspection-pending`. A rejected component must not enter a shipment or product.

### Commitment

`requested → accepted → in-production → dispatched → delivered → completed`

The lifecycle also permits `requested → rejected` and `delivered → replacement-requested → in-production`. A rejected commitment closes at Munich and activates the TinyHouse fallback route.

### Print Job

`requested → accepted → queued → running → succeeded`

Additional print-job transitions cover rejection and failure. The lifecycle permits `requested → rejected`, `queued → cancelled`, and `running → failed`. A terminal job must reject later execution commands with the same command identifier.

### Shipment

`open → packed → sealed → dispatched → received → reconciled`

The lifecycle also permits `dispatched → delayed` and `received → discrepancy-review`. Shipment reconciliation requires every expected component identity.

### Product Unit

`planned → kitted → assembled → test-pending → calibrated → deployment-approved → deployed → maintenance → retired`

The lifecycle also permits `test-pending → rework` and `maintenance → deployed`. A product cannot reach `deployment-approved` without a passing functional test and calibration.

### Human Task

`offered → claimed → started → completed`

Additional human-task transitions cover expiry and failure. The lifecycle permits `offered → expired`, `claimed → released`, and `started → failed`. Participant identity remains local unless the protocol explicitly permits disclosure.

## Object-Centric Petri-Net View

The process net contains several typed places. The object types include work orders, components, print jobs, shipments, products, and inspections. The `Schedule parallel production` transition creates one print-job token for each required printed component. Variable arcs allow a work order to request more than two printed components.

The `Pack shipment` transition consumes every accepted remote component selected for one shipment. The `Assemble product` transition synchronizes the required component roles for one product. The `Authorize reprint` transition creates a new print job while retaining the failed component for traceability.

The model must preserve object identity across loops. A reprint must create a new component identity. A rework of the same physical component must retain the component identity. The event qualifier and disposition distinguish both cases.

## Conformance Constraints

| Constraint | Severity | Detection point |
| --- | --- | --- |
| A print cannot start before its design revision is frozen. | Error | Command authorization |
| A printed component must reference one print job and one design revision. | Error | Event normalization |
| A rejected component cannot be packed. | Error | Shipment preparation |
| A shipment cannot reconcile with missing expected component identities. | Error | Receipt processing |
| An assembly cannot complete without all mandatory component roles. | Error | Assembly completion |
| A robot job cannot run without local safety readiness. | Error | Local machine adapter |
| A participant event cannot leave the site with a direct identity by default. | Error | Disclosure gateway |
| A decision event must precede a data-driven route change. | Error | Online conformance monitor |
| An event occurrence time can precede ingestion time. | Information | Late-event monitor |
| A duplicate event identifier must not change object state twice. | Error | Event correlator |
| A product cannot deploy before test and calibration pass. | Error | Deployment approval |
| A consent withdrawal must block future nonessential collection. | Error | Policy enforcement point |

## Analysis Views

| View | Object focus | Research use |
| --- | --- | --- |
| Work-order view | Work order and product | End-to-end throughput and route variants |
| Component view | Component and print job | Reprints, rework, and quality causes |
| Resource view | Equipment and execution jobs | Utilization, queues, and failures |
| Shipment view | Shipment and component | Batching, custody, and cross-site delays |
| Choreography view | Commitment, shipment, and component | Message order, replacement loops, and cross-site deadlines |
| Human-task view | Human task and participant | Workload, handoffs, and automation interaction |
| Product-lifecycle view | Product and maintenance | Drift, recalibration, and useful life |
| Privacy view | Consent record and data asset | Disclosure compliance and data minimization |

## Example Log

The file [example-ocel20.json](example-ocel20.json) provides a small structural example. The example demonstrates qualified relationships between one experiment, one work order, two components, one shipment, and one product. The example is illustrative data and not empirical evidence.
