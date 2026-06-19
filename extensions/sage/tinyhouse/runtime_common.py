from __future__ import annotations

import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SAGE_ROOT = Path(__file__).resolve().parents[1]
SENSOR_NODE_DIR = SAGE_ROOT / "sensor_node"
BROKER_DIR = SAGE_ROOT / "broker"

for path in (SENSOR_NODE_DIR, BROKER_DIR, SAGE_ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def host_slug(default: str = "tinyhouse") -> str:
    return socket.gethostname().strip().lower().replace("_", "-") or default


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def ensure_pipeline_config(
    data_dir: Path,
    sensor_id: str,
    sensor_kind: str,
    *,
    delta_per_unit: float | None = None,
    color_labels: Iterable[str] | None = None,
) -> None:
    thresholds_dir = data_dir / sensor_id / "thresholds"
    thresholds_dir.mkdir(parents=True, exist_ok=True)

    thresholds_file = thresholds_dir / "thresholds.json"
    activity_file = thresholds_dir / "cluster_activity_mapping.json"
    event_file = thresholds_dir / "event_mapping.json"

    if sensor_kind == "scale":
        thresholds = {
            "feature_keys": ["median_value"],
            "clusters": [
                {"cluster_id": 0, "centroid": {"median_value": 0.0}},
                {"cluster_id": 1, "centroid": {"median_value": 1.0}},
                {"cluster_id": 2, "centroid": {"median_value": -1.0}},
            ],
            "thresholds": [{"delta_per_unit": float(delta_per_unit or 5.0)}],
        }
        activities = {
            "0": "stable",
            "1": "weight_added",
            "2": "weight_removed",
        }
        events = {
            "stable -> weight_added": "scale_weight_added",
            "stable -> weight_removed": "scale_weight_removed",
            "weight_added -> weight_removed": "scale_weight_removed",
            "weight_removed -> weight_added": "scale_weight_added",
        }
    elif sensor_kind == "color":
        labels = list(color_labels or ["none", "red", "green", "blue", "yellow"])
        thresholds = {
            "feature_keys": ["median_value"],
            "clusters": [
                {"cluster_id": index, "centroid": {"median_value": float(index)}}
                for index, _ in enumerate(labels)
            ],
            "thresholds": [{}],
        }
        activities = {str(index): label for index, label in enumerate(labels)}
        events = {}
        for previous in labels:
            for current in labels:
                if previous != current and current != "none":
                    events[f"{previous} -> {current}"] = f"color_{current}_detected"
                elif previous != current and current == "none":
                    events[f"{previous} -> none"] = "color_cleared"
    else:
        thresholds = {
            "feature_keys": [
                "median_value",
                "mean_value",
                "min_value",
                "max_value",
                "variance_value",
                "delta_value",
                "max_delta_value",
            ],
            "clusters": [
                {
                    "cluster_id": 0,
                    "centroid": {
                        "median_value": 0.0,
                        "mean_value": 0.0,
                        "min_value": 0.0,
                        "max_value": 0.0,
                        "variance_value": 0.0,
                        "delta_value": 0.0,
                        "max_delta_value": 0.0,
                    },
                },
                {
                    "cluster_id": 1,
                    "centroid": {
                        "median_value": 4.0,
                        "mean_value": 4.0,
                        "min_value": 4.0,
                        "max_value": 4.0,
                        "variance_value": 0.0,
                        "delta_value": 0.0,
                        "max_delta_value": 0.0,
                    },
                },
            ],
            "thresholds": [{}],
        }
        activities = {"0": "idle", "1": "active"}
        events = {
            "idle -> active": f"{sensor_kind}_activated",
            "active -> idle": f"{sensor_kind}_released",
        }

    if not thresholds_file.exists():
        write_json(thresholds_file, thresholds)
    if not activity_file.exists():
        write_json(activity_file, activities)
    if not event_file.exists():
        write_json(event_file, events)


def normalize_sensor_id(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "sensor"
