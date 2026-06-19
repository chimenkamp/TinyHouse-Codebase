import json
from pathlib import Path
from typing import Callable, Optional

from event_abstraction.classifier import Classifier
from event_abstraction.events import EventGenerator
from event_abstraction.segment import SegmentProcessor

"""
Initialisation of the event abstraction pipeline.
Following steps of van Eck et al.
"""


class SensorPipeline:
    def __init__(
        self,
        sensor_id: str,
        data_dir: str,
        window_size: float = 2.0,
        mqtt_client=None,
        mqtt_topic: Optional[dict] = None,
        on_event_ready: Optional[Callable[[dict], Optional[dict]]] = None,
        mseg=None,
    ):
        self.sensor_id = sensor_id
        self.data_dir = Path(data_dir) / sensor_id
        self.mqtt_client = mqtt_client
        self.mqtt_topic = mqtt_topic or f"events/{sensor_id}"
        self.current_case_id = None
        self.on_event_ready = on_event_ready
        self.mseg = mseg

        # make directories
        raw_dir = self.data_dir / "raw"
        events_dir = self.data_dir / "events"
        segments_dir = self.data_dir / "segments"
        thresholds_dir = self.data_dir / "thresholds"
        raw_dir.mkdir(parents=True, exist_ok=True)
        events_dir.mkdir(parents=True, exist_ok=True)
        segments_dir.mkdir(parents=True, exist_ok=True)
        thresholds_dir.mkdir(parents=True, exist_ok=True)

        self.raw_file = open(raw_dir / f"{sensor_id}.jsonl", "a")

        # if/else: either mseg or single event generator (fallback is event generator)
        if mseg:
            self.event_generator = None
            on_classified = self._on_classified
        else:
            self.event_generator = EventGenerator(
                mapping_file=str(thresholds_dir / "event_mapping.json"),
                output_file=str(events_dir / f"{sensor_id}_events.jsonl"),
                on_event=self._on_event,
            )
            on_classified = self.event_generator.process

        self.classifier = Classifier(
            thresholds_file=str(thresholds_dir / "thresholds.json"),
            mapping_file=str(thresholds_dir / "cluster_activity_mapping.json"),
            output_file=str(segments_dir / f"{sensor_id}_classified.jsonl"),
            on_classified=on_classified,
        )

        self.segment_processor = SegmentProcessor(
            sensor_id=sensor_id,
            window_size_seconds=window_size,
            on_segment=self.classifier.classify,
            segments_file=str(segments_dir / f"{sensor_id}_segments.jsonl"),
        )

    def _on_classified(self, segment: dict):
        """Only active if mseg is set — classified segments go to MSEG"""
        self.mseg.process(self.sensor_id, segment)

    def process_reading(self, reading: dict):
        """writes reading into json, only if case id is set."""
        if not self.current_case_id:
            return
        entry = {**reading, "case_id": self.current_case_id}
        self.raw_file.write(json.dumps(entry) + "\n")
        self.raw_file.flush()
        self.segment_processor.add_reading({**reading, "case_id": self.current_case_id})

    def _on_event(self, event: dict):
        """Callback if event was read: MQTT publish."""
        if self.mqtt_client and self.mqtt_client.is_connected():
            print(f"MQTT connected: {self.mqtt_client.is_connected()}")
            self.mqtt_client.publish(self.mqtt_topic, json.dumps(event))
        if self.on_event_ready:
            self.on_event_ready(event)
        print(
            f"  [{self.sensor_id}] EVENT: {event.get('event_type', '?')} "
            f"(case={event.get('case_id', '?')})"
        )

    def start_case(self, case_id):
        if self.current_case_id:
            self.segment_processor.flush()
        self.current_case_id = case_id

    def stop_case(self):
        self.segment_processor.flush()
        self.current_case_id = None

    def close(self):
        """Closes Pipeline"""
        self.segment_processor.close()
        self.classifier.close()
        if self.event_generator:
            self.event_generator.close()
        self.raw_file.close()
