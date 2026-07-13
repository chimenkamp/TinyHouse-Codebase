"""Re-export :class:`SerialCamera` from the proven viewer implementation.

Putting this here keeps the rest of the suite import path uniform
(``from scotty.camera import SerialCamera``) while we still rely on the
single, battle-tested implementation in
``Xiao_ESP32S3_Sense/usb_serial_camera_viewer.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make sure the Xiao_ESP32S3_Sense source directory is importable.
_SUBDIR = Path(__file__).resolve().parents[2] / "Xiao_ESP32S3_Sense"
_s = str(_SUBDIR)
if _s not in sys.path:
    sys.path.insert(0, _s)

from serial.tools import list_ports  # noqa: E402
from usb_serial_camera_viewer import SerialCamera, autodetect_port as _viewer_autodetect_port  # noqa: E402


def _is_likely_camera_port(port) -> bool:
    device = port.device or ""
    description = (port.description or "").lower()
    manufacturer = (port.manufacturer or "").lower()
    return "usbmodem" in device or "seeed" in manufacturer or "esp32" in description


def _with_macos_serial_companions(devices: set[str]) -> set[str]:
    expanded = set(devices)
    for device in devices:
        if device.startswith("/dev/tty."):
            expanded.add("/dev/cu." + device[len("/dev/tty."):])
        elif device.startswith("/dev/cu."):
            expanded.add("/dev/tty." + device[len("/dev/cu."):])
    return expanded


def list_camera_ports(exclude: set[str] | None = None) -> list[str]:
    """Return likely camera serial devices, excluding known robot ports."""
    exclude = _with_macos_serial_companions(exclude or set())
    candidates: list[str] = []
    fallback: list[str] = []
    for port in list_ports.comports():
        device = port.device or ""
        if not device or device in exclude:
            continue
        if _is_likely_camera_port(port):
            candidates.append(device)
        fallback.append(device)
    return candidates or fallback


def autodetect_port(exclude: set[str] | None = None) -> str:
    """Detect the serial camera port, ignoring known non-camera devices."""
    exclude = exclude or set()
    candidates = list_camera_ports(exclude=exclude)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates and not exclude:
        return _viewer_autodetect_port()
    if not candidates:
        raise RuntimeError("No likely camera serial port found.")
    raise RuntimeError(
        "Multiple possible camera serial ports found: "
        + ", ".join(candidates)
        + ". Pick one in the Camera tab."
    )


__all__ = ["SerialCamera", "autodetect_port", "list_camera_ports"]
