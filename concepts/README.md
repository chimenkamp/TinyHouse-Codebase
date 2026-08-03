# Distributed Process Laboratory Concept Pack

## Outcome

This concept pack defines a two-site real-world laboratory for distributed object-centric process mining. The proposed demonstrator produces a configurable sensor node. The TinyHouse and the Munich laboratory manufacture different components in parallel. Robot arms perform handling and inspection tasks. Human participants perform setup, assembly, quality control, and exception work.

The design keeps machine control local to each site. A cross-site coordinator exchanges task commitments and privacy-minimized events. The design does not require an external MQTT bridge. Each site can continue safe local work during a network interruption.

## Recommended Demonstrator

The recommended product is a **Distributed Adaptive Sensor Node**. The product contains a printed enclosure base, a printed lid or mount, an electronics kit, and one or more sensors. The product receives a QR identity at creation. The completed node remains in the TinyHouse and generates lifecycle telemetry after manufacturing.

The demonstrator creates useful object interactions. One work order creates several print jobs. Several components converge into one product. One shipment can contain several components.

The quality paths add controlled complexity. One inspection can cover a batch. Failed inspections create reprint or rework loops. Human tasks and machine tasks can overlap.

## Pack Contents

| File | Purpose |
| --- | --- |
| [01-demonstrator.md](01-demonstrator.md) | Product scenario and end-to-end distributed process |
| [02-object-centric-process-model.md](02-object-centric-process-model.md) | Object types, relations, activities, lifecycles, and constraints |
| [03-orchestration-and-monitoring.md](03-orchestration-and-monitoring.md) | Local orchestration, cross-site choreography, event ingestion, and monitoring |
| [04-privacy-safety-governance.md](04-privacy-safety-governance.md) | Privacy, safety, access, retention, and research governance |
| [05-experiment-program.md](05-experiment-program.md) | Research questions, controlled variants, fault injection, and evaluation |
| [06-hardware-roadmap.md](06-hardware-roadmap.md) | Verified baseline, unverified inventory, and low-cost additions |
| [07-implementation-roadmap.md](07-implementation-roadmap.md) | Phased delivery plan and acceptance gates |
| [08-bpmn-models.md](08-bpmn-models.md) | Formal BPMN orchestration, choreography, interaction contracts, and soundness basis |
| [data-contract.md](data-contract.md) | Event envelope, MQTT namespace, object identifiers, and quality rules |
| [example-ocel20.json](example-ocel20.json) | Small OCEL 2.0 JSON example for the demonstrator |
| [distributed-process.svg](distributed-process.svg) | Visual rendering of the BPMN orchestration |
| [distributed-choreography.svg](distributed-choreography.svg) | Visual rendering of the BPMN choreography |
| [object-centric-model.svg](object-centric-model.svg) | Object and relationship model |
| [orchestration-architecture.svg](orchestration-architecture.svg) | Federated orchestration and data architecture |
| [monitoring-abstraction.svg](monitoring-abstraction.svg) | Telemetry-to-process abstraction model |
| [privacy-boundaries.svg](privacy-boundaries.svg) | Data zones and disclosure boundaries |
| [distributed-orchestration.bpmn](bpmn/distributed-orchestration.bpmn) | Editable BPMN 2.0 collaboration source |
| [distributed-choreography.bpmn](bpmn/distributed-choreography.bpmn) | Editable BPMN 2.0 choreography source |

## Model Set

| Model view | Primary question | Operational use |
| --- | --- | --- |
| Collaboration model | Which site or actor owns each activity? | Coordination and responsibility assignment |
| Object-centric process model | Which objects interact in each event? | Discovery, conformance, and multi-object analysis |
| Object lifecycle model | Which state changes are valid for each object type? | Runtime validation and alerting |
| Decision model | Which measured conditions select each variant? | Reproducible routing and experiment control |
| Monitoring abstraction model | Which raw signals become process events? | Live monitoring without telemetry overload |
| Privacy model | Which data may leave each trust zone? | Data minimization and collaboration governance |
| Safety model | Which actions require a local interlock or human approval? | Safe machine execution |

## Source Basis

The source basis is the current `docs/` folder and the user-supplied laboratory description. The Markdown documentation confirms the network, management PC, Raspberry Pi broker nodes, Jetson edge computers, Arduino-class sensor boards, weight sensors, a network scale, cameras, and MQTT services. The user confirms a robot arm and a 3D printer in each laboratory.

The existing [image.png](image.png) shows an earlier cocktail-robot concept. The new demonstrator preserves the useful ideas of service orientation and process orchestration. The new demonstrator adds distributed manufacturing, object-centric logging, controlled variants, privacy, and research evaluation.

## Evidence Labels

The pack uses four evidence labels.

| Label | Meaning |
| --- | --- |
| `Documented` | The Markdown documentation states the capability or device. |
| `User-confirmed` | The current request states the capability or device. |
| `Image-observed` | A repository image shows the item but the text does not confirm its operational state. |
| `Proposed` | The concept introduces the capability or device. |

## Important Limitations

The robot-arm models and printer models are not documented. The concept therefore uses capability-level adapters. A later integration step must record each machine interface, work envelope, safety mode, controller protocol, and supported commands.

The workbook `docs/EDV TinyHouse.xlsx` was not inspected. The required spreadsheet runtime was unavailable in the current environment. Hardware details that exist only in that workbook remain unverified.

The current Arduino-to-Pi receiver is incomplete. The current broker estate also mixes Mosquitto and EMQX. The roadmap treats both gaps as prerequisites for reliable experiments.

## External Standards and Product Sources

- [OCEL 2.0 overview](https://www.ocel-standard.org/) defines events, objects, object relationships, and qualified event-to-object relationships.
- [OCEL 2.0 JSON format](https://www.ocel-standard.org/specification/formats/json/) defines the exchange structure used by the example log.
- [Object-centric Petri-net discovery paper](https://arxiv.org/abs/2010.02047) motivates models that combine several object types without selecting one case identifier.
- [OPC UA companion specification overview](https://opcfoundation.org/about/opc-technologies/opc-ua/ua-companion-specifications/) provides a future interoperability path when machine controllers support OPC UA.
- [BPMN 2.0.2](https://www.omg.org/spec/BPMN/2.0.2/) defines the orchestration, collaboration, choreography, and Diagram Interchange elements used by the formal models.
- [chor-js](https://github.com/bptlab/chor-js) provides a BPMN 2.0 choreography editor based on bpmn-js.
