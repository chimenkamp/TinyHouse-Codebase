import json
import logging
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class EventGenerator:
    def __init__(
        self,
        mapping_file: str = "event_mapping.json",
        output_file: Optional[str] = "events.jsonl",
        on_event: Optional[Callable[[dict], Optional[dict]]] = None,
    ):
        self._mapping = self._load_mapping(mapping_file)
        self.on_event = on_event
        self._last_label: Optional[str] = None
        self._event_count = 0

        self._out_file = None
        if output_file:
            self._out_file = open(output_file, "a")

    def _load_mapping(self, filepath: str) -> dict:
        path = Path(filepath)
        if not path.exists():
            template = {}
            with open(path, "w") as f:
                json.dump(template, f, indent=2)
                raise FileNotFoundError(
                    f"event_mapping.json created at {path}\n"
                    "Please fill in label transitions manually before runnign again."
                )

        else:
            with open(path) as f:
                mapping = json.load(f)
            logger.info(f"loaded event mapping: {len(mapping)} transitions")
        return mapping

    def process(self, segment: dict) -> Optional[dict]:
        """
        Prueft ob ein Label-Wechsel ein Event ausloest.

        Regeln:
            vorher != placed, jetzt == placed  ->  object_placed
            vorher == placed, jetzt != placed   ->  object_removed
        """
        label = segment["label"]
        event = None

        if self._last_label is not None:
            transition_key = f"{self._last_label} -> {label}"
            event_name = self._mapping.get(transition_key)

            if event_name:
                event = self._make_event(event_name, segment)

        self._last_label = label
        return event

    def _make_event(self, event_name: str, segment: dict) -> dict:
        """Event-Dict erzeugen, in Datei schreiben, Callback aufrufen."""
        self._event_count += 1

        event = {
            # general event log for convenience
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


# ---------------------------------------------------------------------------
# Standalone: Batch-Verarbeitung auf classified_segments.jsonl
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    input_file = sys.argv[1] if len(sys.argv) > 1 else "classified_segments.jsonl"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "events.jsonl"
    mapping_file = sys.argv[3] if len(sys.argv) > 3 else "event_mapping.json"

    generator = EventGenerator(output_file=output_file, mapping_file=mapping_file)

    print(f"Verarbeite: {input_file}\n")

    with open(input_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            seg = json.loads(line)
            generator.process(seg)

    generator.close()
    print(f"\n{generator._event_count} Events written to {output_file}")
