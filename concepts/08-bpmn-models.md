# BPMN Orchestration and Choreography

## Model Scope

The BPMN model set defines one synchronized collaboration. The orchestration view specifies the private control flow at each laboratory. The choreography view specifies the public message order between the TinyHouse and Munich.

The model set is descriptive rather than directly executable. Both processes use `isExecutable="false"` because the printer APIs and robot APIs remain unverified. A later implementation can bind service tasks to local adapters without changing the collaboration contract.

| Artifact | Purpose |
| --- | --- |
| [distributed-orchestration.bpmn](bpmn/distributed-orchestration.bpmn) | BPMN 2.0 collaboration with two participant pools and seven message flows |
| [distributed-choreography.bpmn](bpmn/distributed-choreography.bpmn) | BPMN 2.0 choreography with participant bands and five message contracts |
| [distributed-process.svg](distributed-process.svg) | Compact visual rendering of the orchestration source |
| [distributed-choreography.svg](distributed-choreography.svg) | Compact visual rendering of the choreography source |
| [render-models.mjs](bpmn/render-models.mjs) | Deterministic renderer for the stored BPMN Diagram Interchange coordinates |

## Visual Semantics

The orchestration visual uses BPMN task markers. The person marker identifies a user task. The hand marker identifies a manual task. The gear marker identifies a service task. The table marker identifies a business rule task. The envelope marker identifies a send task or message event.

The gateways retain their BPMN meaning. An `X` gateway selects one data-driven route. A `+` gateway starts or joins concurrent branches. Solid arrows represent sequence flows inside one process. Dashed arrows represent message flows between participants.

The choreography visual uses participant bands. The darker participant band identifies the initiating participant. Each choreography task contains exactly two participants. Each choreography task references one or two message flows as permitted by BPMN 2.0.2.

## Cotton Candy Palette

The SVGs use the following paired fill and stroke values. The Markdown carries the color legend so the diagrams remain compact.

| Name | Fill | Stroke | Primary use |
| --- | --- | --- | --- |
| Cotton Candy — Blush | `#FAE7EB` | `#C9B6BA` | Human work and start states |
| Cotton Candy — Lavender | `#E0D4E7` | `#AFA3B6` | Business rules and Munich context |
| Cotton Candy — Ice | `#DBEEF7` | `#AABDC6` | Equipment work and TinyHouse context |
| Cotton Candy — Powder | `#BDD2E4` | `#8CA1B3` | Gateways and primary control flow |
| Cotton Candy — Rose | `#EECEDA` | `#BD9DA9` | Message catches and governance boundaries |
| Cotton Candy — Mist | `#CCDCEB` | `#9BABBA` | Send tasks and shared data paths |

## Orchestration Semantics

The TinyHouse owns the overall product instance. The Munich laboratory owns its printer and local handling work. No cross-site message contains a direct machine command.

| BPMN segment | Formal behavior | Main object state |
| --- | --- | --- |
| Register and select topology | A user task creates the run before a business rule selects `local` or `distributed` | Experiment run and work order become active |
| Negotiate remote lid | A send task starts the Munich process and a message catch waits for the decision | Commitment becomes accepted or rejected |
| Split production | A parallel gateway starts the base branch and remote-lid branch | Base component and lid component progress independently |
| Base quality | An exclusive gateway selects acceptance or human review | Base becomes accepted or receives a disposition |
| Delivery quality | An exclusive gateway selects delivery acceptance or replacement | Shipment and lid become reconciled or disputed |
| Parts ready | An exclusive base merge feeds a two-input parallel join | Both required component roles become available |
| Assemble and calibrate | Robot work precedes a user task and a service task | Product unit becomes assembled and calibrated |
| Share outcome | A data gateway applies disclosure only for an active collaboration | Munich receives a minimized terminal milestone |

## Choreography Contract

The choreography exposes only the interaction points. Local print tasks and local human tasks remain inside the orchestration model.

| Choreography task | Initiator | Message exchange | Result |
| --- | --- | --- | --- |
| Negotiate lid | TinyHouse | Remote lid request then commitment decision | Distributed or local route |
| Dispatch lid | Munich | Lid dispatch | Shipment becomes in transit |
| Confirm delivery | TinyHouse | Delivery decision | Delivery accepted or replacement required |
| Share outcome | TinyHouse | Minimized outcome | Collaboration reaches completion |

