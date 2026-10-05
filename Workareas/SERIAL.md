# Nano USB acquisition

This is a runnable acquisition path for the existing firmware at
[`extensions/sage/arduino/sensor_sketch/sensor_sketch.ino`](../extensions/sage/arduino/sensor_sketch/sensor_sketch.ino).
It records observations and transport diagnostics. A voltage observation is
not an abstract process event. No tool, material, test result, or completion is
inferred by this application.

The deployed sketch provides exactly two channels:

| USB payload ID | Nano input | Firmware payload | Sampling |
| --- | --- | --- | --- |
| P1 | A0 | `P1,<voltage V>,<resistance kΩ>` | Once per loop |
| P2 | A1 | `P2,<voltage V>,<resistance kΩ>` | Once per loop |

The firmware waits 500 ms after each pair and uses 9600 baud. Its computation
assumes a 5.0 V ADC reference and a **510 kΩ** fixed resistor. This is the literal
value and unit in the source, not a verified measurement of the installed
resistor. Do not read it as 510 Ω or assume that the resulting resistance is a
calibrated force measurement. The physical resistor, divider orientation,
sensor model, board variant, and ADC reference must be checked at the bench.

The equation `R_sensor = R_fixed × 5.0 / Vout − R_fixed` corresponds to a sensor
between 5 V and the analog input with the fixed resistor between that input and
GND. This wiring is inferred from the equation; inspect the installed circuit
before powering it. The Pi receives the Nano data over USB. Do not connect a
5 V analog output directly to a Pi GPIO input. These two channels are not a
general replacement for the workstation sensor inventory.

## Run on the Raspberry Pi

Use Python 3.11 or newer, from the repository root. A virtual environment with
`pyserial>=3.5,<4` is sufficient for this acquisition application; the parser and
unit tests use the standard library only.

```bash
python3.11 -m venv /tmp/tinyhouse-workareas
/tmp/tinyhouse-workareas/bin/python -m pip install 'pyserial>=3.5,<4'
ls -l /dev/serial/by-id/
```

Set `WORKAREA_SERIAL_PORT` to the exact `/dev/serial/by-id/` path shown for the
intended Nano. Set `WORKAREA_ID` to `WA1`, `WA2`, `WA3`, or `WA4`, and set
`WORKAREA_SOURCE_ID` to the unique device label attached to that Nano. These are
required inputs; no device or workstation is automatically guessed. The
application deliberately reconnects only the configured port. If a board has no
unique USB serial number, bind its physical USB connection with a suitable
udev rule and document the mapping before deployment.

After exporting those three environment variables, run:

```bash
/tmp/tinyhouse-workareas/bin/python -m Workareas.tools.serial_capture.main
```

For an append-only JSONL capture using shell redirection:

```bash
mkdir -p Workareas/captures
/tmp/tinyhouse-workareas/bin/python -m Workareas.tools.serial_capture.main >> Workareas/captures/nano.jsonl
```

The entry point only constructs `SerialCaptureConfig` and starts the application.
For a configured file destination without shell redirection, set the dataclass's
`output_path` to a `pathlib.Path` in that entry point. `run_capture()` opens that
path in append mode and creates its parent directories. File failures propagate
and stop capture; they are not mislabeled as device disconnects. Stop with
Ctrl+C. Give the runtime user access to the selected serial device under the
Pi's configured permissions, and close other programs that hold the same port.

## Record meaning

Every record includes:

| Field | Meaning |
| --- | --- |
| `record_type` | `observation` or `diagnostic`; neither is a process event |
| `workstation`, `source_id` | Operator-configured placement and device identity |
| `session_id` | New UUID for each open/reconnect attempt |
| `sequence` | Increasing edge record counter within that session, starting at 1; includes diagnostics |
| `source_timestamp` | UTC time when a serial read completed on the Pi |
| `timestamp_quality` | Always `edge_ingest`; no Nano measurement clock is available |
| `status` | Acquisition outcome described below |

Observation records preserve `sensor_id`, `raw_line`, `voltage_v`, and
`resistance_kohm`. The firmware's `-1` resistance sentinel becomes JSON `null`
with status `resistance_unavailable`; the raw line retains the original value.
A normal parsed observation has status `valid`. Neither status establishes
physical sensor health. An unloaded FSR, a broken connection, and a saturated
circuit cannot be distinguished reliably by this wire protocol alone.

Diagnostics cover `connected`, `connection_failed`, `serial_timeout`,
`disconnected`, `close_failed`, `invalid_encoding`, `invalid_reading`,
`line_too_long`, and `stopped`. Read timeout defaults to 2 seconds and reconnect
delay to 2 seconds. A timeout reports that no bytes arrived during the read; it
does not assert that a sensor is faulty. Partial frames are retained across
timeouts; after 128 payload bytes without a newline, acquisition reports the
oversize frame and discards through the next newline. Invalid ASCII is retained
as `raw_hex`; malformed text is retained as `raw_line`.

Disconnect/reconnect resets the pending frame and sequence through a new
session. The protocol contains no board boot identifier or source sequence,
so a Nano reboot that keeps USB open cannot be detected reliably. Opening the
USB serial connection can itself reset some Nano boards. Acquisition does not
discard a startup buffer or fabricate missing samples. Pi wall-clock accuracy
depends on the Pi's clock synchronization; timestamps are not measurement-time
claims. Flushing JSONL does not provide fsync durability or guaranteed recovery
from power loss. Configure log retention for continuous operation.

## Connecting acquisition to process events

Capture representative labeled traces with the actual sensors and mechanics.
Record channel placement, unloaded/loaded baselines, noise, drift, known sensor
faults, and the timing of independently observed human actions. Derive and
validate thresholds or recognition rules from those traces before mapping a
channel to an activity in a WA card. A mapping must establish both the sensor's
meaning and the transition evidence for that activity. Timeout, invalid data,
or a new session must invalidate continuity-dependent recognition state.

This application supplies real raw input for that work. It does not supply
calibration, source-device timestamps, case assignment, a WA3 test jig, or
authoritative activity classifications. It does not emit events directly to
an orchestrator. The workstation plans describe which integration evidence is
still required.

## Verification

From the repository root:

```bash
python3.11 -m unittest Workareas.tests.test_serial_capture
python3.11 -m compileall -q Workareas/shared/serial_capture.py Workareas/tools/serial_capture/main.py Workareas/tests/test_serial_capture.py
```

The acquisition suite was written and run before the implementation: it failed
because `Workareas.shared.serial_capture` did not exist. After implementation,
all seven tests passed. These checks cover P1/P2 values and units, the `-1`
sentinel, malformed/nonfinite inputs, partial-frame timeouts, corrupt and
oversized frames, reconnect identity, JSONL records, configuration validation,
and timezone requirements. A separate child-process check using the installed
pyserial package and a POSIX pseudo-terminal also passed real serial reads,
read timeout, disconnect detection, Ctrl+C shutdown, and preservation of an
existing output file. Its input was a test fixture, not a physical Nano. These
checks do not establish electrical safety, sensor calibration, physical USB
reliability, or event-recognition accuracy. Ruff and strict mypy checks of the
three Python files also passed using the temporary verification environment.
