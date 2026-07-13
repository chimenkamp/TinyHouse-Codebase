"""Detect LEGO bricks (Roboflow) → click to project to table → grasp.

Pipeline:
    1. Toggle inference on; bricks get bounding boxes overlayed on the live feed.
    2. Click a brick in the video to compute its (X, Y, Z) on the table plane
       in the robot base frame.
    3. *Plan grasp* visualises the planned hover/grasp/lift Cartesian poses.
    4. *Execute grasp* (only if robot connected) sends move_l commands.
"""

from __future__ import annotations

import cv2
import numpy as np
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QListWidget, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from ..calibration import load_intrinsics, load_hand_eye, pose_mm_deg_to_transform
from ..config import SETTINGS
from ..grasp import GraspPlan, plan_topdown_grasp
from ..robot import Parol6Controller
from ..vision import LegoDetector, pixel_to_table_xy
from ..vision.detector import LocalColorLegoDetector, LocalYoloV7LegoDetector
from ..vision.detector import Detection, annotate
from .widgets import VideoLabel


class DetectGraspTab(QWidget):
    def __init__(self, robot: Parol6Controller) -> None:
        super().__init__()
        self.robot = robot
        self.roboflow_detector = LegoDetector()
        self.local_detector = LocalColorLegoDetector()
        self.yolov7_detector = LocalYoloV7LegoDetector()
        self.detector = self.local_detector

        intr = load_intrinsics()
        self.K = intr[0] if intr else None
        self.D = intr[1] if intr else None
        self.T_gripper_cam = load_hand_eye()
        self._intrinsics_mtime = 0.0
        self._hand_eye_mtime = 0.0
        self._last_calib_reload_at = 0.0

        self.video = VideoLabel()
        self.video.pixel_clicked.connect(self._on_pixel_clicked)

        self.infer_cb = QCheckBox("Run inference")
        self.detector_mode = QComboBox()
        self.detector_mode.addItem("Local color (offline)", "local")
        self.detector_mode.addItem("Local YOLOv7 (offline)", "yolov7")
        self.detector_mode.addItem("Roboflow", "roboflow")
        self.detector_mode.currentIndexChanged.connect(self._set_detector_mode)
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.05, 0.95)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setValue(SETTINGS.detection.confidence)
        self.confidence_spin.setMinimumWidth(130)

        self.table_z_spin = QDoubleSpinBox()
        self.table_z_spin.setRange(-1000.0, 1000.0)
        self.table_z_spin.setDecimals(0)
        self.table_z_spin.setSingleStep(1.0)
        self.table_z_spin.setValue(SETTINGS.grasp.table_z_m * 1000.0)
        self.table_z_spin.setSuffix(" mm")
        self.table_z_spin.setMinimumWidth(130)

        self.detections_list = QListWidget()
        self.detections_list.setMinimumHeight(150)

        self.target_label = QLabel("Target: none — click a brick in the video.")
        self.target_label.setWordWrap(True)
        self.target_label.setStyleSheet("font-family: ui-monospace, monospace;")

        self.plan_label = QLabel("")
        self.plan_label.setWordWrap(True)
        self.plan_label.setStyleSheet("font-family: ui-monospace, monospace; color: #888;")

        self.plan_btn = QPushButton("Plan grasp from selected pixel")
        self.plan_btn.setEnabled(False)
        self.execute_btn = QPushButton("Execute grasp (move_l)")
        self.execute_btn.setEnabled(False)
        self.plan_btn.clicked.connect(self._on_plan)
        self.execute_btn.clicked.connect(self._on_execute)

        settings_box = QGroupBox("Settings")
        settings_layout = QFormLayout(settings_box)
        settings_layout.setContentsMargins(10, 10, 10, 10)
        settings_layout.setSpacing(8)
        settings_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        settings_layout.addRow(self.infer_cb)
        settings_layout.addRow("Detector", self.detector_mode)
        settings_layout.addRow("Confidence", self.confidence_spin)
        settings_layout.addRow("Table Z", self.table_z_spin)

        inference_box = QGroupBox("Inference")
        inference_layout = QVBoxLayout(inference_box)
        inference_layout.setContentsMargins(10, 10, 10, 10)
        inference_layout.addWidget(self.detections_list, 1)

        target_box = QGroupBox("Target")
        target_layout = QVBoxLayout(target_box)
        target_layout.setContentsMargins(10, 10, 10, 10)
        target_layout.setSpacing(8)
        target_layout.addWidget(self.target_label)
        target_layout.addWidget(self.plan_btn)
        target_layout.addWidget(self.execute_btn)
        target_layout.addWidget(self.plan_label)

        controls = QWidget()
        controls.setMinimumWidth(360)
        c_layout = QVBoxLayout(controls)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(10)
        c_layout.addWidget(settings_box)
        c_layout.addWidget(inference_box, 1)
        c_layout.addWidget(target_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(controls)
        scroll.setMinimumWidth(380)

        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.video, 5)
        layout.addWidget(scroll, 2)

        self._latest_frame: np.ndarray | None = None
        self._latest_detections: list[Detection] = []
        self._selected_pixel: tuple[float, float] | None = None
        self._selected_world: tuple[float, float, float] | None = None
        self._plan: GraspPlan | None = None
        self._projection_error = ""

        # Inference is rate-limited so we don't peg the CPU and the network.
        self._infer_timer = QTimer(self)
        self._infer_timer.setInterval(400)  # 2.5 Hz
        self._infer_timer.timeout.connect(self._maybe_infer)
        self._infer_timer.start()

    # --- frame pump
    def update_frame(self, frame_bgr: np.ndarray) -> None:
        self._reload_calibration_files(throttle_s=1.0)
        frame = cv2.flip(frame_bgr, 1)
        self._latest_frame = frame.copy()
        display = frame.copy()
        if self._latest_detections:
            annotate(display, self._latest_detections)
        if self._selected_pixel is not None:
            u, v = self._selected_pixel
            cv2.drawMarker(display, (int(u), int(v)), (0, 255, 255),
                           cv2.MARKER_CROSS, 24, 2)
        cv2.putText(display,
                    f"K:{'OK' if self.K is not None else 'MISSING'}  "
                    f"hand-eye:{'OK' if self.T_gripper_cam is not None else 'MISSING'}  "
                    f"detections:{len(self._latest_detections)}",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        self.video.set_frame_bgr(display)

    def _maybe_infer(self) -> None:
        if not self.infer_cb.isChecked() or self._latest_frame is None:
            return
        self._set_detector_mode()
        dets = self.detector.infer(self._latest_frame, self.confidence_spin.value())
        self._latest_detections = dets
        self.detections_list.clear()
        for i, d in enumerate(dets):
            self.detections_list.addItem(
                f"{i:02d} {d.class_name:<8s} {d.confidence:.2f}  "
                f"({d.cx:.0f},{d.cy:.0f})  {int(d.w)}x{int(d.h)}"
            )
        if self.detector.last_error and not dets:
            self.detections_list.addItem(f"!! {self.detector.last_error}")

    def _set_detector_mode(self) -> None:
        mode = self.detector_mode.currentData()
        if mode == "roboflow":
            self.detector = self.roboflow_detector
        elif mode == "yolov7":
            self.detector = self.yolov7_detector
        else:
            self.detector = self.local_detector

    # --- pixel click
    def _on_pixel_clicked(self, u: float, v: float) -> None:
        # Snap to nearest detection centre if any.
        if self._latest_detections:
            best = min(self._latest_detections,
                       key=lambda d: (d.cx - u) ** 2 + (d.cy - v) ** 2)
            u, v = best.cx, best.cy
        self._selected_pixel = (u, v)
        self._selected_world = self._project_pixel(u, v)
        if self._selected_world is None:
            self.plan_btn.setEnabled(False)
            self.execute_btn.setEnabled(False)
            self.target_label.setText(
                f"Selected pixel ({u:.1f},{v:.1f}) — projection failed: {self._projection_error}"
            )
        else:
            self.plan_btn.setEnabled(True)
            x, y, z = self._selected_world
            self.target_label.setText(
                f"Selected pixel ({u:.1f},{v:.1f}) → base XYZ "
                f"({x*1000:+.1f}, {y*1000:+.1f}, {z*1000:+.1f}) mm"
            )

    def _project_pixel(self, u: float, v: float) -> tuple[float, float, float] | None:
        self._reload_calibration_files(throttle_s=0.0)
        missing = []
        if self.K is None or self.D is None:
            missing.append("intrinsics")
        if self.T_gripper_cam is None:
            missing.append("hand-eye")
        if missing:
            self._projection_error = "missing " + " + ".join(missing)
            return None
        pose = self.robot.pose() if self.robot.connected else None
        if pose is None:
            self._projection_error = "missing live robot pose"
            return None
        T_b_g = pose_mm_deg_to_transform(pose)
        projected = pixel_to_table_xy(
            u, v, self.K, self.D, T_b_g, self.T_gripper_cam,
            table_z_m=float(self.table_z_spin.value()) / 1000.0,
            min_abs_ray_z=SETTINGS.grasp.min_table_ray_z_abs,
            max_ray_distance_m=SETTINGS.grasp.max_table_ray_distance_m,
        )
        if projected is None:
            self._projection_error = self._projection_failure_detail(u, v, T_b_g)
            return None
        self._projection_error = ""
        return projected

    def _projection_failure_detail(self, u: float, v: float, T_b_g: np.ndarray) -> str:
        table_z_m = float(self.table_z_spin.value()) / 1000.0
        try:
            pts = np.array([[[u, v]]], dtype=np.float64)
            undist = cv2.undistortPoints(pts, self.K, self.D)  # type: ignore[arg-type]
            nx, ny = float(undist[0, 0, 0]), float(undist[0, 0, 1])
            ray_cam = np.array([nx, ny, 1.0, 0.0])
            origin_cam = np.array([0.0, 0.0, 0.0, 1.0])
            T_b_c = T_b_g @ self.T_gripper_cam  # type: ignore[arg-type]
            origin = (T_b_c @ origin_cam)[:3]
            direction = (T_b_c @ ray_cam)[:3]
            direction = direction / max(1e-9, float(np.linalg.norm(direction)))
            dz = float(direction[2])
            denom = dz if abs(dz) > 1e-9 else float("nan")
            t = (table_z_m - float(origin[2])) / denom
            if abs(dz) < SETTINGS.grasp.min_table_ray_z_abs:
                reason = "ray is almost parallel to table"
            elif t <= 0.0:
                reason = "ray points away from table"
            elif t > SETTINGS.grasp.max_table_ray_distance_m:
                reason = "table hit is implausibly far from camera"
            else:
                reason = "ray/table intersection invalid"

            quality = self._hand_eye_quality_text()
            return (
                f"{reason}: camZ={origin[2] * 1000:+.0f}mm, "
                f"rayZ={dz:+.2f}, rayLen={t:.2f}m, "
                f"tableZ={table_z_m * 1000:+.0f}mm. "
                f"{quality}"
            )
        except Exception as exc:
            return f"camera ray does not hit table Z ({type(exc).__name__}: {exc})"

    def _hand_eye_quality_text(self) -> str:
        try:
            with np.load(SETTINGS.files.hand_eye) as data:
                rot = float(data["rms_rotation_deg"]) if "rms_rotation_deg" in data.files else float("nan")
                trans = (
                    float(data["rms_translation_m"]) * 1000.0
                    if "rms_translation_m" in data.files else float("nan")
                )
            if np.isfinite(rot) and np.isfinite(trans):
                cfg = SETTINGS.hand_eye
                verdict = (
                    "hand-eye quality OK"
                    if rot <= cfg.max_rms_rotation_deg
                    and trans <= cfg.max_rms_translation_m * 1000.0
                    else "redo hand-eye"
                )
                return f"{verdict}; loaded RMS is {rot:.1f}deg/{trans:.0f}mm."
        except Exception:
            pass
        return "Redo hand-eye calibration."

    def _reload_calibration_files(self, throttle_s: float = 1.0) -> None:
        now = time.monotonic()
        if throttle_s > 0.0 and now - self._last_calib_reload_at < throttle_s:
            return
        self._last_calib_reload_at = now

        intr_path = SETTINGS.files.intrinsics
        intr_mtime = intr_path.stat().st_mtime if intr_path.exists() else 0.0
        if intr_mtime and (
            self.K is None or self.D is None or intr_mtime != self._intrinsics_mtime
        ):
            intr = load_intrinsics()
            if intr is not None:
                self.K, self.D = intr[0], intr[1]
                self._intrinsics_mtime = intr_mtime

        hand_eye_path = SETTINGS.files.hand_eye
        hand_eye_mtime = hand_eye_path.stat().st_mtime if hand_eye_path.exists() else 0.0
        if hand_eye_mtime and (
            self.T_gripper_cam is None or hand_eye_mtime != self._hand_eye_mtime
        ):
            self.T_gripper_cam = load_hand_eye()
            self._hand_eye_mtime = hand_eye_mtime

    # --- buttons
    def _on_plan(self) -> None:
        if self._selected_world is None:
            if self._selected_pixel is None:
                self.plan_label.setText("Pick a pixel first.")
            else:
                self.plan_label.setText(f"Cannot plan: projection failed ({self._projection_error})")
            return
        pose = self.robot.pose() if self.robot.connected else None
        self._plan = plan_topdown_grasp(self._selected_world, pose)
        self.plan_label.setText(
            "Plan: hover → grasp → lift\n"
            f"  hover {self._plan.hover}\n"
            f"  grasp {self._plan.grasp}\n"
            f"  lift  {self._plan.lift}"
        )
        self.execute_btn.setEnabled(self.robot.connected)

    def _on_execute(self) -> None:
        if self._plan is None or not self.robot.connected:
            return
        for label, p in (("hover", self._plan.hover), ("grasp", self._plan.grasp),
                         ("lift", self._plan.lift)):
            ok, msg = self.robot.move_to_pose(p, duration=2.5)
            self.plan_label.setText(self.plan_label.text() + f"\n  ▶ {label}: {msg}")
            if not ok:
                return
