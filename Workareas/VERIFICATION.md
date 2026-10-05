# Implementation and verification record

Recorded 2026-09-28. **Feasible with limitations:** the files and local software are implemented and tested; physical station operation remains partial because required device contracts, calibration inputs and the approved DUT procedure are absent. Nothing below claims a live TinyHouse production run.

## Requirement-to-evidence review

| Requirement | Status | Implementation evidence | Verification evidence |
| --- | --- | --- | --- |
| Top-level Workareas with WA1, WA2, WA3, WA4 | Implemented exactly | Four WA folders, each with main.py, README.md and BUILD.md | All four actual entry points started, returned authenticated station health, and stopped cleanly |
| Read every concepts file, especially the cards | Implemented exactly | SOURCES.md inventories all 22 files and records conflicts/decisions | Complete source review; all 4 card pages and all 9 floorplan pages visually inspected |
| Hardware connection and build plan for each WA | Implemented exactly as a plan; physical installation not verified | Each WA BUILD.md: parts, fixture links, wiring, bring-up and acceptance gates | Relative links checked; source/manufacturer pin references checked; no physical wiring test claimed |
| Code to run each physical workstation | Partial | Four runnable evidence services, shared real Nano capture, energy calculations and MQTT delivery | Four startup smoke checks, real HTTP and MQTT checks, real pyserial/OS-PTY check; other physical adapters remain missing |
| Emit abstracted process events for card activities | Implemented exactly at the normalized-evidence boundary; device-to-event path partial | rules.py covers all 26 exact card activity labels and specified independent evidence; events.py creates durable correlated lifecycle events | 62-test suite including all-activity positive paths, missing sources, wrong identities, stale/conflicting records, faults and rework/approval history |
| Exact energy policy and fresh start/reprint checks | Implemented exactly as pure calculations | energy.py: available_renewable_energy, evaluate_schedule, authorize_print, authorize_reprint | 17 tests: formula, zero floor, inclusive thresholds, standard upper bound, ordering/objectives, units, freshness, resources, windows and authorization |
| Durable local event delivery, unique IDs and QoS1/nonretained publication | Implemented exactly at the broker acknowledgment boundary | SQLite transaction/outbox in events.py; MqttDelivery in mqtt_delivery.py | Restart/idempotency tests, six transport tests and real authenticated TLS broker PUBACK; wrong password retained outbox |
| Typed modular Python, configuration-only main.py and no new CLI | Implemented exactly in changed scope | Dataclasses, focused shared modules, entry-point configuration and stdlib unittest | Strict mypy passed all 21 Python files; Ruff and compilation passed; function annotation/docstring scan passed |
| Preserve unrelated changes | Implemented exactly | Changes created only within Workareas/ | Final repository status compared with initial status; existing assets, CAD, tests, root main.py and docs/sensors edits preserved |

## Implemented

- Each WA has a build/wiring plan, implementation runbook and entry point. Shared documents specify event contracts, source decisions and physical/research acceptance.
- Authenticated loopback JSON ingestion checks source assignment, health, confidence, timestamps, required object identity and independent observations. Missing/conflicting evidence stays unknown and produces a local diagnostic; real faults have explicit failure lifecycles.
- SQLite keeps accepted/rejected evidence and event/outbox state. Identical retries retain event identity; changed observations cannot silently repeat an already recorded operation completion.
- Deployment approval requires the latest appropriate passing history for the same run/order/product, with unchanged procedure/calibration records and no intervening failure or rework.
- Candidate output is isolated from authoritative topics. A real commissioning-report reference and all documented numerical/approval gates are required to enable authority. Entering those fields does not itself prove empirical validation.
- Nano acquisition reads the actual existing P1/P2 serial protocol; the new path preserves raw data and explicit diagnostics without fabricating calibrated force or process meaning.

## Commands and checks actually executed

The temporary Python 3.11 environment was `/tmp/tinyhouse-workareas-venv`. It contains Paho, pyserial, mypy, Ruff and pyserial stubs; aMQTT was added only for the ephemeral real-broker check, not as an application dependency.

