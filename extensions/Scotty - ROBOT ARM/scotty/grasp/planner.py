"""Top-down grasp planner.

Given a target XYZ in the robot base frame plus the current TCP orientation,
build three Cartesian way-points (mm + degrees, WRF) suitable for
``RobotClient.move_l``: hover → descend → lift.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import SETTINGS


@dataclass
class GraspPlan:
    hover: list[float]    # [x_mm, y_mm, z_mm, rx_deg, ry_deg, rz_deg]
    grasp: list[float]
    lift: list[float]


def plan_topdown_grasp(
    target_xyz_m: tuple[float, float, float],
    current_pose_mm_deg: np.ndarray | None = None,
    safe_height_m: float | None = None,
    descend_height_m: float | None = None,
) -> GraspPlan:
    """Build hover/grasp/lift poses around ``target_xyz_m``.

    ``current_pose_mm_deg`` keeps the wrist orientation; if missing we
    default to a top-down RX=180, RY=0, RZ=0 pose.
    """
    safe = SETTINGS.grasp.safe_height_m if safe_height_m is None else safe_height_m
    desc = SETTINGS.grasp.descend_height_m if descend_height_m is None else descend_height_m

    x_mm = target_xyz_m[0] * 1000.0
    y_mm = target_xyz_m[1] * 1000.0
    z_table_mm = target_xyz_m[2] * 1000.0

    if current_pose_mm_deg is not None and len(current_pose_mm_deg) >= 6:
        rx, ry, rz = (float(v) for v in current_pose_mm_deg[3:6])
    else:
        rx, ry, rz = 180.0, 0.0, 0.0

    hover = [x_mm, y_mm, z_table_mm + safe * 1000.0, rx, ry, rz]
    grasp = [x_mm, y_mm, z_table_mm + desc * 1000.0, rx, ry, rz]
    lift = [x_mm, y_mm, z_table_mm + safe * 1000.0, rx, ry, rz]
    return GraspPlan(hover=hover, grasp=grasp, lift=lift)
