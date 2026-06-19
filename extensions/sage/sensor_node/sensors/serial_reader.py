""""""

import time
from datetime import datetime
from typing import Callable

import serial
from typing_extensions import Sequence

from sensors.adapter import PressureAdapter, SensorAdapter


class SerialReader:
    """Initialisation of the Reader class
    port: on which port the sensor (eg. Arduino with sensor installed) sends
    baudrate: which frequency/speed of transmission is being used to send infromation over the port
    adapters: which sensor adapters are needed (one for each Sensor running on a Pi)
    on_reading: defined in main - check if pipeline exists for sensor_id and pushes readings into the pipeline
    """

    def __init__(
        self,
        port: str,
        baudrate: int,
        adapters: Sequence[SensorAdapter],
        on_reading: Callable[[dict], None],
    ):
        self.ser = serial.Serial(port, baudrate, timeout=2)
        self.adapters = adapters
        self.on_reading = on_reading

    def run(self):
        """loop for reading serial port inputs."""
        while True:
            try:
                raw_line = self.ser.readline().decode("utf-8", errors="ignore").strip()
            except serial.SerialException:
                print("Serielle Verbindung verloren, reconnecte...")
                time.sleep(2)
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = serial.Serial(self.ser.port, self.ser.baudrate)
                continue

            if not raw_line:
                continue
            # checks if any adapter in the adapter list can handle the read line and pushes line into the adapter
            for adapter in self.adapters:
                reading = adapter.parse(raw_line)
                if reading is not None:
                    reading["timestamp"] = datetime.now().isoformat()
                    self.on_reading(reading)
                    break

    # closes the serial connection - eg. if programm is interrupted
    def close(self):

        if self.ser and self.ser.is_open:
            self.ser.close()


if __name__ == "__main__":
    import json
    import os
    import sys
    from pathlib import Path

    from dotenv import load_dotenv

    from sensors.adapter import PressureAdapter

    load_dotenv()

    SERIAL_PORT = os.getenv("SERIAL_PORT")
    if not SERIAL_PORT:
        print("Error: SERIAL_PORT not set in .env")
        sys.exit(1)

    output_file = sys.argv[1] if len(sys.argv) > 1 else "raw_readings.jsonl"
    out = open(output_file, "a")

    adapters = [
        PressureAdapter(sensor_id="pressure_1", line_prefix="P1"),
        PressureAdapter(sensor_id="pressure_2", line_prefix="P2"),
    ]

    def on_reading(reading: dict):
        print(
            f"  {reading['sensor_id']}: value={reading['value']:.3f} {reading['unit']}"
        )
        out.write(json.dumps(reading) + "\n")
        out.flush()

    reader = SerialReader(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        adapters=adapters,
        on_reading=on_reading,
    )

    print(f"Collecting raw readings -> {output_file}")
    print("Ctrl+C to stop\n")

    try:
        reader.run()
    except KeyboardInterrupt:
        print(f"\nDone. Readings saved to {output_file}")
    finally:
        reader.close()
        out.close()
