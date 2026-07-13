"""Hand-eye calibration tab.

Robot motion (sliders, Home, Park, HALT) lives in the shared header above
the tabs — this tab only owns the camera view, capture buttons, and sample
list.

Workflow:
    1. Move the robot with the header nudge buttons or sliders to a new pose.
    2. When the ChArUco board is detected, click *Capture sample*.
    3. Repeat ≥ 15 times in varied orientations.
    4. *Solve* and *Save → hand_eye.npz*.
"""

from __future__ import annotations

from typing import Callable

import cv2
import numpy as np
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget,
)

from ..calibration import (
    HandEyeSample,
    load_intrinsics,
    make_aruco_detector,
    make_board,
    parol6_fk,
    pose_mm_deg_to_transform,
    save_hand_eye,
    solve_hand_eye,
)
from ..calibration.charuco import (
    detect_charuco,
    detection_quality,
    estimate_board_pose_quality,
)
from ..config import SETTINGS
from ..robot import Parol6Controller
from .widgets import VideoLabel


class HandEyeTab(QWidget):
    def __init__(self, robot: Parol6Controller, get_slider_angles: Callable[[], list[float]]) -> None:
        super().__init__()
        self.robot = robot
        self.samples: list[HandEyeSample] = []

        intr = load_intrinsics()
        if intr is None:
            self.K = None
            self.D = None
        else:
            self.K, self.D, _ = intr
        self.board, self.dictionary = make_board()
        self.detector = make_aruco_detector(self.dictionary)
        self.clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

        self.video = VideoLabel()

        self.sample_list = QListWidget()
        self.sample_list.setMinimumHeight(160)

        self.info_label = QLabel("Move the robot with nudge buttons or sliders, then capture.")
        self.live_label = QLabel("Live: no board")
        self.info_label.setWordWrap(True)
        self.live_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-family: ui-monospace, monospace;")
        self.live_label.setStyleSheet("font-family: ui-monospace, monospace; color: #aaa;")

        self.capture_btn = QPushButton("Capture sample")
        self.drop_btn = QPushButton("Drop selected")
        self.solve_btn = QPushButton("Solve")
        self.save_btn = QPushButton("Save → hand_eye.npz")
        self.solve_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.capture_btn.clicked.connect(self._on_capture)
        self.drop_btn.clicked.connect(self._on_drop)
        self.solve_btn.clicked.connect(self._on_solve)
        self.save_btn.clicked.connect(self._on_save)

        controls = QGroupBox("Hand-eye")
        c_layout = QVBoxLayout(controls)
        c_layout.addWidget(self.live_label)
        c_layout.addWidget(self.info_label)
        c_layout.addWidget(self.capture_btn)
        c_layout.addWidget(self.drop_btn)
        c_layout.addWidget(self.solve_btn)
        c_layout.addWidget(self.save_btn)
        c_layout.addWidget(QLabel("Samples:"))
        c_layout.addWidget(self.sample_list, 1)

        layout = QHBoxLayout(self)
        layout.addWidget(self.video, 3)
        layout.addWidget(controls, 2)

        self._latest_pose = None  # last (rvec, tvec) of board in camera
        self._latest_pose_quality = None
        self._last_solve = None   # (T, rms_rot, rms_trans)
        self._last_solve_ok = False

    # --- frame pump
    def update_frame(self, frame_bgr: np.ndarray) -> None:
        # Un-mirror.
        frame = cv2.flip(frame_bgr, 1)
        if self.K is None:
            self.video.set_frame_bgr(frame)
            return
        det = detect_charuco(frame, self.detector, self.board, self.clahe)
        display = frame.copy()
        if det.marker_ids is not None and len(det.marker_ids) > 0:
            cv2.aruco.drawDetectedMarkers(display, det.marker_corners, det.marker_ids)
        if det.ids is not None and len(det.ids) > 0:
            cv2.aruco.drawDetectedCornersCharuco(display, det.corners, det.ids)
        q = detection_quality(det)
        pose = estimate_board_pose_quality(det, self.board, self.K, self.D)
        if pose is not None:
            rvec, tvec = pose.rvec, pose.tvec
            cv2.drawFrameAxes(display, self.K, self.D, rvec, tvec, 0.04)
            self._latest_pose = (rvec.copy(), tvec.copy())
            self._latest_pose_quality = pose
            quality_ok, reason = self._current_board_quality()
            self.live_label.setText(
                f"Live: {q.label()} boardErr={pose.reprojection_error_px:.2f}px "
                f"{'OK' if quality_ok else reason}"
            )
        else:
            self._latest_pose = None
            self._latest_pose_quality = None
            self.live_label.setText(f"Live: {q.label()} board pose not solved")
        self.video.set_frame_bgr(display)

    # --- buttons
    def _on_capture(self) -> None:
        if self._latest_pose is None or self._latest_pose_quality is None:
            self.info_label.setText("Capture rejected: no board pose available.")
            return
        quality_ok, reason = self._current_board_quality()
        if not quality_ok:
            self.info_label.setText(f"Capture rejected: {reason}")
            return
        rvec, tvec = self._latest_pose
        if not self.robot.connected:
            self.info_label.setText("Capture rejected: robot must be connected for hand-eye.")
            return
        angles = self.robot.angles()
        if angles is None:
            self.info_label.setText("Capture rejected: could not read joint angles.")
            return
        angles_arr = np.asarray(angles, dtype=float)
        T_b_g = parol6_fk(angles_arr)
        pose = self.robot.pose()
        pose_note = ""
        if pose is not None:
            T_pose = pose_mm_deg_to_transform(pose)
            pose_delta_mm = float(np.linalg.norm(T_pose[:3, 3] - T_b_g[:3, 3]) * 1000.0)
            pose_note = f" pose-vs-FK={pose_delta_mm:.0f}mm"
        duplicate, dup_reason = self._pose_too_close_to_existing(T_b_g)
        if duplicate:
            self.info_label.setText(f"Capture rejected: {dup_reason}")
            return
        sample = HandEyeSample(
            joints_deg=angles_arr,
            T_base_gripper=T_b_g,
            rvec_target_cam=rvec,
            tvec_target_cam=tvec,
            board_reprojection_px=float(self._latest_pose_quality.reprojection_error_px),
            charuco_corners=int(self._latest_pose_quality.corners),
        )
        self.samples.append(sample)
        self.solve_btn.setEnabled(len(self.samples) >= 5)
        self.sample_list.addItem(
            f"{len(self.samples):02d}  J=[" + ",".join(f"{a:+6.1f}" for a in angles) +
            f"]  err={sample.board_reprojection_px:.2f}px  "
            f"gxyz(mm)={(T_b_g[:3, 3] * 1000.0).round(0).tolist()}  "
            f"t=[{float(tvec[0]):+.3f},{float(tvec[1]):+.3f},{float(tvec[2]):+.3f}]"
        )
        self.info_label.setText(self._sample_summary() + pose_note)

    def _on_drop(self) -> None:
        row = self.sample_list.currentRow()
        if row < 0 or row >= len(self.samples):
            return
        del self.samples[row]
        self.sample_list.takeItem(row)
        self.solve_btn.setEnabled(len(self.samples) >= 5)
        self.save_btn.setEnabled(False)
        self._last_solve = None
        self._last_solve_ok = False
        self.info_label.setText(self._sample_summary())

    def _on_solve(self) -> None:
        try:
            T, rms_rot, rms_trans = solve_hand_eye(self.samples)
        except Exception as exc:
            self.info_label.setText(f"Solve failed: {exc}")
            self.save_btn.setEnabled(False)
            return
        self._last_solve = (T, rms_rot, rms_trans)
        self._last_solve_ok = self._solve_quality_ok(rms_rot, rms_trans)
        verdict = "OK to save" if self._last_solve_ok else "FAILED quality gate"
        self.info_label.setText(
            f"PARK: rms_rot={rms_rot:.3f}°  rms_trans={rms_trans*1000:.2f}mm  "
            f"{verdict}. {self._sample_summary()}"
        )
        self.save_btn.setEnabled(self._last_solve_ok)

    def _on_save(self) -> None:
        if self._last_solve is None or not self._last_solve_ok:
            self.info_label.setText("Save blocked: solve quality is not good enough.")
            return
        T, rms_rot, rms_trans = self._last_solve
        path = save_hand_eye(T, len(self.samples), rms_rot, rms_trans)
        self.info_label.setText(f"Saved → {path}")

    def _current_board_quality(self) -> tuple[bool, str]:
        pose = self._latest_pose_quality
        if pose is None:
            return False, "board pose not solved"
        cfg = SETTINGS.hand_eye
        if pose.corners < cfg.min_corners_per_sample:
            return False, f"need at least {cfg.min_corners_per_sample} corners"
        if pose.reprojection_error_px > cfg.max_board_reprojection_px:
            return False, (
                f"board reprojection {pose.reprojection_error_px:.2f}px > "
                f"{cfg.max_board_reprojection_px:.2f}px"
            )
        return True, "OK"

    def _solve_quality_ok(self, rms_rot: float, rms_trans: float) -> bool:
        cfg = SETTINGS.hand_eye
        return (
            len(self.samples) >= cfg.min_samples
            and rms_rot <= cfg.max_rms_rotation_deg
            and rms_trans <= cfg.max_rms_translation_m
        )

    def _pose_too_close_to_existing(self, T_b_g: np.ndarray) -> tuple[bool, str]:
        cfg = SETTINGS.hand_eye
        for i, sample in enumerate(self.samples, start=1):
            trans_delta = float(np.linalg.norm(T_b_g[:3, 3] - sample.T_base_gripper[:3, 3]))
            dR = sample.T_base_gripper[:3, :3].T @ T_b_g[:3, :3]
            rot_delta = float(
                np.degrees(
                    np.arccos(np.clip((np.trace(dR) - 1.0) / 2.0, -1.0, 1.0))
                )
            )
            if trans_delta < cfg.min_pose_delta_m and rot_delta < cfg.min_pose_delta_deg:
                return (
                    True,
                    f"too close to sample {i:02d} "
                    f"({trans_delta * 1000:.1f}mm/{rot_delta:.1f}deg)",
                )
        return False, ""

    def _sample_summary(self) -> str:
        cfg = SETTINGS.hand_eye
        n = len(self.samples)
        if n == 0:
            return f"0 sample(s); need >= {cfg.min_samples}"
        reproj = np.asarray([s.board_reprojection_px for s in self.samples], dtype=float)
        corners = [s.charuco_corners for s in self.samples]
        trans = np.asarray([s.T_base_gripper[:3, 3] for s in self.samples], dtype=float)
        span_mm = float(np.linalg.norm(np.ptp(trans, axis=0)) * 1000.0) if n > 1 else 0.0
        rot_span = 0.0
        if n > 1:
            R0 = self.samples[0].T_base_gripper[:3, :3]
            for s in self.samples[1:]:
                dR = R0.T @ s.T_base_gripper[:3, :3]
                angle = np.degrees(
                    np.arccos(np.clip((np.trace(dR) - 1.0) / 2.0, -1.0, 1.0))
                )
                rot_span = max(rot_span, float(angle))
        return (
            f"{n} sample(s); need >= {cfg.min_samples}; "
            f"boardErr avg/max={np.nanmean(reproj):.2f}/{np.nanmax(reproj):.2f}px; "
            f"corners min={min(corners)}; robot span={span_mm:.0f}mm/{rot_span:.0f}deg"
        )
