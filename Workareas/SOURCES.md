# Concept coverage and implementation decisions

The implementation/build plans use the complete `concepts` inventory below. Work-area card responsibilities and event labels take priority when older descriptive sources disagree. Reading a concept establishes its stated design; it does not establish that hardware is installed, calibrated or operational.

| Concept file | Review coverage and use |
| --- | --- |
| [`tinyhouse-workarea-cards.pdf`](../concepts/tinyhouse-workarea-cards.pdf) | All four pages read as text and visually by the hardware reviewer. Primary WA1–WA4 responsibilities, parts, expected events and acceptance records. |
| [`floorplans.pdf`](../concepts/floorplans.pdf) | All nine pages read visually by the hardware reviewer, with available text extracted. Dimensions and listed energy hardware support a measured-survey plan, not certified clearance or electrical design. |
| [`tables.png`](../concepts/tables.png) | Reviewed visually by the hardware reviewer for the four existing table shapes/dimensions. |
| [`resources/tables.drawio`](../concepts/resources/tables.drawio) | Complete editable table source inspected by the hardware reviewer; corroborates the table geometry, without establishing a station assignment. |
| [`tinyhouse-bayreuth-laboratory-concept.md`](../concepts/tinyhouse-bayreuth-laboratory-concept.md) | Complete hardware review: parts, layout, fixture allocation, signal requirements, safety and commissioning hold points. |
| [`Overview.md`](../concepts/Overview.md) | Complete integration review: exact energy formula and ordered decisions, evidence rules, MQTT contracts, OCEL relationships, failures, acceptance and privacy. |
| [`tinyhouse-bayreuth-floorplan.svg`](../concepts/tinyhouse-bayreuth-floorplan.svg) | Layout labels/geometry inspected; table positions, 207 cm rear table-free bay and nominal aisle retained as survey-dependent concept values. |
| [`distributed-process.svg`](../concepts/distributed-process.svg) | Every activity/flow label extracted and compared with the corresponding BPMN process source. |
| [`distributed-choreography.svg`](../concepts/distributed-choreography.svg) | Every collaboration label extracted and compared with the corresponding BPMN choreography. |
| [`bpmn/distributed-orchestration.bpmn`](../concepts/bpmn/distributed-orchestration.bpmn) | Complete XML parsed; all tasks, events, flows, conditions and identities inspected. Both site processes are descriptive, with `isExecutable="false"`. |
| [`bpmn/distributed-choreography.bpmn`](../concepts/bpmn/distributed-choreography.bpmn) | Complete XML parsed; five message contracts, commitment branch, delivery/replacement loop and outcome inspected. |
| [`example-ocel20.json`](../concepts/example-ocel20.json) | Complete JSON read: event/object types, time-varying attributes and qualified relationships. Illustrative data only; not measured runtime evidence or a complete authoritative-event schema. |
| [`object-centric-model.svg`](../concepts/object-centric-model.svg) | All object and relationship labels extracted; explicit run, order, physical, execution, quality and governance relationships retained. |
| [`monitoring-abstraction.svg`](../concepts/monitoring-abstraction.svg) | All L0–L5 labels inspected. Raw readings, state episodes, activities, site/collaboration milestones and experiment outcomes remain distinct. |
| [`orchestration-architecture.svg`](../concepts/orchestration-architecture.svg) | Every architecture label inspected: local adapters/safety, scheduler, local OCEL/outbox, shared object state and disclosure gateway. |
| [`privacy-boundaries.svg`](../concepts/privacy-boundaries.svg) | Every boundary label inspected. Raw process/energy evidence and direct identity remain local; disclosure controls partner/dataset/public views. |
| [`cpee-architecture/README.md`](../concepts/cpee-architecture/README.md) | Complete runtime interpretation and deployment decision review; compared against current CPEE gateway code. |
| [`cpee-architecture/system-overview.svg`](../concepts/cpee-architecture/system-overview.svg) | All labels extracted: C0 coordinator, C1–C4 work areas, C5 Munich, local MQTT/log and unassigned Pi roles. |
| [`cpee-architecture/wa-1-print-base.svg`](../concepts/cpee-architecture/wa-1-print-base.svg) | All labels extracted: printer/energy/thermal/camera/Hall/inspection, normalized evidence, state/fusion and callback boundary. |
| [`cpee-architecture/wa-2-kit-preparation.svg`](../concepts/cpee-architecture/wa-2-kit-preparation.svg) | All labels extracted: controller, bins/load cells/camera and independent guard/E-stop. |
| [`cpee-architecture/wa-3-assembly-test.svg`](../concepts/cpee-architecture/wa-3-assembly-test.svg) | All labels extracted: pressure/camera/jig/scale, explicit approval and independent jig electrical limits. |
| [`cpee-architecture/wa-4-control-lid.svg`](../concepts/cpee-architecture/wa-4-control-lid.svg) | All labels extracted: read-only PV/BMS, scale/camera/identity/management, scheduler and independent BMS protection. |

