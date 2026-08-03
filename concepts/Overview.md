# Distributed Process Laboratory Overview

## Goal

The laboratory generates real distributed process data for object-centric process mining. The TinyHouse and a Munich research laboratory execute one physical process together. Each site uses a 3D printer and a robot arm. Human participants perform selected production, inspection, handover, and exception tasks.

The laboratory also supports live monitoring. Raw machine and sensor data become object states, activities, site milestones, collaboration milestones, and experiment outcomes. Privacy-minimized events can cross the site boundary while raw evidence stays local.

## Demonstrator

The recommended product is a **Distributed Adaptive Sensor Node**. The product contains a printed enclosure base, a printed lid or mount, an electronics kit, and one or more sensors. Every work order, component, shipment, task, and product receives a stable identifier.

The nominal process follows this path:

1. A researcher registers an experiment and work order.
2. The TinyHouse prints the enclosure base.
3. The Munich laboratory prints the lid or mount in parallel.
4. Each site inspects its printed component.
5. Munich packs and ships the accepted component.
6. The TinyHouse receives and reconciles the shipment.
7. A robot prepares the assembly kit.
8. A human and robot assemble the sensor node.
9. The TinyHouse tests and calibrates the node.
10. A human approves deployment.
11. The deployed node generates lifecycle and maintenance data.

## Formal Process Models

The orchestration model contains the private control flow for both laboratories. Human work uses BPMN user and manual tasks. Machine work uses service tasks. Business rules select the topology and quality routes.

![BPMN orchestration](distributed-process.svg)

The choreography model contains only the cross-site contract. The TinyHouse initiates the lid negotiation. Munich initiates dispatch. The TinyHouse initiates the delivery decision and final minimized outcome.

![BPMN choreography](distributed-choreography.svg)

The editable sources are [distributed-orchestration.bpmn](bpmn/distributed-orchestration.bpmn) and [distributed-choreography.bpmn](bpmn/distributed-choreography.bpmn). The [BPMN model guide](08-bpmn-models.md) defines every gateway condition, message contract, object projection, visual convention, and soundness assumption.

The distributed route contains one matched parallel region. Base production and remote lid delivery run concurrently. An exclusive merge combines the base-quality alternatives before the two-input parallel join. Delivery rejection returns both formal views to the dispatch interaction.

## Object-Centric Model

The canonical research log uses OCEL 2.0 concepts. Events link to several typed objects through explicit qualifiers such as `input`, `output`, `resource`, `actor`, `container`, and `evidence`. The model does not force every event into one case identifier.

| Object group | Main object types |
| --- | --- |
| Control | Experiment run, work order, commitment, incident |
| Physical | Product unit, component, material batch |
| Execution | Print job, robot job, human task |
| Quality | Inspection, calibration |
| Logistics | Shipment |
| Resources | Equipment, station, participant |
| Information | Design revision, data asset, dataset manifest |
| Governance | Consent record, disclosure policy |

The main synchronization occurs during assembly. One product requires accepted components from both sites. A failed component remains traceable while a reprint receives a new component identity. A shipment can contain several components from several work orders.

![Object-centric process model](object-centric-model.svg)

## Federated Orchestration

Machine control remains local to each laboratory. A site orchestrator manages local printer, robot, sensor, and human tasks. A collaboration coordinator exchanges commitments, deadlines, object identifiers, and process milestones. The coordinator never sends direct robot motion or printer-heater commands.

Each site keeps an append-only event outbox. Local work can continue during a cross-site network interruption. Late events retain their occurrence time, observation time, source sequence, and clock-quality information.

The cross-site channel uses an approved application gateway. The architecture does not require an external MQTT bridge. Every shared event passes a versioned disclosure policy.

![Federated orchestration architecture](orchestration-architecture.svg)

## Data-Driven Variants

Every route decision creates a process event. The event records the policy version, input snapshot, eligible options, selected option, and reason code.

| Condition | Possible process change |
| --- | --- |
| Printer queue or failure | Move the print job to the other site |
| Material unavailable | Delay or reroute production |
| Inspection uncertainty | Create a human review task |
| Inspection failure | Rework or create a replacement component |
| Robot unavailable | Use an approved human fallback |
| Shipment batch available | Combine several components in one shipment |
| Network unavailable | Continue locally and synchronize later |
| Minimal privacy profile | Share only role-level and derived data |
| Calibration drift | Recalibrate, repair, or replace the node |

The experiment controller supports controlled factor changes. The factors include production topology, shipment policy, inspection mode, event delay, clock offset, privacy profile, workload, human availability, and policy version. Safe fault injection occurs above the machine-safety layer.

## Monitoring and Abstraction

The monitoring pipeline separates process events from high-volume telemetry. Raw samples remain evidence. Higher levels represent meaningful state changes and collaboration outcomes.

| Level | Meaning | Example |
| --- | --- | --- |
| L0 | Raw signal | Temperature sample or scale reading |
| L1 | State episode | Printer heating or robot blocked |
| L2 | Activity instance | Complete print or receive shipment |
| L3 | Site milestone | Component accepted |
| L4 | Collaboration milestone | Shipment reconciled |
| L5 | Experiment outcome | Run complete with quality score |

Live monitoring needs several coordinated views. The views should cover object location, commitment status, resource readiness, human tasks, conformance, data quality, privacy state, and remaining-time predictions. Every derived state should show its confidence, freshness, source time, and policy version.

![Monitoring abstraction model](monitoring-abstraction.svg)

## Human Interaction Privacy and Safety

Human interaction remains visible in the process model. Humans select product configurations, load materials, review uncertain inspections, install electronics, transfer custody, resolve exceptions, and approve deployment. Shared process data uses a participant role or study pseudonym by default. Direct identity remains in a separate local identity vault.

Raw video remains local by default. Workpiece cameras should exclude faces and unrelated areas. The research pipeline should store derived inspection results instead of continuous media when the experiment permits that approach.

Safety functions remain local and independent from research orchestration. No experiment may disable emergency stops, guards, thermal limits, safe-speed modes, or manufacturer safety checks.

![Privacy and safety boundaries](privacy-boundaries.svg)

## Existing Hardware Basis

The documented TinyHouse baseline spans several hardware layers. The baseline includes a management PC with WSL, Raspberry Pi broker nodes, Jetson edge computers, Arduino-class boards, ESP scale boards, weight sensors, a network scale, cameras, MQTT services, and a broad sensor-module kit. The user confirms a robot arm and a 3D printer in each laboratory.

The first pilot should use QR labels and existing sensors. Optional low-cost additions include load-cell amplifiers, compact ESP32 camera boards, and a dedicated workpiece camera. RFID should follow only when QR limitations are measured.

## Required Preparation

The following work should precede joint experiments:

- Inventory both robot arms and both printers.
- Record controller interfaces and validated programs.
- Complete the Arduino-to-Pi receiver.
- Standardize the TinyHouse MQTT broker role.
- Add authentication and topic authorization.
- Approve the cross-site gateway and data-sharing agreement.
- Define exact camera zones and retention periods.
- Validate one manual object-centric run before machine automation.

## First Joint Milestone

The first joint milestone is one nominal split build. Munich prints and ships the lid. The TinyHouse prints the base and completes assembly. Both sites reconstruct the same shared object state. The final OCEL contains the complete custody chain, qualified object relations, decision evidence, human tasks, and privacy transformation record.
