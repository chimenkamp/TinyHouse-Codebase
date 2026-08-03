"""Project a pixel into the table plane in robot base coordinates.

Pipeline:
    pixel (u, v) ──undistort──▶ normalised camera ray ─▶
    transform to base via T_base_gripper · T_gripper_cam ─▶
    intersect with the table plane (z = ``table_z_m``) ─▶ (X, Y, Z) in metres.

``T_gripper_cam`` is the OpenCV hand-eye result: points in camera coordinates
transformed into the gripper frame.
"""

from __future__ import annotations

import cv2
import numpy as np


def pixel_to_table_xy(
    u: float,
    v: float,
    K: np.ndarray,
    dist: np.ndarray,
    T_base_gripper: np.ndarray,
    T_gripper_cam: np.ndarray,
    table_z_m: float = 0.0,
    min_abs_ray_z: float = 0.0,
    max_ray_distance_m: float | None = None,
) -> tuple[float, float, float] | None:
    """Project pixel ``(u, v)`` onto plane ``z = table_z_m`` (base frame).

    :returns: ``(X, Y, table_z_m)`` in metres, or ``None`` if the ray is parallel
        to the plane / points away from it.
    """
    pts = np.array([[[u, v]]], dtype=np.float64)
    undist = cv2.undistortPoints(pts, K, dist)  # in normalised camera coords
    nx, ny = float(undist[0, 0, 0]), float(undist[0, 0, 1])
    ray_cam = np.array([nx, ny, 1.0, 0.0])  # direction (w=0)
    origin_cam = np.array([0.0, 0.0, 0.0, 1.0])

    T_base_cam = T_base_gripper @ T_gripper_cam

    origin_base = (T_base_cam @ origin_cam)[:3]
    dir_base = (T_base_cam @ ray_cam)[:3]
    n = np.linalg.norm(dir_base)
    if n < 1e-9:
        return None
    dir_base = dir_base / n

    if abs(dir_base[2]) < max(1e-9, float(min_abs_ray_z)):
        return None
    t = (table_z_m - origin_base[2]) / dir_base[2]
    if t <= 0:
        return None  # plane behind the camera
    if max_ray_distance_m is not None and t > max_ray_distance_m:
        return None
    p = origin_base + t * dir_base
    return float(p[0]), float(p[1]), float(p[2])
