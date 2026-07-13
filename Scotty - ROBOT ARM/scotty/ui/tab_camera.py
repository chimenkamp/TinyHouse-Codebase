"""Plain camera viewer tab."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .widgets import VideoLabel


class CameraTab(QWidget):
    reconnect_requested = Signal(str)
    refresh_ports_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.video = VideoLabel()
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(260)
        self.port_combo.addItem("Auto detect", "")
        self.port_combo.setToolTip("Select the XIAO camera serial port, or use auto detect.")
        self.btn_refresh_ports = QPushButton("Refresh ports")
        self.btn_refresh_ports.clicked.connect(self.refresh_ports_requested)
        self.btn_reconnect = QPushButton("Reconnect camera")
        self.btn_reconnect.setToolTip(
            "Tear down the serial reader and re-open the camera (e.g. after\n"
            "replugging the XIAO so the OS assigns a new /dev/tty.usbmodem*)."
        )
        self.btn_reconnect.clicked.connect(
            lambda: self.reconnect_requested.emit(self.selected_port())
        )

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Port:"))
        bar.addWidget(self.port_combo)
        bar.addWidget(self.btn_refresh_ports)
        bar.addWidget(self.btn_reconnect)
        bar.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(self.video, 1)

    def update_frame(self, frame_bgr: np.ndarray) -> None:
        self.video.set_frame_bgr(frame_bgr)

    def set_status(self, message: str) -> None:
        """Show a status / error in place of the video frame."""
        self.video.clear()
        self.video.setText(message)

    def selected_port(self) -> str:
        data = self.port_combo.currentData()
        return "" if data is None else str(data)

    def set_ports(self, ports: list[str], selected: str | None = None) -> None:
        current = selected if selected is not None else self.selected_port()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItem("Auto detect", "")
        for port in ports:
            self.port_combo.addItem(port, port)
        idx = self.port_combo.findData(current or "")
        self.port_combo.setCurrentIndex(max(0, idx))
        self.port_combo.blockSignals(False)
