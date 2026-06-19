import json
import logging
from typing import Callable, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)
SUBSCRIBE_TOPIC = "case/control"

"""listens to subscribe topic to receive cases and starts and stops pipeline. """


class Case_Receiver:
    def __init__(
        self,
        client: mqtt.Client,
        on_case_start: Callable[[str], None],
        on_case_stop: Callable[[], None],
    ):
        self.client = client
        self.on_case_start = on_case_start
        self.on_case_stop = on_case_stop
        self.current_case_id: Optional[str] = None
        self.client.subscribe(SUBSCRIBE_TOPIC)

        self.client.message_callback_add(SUBSCRIBE_TOPIC, self._on_message)

    def _on_message(self, client, userdata, msg):

        try:
            case = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"invalid case/control message: {e}")
            return

        action = case.get("action", "?")

        if action == "start":
            case_id = case.get("case_id", "?")
            if not case_id:
                logger.error("Received start signal without case_id - ignore")
                return

            previous = self.current_case_id
            self.current_case_id = case_id

            if previous:
                logger.info(f"New round: {case_id}, closed previous {previous}")
            else:
                logger.info(f"started first round: {case_id}")

            print(f">>> Case started: {case_id}\n ")
            self.on_case_start(case_id)

        elif action == "stop":
            if not self.current_case_id:
                logger.warning("received stop signal, but no active round")
                return

            logger.info(f"complete stop with last case: {self.current_case_id}")
            print(f"stop signal received - last case: {self.current_case_id}")

            self.current_case_id = None
            self.on_case_stop()

        else:
            logger.warning(f"unkown action in case/control: '{action}'")
