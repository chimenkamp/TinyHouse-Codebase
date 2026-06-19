import json
import os
from pathlib import Path

from dotenv import load_dotenv
from event_abstraction.mseg import MultiSensorEventGenerator
from mqtt.case_receiver import Case_Receiver
from mqtt.sensor_publisher import create_mqtt_client
from pipeline import SensorPipeline
from sensor_xes_export import event_to_xes_fragment, events_to_xes
from sensors.adapter import PressureAdapter
from sensors.fake_sensor import run as fake_run
from sensors.serial_reader import SerialReader

"""main instance of the Sensor.
Kicks off pipeline upon case_ID received from MQTT Case_ID publisher. Initializes serial reader, pipeline, sensor adapter"""

load_dotenv()
# === Konfiguration ===
SERIAL_PORT = os.getenv("SERIAL_PORT")
if not SERIAL_PORT:
    raise EnvironmentError("SERIAL_PORT must be set in .env")
BAUDRATE = 9600
DATA_DIR = Path(os.getenv("OUTPUT_DIR", "./data"))
BROKER_HOST = os.getenv("BROKER_HOST", "localhost")
WINDOW_SIZE = 2.0


def main():

    # MQTT-Client (optional — bei Fehler ohne MQTT weiterarbeiten)
    mqtt_client = None
    try:
        mqtt_client = create_mqtt_client(BROKER_HOST)
        print("MQTT aktiviert")
    except Exception as e:
        print(f"MQTT nicht verfügbar ({e}), arbeite lokal weiter")

    # register sensor adapter
    adapters = [
        PressureAdapter(sensor_id="pressure_1", line_prefix="P1"),
        # PressureAdapter(sensor_id="pressure_2", line_prefix="P2"),
        # Weitere Sensoren hier einfach ergaenzen:
        # TemperatureAdapter(sensor_id="temp_1", line_prefix="T1"),
    ]

    def on_event_ready(event: dict) -> None:
        """upon close all read events are transformed into an XES log for the sensor"""
        xes = event_to_xes_fragment(event)
        print(f"[XES] {xes}")

    def on_mseg_event(event: dict):
        xes = event_to_xes_fragment(event)
        print(f"[XES] {xes}")
        if mqtt_client:
            mqtt_client.publish(
                f"events/{event.get('sensor_id', 'multi')}", json.dumps(event)
            )

    # if Multiple sensors are used for event abstraction
    #    mseg = MultiSensorEventGenerator(
    #        sensor_ids=[a.sensor_id for a in adapters],
    #        mapping_file=f"{DATA_DIR}/multi_sensor_event_mapping.json",
    #        output_file=f"{DATA_DIR}/events/multi_sensor_events.jsonl",
    #        on_event=on_mseg_event,
    #    )

    # one pipeline per sensor
    pipelines: dict[str, SensorPipeline] = {}
    for adapter in adapters:
        pipelines[adapter.sensor_id] = SensorPipeline(
            sensor_id=adapter.sensor_id,
            data_dir=str(DATA_DIR),
            window_size=WINDOW_SIZE,
            mqtt_client=mqtt_client,
            mqtt_topic=f"events/{adapter.sensor_id}",
            on_event_ready=on_event_ready,
            # mseg=mseg
        )

    def on_case_start(case_id):
        for pipeline in pipelines.values():
            pipeline.start_case(case_id)

    def on_case_stop():
        for pipeline in pipelines.values():
            pipeline.stop_case()

    if mqtt_client:
        case_receiver = Case_Receiver(
            client=mqtt_client,
            on_case_start=on_case_start,
            on_case_stop=on_case_stop,
        )

    # Callback: Reading an die richtige Pipeline weiterleiten
    def on_reading(reading: dict):
        sid = reading["sensor_id"]
        if sid in pipelines:
            pipelines[sid].process_reading(reading)

    #    Serial Reader starten
    reader = SerialReader(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        adapters=adapters,
        on_reading=on_reading,
    )

    print(f"Aufnahme gestartet ({len(adapters)} Sensoren), Strg+C zum Beenden...")

    try:
        # fake_run(on_reading, sensor_id="pressure_1")
        reader.run()
    except KeyboardInterrupt:
        print("\nBeende...")

        # Pipelines sauber schliessen
        for p in pipelines.values():
            p.close()

        reader.close()

        # XES-Export fuer alle Sensoren
        for sid in pipelines:
            events_file = f"{DATA_DIR}/events/{sid}_events.jsonl"
            xes_file = f"{DATA_DIR}/logs/{sid}.xes"
            try:
                events_to_xes(events_file, xes_file, sensor_id=sid)
            except FileNotFoundError:
                print(f"Keine Events fuer {sid}")

        # Kombiniertes XES ueber alle Sensoren
        try:
            # Alle Event-Dateien zusammenfuehren
            combined = f"{DATA_DIR}/events/all_events.jsonl"
            import glob

            with open(combined, "w") as out:
                for ef in glob.glob(f"{DATA_DIR}/events/*_events.jsonl"):
                    with open(ef) as inp:
                        out.write(inp.read())
            events_to_xes(combined, f"{DATA_DIR}/logs/combined.xes")
        except Exception as e:
            print(f"Kombinierter XES-Export fehlgeschlagen: {e}")

        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        print("Fertig.")


if __name__ == "__main__":
    main()
