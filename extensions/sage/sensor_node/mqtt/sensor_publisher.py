import paho.mqtt.client as mqtt


def create_mqtt_client(
    broker_host: str,
    broker_port: int = 1883,
    client_id: str = "pi_sensor_publisher",
) -> mqtt.Client:
    """
    Creates and connects an MQTT client.

    Args:
        broker_host: IP/hostname of the broker
        broker_port: port (default 1883)
        client_id: client ID for the broker

    Returns:
        Connected mqtt.Client
    """
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
    )

    def on_connect(c, userdata, flags, rc, properties):
        if rc == 0:
            print(f"MQTT connected to {broker_host}:{broker_port}")
        else:
            print(f"MQTT connection failed: rc={rc}")

    def on_disconnect(c, userdata, flags, rc, properties):
        print(f"MQTT disconnected (rc={rc})")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    client.connect(broker_host, broker_port, keepalive=60)
    client.loop_start()

    return client
