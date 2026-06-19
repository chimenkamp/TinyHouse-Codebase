from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .runtime_common import utc_now


COLOR_LABELS = ["none", "red", "green", "blue", "yellow"]
COLOR_CODES = {label: index for index, label in enumerate(COLOR_LABELS)}


@dataclass(frozen=True)
class ColorReading:
    label: str
    confidence: float
    rgb: tuple[float, float, float]


class CameraColorReader:
    def __init__(
        self,
        sensor_id: str,
        camera_index: int = 0,
        interval_seconds: float = 0.5,
        min_saturation: float = 55.0,
        min_value: float = 35.0,
    ) -> None:
        self.sensor_id = sensor_id
        self.camera_index = camera_index
        self.interval_seconds = interval_seconds
        self.min_saturation = min_saturation
        self.min_value = min_value
        self._capture = None

    def run(self, on_reading: Callable[[dict], None]) -> None:
        try:
            import cv2
        except ImportError as error:
            raise RuntimeError(
                "OpenCV is required for the camera node. Install python3-opencv "
                "or opencv-python-headless."
            ) from error

        self._capture = cv2.VideoCapture(self.camera_index)
        if not self._capture.isOpened():
            raise RuntimeError(f"Could not open camera index {self.camera_index}.")

        try:
            while True:
                ok, frame = self._capture.read()
                if not ok or frame is None:
                    time.sleep(self.interval_seconds)
                    continue

                reading = self._classify_frame(cv2, frame)
                code = COLOR_CODES.get(reading.label, 0)
                on_reading(
                    {
                        "sensor_id": self.sensor_id,
                        "sensor_type": "color_camera",
                        "value": float(code),
                        "unit": "color_code",
                        "timestamp": utc_now(),
                        "raw": {
                            "label": reading.label,
                            "confidence": reading.confidence,
                            "rgb": reading.rgb,
                        },
                    }
                )
                time.sleep(self.interval_seconds)
        finally:
            self.close()

    def _classify_frame(self, cv2, frame) -> ColorReading:
        height, width = frame.shape[:2]
        crop = frame[
            int(height * 0.25) : int(height * 0.75),
            int(width * 0.25) : int(width * 0.75),
        ]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        rgb_mean = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).mean(axis=(0, 1))
        hue = float(hsv[:, :, 0].mean()) * 2.0
        saturation = float(hsv[:, :, 1].mean())
        value = float(hsv[:, :, 2].mean())

        if saturation < self.min_saturation or value < self.min_value:
            label = "none"
            confidence = max(0.0, min(1.0, value / max(self.min_value, 1.0))) * 0.25
        elif hue < 25 or hue >= 335:
            label = "red"
            confidence = min(1.0, saturation / 255.0)
        elif 25 <= hue < 85:
            label = "yellow"
            confidence = min(1.0, saturation / 255.0)
        elif 85 <= hue < 170:
            label = "green"
            confidence = min(1.0, saturation / 255.0)
        elif 170 <= hue < 270:
            label = "blue"
            confidence = min(1.0, saturation / 255.0)
        else:
            label = "red"
            confidence = min(1.0, saturation / 255.0)

        return ColorReading(
            label=label,
            confidence=round(float(confidence), 4),
            rgb=tuple(round(float(channel), 2) for channel in rgb_mean),
        )

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

