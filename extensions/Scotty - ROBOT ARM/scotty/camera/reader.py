"""Background camera reader: drains the serial stream into a single-slot buffer.

The Qt UI polls :meth:`CameraReader.latest` from a timer; the reader thread
keeps draining the serial port at full speed, dropping older frames if the UI
falls behind.
"""

from __future__ import annotations

import threading
import time

import numpy as np
from PySide6.QtCore import QObject, Signal

from .serial_camera import SerialCamera


class CameraReader(QObject):
    error = Signal(str)
    stopped = Signal()

    def __init__(self, camera: SerialCamera) -> None:
        super().__init__()
        self._camera = camera
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest: np.ndarray | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        self.stopped.emit()

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def latest(self) -> np.ndarray | None:
        with self._lock:
            f = self._latest
            self._latest = None
            return f

    def _run(self) -> None:
        last_err_t = 0.0
        while not self._stop.is_set():
            try:
                f, _, _, _ = self._camera.read()
            except (TimeoutError, RuntimeError) as exc:
                if time.time() - last_err_t > 2.0:
                    self.error.emit(f"{type(exc).__name__}: {exc}")
                    last_err_t = time.time()
                time.sleep(0.05)
                continue
            except BaseException as exc:  # surface unexpected failures
                self.error.emit(f"FATAL {type(exc).__name__}: {exc}")
                return
            with self._lock:
                self._latest = f
