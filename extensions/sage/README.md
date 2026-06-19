# SAGE – Sensor-Agnostic Event Abstraction

A prototype for abstracting IoT sensor data into XES event logs for process mining, developed as part of a Bachelor's thesis at TU Dresden.

The system monitors a physical manufacturing simulation (Tiny House / Lego environment) using distributed Raspberry Pi nodes and abstracts raw sensor readings into process-mining-ready event logs via a local, edge-side pipeline.

Theoretical foundation: van Eck et al. (2016) – *Enabling Process Mining on Sensor Data from Low-Level Sensors*.

---

## Architecture Overview

```
[Arduino / Sensors]
        │ serial (USB)
        ▼
[Raspberry Pi – Edge Node]
  SerialReader → Adapter → SegmentProcessor → Classifier → EventGenerator
                                                                  │
                                                             MQTT publish
                                                                  │
                                                                  ▼
                                                    [Windows Hub – Broker]
                                                    Mosquitto │ SQLite │ XES Export
                                                                  │
                                                                  ▼
                                                           [pm4py / Analysis]
```

Three Raspberry Pis act as edge nodes. Each runs an independent pipeline. The Windows hub coordinates case IDs and collects events.

---

## Repository Structure

```
.
├── arduino/
│   └── sensor_sketch/
│       └── sensor_sketch.ino     # Arduino firmware for dual FSR pressure sensors
│
├── broker/
│   ├── mqtt/
│   │   ├── broker_publisher.py   # Publishes case start/stop with case_id
│   │   └── broker_subscriber.py  # Receives events, writes to events.jsonl
│   ├── received_events/          # Runtime output: collected events.jsonl
│   ├── broker_main.py            # Entry point for Windows hub / broker node
│   └── broker_xes_export.py      # XES export from collected events.jsonl
│
├── examples/                     # Reference calibration files
│   ├── cluster_activity_mapping.json
│   ├── event_mapping.json
│   └── thresholds.json
│
├── sensor_node/
│   ├── discovery/                # Raw reading capture to inspect sensor output format
│   ├── event_abstraction/
│   │   ├── classifier.py         # Threshold- or delta-based segment classification
│   │   ├── cluster.py            # k-Means clustering → thresholds.json (offline calibration)
│   │   ├── events.py             # EventGenerator: label transitions → named events
│   │   ├── mseg.py               # MultiSensorEventGenerator (multi-sensor event fusion)
│   │   ├── segment.py            # Sliding window segmentation + feature extraction
│   │   └── test_mseg.py          # Standalone MSEG test
│   ├── mqtt/
│   │   ├── case_receiver.py      # Subscribes to case/control, triggers pipeline start/stop
│   │   └── sensor_publisher.py   # Creates and connects MQTT client
│   ├── sensors/
│   │   ├── adapter.py            # SensorAdapter base class + PressureAdapter
│   │   ├── fake_sensor.py        # Simulated pressure readings (no hardware needed)
│   │   └── serial_reader.py      # Reads serial port, dispatches to adapters
│   ├── pipeline.py               # SensorPipeline: wires all stages together per sensor
│   ├── sensor_main.py            # Entry point for Raspberry Pi nodes
│   └── sensor_xes_export.py      # XES export (per-event fragment + batch)
│
├── mqtt_collector.py             # ESP32 drawer scale → virtual serial bridge (socat)
├── .env.example                  # Environment variable template
└── README.md
```

---

## Setup

### Requirements

```bash
pip install paho-mqtt pyserial pm4py python-dotenv
```

Python 3.9+ required.

### Environment variables

Each Raspberry Pi reads configuration from a `.env` file:

```env
SERIAL_PORT=/dev/ttyACM0
BROKER_HOST=192.168.x.x
OUTPUT_DIR=./data
```

Load with:
```bash
export $(grep -v '^#' .env | xargs)
```

---

## Adding a New Sensor

To support a new sensor type, implement a subclass of `SensorAdapter` in `sensors/adapter.py`:

```python
class TemperatureAdapter(SensorAdapter):
    def __init__(self, sensor_id: str, line_prefix: str):
        self.sensor_id = sensor_id
        self.line_prefix = line_prefix

    @property
    def sensor_type(self) -> str:
        return "temperature"

    def parse(self, raw_line: str) -> Optional[dict]:
        parts = raw_line.strip().split(",")
        if len(parts) != 2 or parts[0].strip() != self.line_prefix:
            return None
        try:
            value = float(parts[1])
        except ValueError:
            return None
        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "value": value,
            "unit": "C",
        }
```

The adapter is responsible for two things: identifying which serial lines belong to it (via `line_prefix`) and parsing them into a reading dict with at least `sensor_id`, `sensor_type`, `value`, and `unit`. `SerialReader` tries each registered adapter in order and dispatches the line to the first one that returns a non-`None` result.

---

## Calibration Workflow

Calibration is done once per sensor type and produces the three config files needed for classification. It can be run entirely standalone without a running pipeline.

**Step 1 — Collect raw readings**

