"""ChArUco board, detector, and pose estimation helpers (OpenCV)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from ..config import SETTINGS


def make_board(charuco=None) -> Any:
    cfg = charuco or SETTINGS.charuco
    dictionary = cv2.aruco.getPredefinedDictionary(cfg.dict_id)
    board = cv2.aruco.CharucoBoard(
        (cfg.squares_x, cfg.squares_y),
        cfg.square_length_m,
        cfg.marker_length_m,
        dictionary,
    )
    return board, dictionary


def make_aruco_detector(dictionary) -> cv2.aruco.ArucoDetector:
    p = cv2.aruco.DetectorParameters()
    p.adaptiveThreshWinSizeMin = 5
    p.adaptiveThreshWinSizeMax = 45
    p.adaptiveThreshWinSizeStep = 4
    p.minMarkerPerimeterRate = 0.01
    p.polygonalApproxAccuracyRate = 0.05
    p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    p.cornerRefinementWinSize = 5
    if hasattr(p, "useAruco3Detection"):
        p.useAruco3Detection = True
    p.errorCorrectionRate = 0.8
    return cv2.aruco.ArucoDetector(dictionary, p)


@dataclass
class CharucoDetection:
    marker_corners: list[np.ndarray]
    marker_ids: np.ndarray | None
    rejected: list[np.ndarray] | None
    corners: np.ndarray | None  # ChArUco interpolated corners
    ids: np.ndarray | None      # ChArUco interpolated ids
    gray: np.ndarray


@dataclass(frozen=True)
class DetectionQuality:
    corners: int
    markers: int
    coverage: float
    sharpness: float

    def label(self) -> str:
        return (
            f"corners={self.corners} markers={self.markers} "
            f"coverage={self.coverage * 100:.1f}% sharp={self.sharpness:.0f}"
        )


@dataclass(frozen=True)
class BoardPoseEstimate:
    rvec: np.ndarray
    tvec: np.ndarray
    reprojection_error_px: float
    corners: int


def detection_quality(detection: CharucoDetection) -> DetectionQuality:
    corners = 0 if detection.ids is None else int(len(detection.ids))
    markers = 0 if detection.marker_ids is None else int(len(detection.marker_ids))
    coverage = 0.0
    if detection.corners is not None and len(detection.corners) > 0:
        pts = detection.corners.reshape(-1, 2)
        x, y, w, h = cv2.boundingRect(pts.astype(np.float32))
        image_area = max(1, detection.gray.shape[0] * detection.gray.shape[1])
        coverage = float((w * h) / image_area)
    sharpness = float(cv2.Laplacian(detection.gray, cv2.CV_64F).var())
    return DetectionQuality(corners, markers, coverage, sharpness)


def detect_charuco(
    frame_bgr: np.ndarray,
    detector: cv2.aruco.ArucoDetector,
    board,
    clahe=None,
) -> CharucoDetection:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    if clahe is not None:
        gray = clahe.apply(gray)
    marker_corners, marker_ids, rejected = detector.detectMarkers(gray)
    corners, ids = None, None
    if marker_ids is not None and len(marker_ids) > 0:
        try:
            _, corners, ids = cv2.aruco.interpolateCornersCharuco(
                marker_corners, marker_ids, gray, board
            )
        except cv2.error:
            corners, ids = None, None
    return CharucoDetection(marker_corners, marker_ids, rejected, corners, ids, gray)


def estimate_board_pose(
    detection: CharucoDetection,
    board,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (rvec, tvec) of the board in the camera frame, or ``None``."""
    estimate = estimate_board_pose_quality(
        detection, board, camera_matrix, dist_coeffs
    )
    if estimate is None:
        return None
    return estimate.rvec, estimate.tvec


def estimate_board_pose_quality(
    detection: CharucoDetection,
    board,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
) -> BoardPoseEstimate | None:
    """Return board pose plus reprojection quality, or ``None``."""
    if detection.corners is None or detection.ids is None or len(detection.ids) < 4:
        return None
    obj_pts, img_pts = board.matchImagePoints(detection.corners, detection.ids)
    if obj_pts is None or len(obj_pts) < 4:
        return None
    ok, rvec, tvec = cv2.solvePnP(
        obj_pts, img_pts, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
    )
    if not ok:
        return None
    projected, _ = cv2.projectPoints(obj_pts, rvec, tvec, camera_matrix, dist_coeffs)
    err = np.linalg.norm(
        projected.reshape(-1, 2) - img_pts.reshape(-1, 2), axis=1
    )
    return BoardPoseEstimate(
        rvec=rvec,
        tvec=tvec,
        reprojection_error_px=float(np.sqrt(np.mean(np.square(err)))),
        corners=int(len(obj_pts)),
    )