| Command/check | Final result | What it establishes |
| --- | --- | --- |
| `/tmp/tinyhouse-workareas-venv/bin/python -m unittest discover -s Workareas/tests -v` | **62 tests passed** | Changed-scope rule/calculation/persistence/HTTP/parser/transport behavior; synthetic data is explicitly test-only |
| `/tmp/tinyhouse-workareas-venv/bin/python -m mypy --strict --explicit-package-bases Workareas` | Passed: 21 source files | Static type consistency in implementation and tests |
| `/tmp/tinyhouse-workareas-venv/bin/python -m ruff check Workareas` | Passed | Applicable inherited lint checks |
| `/tmp/tinyhouse-workareas-venv/bin/python -m compileall -q Workareas` | Passed | Python syntax/import compilation; not hardware operation |
| `/tmp/tinyhouse-workareas-venv/bin/python /tmp/workareas_entrypoint_check.py` | WA1–WA4 passed | Actual module startup, random token generation, authenticated localhost health and clean shutdown; temporary state removed |
| `/tmp/tinyhouse-workareas-venv/bin/python /tmp/workareas_mqtt_tls_check.py` | Passed | Real temporary TLS broker, verified certificate, username/password, QoS1 PUBACK; wrong password kept durable outbox |
| `/tmp/tinyhouse-workareas-venv/bin/python /tmp/workareas_serial_pty_check.py` | Passed | Actual pyserial reads against an OS pseudo-terminal, timeout/disconnect, Ctrl+C and append preservation; no physical Nano |
| `git diff --check` plus explicit new-file whitespace/local-link scan | Passed after this report was added | Tracked diff whitespace and newly created Markdown references/whitespace |
| Python AST scan of Workareas Python files | Passed | Authored functions have docstrings and parameter/return annotations; literal declaration scan found no untyped declarations |
| `rg -n 'TODO\|FIXME\|NotImplementedError\|except Exception\|\blambda\b\|\bpass\b\|mock\|stub\|simulat' Workareas --glob '*.py'` | Reviewed | No production placeholder handlers or broad swallowed exceptions; mocks are confined to explicitly labelled unit tests |
| Final file/diff/status inspection | Passed | Only the new Workareas tree belongs to this task |

The temporary integration scripts are local verification artifacts, not installed production components or runtime data. Their broker credentials/certificates and serial payloads are test-only. Local MQTT round-trip does not establish production broker ACLs or downstream consumer behavior.

### Test-first and intermediate failures

Initial event, HTTP, energy, serial and MQTT test runs failed because their new implementation modules did not yet exist. The same tests passed after implementation. Independent rule/history tests then reproduced real defects before fixes: a four-bin assumption, rejecting a genuinely wrong lid before its rejected verification could be recorded, cross-run/order approval, altered procedure/reference reuse, duplicate completion and late pre-rework passes, plus an extra-record validation bypass. Those regressions pass in the final suite.

Initial HTTP socket binding and dependency downloads were blocked by sandbox restrictions; the authorized isolated downloads and localhost tests succeeded when run with the required tool permissions. Initial lint/type errors were corrected before final checks. No final test failure is left undisclosed. No unrelated repository suite is described as having passed; existing application/build code outside Workareas was unchanged.

## Deviations

No specified algorithm, physical part or approved test method was replaced with a heuristic, fake integration or fabricated output. The software uses the requested card labels where older concept sources disagree; SOURCES.md makes those decisions explicit. Missing physical/device capabilities remain partial or blocked rather than being silently substituted.

The configurable 30-second evidence freshness default is a software starting point, not a measured acquisition parameter. Logical source names, WA ports and a local development API are implementation choices; physical Pi/broker assignments and calibrated thresholds remain commissioning inputs.

## Not verified

No connected printer, PAROL6, Nano, scale, camera, thermal array, energy meter, inverter or BMS was available for physical acceptance. The tests cannot establish electrical compatibility, mechanical fit, machine safety, signal units from a real instrument, accuracy/calibration, held-out macro-F1, message availability during production, actual clock offsets, camera privacy, measured energy/reserve, or a completed product.

No live CPEE/Redis station callback or executable child workflow was tested. Those adapters/fragments are not implemented here. The descriptive source's local fallback path remains incomplete. No OCEL exporter, cross-site disclosure sender, forecast service, energy reservation transaction or remote recipient behavior is claimed implemented.

## Remaining issues and inputs

1. Supply and verify actual hardware models, asset assignments, interfaces, firmware schemas, units and calibration references. Build real normalized acquisition adapters for printer/controller/meter/thermal/camera/bins/scale/identity and management records.
2. Provide the complete approved WA3 DUT schematic/pinout, voltage/current limits, scientific test/calibration steps, formulas/tolerances, references and procedure version before jig firmware/test execution can be implemented correctly.
3. Establish read-only inverter/BMS acquisition, candidate forecasts, loss model, measured print profiles and approved protected reserve. Serialize shared reservations externally so concurrent accepted jobs cannot spend the same budget.
4. Complete physical/research commissioning before enabling authority. Unit fixtures, a populated Commissioning dataclass or broker delivery do not replace that evidence.
5. Implement the actual cross-site disclosure/delivery service and station CPEE observer/callback/child workflows; preserve required authorization and accepted-parts dependencies.
6. Set archive/retention/backup/storage monitoring before long runs. JSONL capture flushes but does not fsync every record; the event outbox uses SQLite durability. Paho shutdown may wait for an OS DNS lookup already in progress; the HTTP loop itself does not wait for broker DNS.

## Changed files

Created only the `Workareas/` tree: four `BUILD.md`, four station `README.md`, four station `main.py`, WA4 energy guide; root entry point/setup/event/commissioning/source/serial/verification documents; eight focused shared Python modules; seven test modules; the serial-capture entry point; scoped requirements/dev requirements and local-data ignore rules. No existing repository file was modified or deleted by this task.
