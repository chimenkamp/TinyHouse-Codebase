# CPEE / WEEL architecture set

These five SVGs describe the target deployment. They intentionally use direct labels instead of page titles, legends, headers, or footers.

- [System overview](system-overview.svg)
- [WA-1 · Print / base quality](wa-1-print-base.svg)
- [WA-2 · Kit preparation](wa-2-kit-preparation.svg)
- [WA-3 · Assembly / test](wa-3-assembly-test.svg)
- [WA-4 · Control / lid](wa-4-control-lid.svg)

## Runtime interpretation

CPEE is the REST, persistence, callback, and event layer around WEEL. A CPEE node is the persistent service deployment. A workflow instance is one run-specific process: CPEE transforms the XML description into WEEL, creates `Instance < WEEL`, and starts that instance in its own OS process.

WEEL owns executable control flow: sequence, service `call`, data manipulation, parallel branches, choices, and loops. Logical endpoint names keep device addresses out of the process model. CPEE's connection wrapper resolves those endpoints and sends HTTP requests with instance, activity, and callback correlation headers.

The local observation contract uses the supported asynchronous activity pattern:

```text
WEEL call → WA API → CPEE-CALLBACK: true
                         ↓
sensor → driver → normalize → state/fusion
                         ↓
                 callback PUT → WEEL resumes
```

`wait_for_signal` is not used as a general sensor API. The inspected WEEL implementation couples it to signaling inside a parallel construct. Raw GPIO, camera, serial, and MQTT samples remain outside WEEL.

## Target topology

The phrase “one controller and five subinstances” is interpreted as six workflow instances per distributed run:

```text
C0 · Munich coordinator
├── C1 · WA-1
├── C2 · WA-2
├── C3 · WA-3
├── C4 · WA-4
└── C5 · Munich lid fragment
```

CPEE and WEEL do not provide a native five-child supervision primitive. The orange fragment gateway in the overview is therefore a required application component. It creates and starts a child through the remote CPEE REST API, stores parent/child/case correlation, reconciles retries and WAN outages, and completes the parent activity through the supplied CPEE callback URL.

The CPEE `remote` instance attribute is deliberately not used. It copies and starts one runtime worker with SSH while retaining the originating server configuration; it does not create an autonomous child CPEE node.

## Workstation boundary

Each target `Pi-WA*` role contains a local CPEE node, Redis/event support, the run-specific WEEL fragment, device drivers, and a long-lived WA abstraction service. The abstraction path is:

```text
Drivers → Normalize → State / fusion → WA API → CPEE callback
```

The normalized evidence contract must include source identity, source and ingestion time, health, freshness, quality, sequence, and run/work-order correlation. A disconnected, stale, invalid, or conflicting input becomes `unknown`; it cannot silently complete an activity.

Command endpoints and observation endpoints remain separate. Printer interlocks, the PAROL6 guard/E-stop, test-jig electrical limits, and BMS protection remain local and independent of CPEE. CPEE events may feed audit and monitoring, but they are not safety control.

## Evidence versus target design

| Item | Repository evidence | Architecture status |
| --- | --- | --- |
| REST instance lifecycle | [`CPEE/lib/engine.xml`](../../CPEE/lib/engine.xml) | Implemented by CPEE |
| XML/DSLX to WEEL generation | [`CPEE/server/executionhandlers/ruby/execution.rb`](../../CPEE/server/executionhandlers/ruby/execution.rb), [`instance.template`](../../CPEE/server/executionhandlers/ruby/backend/instance.template) | Implemented by CPEE |
| HTTP activity metadata and callback URL | [`CPEE/server/executionhandlers/ruby/connection.rb`](../../CPEE/server/executionhandlers/ruby/connection.rb) | Implemented by CPEE |
| Endpoints, calls, parallelism, choices, loops | [`weel/lib/weel.rb`](../../weel/lib/weel.rb) | Implemented by WEEL |
| Driver → adapter → classifier → event prototype | [`extensions/sage/README.md`](../../extensions/sage/README.md) | Partial prototype |
| Multi-sensor authoritative fusion | [`concepts/Overview.md`](../Overview.md) | Target; not active in the current runtime |
| C0 parent/child gateway | No implementation found in CPEE or WEEL | Required new component |
| Four `Pi-WA*` host assignments | [`docs/infrastructure/raspberry-pis.md`](../../docs/infrastructure/raspberry-pis.md) | Target roles; physical mapping unassigned |
| Fragmented executable process models | [`distributed-orchestration.bpmn`](../bpmn/distributed-orchestration.bpmn) | Required; current BPMN is descriptive (`isExecutable="false"`) |

The analysis was performed against CPEE commit `da2303e97760` and WEEL commit `292cec1dbc92`.

## Deployment decisions still open

- Select and benchmark the Raspberry Pi model, CPEE execution handler, and evaluator service.
- Assign `Pi-WA1` through `Pi-WA4` to physically verified inventory devices.
- Choose one authenticated local MQTT broker; the documented fleet currently mixes EMQX and Mosquitto.
- Implement the Nano/serial receiver, non-pressure sensor adapters, evidence fusion, WA API, and fragment gateway.
- Put the cross-site gateway behind authenticated TLS over a site-to-site VPN. No complete engine-level authentication or TLS enforcement was found in the inspected CPEE paths.
- Fragment the descriptive BPMN into six executable CPEE descriptions and define timeout, retry, idempotency, and reconciliation behavior.
