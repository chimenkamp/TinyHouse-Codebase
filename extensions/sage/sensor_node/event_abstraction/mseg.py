import json
import logging
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class MultiSensorEventGenerator:
    def __init__(
        self,
        sensor_ids: list[str],
        mapping_file: str = "event_mapping.json",
        output_file: Optional[str] = "events.jsonl",
        on_event: Optional[Callable[[dict], Optional[dict]]] = None,
    ):
        self._event_count = 0
        self._out_file = open(output_file, "a") if output_file else None
        self._last_labels = {}
        self.sensor_ids = sensor_ids
        self._mapping = self._load_mapping(mapping_file)
        self.on_event = on_event

    def _load_mapping(self, filepath: str) -> dict:
        path = Path(filepath)
        if not path.exists():
            template = {
                sid: {"idle -> activated": "REPLACE_ME"} for sid in self.sensor_ids
            }
            with open(path, "w") as f:
                json.dump(template, f, indent=2)
                raise FileNotFoundError(
                    f"event_mapping.json created at {path}\n"
                    "Please fill in label transitions manually before runnign again."
                )
        with open(path) as f:
            mapping = json.load(f)

        for sensor_id in self.sensor_ids:
            if sensor_id not in mapping:
                raise KeyError(
                    f"No mapping found for sensor '{sensor_id}' in {filepath}"
                )

        logger.info(f"loaded event mapping: {len(mapping)} transitions")
        return mapping

    def process(self, sensor_id: str, segment: dict):
        new_label = segment["label"]

        old_label = self._last_labels.get(sensor_id)
        self._last_labels[sensor_id] = new_label

        if old_label is None:
            return

        if old_label == new_label:
            return

        transition_key = f"{old_label} -> {new_label}"
        sensor_mapping = self._mapping.get(sensor_id, {})
        event_name = sensor_mapping.get(transition_key)

        if event_name:
            self._make_event(event_name, segment)

    def _make_event(self, event_name: str, segment: dict) -> dict:
        """Event-Dict erzeugen, in Datei schreiben, Callback aufrufen."""
        self._event_count += 1

        event = {
            "event_id": self._event_count,
            "event_type": event_name,
            "timestamp": segment["window_start"],
            "case_id": segment.get("case_id"),
            "sensor_id": segment["sensor_id"],
            # XES mandatory fields:
            "concept:name": event_name,
            "time:timestamp": segment["window_start"],
            "lifecycle:transition": "complete",
            "case:concept:name": segment.get("case_id"),
            # XES additional fields for monitoring purposes
            "org:resource": segment["sensor_id"],
            "sensor:type": segment.get("sensor_type"),
            "sensor:unit": segment.get("unit"),
            # raw value of representative feature
            "sensor:value": segment.get("median_value"),
        }

        logger.info(
            f"Event #{self._event_count}: {event_name}"
            f"(case={event['case_id']} @{segment['window_start'][11:19]})"
        )
        print(
            f"  >>> EVENT: {event_name: <24} "
            f"case={event['case_id']}"
            f"@ {segment['window_start'][11:19]}"
        )

        if self._out_file:
            self._out_file.write(json.dumps(event) + "\n")
            self._out_file.flush()

        if self.on_event:
            self.on_event(event)

        return event

    def close(self):
        """Ressourcen freigeben."""
        if self._out_file:
            self._out_file.close()
            self._out_file = None