The replacement route returns to `Dispatch lid`. The loop creates a new component identity and print-job identity. The work-order identity and commitment identity remain stable.

## Data Conditions

Every exclusive split reads a versioned decision result. Each decision must emit a `Decision evaluated` event before the selected sequence flow fires.

| Gateway | Positive condition | Default condition |
| --- | --- | --- |
| Distributed? | `topology = 'distributed'` | Local production |
| Commitment accepted? | `commitmentStatus = 'accepted'` | Local production after rejection |
| Base passed? | `baseQuality = 'accepted'` | Human review |
| Base reprint? | `baseDisposition = 'reprint'` | Human release |
| Lid passed? | `lidQuality = 'accepted'` | Replacement request |
| Calibration passed? | `calibrationStatus = 'passed'` | Human resolution and rework |
| Shared run? | `collaborationStatus = 'active'` | Local completion without a remote outcome |

The model keeps experiment factors outside the BPMN expressions. The decision service records the factor values and writes the normalized result used by the gateway. This separation supports reproducible policy changes.

## Object-Centric Projection

One BPMN task can create several qualified object relations. The mapping below defines the minimum event projection.

| BPMN activity | OCEL activity | Required related objects |
| --- | --- | --- |
| Register run | `Register experiment run` | experiment-run as `output`; work-order as `output`; participant as `actor` |
| Request lid | `Request commitment` | work-order as `input`; commitment as `output`; component as `target` |
| Print base or lid | `Complete print` | print-job as `input`; component as `output`; equipment as `resource`; material-batch as `input` |
| Inspect base or lid | `Complete inspection` | inspection as `output`; component as `input`; data-asset as `evidence` |
| Dispatch lid | `Dispatch shipment` | shipment as `input`; component as `input`; participant as `actor` |
| Receive lid | `Receive shipment` | shipment as `input`; component as `output`; participant as `actor` |
| Robot kit | `Prepare assembly kit` | robot-job as `input`; product-unit as `target`; components as `input` |
| Assemble node | `Assemble product` | product-unit as `output`; components as `input`; human-task as `resource`; participant as `actor` |
| Test and calibrate | `Complete calibration` | calibration as `output`; product-unit as `input`; equipment as `resource` |
| Share outcome | `Disclose milestone` | work-order as `input`; disclosure-policy as `resource`; data-asset as `output` |

## Human Interaction

Human work remains explicit in the orchestration. The TinyHouse participant registers the run and resolves uncertain quality. The TinyHouse participant also receives the shipment and assembles the product. The Munich participant assesses the commitment and packs the lid.

| User or manual task | Required local control |
| --- | --- |
| Register run | Valid study role and consent state |
| Assess commitment | Verified capacity and material state |
| Review base or lid | Approved workpiece evidence and reason code |
| Receive lid | Shipment scan and custody confirmation |
| Pack lid | Component scan and seal confirmation |
| Release component | Named participant and recorded exception reason |
| Assemble node | Workcell readiness and task authorization |
| Approve deployment | Calibration result and local safety approval |

## Soundness Basis

The model targets workflow soundness under explicit operational assumptions. Soundness means that every modeled activity is reachable in some valid run. Soundness also means that every reachable route can reach a defined end state without leaving an enabled internal token.

The orchestration uses matched split and join semantics. The distributed route creates exactly two concurrent branches. The base alternatives merge through an exclusive gateway before the two-input parallel join. The local route bypasses the parallel region and merges after production.

The message protocol has balanced outcomes. A remote request always receives one commitment decision. Each dispatch always receives one delivery decision. An accepted delivery receives one minimized outcome. A rejected delivery returns both models to the dispatch interaction.

The soundness claim depends on four assumptions. The transport eventually delivers accepted messages. The receivers deduplicate repeated messages through stable correlation identifiers. Each human or machine task eventually returns a modeled result. A quality loop eventually selects an exit under the experiment protocol.

Permanent machine loss is outside the current formal model. A later fault model should add boundary events and a cancellation choreography. The current model represents temporary failure through reprint and rework loops.

## Correlation and Privacy

Every cross-site message needs stable correlation data. The minimum set is `experimentRunId`, `workOrderId`, `commitmentId`, and `messageId`. Dispatch and delivery messages also require `shipmentId` and `componentId`.

The choreography does not disclose participant identity. Human events use a site-local pseudonym in the local OCEL. The shared view uses a role code unless the approved study policy requires a stronger identifier.