## Existing implementation reviewed for reuse

- [`cpee_orchestration`](../cpee_orchestration/README.md) already implements the durable Ruby parent/child gateway, state notifications/polling and asynchronous CPEE callbacks. Reuse this lifecycle boundary; do not create another child supervisor.
- [`extensions/sage`](../extensions/sage/README.md) provides serial pressure ingestion, calibrated-segment/classifier interfaces, candidate event mappings, MQTT scale compatibility and camera candidates. The current runtimes do not instantiate MSEG. MSEG itself maps individual sensor transitions; it does not implement the station evidence rules required for authoritative completion.
- [`bambu_printer_mqtt.py`](../modules/administration/scripts/bambu_printer_mqtt.py) is a real local MQTT discovery/subscription utility, not a verified job lifecycle adapter. It supplies no commissioning evidence for a particular installed printer.
- Existing PAROL6/Scotty, XIAO SCAM receiver, pressure firmware, sensor/network documentation and printed-fixture catalog inform the build plans; those plans link the relevant implementation and manufacturer references directly.

## Conflicts and resulting decisions

| Source issue | Decision and limitation |
| --- | --- |
| Overview runbook step 8 labels base inspection `ST-20`; cards, the physical WA table and CPEE WA1 drawing put base quality in WA1/ST-10. | Place base quality in WA1/ST-10, following the requested cards. WA4/ST-20 receives and verifies lids. |
| Overview proposes three shared Pi allocations; CPEE drawings show four `Pi-WA*` roles. | Use four logical WA service configurations. Physical Pi assignments are commissioning records; names or historical addresses are not claimed commissioned. |
| CPEE architecture README says the fragment gateway is missing. | Current Ruby gateway code is later implementation evidence and is reused. Its existence does not prove a live CPEE/Redis installation or real child workflows. |
| Holistic coordinator starts WA1/Munich in parallel with WA4 and lacks cross-fragment energy/receipt gates. | Station observations must preserve authorization and accepted-part correlation. Do not interpret the parent parallel shape alone as permission to print or assemble. |
| `Task_ProduceLocally` has no outgoing BPMN flow. | Direct local/fallback end-to-end execution remains blocked until its source route is deliberately completed and validated. |
| OCEL example uses different activity labels and lacks some authority metadata. | Keep the work-area cards' activity labels and explicit evidence/identity contract. The example guides OCEL structure rather than replacing the card contract. |
| OCEL example shows usable battery 1.4 kWh, forecast 1.3 kWh and available 2.5 kWh, without a committed-energy value. | Do not infer a measurement or threshold. The runtime requires committed energy explicitly and uses the exact Overview formula. |
| SAGE generates fallback calibration values and integer event counters, with QoS 0 publication. | Treat its output as candidates. No default threshold or SAGE transition alone establishes authoritative station completion. |
| Sensor/meter/ADC identities, inverter/BMS protocols, full DUT test method and accepted physical installation are missing. | Preserve explicit build/commissioning hold points. Do not invent pinouts, scientific test limits, machine commands or simulated production evidence. |

## Evidence still required

The source's physical/research acceptance gates remain external: real device identities and interfaces; safe mounting/electrical installation; measured standard/large/reprint energy and approved reserve/loss/battery limits; calibrated thresholds; versioned full DUT test/calibration procedure; clock offset at most 250 ms; at least 99% expected-message availability; held-out per-station macro F1 at least 0.90 with confusion matrix/unmatched-event counts; complete mandatory lifecycle evidence; no false completion or approval on negative runs; approved camera regions and retention.

Software tests establish only the exercised software behavior. No live site access, physical build, classifier validation or production run is claimed by this source review.
