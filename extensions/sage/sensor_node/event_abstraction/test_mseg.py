# test_mseg.py
import json
from pathlib import Path

from mseg import MultiSensorEventGenerator

# 1. Test-Mapping erstellen
mapping = {
    "sensor_red": {
        "idle -> activated": "red_brick_placed",
        "activated -> idle": "red_brick_removed",
    },
    "sensor_blue": {
        "idle -> activated": "blue_brick_placed",
        "activated -> idle": "blue_brick_removed",
    },
    "sensor_green": {
        "idle -> activated": "green_brick_placed",
        "activated -> idle": "green_brick_removed",
    },
}
Path("test_mapping.json").write_text(json.dumps(mapping, indent=2))

# 2. Output zurücksetzen
Path("test_events.jsonl").unlink(missing_ok=True)

# 3. MSEG instanziieren
mseg = MultiSensorEventGenerator(
    sensor_ids=["sensor_red", "sensor_blue", "sensor_green"],
    mapping_file="test_mapping.json",
    output_file="test_events.jsonl",
)


# 4. Hilfsfunktion für Fake-Segmente
def fake_segment(sensor_id, label, t):
    return {
        "label": label,
        "sensor_id": sensor_id,
        "sensor_type": "pressure",
        "unit": "V",
        "window_start": f"2025-01-01T00:00:{t:02d}",
        "case_id": "case_1",
        "median_value": 2.5,
    }


# 5. Szenario abspielen
print("\n--- Test 1: Erster Aufruf (kein Event erwartet) ---")
mseg.process("sensor_red", fake_segment("sensor_red", "idle", 0))
mseg.process("sensor_blue", fake_segment("sensor_blue", "idle", 1))
mseg.process("sensor_green", fake_segment("sensor_green", "idle", 2))

print("\n--- Test 2: Rot wechselt idle -> activated (Event erwartet) ---")
mseg.process("sensor_red", fake_segment("sensor_red", "activated", 3))

print("\n--- Test 3: Rot bleibt activated (kein Event) ---")
mseg.process("sensor_red", fake_segment("sensor_red", "activated", 4))

print("\n--- Test 4: Rot wechselt activated -> idle (Event erwartet) ---")
mseg.process("sensor_red", fake_segment("sensor_red", "idle", 5))

mseg.close()

print("\n--- Inhalt von test_events.jsonl: ---")
print(Path("test_events.jsonl").read_text())
