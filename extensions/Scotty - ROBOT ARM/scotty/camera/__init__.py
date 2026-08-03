"""Camera abstractions: SerialCamera + background reader thread."""

from .serial_camera import SerialCamera, autodetect_port, list_camera_ports
from .reader import CameraReader

__all__ = ["SerialCamera", "CameraReader", "autodetect_port", "list_camera_ports"]
