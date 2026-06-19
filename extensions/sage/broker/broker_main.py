import argparse
import os
import threading
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from mqtt.broker_publisher import publish_case_start, publish_case_stop
from mqtt.broker_subscriber import make_on_message, on_connect, on_disconnect

load_dotenv()

OUTPUT_DIR = Path(os.getenv("BROKER_OUTPUT_DIR", "./received_data/events"))
EVENTS_FILE = OUTPUT_DIR / "events.jsonl"


def listen_for_enter(client):
    print("Listener started, press Enter...")
    while True:
        if input() == "s":
            publish_case_stop(client)
        else:
            publish_case_start(client)
            print("enter pressed")


def main():
    parser = argparse.ArgumentParser(description="MQTT Event Subscriber")
    parser.add_argument("--broker", default="localhost", help="Broker-Adresse")
    parser.add_argument("--port", type=int, default=1883, help="Broker-Port")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Events written to: {EVENTS_FILE}")

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id="pc_event_subscriber"
    )
    client.on_connect = on_connect
    client.on_message = make_on_message(EVENTS_FILE)  # Factory hier
    client.on_disconnect = on_disconnect

    client.connect(args.broker, args.port, keepalive=60)

    print(f"Verbinde mit {args.broker}:{args.port}...")
    print("Strg+C zum Beenden\n")

    try:
        enter_thread = threading.Thread(
            target=listen_for_enter, args=(client,), daemon=True
        )
        enter_thread.start()
        client.loop_forever()
    except KeyboardInterrupt:
        print(f"\nBeendet. {EVENTS_FILE} enthaelt die empfangenen Events.")
        print("Naechster Schritt: XES-Export + pm4py auf dieser Datei ausfuehren.")
        client.disconnect()


if __name__ == "__main__":
    main()