Run `serial_reader.py` directly to record raw sensor data to a JSONL file. Make sure `SERIAL_PORT` is set in your `.env` and the adapter in the `__main__` block matches your sensor:

```bash
python sensor_node/sensors/serial_reader.py raw_readings.jsonl
```

Interact with the sensor to cover all relevant states (e.g. idle, object placed, object removed). Press `Ctrl+C` when done. Readings are appended to `raw_readings.jsonl` in the current directory.

**Step 2 — Segment**

```bash
python sensor_node/event_abstraction/segment.py raw_readings.jsonl
```

Produces `segments.jsonl` via sliding window feature extraction.

**Step 3 — Cluster**

```bash
python sensor_node/event_abstraction/cluster.py <n_clusters> segments.jsonl thresholds.json

# Example: 3 activities (idle, placed, removed)
python sensor_node/event_abstraction/cluster.py 3 segments.jsonl thresholds.json

# For weight sensors with consistent deltas (drawer scales):
python sensor_node/event_abstraction/cluster.py --delta 3 segments.jsonl thresholds.json
```

Produces `thresholds.json` with cluster centroids and decision boundaries.

**Step 4 — Edit `cluster_activity_mapping.json`**

Assign human-readable labels to the cluster IDs output by the previous step:

```json
{
  "0": "idle",
  "1": "placed",
  "2": "removed"
}
```

**Step 5 — Edit `event_mapping.json`**

Define which label transitions trigger named process events:

```json
{
  "idle -> placed": "object_placed",
  "placed -> idle": "object_removed"
}
```

Copy all three config files (`thresholds.json`, `cluster_activity_mapping.json`, `event_mapping.json`) into `data/{sensor_id}/thresholds/` before running the full pipeline. Reference examples are in `examples/`.

> **Note:** Transition key spacing must be consistent — SAGE uses `"A -> B"` (space on both sides of `->`) throughout. Asymmetric spacing (`"A ->B"`) is a common source of silent mapping misses.

---

## Running

### Sensor node (Raspberry Pi)

```bash
python sensor_node/sensor_main.py
```

For testing without hardware:

```bash
# In sensor_main.py, replace reader.run() with:
fake_run(on_reading, sensor_id="pressure_1")
```

### Broker / Hub (Windows)

```bash
python broker/broker_main.py --broker localhost --port 1883
```

Press **Enter** to start a new case, **`s` + Enter** to stop the current case.

---

## Data Flow

Each reading passes through the following stages:

```
raw line (serial)
  → Adapter.parse()           → {sensor_id, value, unit, timestamp}
  → SegmentProcessor          → {window_start, window_end, median_value, ...}
  → Classifier.classify()     → {label, cluster_id, ...}
  → EventGenerator.process()  → {concept:name, time:timestamp, case:concept:name, ...}
  → MQTT publish (events/{sensor_id})
  → [Broker] events.jsonl
  → XES export
```

Intermediate outputs (segments, classified segments, raw readings) are written to `data/{sensor_id}/` for debugging and offline reprocessing.

---

## Multi-Sensor Event Generation (MSEG)

`mseg.py` provides `MultiSensorEventGenerator` for fusing events from multiple sensors into composite process events. It is implemented but not yet active in `pipeline.py` (activation pending post-deployment integration).

When activated, MSEG replaces (not supplements) the single-sensor `EventGenerator` via an if/else branch in `SensorPipeline._on_classified`. The mapping file for MSEG is nested by sensor ID:

```json
{
  "sensor_red": {
    "idle -> activated": "red_brick_placed"
  },
  "sensor_blue": {
    "idle -> activated": "blue_brick_placed"
  }
}
```

Test MSEG in isolation:

```bash
python test_mseg.py
```

---

## XES Export

XES logs are generated at shutdown (sensor side) or on demand (broker side):

```python
# Broker side
from broker.broker_xes_export import events_to_xes
events_to_xes("received_events/events.jsonl", "output.xes", sensor_id="pressure_1")

# Sensor side – per-event fragment (for streaming/monitoring)
from sensor_node.sensor_xes_export import event_to_xes_fragment
fragment = event_to_xes_fragment(event)
```

The XES output is compatible with pm4py for process discovery and conformance checking.

---

## Known Limitations

- **State bleed across cases:** `_last_label` in `EventGenerator` and `_last_labels` in MSEG persist between cases. Mitigation: ensure all sensors return to idle before starting a new case.
- **Single-sensor calibration:** Each sensor type requires separate calibration. The clustering step is manual and must be re-run if the physical setup changes significantly.
- **Case ID distribution:** Case IDs are ISO timestamps generated by the broker and broadcast via MQTT. Clocks on Pis are not synchronized — event timestamps may drift slightly.

---

## Related Work

- van Eck et al. (2016) – *Enabling Process Mining on Sensor Data from Low-Level Sensors*
- van Zelst et al. (2020) – *Extracting Meaningful Insights from Sensor Data*
- Weisenseel et al. (2025) – Distributed Process Mining as open research agenda
- Buijs et al. (2014) – Four quality dimensions: Fitness, Precision, Generalization, Simplicity

---

## License

Academic prototype. See thesis for full context and attribution.
