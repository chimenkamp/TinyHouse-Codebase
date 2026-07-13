"""Hand-eye calibration: gripper-mounted camera + ChArUco target.

Wraps OpenCV's ``calibrateHandEye`` (PARK) plus a residual estimate.
Also bundles the PAROL6 forward-kinematics fallback used to compute
``T_base_gripper`` from joint angles when the controller's pose readback
is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..config import SETTINGS

# ----- PAROL6 modified-DH chain (fallback FK) -----
PAROL6_DH = np.array(
    [
        # alpha_{i-1}, a_{i-1}, d_i,    theta_offset
        [0.0,           0.0,    0.1105, 0.0],
        [-np.pi / 2,    0.0,    0.0,    -np.pi / 2],
        [0.0,           0.180,  0.0,    0.0],
        [-np.pi / 2,    0.0,    0.17655, 0.0],
        [np.pi / 2,     0.0,    0.0,    0.0],
        [-np.pi / 2,    0.0,    0.06542, 0.0],
    ],
    dtype=float,
)


def _dh_transform(alpha: float, a: float, d: float, theta: float) -> np.ndarray:
    ca, sa = np.cos(alpha), np.sin(alpha)
    ct, st = np.cos(theta), np.sin(theta)
    return np.array(
        [
            [ct,      -st,     0.0,    a],
            [st * ca, ct * ca, -sa,   -sa * d],
            [st * sa, ct * sa,  ca,    ca * d],
            [0.0,     0.0,     0.0,    1.0],
        ],
        dtype=float,
    )


def parol6_fk(joint_angles_deg: np.ndarray) -> np.ndarray:
    """6 joint angles (degrees) -> T_base_gripper (4x4, m)."""
    if joint_angles_deg.shape != (6,):
        raise ValueError(f"Expected 6 joint angles, got shape {joint_angles_deg.shape}")
    thetas = np.deg2rad(joint_angles_deg)
    T = np.eye(4)
    for i in range(6):
        alpha, a, d, off = PAROL6_DH[i]
        T = T @ _dh_transform(alpha, a, d, thetas[i] + off)
    return T


def pose_mm_deg_to_transform(pose: np.ndarray | list[float]) -> np.ndarray:
    """Convert controller pose [x,y,z,rx,ry,rz] in mm/deg to a 4x4 transform."""
    p = np.asarray(pose, dtype=float)
    if p.shape != (6,):
        raise ValueError(f"Expected 6 pose values, got shape {p.shape}")
    x, y, z, rx, ry, rz = p
    rx, ry, rz = np.deg2rad([rx, ry, rz])

    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    R_x = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]])
    R_y = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
    R_z = np.array([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]])

    T = np.eye(4)
    T[:3, :3] = R_z @ R_y @ R_x
    T[:3, 3] = [x / 1000.0, y / 1000.0, z / 1000.0]
    return T


@dataclass
class HandEyeSample:
    joints_deg: np.ndarray            # (6,)
    T_base_gripper: np.ndarray        # (4, 4)
    rvec_target_cam: np.ndarray       # (3, 1)
    tvec_target_cam: np.ndarray       # (3, 1)
    board_reprojection_px: float = float("nan")
    charuco_corners: int = 0


def solve_hand_eye(samples: list[HandEyeSample]) -> tuple[np.ndarray, float, float]:
    """cv2.calibrateHandEye(PARK) + AX=XB residual.

    :returns: ``(T_gripper_cam (4x4), rms_rotation_deg, rms_translation_m)``.

    OpenCV returns the camera-to-gripper transform, conventionally written
    ``T_gripper_cam`` (points in camera coordinates -> gripper coordinates).
    """
    if len(samples) < 5:
        raise ValueError(f"Need at least 5 samples, have {len(samples)}.")

    R_g2b, t_g2b, R_t2c, t_t2c = [], [], [], []
    for s in samples:
        R_g2b.append(s.T_base_gripper[:3, :3])
        t_g2b.append(s.T_base_gripper[:3, 3].reshape(3, 1))
        R, _ = cv2.Rodrigues(s.rvec_target_cam)
        R_t2c.append(R)
        t_t2c.append(s.tvec_target_cam.reshape(3, 1))

    R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
        R_g2b, t_g2b, R_t2c, t_t2c, method=cv2.CALIB_HAND_EYE_PARK,
    )
    T_gripper_cam = np.eye(4)
    T_gripper_cam[:3, :3] = R_cam2gripper
    T_gripper_cam[:3, 3] = t_cam2gripper.flatten()

    # Residual: every sample should produce the same T_base_target.
    T_b_t_ref = None
    rot_errs, trans_errs = [], []
    for s in samples:
        T_cam_target = np.eye(4)
        R, _ = cv2.Rodrigues(s.rvec_target_cam)
        T_cam_target[:3, :3] = R
        T_cam_target[:3, 3] = s.tvec_target_cam.flatten()
        T_b_t = s.T_base_gripper @ T_gripper_cam @ T_cam_target
        if T_b_t_ref is None:
            T_b_t_ref = T_b_t
            continue
        delta = np.linalg.inv(T_b_t_ref) @ T_b_t
        rot_errs.append(
            float(np.degrees(np.arccos(np.clip((np.trace(delta[:3, :3]) - 1) / 2, -1, 1))))
        )
        trans_errs.append(float(np.linalg.norm(delta[:3, 3])))

    rms_rot = float(np.sqrt(np.mean(np.square(rot_errs)))) if rot_errs else 0.0
    rms_trans = float(np.sqrt(np.mean(np.square(trans_errs)))) if trans_errs else 0.0
    return T_gripper_cam, rms_rot, rms_trans


def save_hand_eye(
    T_gripper_cam: np.ndarray,
    n_samples: int,
    rms_rot_deg: float,
    rms_trans_m: float,
    path: Path | None = None,
) -> Path:
    out = Path(path) if path is not None else SETTINGS.files.hand_eye
    out.parent.mkdir(parents=True, exist_ok=True)
    T_cam_gripper = np.linalg.inv(T_gripper_cam)
    rvec, _ = cv2.Rodrigues(T_gripper_cam[:3, :3])
    np.savez(
        out,
        T_gripper_cam=T_gripper_cam,
        # Compatibility for older tools that read this key. The value is now
        # the literal camera<-gripper inverse, not the old mislabeled matrix.
        T_cam_gripper=T_cam_gripper,
        legacy_T_cam_gripper=T_gripper_cam,
        rvec=rvec,
        tvec=T_gripper_cam[:3, 3].reshape(3, 1),
        method="PARK",
        n_samples=int(n_samples),
        rms_rotation_deg=float(rms_rot_deg),
        rms_translation_m=float(rms_trans_m),
    )
    return out.resolve()


def load_hand_eye(path: Path | None = None) -> np.ndarray | None:
    """Load ``T_gripper_cam``.

    Older calibration files only contain a key named ``T_cam_gripper``. Those
    files were written with the OpenCV camera-to-gripper result under the wrong
    name, so we treat that legacy key as ``T_gripper_cam``.
    """
    p = Path(path) if path is not None else SETTINGS.files.hand_eye
    if not p.exists():
        return None
    with np.load(p) as data:
        if "T_gripper_cam" in data.files:
            return data["T_gripper_cam"].astype(np.float64)
        return data["T_cam_gripper"].astype(np.float64)
