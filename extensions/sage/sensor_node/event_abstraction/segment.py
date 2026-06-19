import json
import logging
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from typing_extensions import Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature calculation per segment
# ---------------------------------------------------------------------------


def private_feature_calculation(values: list[float]) -> dict[str, float]:
    """private function just for this module: calculates the features for a segment
    based on the input readings
    takes the parts of the dictionary holding the readings and calculates:
    - median
    - mean
    - min
    - max
    - variance
    - delta
    - max_delta
    it has to calculate those indipendently of unit and is called for example RGB, where multiple readings are send, for EACH reading.
    """
    n = len(values)

    return {
        # statistics is used to reliably find the median, mean and variances without sorting the lists first
        # values are rounded to 4 decimal places -> cutoff point to be not too long but also long enough to be more precise
        # building the dict
        "median_value": round(statistics.median(values), 4),
        "mean_value": round(statistics.mean(values), 4),
        "min_value": round(min(values), 4),
        "max_value": round(max(values), 4),
        "variance_value": round(statistics.variance(values) if n > 1 else 0.0, 6),
        "delta_value": round(values[-1] - values[0], 4),
        "max_delta_value": round(
            max(abs(values[i + 1] - values[i]) for i in range(n - 1)) if n > 1 else 0.0,
            4,
        ),
    }


def make_segment(
    window_start: datetime,
    window_end: datetime,
    sensor_id: str,
    sensor_type: str,
    unit: str,
    readings: Union[list[float], list[dict]],
) -> dict:
    """
    Builds segment json with relevant information

    float readings: generic feature caluclation
    dict readings: feature calculation per canal (median_value_r, etc)

    """

    if not readings:
        raise ValueError("readings cannot be empty")

    segment = {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "sensor_id": sensor_id,
        "sensor_type": sensor_type,
        "unit": unit,
        "n_readings": len(readings),
        "label": None,
    }

    if isinstance(readings[0], dict):
        # if reading is a dict (for example: RGB): calculates features per channel
        channels = readings[0].keys()
        for channel in channels:
            channel_values = [r[channel] for r in readings]
            channel_features = private_feature_calculation(channel_values)
            # rename key so no overwriting happens
            for feat_name, feat_val in channel_features.items():
                segment[f"{feat_name}_{channel}"] = feat_val
    else:
        # scalar reading for generic features (like float, int)
        float_readings = [float(r) for r in readings]
        segment.update(private_feature_calculation(float_readings))

    return segment


# ---------------------------------------------------------------------------
# Realtime-Prozessor
# ---------------------------------------------------------------------------


class SegmentProcessor:
    def __init__(
        self,
        sensor_id: str,
        window_size_seconds: float = 2.0,
        step_size_seconds: float = 0.5,
        on_segment: Optional[Callable[[dict], Optional[dict]]] = None,
        segments_file: Optional[str] = "segments.jsonl",
        gap_threshold_seconds: float = 60.0,
    ):
        self.sensor_id = sensor_id
        self.window_size = timedelta(seconds=window_size_seconds)
        self.step_size = timedelta(seconds=step_size_seconds)
        self.gap_threshold = timedelta(seconds=gap_threshold_seconds)
        self.on_segment = on_segment

        # file output
        self._seg_file = None
        if segments_file:
            self._seg_file = open(segments_file, "a")

        # Readings-buffer: list of readings.
        self._readings: list[tuple] = []
        self._window_start: Optional[datetime] = None
        self._last_timestamp: Optional[datetime] = None

        # segment id and statistic
        self.segments_count = 0

    def add_reading(self, reading: dict) -> list[dict]:
        """adds reading to a segment using sliding window technique"""

        timestamp = reading["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        completed = []

        if (
            self._last_timestamp is not None
            and timestamp - self._last_timestamp > self.gap_threshold
        ):
            logger.info(f"gap: {timestamp - self._last_timestamp}. Window closing.")
            seg = self._finalize_window()
            if seg:
                completed.append(seg)
            self._readings = []
            self._window_start = None

        # first reading ever
        if self._window_start is None:
            self._window_start = timestamp

        # add reading in buffer
        self._readings.append((timestamp, reading))
        self._last_timestamp = timestamp

        # Sliding Window
        while (
            self._window_start is not None
            and timestamp >= self._window_start + self.window_size
        ):
            seg = self._finalize_window()
            if seg:
                completed.append(seg)
            self._window_start += self.step_size
            self._readings = [r for r in self._readings if r[0] >= self._window_start]

        return completed

    def flush(self) -> Optional[dict]:
        """
        Closes current unfinished window.
        call when closing programm
        """
        return self._finalize_window()

    def close(self):
        """opens resources."""
        self.flush()
        if self._seg_file:
            self._seg_file.close()
            self._seg_file = None

    def _finalize_window(self) -> Optional[dict]:
        """clean finishes window."""
        if self._window_start is None or not self._readings:
            return None

        window_end = self._window_start + self.window_size

        window_entries = [
            r for r in self._readings if self._window_start <= r[0] < window_end
        ]

        if not window_entries:
            return None

        first = window_entries[0][1]
        raw_values = [entry[1]["value"] for entry in window_entries]

        segment = make_segment(
            window_start=self._window_start,
            window_end=window_end,
            sensor_id=first["sensor_id"],
            sensor_type=first["sensor_type"],
            unit=first["unit"],
            readings=raw_values,
        )

        segment["case_id"] = first.get("case_id")

        self.segments_count += 1

        # callback
        if self.on_segment:
            self.on_segment(segment)

        # write into json file
        if self._seg_file:
            self._seg_file.write(json.dumps(segment) + "\n")
            self._seg_file.flush()

        logger.debug(f"Segment #{self.segments_count}: {segment}")

        return segment


# ---------------------------------------------------------------------------
# Batch-Modus: prerecorded data - used for eg. clustering
# ---------------------------------------------------------------------------


def process_file(
    filepath: Union[str, Path],
    window_size_seconds: float = 2.0,
) -> list[dict]:
    """
    Batch processing of a json file. Independant of sensor type.
    """
    filepath = Path(filepath)
    segments: list[dict] = []

    processor = SegmentProcessor(
        "sensor",  # any sensor id.
        window_size_seconds=window_size_seconds,
        on_segment=lambda seg: segments.append(seg),
        segments_file="segments.jsonl",
    )

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                processor.add_reading(data)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"skipped line: {e}")

    processor.flush()
    print(f"Processed: {filepath.name} -> {len(segments)} Segmente")
    return segments


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    data_file = sys.argv[1] if len(sys.argv) > 1 else "sensor_data.jsonl"
    segments = process_file(data_file)

    for seg in segments:
        print(json.dumps(seg))
