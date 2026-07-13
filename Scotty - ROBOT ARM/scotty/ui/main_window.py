"""Tabbed main window: shared camera + robot, dispatching frames to each tab."""

from __future__ import annotations

import sys
import time
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QSplitter, QStatusBar, QTabWidget, QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from ..camera import CameraReader, SerialCamera, autodetect_port, list_camera_ports
from ..config import SETTINGS
from ..robot import Parol6Controller
from .header import HeaderPanel
from .tab_camera import CameraTab
from .tab_detect_grasp import DetectGraspTab
from .tab_hand_eye import HandEyeTab
from .tab_intrinsic import IntrinsicTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(SETTINGS.ui.window_title)
        self.resize(1400, 900)

        # Robot is owned by the main window and shared with every tab.
        self.robot = Parol6Controller()
        self.robot.connect()

        self.header = HeaderPanel(self.robot)
        self.status_panel = self.header.status  # backward-compat alias
        self.setStatusBar(QStatusBar())

        # --- Camera
        self.camera: SerialCamera | None = None
        self.reader: CameraReader | None = None
        # Tabs are constructed after the camera attempt so the camera tab
        # exists before _open_camera() reports status into it.

        # --- Robot status surface
        if self.robot.connected:
            self.status_panel.set_robot(True, f"({SETTINGS.robot.serial_port})")
        else:
            self.status_panel.set_robot(False, self.robot.last_error or "")

        # --- Tabs
        self.tab_camera = CameraTab()
        self.tab_camera.reconnect_requested.connect(self.reopen_camera)
        self.tab_camera.refresh_ports_requested.connect(self._refresh_camera_ports)
        self.tab_intrinsic = IntrinsicTab()
        self.tab_hand_eye = HandEyeTab(self.robot, self.header.slider_values)
        self.tab_detect = DetectGraspTab(self.robot)

        # Now that the camera tab exists we can bring up the camera and
        # surface failures into both the status panel and the tab itself.
        self._open_camera()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.tab_camera, "Camera")
        self.tabs.addTab(self.tab_intrinsic, "1. Intrinsic calibration")
        self.tabs.addTab(self.tab_hand_eye, "2. Hand-eye calibration")
        self.tabs.addTab(self.tab_detect, "3. Detect && grasp")

        # Layout: robot controls on the left, workspace tabs on the right.
        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(6, 6, 6, 6)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.header)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([470, 930])
        v.addWidget(splitter, 1)
        self.setCentralWidget(central)

        # --- Timers
        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(SETTINGS.ui.frame_interval_ms)
        self.frame_timer.timeout.connect(self._tick_frame)
        self.frame_timer.start()

        self.robot_timer = QTimer(self)
        self.robot_timer.setInterval(SETTINGS.ui.robot_poll_ms)
        self.robot_timer.timeout.connect(self._tick_robot)
        self.robot_timer.start()

    # --- Camera lifecycle
    def _known_non_camera_ports(self) -> set[str]:
        ports = {SETTINGS.robot.serial_port}
        if SETTINGS.camera.port:
            ports.discard(SETTINGS.camera.port)
        return {p for p in ports if p}

    def _refresh_camera_ports(self, selected: str | None = None) -> list[str]:
        ports = list_camera_ports(exclude=self._known_non_camera_ports())
        self.tab_camera.set_ports(ports, selected=selected or SETTINGS.camera.port)
        return ports

    def _open_camera(self, requested_port: str | None = None) -> None:
        """(Re-)open the serial camera with autodetect + one retry.

        Surfaces failure into both the status panel and the Camera tab so a
        permanent ``"(no frame)"`` placeholder can't hide a missing port.
        """
        cfg = SETTINGS.camera
        last_exc: Exception | None = None
        chosen_port: str | None = None
        requested_port = requested_port or cfg.port
        self._refresh_camera_ports(selected=requested_port)
        for attempt in (0, 1):
            try:
                port = requested_port or autodetect_port(exclude=self._known_non_camera_ports())
                chosen_port = port
                cam = SerialCamera(
                    port=port, baud=cfg.baud, timeout=cfg.timeout_s,
                    framesize=cfg.framesize, window_name="scotty (hidden)",
                )
                # NOTE: do NOT call cam.__enter__() — that opens a native
                # cv2.namedWindow which on macOS conflicts with the PySide6
                # event loop and blocks the serial reader.
                cam.send_command(f"SET FRAMESIZE {cfg.framesize}")
                cam.send_command(f"SET QUALITY {cfg.jpeg_quality}")
                cam.set_streaming(True)
                self.camera = cam
                self.reader = CameraReader(cam)
                self.reader.error.connect(
                    lambda msg: self.status_panel.set_message(msg, error=True)
                )
                self.reader.error.connect(self.tab_camera.set_status)
                self.reader.start()
                self.status_panel.set_camera(True, f"({port})")
                self.tab_camera.set_ports(
                    list_camera_ports(exclude=self._known_non_camera_ports()),
                    selected=port,
                )
                self.tab_camera.set_status(f"connecting on {port}…")
                return
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    # USB enumeration race after replug — back off briefly.
                    time.sleep(0.3)
        msg = f"camera unavailable: {type(last_exc).__name__}: {last_exc}"
        if cfg.port is None and chosen_port is None:
            msg += "\n(no XIAO-like /dev/tty.usbmodem* found — plug in or set SETTINGS.camera.port)"
        self.status_panel.set_camera(False, str(last_exc))
        self.tab_camera.set_status(msg)

    def _close_camera(self) -> None:
        try:
            if self.reader is not None:
                self.reader.stop()
        except Exception:
            pass
        self.reader = None
        if self.camera is not None:
            try:
                self.camera.set_streaming(False)
            except Exception:
                pass
            try:
                self.camera._serial_port.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        self.camera = None

    def reopen_camera(self, port: str = "") -> None:
        SETTINGS.camera.port = port or None
        self.tab_camera.set_status("reconnecting camera…")
        self._close_camera()
        self._open_camera(requested_port=SETTINGS.camera.port)

    # --- Timer handlers
    def _tick_frame(self) -> None:
        if self.reader is None:
            return
        frame = self.reader.latest()
        if frame is None:
            return
        active = self.tabs.currentWidget()
        try:
            if hasattr(active, "update_frame"):
                active.update_frame(frame)
        except Exception:
            traceback.print_exc()

    def _tick_robot(self) -> None:
        angles = self.robot.angles() if self.robot.connected else None
        pose = self.robot.pose() if self.robot.connected else None
        self.status_panel.set_angles(angles)
        self.status_panel.set_pose(pose)
        if angles is not None:
            self.header.follow_robot_angles(angles)

    # --- Lifecycle
    def closeEvent(self, ev) -> None:  # noqa: N802
        self._close_camera()
        try:
            self.robot.disconnect()
        except Exception:
            pass
        super().closeEvent(ev)


def run() -> int:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()
