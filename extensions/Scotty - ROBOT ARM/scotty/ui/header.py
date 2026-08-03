"""Shared robot panel: status + joint sliders + Home / Park / HALT.

Lives beside the tab workspace and is shared by every tab. Tabs that
care about the joint targets connect to :pyattr:`HeaderPanel.joint_committed`.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox, QDoubleSpinBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..config import SETTINGS
from ..robot import JOINT_HOME_DEG, JOINT_LIMITS_DEG, Parol6Controller
from .widgets import DigitalTwinView, JointSliderPanel, StatusPanel


class HeaderPanel(QWidget):
    """Status + robot control. Emits :pyattr:`joint_committed` on slider release."""

    joint_committed = Signal(int, float)

    def __init__(self, robot: Parol6Controller) -> None:
        super().__init__()
        self.robot = robot
        self._latest_robot_angles: list[float] | None = None

        self.status = StatusPanel()
        self.sliders = JointSliderPanel()
        self.sliders.joint_committed.connect(self._on_joint_commit)
        self.sliders.joint_committed.connect(self.joint_committed)
        self.sliders.preview_changed.connect(self._on_slider_preview)
        self.twin = DigitalTwinView()
        self.twin.joint_delta_preview.connect(self._on_twin_delta_preview)
        self.twin.joint_delta_requested.connect(self._on_twin_delta_requested)

        # Primary: Safe Home (parks first, never wraps J6).
        self.btn_home = QPushButton("Home")
        self.btn_home.setToolTip(
            "Safe homing: pre-position J6 (or park first) so the firmware\n"
            "seek motion is short and the gripper cables can't tangle."
        )
        self.btn_safe_home = QPushButton("Safe Home (park-first)")
        self.btn_safe_home.setToolTip(
            "Park first (move all joints to JOINT_HOME_DEG), then trigger\n"
            "firmware home. With J6 already near 180° the firmware seek\n"
            "motion is minimal and won't wrap the long way around.\n"
            "Use this once the arm has been homed at least once."
        )
        # Demoted: bare firmware home (the unsafe path that wriggled J6).
        self.btn_force_home = QPushButton("Force firmware home (unsafe)")
        self.btn_force_home.setToolTip(
            "Send the bare firmware HOME command with no host-side\n"
            "workaround. Only needed if the arm is severely un-homed and\n"
            "you understand the J6 wraparound risk. Confirmation required."
        )
        self.btn_park = QPushButton("Park")
        self.btn_park.setToolTip(
            "Move to the safe known pose JOINT_HOME_DEG = " + str(JOINT_HOME_DEG)
        )
        self.btn_halt = QPushButton("HALT")
        self.btn_halt.setStyleSheet("background-color: #c33; color: white; font-weight: bold;")
        self.spin_jog_step = QDoubleSpinBox()
        self.spin_jog_step.setRange(0.1, 30.0)
        self.spin_jog_step.setDecimals(1)
        self.spin_jog_step.setSingleStep(0.5)
        self.spin_jog_step.setSuffix(" °")
        self.spin_jog_step.setValue(5.0)
        self.spin_jog_step.setToolTip("Joint nudge size for the +/- buttons.")
        self.btn_home.clicked.connect(self._on_home)
        self.btn_safe_home.clicked.connect(self._on_safe_home)
        self.btn_force_home.clicked.connect(self._on_force_home)
        self.btn_park.clicked.connect(self._on_park)
        self.btn_halt.clicked.connect(self._on_halt)

        # --- J6 pre-home workaround controls (PAROL6 firmware bug)
        self.chk_prehome = QCheckBox("Pre-home J6")
        self.chk_prehome.setToolTip(
            "Workaround for the PAROL6 J6 wraparound bug: rotate J6 to a safe\n"
            "angle before triggering firmware homing so the seek is always\n"
            "short and never tangles the gripper air lines."
        )
        self.chk_prehome.setChecked(SETTINGS.robot.prehome_j6_deg is not None)
        self.spin_prehome = QDoubleSpinBox()
        self.spin_prehome.setRange(0.0, 360.0)
        self.spin_prehome.setDecimals(1)
        self.spin_prehome.setSingleStep(5.0)
        self.spin_prehome.setSuffix(" °")
        self.spin_prehome.setValue(SETTINGS.robot.prehome_j6_deg or 180.0)
        self.spin_prehome.setToolTip(
            "Pre-home target for J6. Tune so the firmware seek goes the short\n"
            "way and the cables stay clear; persisted via SETTINGS.robot.prehome_j6_deg."
        )
        # Persist spinner / checkbox into SETTINGS so subsequent homes use it.
        self.spin_prehome.valueChanged.connect(self._sync_prehome_setting)
        self.chk_prehome.toggled.connect(lambda _b: self._sync_prehome_setting())

        controls = QGroupBox("Robot")
        c_layout = QVBoxLayout(controls)
        c_layout.addWidget(self.twin)
        c_layout.addWidget(self.sliders)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_home)
        btn_row.addWidget(self.btn_safe_home)
        btn_row.addWidget(self.btn_park)
        btn_row.addWidget(self.btn_halt)
        c_layout.addLayout(btn_row)
        jog_grid = QGridLayout()
        jog_grid.addWidget(QLabel("Nudge:"), 0, 0)
        jog_grid.addWidget(self.spin_jog_step, 0, 1)
        for i in range(6):
            minus = QPushButton(f"J{i + 1}-")
            plus = QPushButton(f"J{i + 1}+")
            for btn in (minus, plus):
                btn.setAutoRepeat(True)
                btn.setAutoRepeatDelay(350)
                btn.setAutoRepeatInterval(160)
            minus.setToolTip(f"Move J{i + 1} down by the selected nudge size.")
            plus.setToolTip(f"Move J{i + 1} up by the selected nudge size.")
            minus.clicked.connect(lambda _checked=False, idx=i: self._on_jog_joint(idx, -1.0))
            plus.clicked.connect(lambda _checked=False, idx=i: self._on_jog_joint(idx, 1.0))
            row = 1 + (i // 2)
            col = (i % 2) * 3
            jog_grid.addWidget(QLabel(f"J{i + 1}"), row, col)
            jog_grid.addWidget(minus, row, col + 1)
            jog_grid.addWidget(plus, row, col + 2)
        jog_grid.setColumnStretch(6, 1)
        c_layout.addLayout(jog_grid)
        prehome_row = QHBoxLayout()
        prehome_row.addWidget(self.chk_prehome)
        prehome_row.addWidget(QLabel("target:"))
        prehome_row.addWidget(self.spin_prehome)
        prehome_row.addWidget(self.btn_force_home)
        prehome_row.addStretch(1)
        c_layout.addLayout(prehome_row)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.status)
        body_layout.addWidget(controls, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        scroll.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    # --- Public API used by main window and tabs
    def follow_robot_angles(self, angles) -> None:
        self._latest_robot_angles = list(map(float, angles))
        if self.sliders.follow_robot():
            self.sliders.set_angles_no_emit(angles)
        self.twin.set_actual_angles(angles)

    def slider_values(self) -> list[float]:
        return self.sliders.values()

    # --- Slots
    def _on_joint_commit(self, _idx: int, _value: float) -> None:
        if not self.robot.connected:
            self.status.set_message("Robot not connected; sliders advisory only.", error=True)
            return
        self._set_pending_target_from_delta(_idx, _value)
        if self.sliders.is_relative(_idx):
            ok, detail = self.robot.move_joint_delta(_idx, _value)
        else:
            ok, detail = self.robot.move_joint_to_angle(_idx, _value)
        if ok and self.robot.last_command_target_angles is not None:
            self.twin.set_target_angles(self.robot.last_command_target_angles)
        elif not ok:
            self.twin.set_target_angles(None)
        self.status.set_message(detail, error=not ok)

    def _on_slider_preview(self, angles: list[float]) -> None:
        self.twin.set_target_angles(angles)

    def _on_twin_delta_preview(self, idx: int, delta: float) -> None:
        self._set_pending_target_from_delta(idx, delta)

    def _on_twin_delta_requested(self, idx: int, delta: float) -> None:
        if not self.robot.connected:
            self.status.set_message("Robot not connected; twin move advisory only.", error=True)
            return
        self._set_pending_target_from_delta(idx, delta)
        ok, detail = self.robot.move_joint_delta(idx, delta)
        if ok and self.robot.last_command_target_angles is not None:
            self.twin.set_target_angles(self.robot.last_command_target_angles)
        elif not ok:
            self.twin.set_target_angles(None)
        self.status.set_message(f"twin: {detail}", error=not ok)

    def _set_pending_target_from_delta(self, idx: int, delta: float) -> None:
        angles = list(self._latest_robot_angles or self.sliders.values())
        if not (0 <= idx < len(angles)):
            return
        lo, hi = JOINT_LIMITS_DEG[idx]
        angles[idx] = min(max(float(angles[idx]) + float(delta), lo), hi)
        self.twin.set_target_angles(angles)

    def _on_home(self) -> None:
        self.status.set_message("home: sending firmware HOME...")
        QApplication.processEvents()
        ok, detail = self.robot.home(
            prehome_j6_deg=None,
            park_first=False,
            allow_unsafe=True,
            watchdog=False,
        )
        self.status.set_message(f"home: {detail}", error=not ok)

    def _on_safe_home(self) -> None:
        # Park the arm first so the firmware home seek is minimal and the
        # gripper cables can't get tangled.
        self.status.set_message("safe-home: preparing...")
        QApplication.processEvents()
        ok, detail = self.robot.home(prehome_j6_deg=None, park_first=True, watchdog=True)
        self.status.set_message(f"safe-home: {detail}", error=not ok)

    def _on_force_home(self) -> None:
        # Bare firmware HOME, no host-side workaround. Confirmation gate.
        ans = QMessageBox.warning(
            self, "Force firmware home",
            "Send the bare firmware HOME command without any J6 workaround?\n\n"
            "This is the path that has been observed to wrap J6 the long way\n"
            "around and tangle the gripper cables. Keep a finger on HALT.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if ans != QMessageBox.StandardButton.Yes:
            self.status.set_message("force-home cancelled")
            return
        self.status.set_message("force-home: sending firmware HOME...")
        QApplication.processEvents()
        ok, detail = self.robot.home(
            prehome_j6_deg=None,
            park_first=False,
            allow_unsafe=True,
            watchdog=False,
        )
        self.status.set_message(f"force-home: {detail}", error=not ok)

    def _sync_prehome_setting(self) -> None:
        """Mirror checkbox + spinner into SETTINGS so subsequent homes use it."""
        if self.chk_prehome.isChecked():
            SETTINGS.robot.prehome_j6_deg = float(self.spin_prehome.value())
        else:
            SETTINGS.robot.prehome_j6_deg = None

    def _on_park(self) -> None:
        if not self.robot.connected:
            self.status.set_message("Robot not connected; cannot park.")
            return
        ok, detail = self.robot.park()
        self.status.set_message(f"park: {detail}", error=not ok)
        # Refresh sliders to whatever the arm actually ended up at.
        ang = self.robot.angles() if ok else None
        if ang is not None:
            self.sliders.set_angles_no_emit(list(map(float, ang)))
            self.twin.set_actual_angles(ang)

    def _refresh_slider_readback(self) -> None:
        ang = self.robot.angles() if self.robot.connected else None
        if ang is not None:
            self.sliders.set_angles_no_emit(list(map(float, ang)))
            self.twin.set_actual_angles(ang)

    def _on_jog_joint(self, idx: int, direction: float) -> None:
        if not self.robot.connected:
            self.status.set_message("Robot not connected; cannot nudge joint.", error=True)
            return
        step = float(self.spin_jog_step.value()) * float(direction)
        self._set_pending_target_from_delta(idx, step)
        ok, detail = self.robot.move_joint_delta(idx, step)
        if ok and self.robot.last_command_target_angles is not None:
            self.twin.set_target_angles(self.robot.last_command_target_angles)
        elif not ok:
            self.twin.set_target_angles(None)
        self.status.set_message(f"nudge: {detail}", error=not ok)

    def _on_halt(self) -> None:
        ok, detail = self.robot.halt()
        self.status.set_message(f"halt: {detail}", error=not ok)
