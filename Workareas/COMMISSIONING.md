# Commissioning and build release

This is a checklist to complete with physical evidence; no item is asserted complete by the software tests. A failed gate stops the affected workarea. Retain results against the exact hardware, firmware, adapter, fixture and policy versions.

| Gate | Evidence to record | Acceptance |
| --- | --- | --- |
| Site survey | Dimensions, openings, table ratings, printer clearances, cable paths, ventilation, robot envelope | Approved measured layout; rear bay and route remain clear |
| Asset allocation | WA, model, serial, firmware, power, network/USB identity, owner, channel | Every role in the station `SOURCE_IDS` maps to an inspected asset/adapter |
| Independent safety | Guard/E-stop/reset, robot mount, electrical protection, printer fire/thermal/ventilation controls, BMS protection | Approved independently of research software |
| Raw signals | Actual samples, units, cadence, valid range, timestamps, tare, calibration references, disconnect/reconnect and corrupt input | No invented units; invalid/missing states are observable |
| Sensor abstraction | Ground truth for idle/start/complete/reject/rework/conflict/disconnect; training and separate validation runs | Per-station macro-F1 ≥ 0.90; confusion matrix and unmatched-event count retained |
| Lifecycle coverage | Machine and human start/complete/accept/reject/approval records | 100% mandatory events; zero false completion/approval in negative scenarios |
| Data quality | Expected and received message counts for each activity interval, measured clock offsets | At least 99% availability; at most 250 ms clock offset |
| Privacy | Approved camera ROI, manual frame sample, retention, local access, disclosure fields | No faces/unrelated areas in sample; raw video and energy local by default |
| Energy | Actual standard/large profiles, loss model, battery limits, protected reserve approval | Large estimate > standard; no fictitious capacity/reserve values |
| Integrated run | Local and distributed routes including every exception | Motion-disabled observation run first, then approved physical run; no simulated station in an accepted experiment |

## Build order

1. Complete the site/asset/safety gates and print only dimension-verified, non-safety fixtures already catalogued under `assets/3D/Workareas`.
2. Assemble low-voltage sensing using each [WA build plan](README.md). Verify one channel at a time, starting with real raw readout, before connecting its derived events to anything.
3. Establish the private Ethernet network, one authenticated broker, clock synchronization and per-WA local storage. Back up the broker/configuration and event stores under the approved retention policy.
4. Record calibrated baseline, positive/negative examples and disconnect/conflict behavior. Validate the real device protocols and normalize their records to [EVENTS.md](EVENTS.md).
5. Run candidate mode during training and held-out validation; inspect false positives and missing events. Synthetic test fixtures are never empirical validation data.
6. Fill a `Commissioning` record only from accepted results. An approver and report path are required; neither a passing unit suite nor a successful process exit justifies authority.
7. Connect authoritative events to CPEE observation callbacks only after correlated timeout/retry tests. Test MQTT interruption, service restart, and consumer deduplication by stable event ID.

## Required negative scenarios

| Scenario | Expected outcome |
| --- | --- |
| Sensor unplug, stale timestamp, malformed frame, wrong source, duplicate sequence | Unknown/rejection or acquisition diagnostic; no completion |
| Printer says running/fault while completion is requested | No print completion; retain conflicting records for review |
| Controller success with wrong/missing bin delta or no kit | No kit completion |
| Controller fault with a visible kit | Fault remains a fault |
| Base/lid ID, revision or size mismatch | No assembly completion or delivery acceptance; record rejected verification/replacement |
| Test/calibration missing, failed or superseded by rework | No deployment approval |
| Energy unavailable, snapshot stale, print starts outside authorized window | Wait/deny; no fabricated permit |
| Munich commitment rejected | Local fallback decision and a new energy schedule for local workload |
| Broker unavailable or process restarted before ACK commit | Evidence/event retained; retry uses same event ID |
| Disclosure denied, payload changed, partner ACK missing | No `Share outcome` completion |

## Still required before hardware-specific code

Record the exact interface documentation for the plug meter, scale/ADC/HX711 carrier if selected, MLX90640 carrier, printer lifecycle schema and robot job protocol. For Growatt/BMS record model, firmware, read-only transport, register map, signedness/scaling, units, operating limits and timestamp behavior. For WA3 provide DUT schematic/pinout, safe voltage/current, complete test steps, reference loads, tolerances, fit/calibration method, pass/fail limits and procedure version. The code intentionally does not invent these facts.
