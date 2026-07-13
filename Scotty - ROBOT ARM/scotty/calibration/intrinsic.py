"""Camera intrinsic calibration via ChArUco corners.

UI-friendly: the GUI repeatedly hands frames to :meth:`add_frame`, the
calibrator decides (auto or manual) whether to keep them, and finally the
GUI calls :meth:`solve` and :meth:`save`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import cv2
import numpy as np

from ..config import SETTINGS
from .charuco import (
    CharucoDetection,
    detect_charuco,
    detection_quality,
    make_aruco_detector,
    make_board,
)


def load_intrinsics(path: Path | None = None) -> tuple[np.ndarray, np.ndarray, float] | None:
    p = Path(path) if path is not None else SETTINGS.files.intrinsics
    if not p.exists():
        return None
    with np.load(p) as data:
        K = data["intrinsics"]
        D = data["distortion"]
        err = float(data["reprojection_error"]) if "reprojection_error" in data.files else float("nan")
    return K.astype(np.float64), D.astype(np.float64), err


@dataclass
class IntrinsicResult:
    rms: float
    K: np.ndarray
    D: np.ndarray
    image_size: tuple[int, int]
    n_views: int


@dataclass
class IntrinsicCalibrator:
    auto_capture: bool = False
    armed: bool = False
    captures: list[tuple[np.ndarray, np.ndarray]] = field(default_factory=list)
    image_size: tuple[int, int] | None = None
    last_auto_at: float = 0.0
    active_dict_id: int = 0
    last_reject_reason: str = ""

    def __post_init__(self) -> None:
        self.board, self.dictionary = make_board()
        self.detector = make_aruco_detector(self.dictionary)
        self.active_dict_id = int(SETTINGS.charuco.dict_id)
        self._detector_options = self._make_detector_options()
        self.clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

    def _make_detector_options(self):
        ids = [
            SETTINGS.charuco.dict_id,
            cv2.aruco.DICT_5X5_100,
            cv2.aruco.DICT_5X5_250,
            cv2.aruco.DICT_5X5_50,
            cv2.aruco.DICT_5X5_1000,
        ]
        seen: set[int] = set()
        options = []
        for dict_id in ids:
            if int(dict_id) in seen:
                continue
            seen.add(int(dict_id))
            board, dictionary = make_board(
                charuco=SimpleNamespace(
                    dict_id=int(dict_id),
                    squares_x=SETTINGS.charuco.squares_x,
                    squares_y=SETTINGS.charuco.squares_y,
                    square_length_m=SETTINGS.charuco.square_length_m,
                    marker_length_m=SETTINGS.charuco.marker_length_m,
                )
            )
            options.append((int(dict_id), board, dictionary, make_aruco_detector(dictionary)))
        return options

    # Per-frame
    def detect(self, frame_bgr: np.ndarray) -> CharucoDetection:
        best = None
        best_score = (-1, -1)
        best_option = None
        for option in self._detector_options:
            dict_id, board, _dictionary, detector = option
            det = detect_charuco(frame_bgr, detector, board, self.clahe)
            score = (
                0 if det.ids is None else int(len(det.ids)),
                0 if det.marker_ids is None else int(len(det.marker_ids)),
            )
            if score > best_score:
                best = det
                best_score = score
                best_option = option
            if score[0] >= 4:
                break
        if best_option is not None and best_score[1] > 0:
            dict_id, self.board, self.dictionary, self.detector = best_option
            self.active_dict_id = int(dict_id)
        return best if best is not None else detect_charuco(frame_bgr, self.detector, self.board, self.clahe)

    def maybe_capture(self, det: CharucoDetection) -> bool:
        """Decide whether to keep this detection given current arm/auto state."""
        self.last_reject_reason = ""
        if det.corners is None or det.ids is None or len(det.ids) < 4:
            self.last_reject_reason = "board pose not detected"
            return False
        now = time.time()
        keep = False
        if self.armed:
            keep = True
        elif self.auto_capture and now - self.last_auto_at > SETTINGS.intrinsic.auto_capture_interval_s:
            keep = True
            self.last_auto_at = now
        if keep:
            ok, reason = self.capture_quality(det)
            if not ok:
                self.last_reject_reason = reason
                return False
            self.armed = False
            self.captures.append((det.corners.copy(), det.ids.copy()))
            return True
        return False

    def capture_quality(self, det: CharucoDetection) -> tuple[bool, str]:
        q = detection_quality(det)
        cfg = SETTINGS.intrinsic
        if q.corners < cfg.min_corners_per_capture:
            return False, f"need at least {cfg.min_corners_per_capture} ChArUco corners"
        if q.coverage < cfg.min_board_coverage:
            return False, f"board too small in frame ({q.coverage * 100:.1f}%)"
        if q.sharpness < cfg.min_sharpness:
            return False, f"image too blurry (sharpness {q.sharpness:.0f})"
        return True, "ok"

    def set_image_size(self, frame_bgr: np.ndarray) -> None:
        self.image_size = (frame_bgr.shape[1], frame_bgr.shape[0])

    def reset(self) -> None:
        self.captures.clear()
        self.armed = False
        self.auto_capture = False
        self.image_size = None
        self.last_reject_reason = ""

    def can_solve(self) -> bool:
        return self.image_size is not None and len(self.captures) >= max(
            8, SETTINGS.intrinsic.min_captures
        )

    def solve(self) -> IntrinsicResult:
        if self.image_size is None:
            raise RuntimeError("No frames seen yet")
        if len(self.captures) < SETTINGS.intrinsic.min_captures:
            raise RuntimeError(
                f"Need at least {SETTINGS.intrinsic.min_captures} captures (have {len(self.captures)})"
            )
        object_points: list[np.ndarray] = []
        image_points: list[np.ndarray] = []
        for corners, ids in self.captures:
            obj_pts, img_pts = self.board.matchImagePoints(corners, ids)
            if obj_pts is not None and len(obj_pts) >= 4:
                object_points.append(obj_pts)
                image_points.append(img_pts)
        if len(object_points) < SETTINGS.intrinsic.min_captures:
            raise RuntimeError("Too few valid 3D-2D correspondences for calibration")
        rms, K, D, _, _ = cv2.calibrateCamera(
            object_points, image_points, self.image_size, None, None
        )
        return IntrinsicResult(float(rms), K, D, self.image_size, len(object_points))

    def save(self, result: IntrinsicResult, path: Path | None = None) -> Path:
        out = Path(path) if path is not None else SETTINGS.files.intrinsics
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            out,
            intrinsics=result.K,
            distortion=result.D,
            reprojection_error=result.rms,
            image_size=np.asarray(result.image_size, dtype=int),
            n_views=int(result.n_views),
        )
        return out
