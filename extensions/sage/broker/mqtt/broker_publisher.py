"""
Broker Module
Module to publish cases to the pis
"""

import json
from datetime import datetime

PUBLISH_TOPIC = "case/control"


def case_ID() -> dict[str, str]:
    """
    generates unique case_ID based on current date and time in isoformat and start action
    """
    return {
        "action": "start",
        "case_id": datetime.now().isoformat(),
    }


def publish_case_start(client):
    """
    publishes case start on PUBSLISH_TOPIC and start action
    """

    client.publish(PUBLISH_TOPIC, json.dumps(case_ID()))


def publish_case_stop(client):
    """
    publishes stop signal to clients
    """
    client.publish(PUBLISH_TOPIC, json.dumps({"action": "stop"}))
