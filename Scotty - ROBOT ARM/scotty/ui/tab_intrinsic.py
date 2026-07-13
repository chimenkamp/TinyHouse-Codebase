"""Intrinsic-camera-calibration tab (ChArUco)."""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ..calibration import IntrinsicCalibrator, load_intrinsics
from ..calibration.charuco import detection_quality
from ..config import SETTINGS
from .widgets import VideoLabel


class IntrinsicTab(QWidget):
    """Press *Arm capture* (or toggle *Auto*) while waving the board."""

    def __init__(self) -> None:
        super().__init__()
        self.calib = IntrinsicCalibrator()

        self.video = VideoLabel()

        self.info_label = QLabel("0 captures")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-family: ui-monospace, monospace;")
        existing = load_intrinsics()
        if existing is not None:
            _K, _D, rms = existing
            self.info_label.setText(f"existing intrinsics: rms={rms:.4f} px")

        self.arm_btn = QPushButton("Arm capture (next detected board)")
        self.auto_btn = QPushButton("Auto-capture: OFF")
        self.auto_btn.setCheckable(True)
        self.solve_btn = QPushButton("Solve")
        self.save_btn = QPushButton("Save → intrinsics.npz")
        self.save_btn.setEnabled(False)
        self.reset_btn = QPushButton("Reset captures")

        self.arm_btn.clicked.connect(self._arm)
        self.auto_btn.toggled.connect(self._toggle_auto)
        self.solve_btn.clicked.connect(self._solve)
        self.save_btn.clicked.connect(self._save)
        self.reset_btn.clicked.connect(self._reset)

        controls = QGroupBox("Capture")
        c_layout = QVBoxLayout(controls)
        for b in (self.arm_btn, self.auto_btn, self.solve_btn, self.save_btn, self.reset_btn):
            c_layout.addWidget(b)
        c_layout.addWidget(self.info_label)
        c_layout.addStretch(1)

        layout = QHBoxLayout(self)
        layout.addWidget(self.video, 3)
        layout.addWidget(controls, 1)

        self._last_result = None
        self._last_status = "Show the ChArUco board."

    # Frame pump (called by main window).
    def update_frame(self, frame_bgr: np.ndarray) -> None:
        self.calib.set_image_size(frame_bgr)
        frame, det = self._detect_best_orientation(frame_bgr)
        captured = self.calib.maybe_capture(det)

        display = frame.copy()
        if det.marker_ids is not None and len(det.marker_ids) > 0:
            cv2.aruco.drawDetectedMarkers(display, det.marker_corners, det.marker_ids)
        if det.ids is not None and len(det.ids) > 0:
            cv2.aruco.drawDetectedCornersCharuco(display, det.corners, det.ids)

        n = len(self.calib.captures)
        corner_count = 0 if det.ids is None else int(len(det.ids))
        marker_count = 0 if det.marker_ids is None else int(len(det.marker_ids))
        q = detection_quality(det)
        quality_ok, quality_msg = self.calib.capture_quality(det)
        status_bits = [f"captures: {n}/{SETTINGS.intrinsic.min_captures}",
                       f"markers: {marker_count}",
                       f"corners: {corner_count}",
                       f"coverage: {q.coverage * 100:.1f}%",
                       f"sharp: {q.sharpness:.0f}",
                       f"dict: {self.calib.active_dict_id}"]
        if self.calib.armed:
            status_bits.append("[ARMED]")
        if self.calib.auto_capture:
            status_bits.append("[AUTO]")
        if captured:
            status_bits.append("[CAPTURED]")
        elif self.calib.last_reject_reason and (self.calib.armed or self.calib.auto_capture):
            status_bits.append(f"[SKIP: {self.calib.last_reject_reason}]")
        elif not quality_ok:
            status_bits.append(f"[{quality_msg}]")
        text = "  ".join(status_bits)
        cv2.putText(display, text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 0) if quality_ok else (0, 0, 255), 2)

        self.video.set_frame_bgr(display)
        self.info_label.setText(text)
        self.solve_btn.setEnabled(self.calib.can_solve())

    def _detect_best_orientation(self, frame_bgr: np.ndarray):
        """Detect on raw and mirrored frames; keep whichever decodes best."""
        raw_det = self.calib.detect(frame_bgr)
        flipped = cv2.flip(frame_bgr, 1)
        flip_det = self.calib.detect(flipped)

        def score(det) -> tuple[int, int]:
            charuco = 0 if det.ids is None else int(len(det.ids))
            markers = 0 if det.marker_ids is None else int(len(det.marker_ids))
            return charuco, markers

        if score(flip_det) > score(raw_det):
            return flipped, flip_det
        return frame_bgr, raw_det

    def _arm(self) -> None:
        self.calib.armed = True

    def _toggle_auto(self, on: bool) -> None:
        self.calib.auto_capture = on
        self.auto_btn.setText(f"Auto-capture: {'ON' if on else 'OFF'}")

    def _solve(self) -> None:
        try:
            self._last_result = self.calib.solve()
        except Exception as exc:
            self.info_label.setText(f"Solve failed: {exc}")
            return
        r = self._last_result
        quality_ok = r.rms <= SETTINGS.intrinsic.max_rms_px
        quality = "OK to save" if quality_ok else "FAILED quality gate"
        self.info_label.setText(
            f"rms={r.rms:.4f}px [{quality}]  fx={r.K[0,0]:.1f}  "
            f"fy={r.K[1,1]:.1f}  views={r.n_views}"
        )
        self.save_btn.setEnabled(quality_ok)

    def _save(self) -> None:
        if self._last_result is None:
            return
        if self._last_result.rms > SETTINGS.intrinsic.max_rms_px:
            self.info_label.setText("Save blocked: intrinsic RMS is not good enough.")
            return
        path = self.calib.save(self._last_result)
        self.info_label.setText(f"Saved → {path}")

    def _reset(self) -> None:
        self.calib.reset()
        self._last_result = None
        self.save_btn.setEnabled(False)
        self.info_label.setText("0 captures")
