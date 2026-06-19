"""
Simuliert Drucksensor-Readings fuer Tests ohne Arduino.

Erzeugt abwechselnd idle (niedrige Spannung) und placed (hohe Spannung)
Phasen, damit Events ausgeloest werden.

Verwendung:
    python fake_sensor.py
"""

import random
import time
from datetime import datetime


def generate_reading(sensor_id: str, vout: float) -> dict:
    """Erzeugt ein Reading im gleichen Format wie PressureAdapter.parse()."""
    rc = (510.0 * 5.0 / vout) - 510.0 if vout > 0 else -1.0
    return {
        "sensor_id": sensor_id,
        "sensor_type": "pressure",
        "value": round(vout, 3),
        "unit": "V",
        "raw": {"vout": round(vout, 3), "rc": round(rc, 3) if rc >= 0 else None},
        "timestamp": datetime.now().isoformat(),
    }


def run(on_reading, sensor_id="pressure_1", interval=0.5):
    """
    Simuliert Sensor-Readings in einer Endlosschleife.

    Phasen:
        - idle:   vout ~0.3-0.5 V  (nichts auf dem Sensor)
        - placed: vout ~2.5-3.5 V  (Objekt auf dem Sensor)

    Args:
        on_reading: Callback wie in main.py
        sensor_id: Sensor-ID
        interval: Sekunden zwischen Readings (default 0.5 wie Arduino)
    """
    phase = "idle"
    readings_in_phase = 0
    phase_length = random.randint(10, 20)

    print(f"Fake-Sensor gestartet: {sensor_id}, {interval}s Intervall")
    print("Phasen wechseln automatisch zwischen idle und placed\n")

    while True:
        if phase == "idle":
            vout = random.uniform(0.3, 0.5)
        else:
            vout = random.uniform(2.5, 3.5)

        reading = generate_reading(sensor_id, vout)
        on_reading(reading)

        readings_in_phase += 1
        if readings_in_phase >= phase_length:
            phase = "placed" if phase == "idle" else "idle"
            readings_in_phase = 0
            phase_length = random.randint(10, 20)
            print(f"  [fake] Phase: {phase}")

        time.sleep(interval)


if __name__ == "__main__":
    # Standalone-Test: gibt Readings auf stdout aus
    def print_reading(r):
        print(f"  {r['sensor_id']}: vout={r['value']:.3f}V")

    run(print_reading)
