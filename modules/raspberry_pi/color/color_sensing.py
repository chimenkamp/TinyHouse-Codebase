"""Detect dominant color from IMX335 camera and publish via MQTT."""

from __future__ import annotations

import json
import signal
import sys
import time
from datetime import datetime, timezone

import cv2
import numpy as np
import paho.mqtt.client as mqtt

COLOR_RANGES: dict[str, tuple[int, int]] = {
    "red": (0, 10),
    "red2": (170, 180),
    "orange": (10, 25),
    "yellow": (25, 35),
    "green": (35, 85),
    "cyan": (85, 100),
    "blue": (100, 130),
    "purple": (130, 145),
    "pink": (145, 170),
}

MQTT_BROKER: str = "localhost"
MQTT_PORT: int = 1883
MQTT_TOPIC: str = "camera/color"
CAPTURE_INTERVAL: float = 1.0

running: bool = True


def handle_signal(signum: int, frame: object) -> None:
    """Set the shutdown flag on SIGTERM/SIGINT.

    Args:
        signum: Signal number received.
        frame: Current stack frame (unused).
    """
    global running
    running = False


def find_camera(max_index: int = 10) -> int | None:
    """Probe /dev/video* devices and return the first working index.

    Args:
        max_index: Highest device index to try.

    Returns:
        The device index, or None if no camera responds.
    """
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            if ret:
                return idx
    return None


def dominant_color_name(frame_hsv: np.ndarray) -> tuple[str, float]:
    """Determine which color name covers the most pixels.

    Only considers pixels with saturation > 40 and value > 40 to
    ignore near-grey/black/white regions.

    Args:
        frame_hsv: Frame in HSV color space (uint8).

    Returns:
        Tuple of (color name, percentage of chromatic pixels).
        Returns ("grey", percentage) if most pixels are achromatic.
    """
    sat = frame_hsv[:, :, 1]
    val = frame_hsv[:, :, 2]
    chromatic_mask = (sat > 40) & (val > 40)
    total_pixels = frame_hsv.shape[0] * frame_hsv.shape[1]
    chromatic_count = int(np.count_nonzero(chromatic_mask))

    if chromatic_count < total_pixels * 0.1:
        return "grey", (1.0 - chromatic_count / total_pixels) * 100.0

    hue = frame_hsv[:, :, 0][chromatic_mask]
    best_name = "unknown"
    best_count = 0

    for name, (lo, hi) in COLOR_RANGES.items():
        count = int(np.count_nonzero((hue >= lo) & (hue < hi)))
        if count > best_count:
            best_count = count
            best_name = name

    if best_name == "red2":
        best_name = "red"

    percentage = best_count / chromatic_count * 100.0
    return best_name, percentage


def average_hex_color(frame_bgr: np.ndarray) -> str:
    """Compute the average BGR color and return it as a hex code.

    Args:
        frame_bgr: Frame in BGR color space (uint8).

    Returns:
        Hex color string like '#1a3fbf'.
    """
    mean_bgr = np.mean(frame_bgr, axis=(0, 1))
    b, g, r = int(mean_bgr[0]), int(mean_bgr[1]), int(mean_bgr[2])
    return f"#{r:02x}{g:02x}{b:02x}"


def run(
    device: int = 0,
    width: int = 2592,
    height: int = 1944,
) -> None:
    """Capture frames, detect color, and publish JSON to MQTT in a loop.

    Args:
        device: V4L2 device index (e.g. 0 for /dev/video0).
        width: Requested capture width in pixels.
        height: Requested capture height in pixels.
    """
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_start()

    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not cap.isOpened():
        sys.exit(f"Error: cannot open /dev/video{device}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"MJPG"))

    print(f"Publishing to {MQTT_BROKER}:{MQTT_PORT} topic={MQTT_TOPIC}")

    while running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(CAPTURE_INTERVAL)
            continue

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        color_name, percentage = dominant_color_name(hsv)
        hex_code = average_hex_color(frame)

        payload = json.dumps({
            "dominant_color": color_name,
            "percentage": round(percentage, 1),
            "hex": hex_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        client.publish(MQTT_TOPIC, payload)
        time.sleep(CAPTURE_INTERVAL)

    cap.release()
    client.loop_stop()
    client.disconnect()
    print("Stopped.")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    idx = find_camera()
    if idx is None:
        sys.exit("Error: no camera found on /dev/video0../dev/video9")
    print(f"Using /dev/video{idx}")
    run(device=idx)
