#!/usr/bin/env python3
"""Audit PAROL6 URDF frames, joint origins, axes, limits, and TCP poses."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URDF = ROOT / "parol6" / "urdf_model" / "urdf" / "PAROL6.urdf"
ARM_JOINTS = ("L1", "L2", "L3", "L4", "L5", "L6")
POSES_DEG = {
    "zero": {name: 0.0 for name in ARM_JOINTS},
    "standby_official": {
        "L1": 0.0,
        "L2": -90.0,
        "L3": 180.0,
        "L4": 0.0,
        "L5": 0.0,
        "L6": 180.0,
    },
    "home_real": {
        "L1": 90.0,
        "L2": -90.0,
        "L3": 180.0,
        "L4": 0.0,
        "L5": 0.0,
        "L6": 180.0,
    },
}


@dataclass(frozen=True)
class Joint:
    name: str
    joint_type: str
    parent: str
    child: str
    xyz: tuple[float, float, float]
    rpy: tuple[float, float, float]
    axis: tuple[float, float, float]
    limit: tuple[float | None, float | None]
    mimic: tuple[str, float, float] | None = None


def parse_vec(text: str | None, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if not text:
        return default
    vals = [float(v) for v in text.split()]
    return (vals[0], vals[1], vals[2])


def matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def trans(xyz: tuple[float, float, float]) -> list[list[float]]:
    x, y, z = xyz
    return [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]


def rot_x(a: float) -> list[list[float]]:
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]]


def rot_y(a: float) -> list[list[float]]:
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]]


def rot_z(a: float) -> list[list[float]]:
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def rpy_mat(rpy: tuple[float, float, float]) -> list[list[float]]:
    return matmul(matmul(rot_z(rpy[2]), rot_y(rpy[1])), rot_x(rpy[0]))


def axis_rot(axis: tuple[float, float, float], angle: float) -> list[list[float]]:
    x, y, z = axis
    n = math.sqrt(x * x + y * y + z * z)
    if n == 0:
        return [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    x, y, z = x / n, y / n, z / n
    c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
    return [
        [t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0],
        [t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0],
        [t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0],
        [0, 0, 0, 1],
    ]


def rpy_from_mat(m: list[list[float]]) -> tuple[float, float, float]:
    sy = -m[2][0]
    cy = math.sqrt(max(0.0, 1.0 - sy * sy))
    if cy > 1e-9:
        return (math.atan2(m[2][1], m[2][2]), math.asin(sy), math.atan2(m[1][0], m[0][0]))
    return (math.atan2(-m[1][2], m[1][1]), math.asin(sy), 0.0)


def parse_urdf(path: Path) -> tuple[dict[str, Joint], dict[str, list[Joint]]]:
    root = ET.parse(path).getroot()
    joints: dict[str, Joint] = {}
    children: dict[str, list[Joint]] = {}
    for node in root.findall("joint"):
        origin = node.find("origin")
        axis = node.find("axis")
        limit = node.find("limit")
        mimic = node.find("mimic")
        joint = Joint(
            name=node.get("name", ""),
            joint_type=node.get("type", "fixed"),
            parent=node.find("parent").get("link", ""),
            child=node.find("child").get("link", ""),
            xyz=parse_vec(origin.get("xyz") if origin is not None else None, (0, 0, 0)),
            rpy=parse_vec(origin.get("rpy") if origin is not None else None, (0, 0, 0)),
            axis=parse_vec(axis.get("xyz") if axis is not None else None, (0, 0, 1)),
            limit=(
                float(limit.get("lower")) if limit is not None and limit.get("lower") is not None else None,
                float(limit.get("upper")) if limit is not None and limit.get("upper") is not None else None,
            ),
            mimic=(
                mimic.get("joint", ""),
                float(mimic.get("multiplier", "1")),
                float(mimic.get("offset", "0")),
            )
            if mimic is not None
            else None,
        )
        joints[joint.name] = joint
        children.setdefault(joint.parent, []).append(joint)
    return joints, children


def joint_value(joint: Joint, values: dict[str, float]) -> float:
    if joint.mimic:
        source, multiplier, offset = joint.mimic
        return values.get(source, 0.0) * multiplier + offset
    return values.get(joint.name, 0.0)


def joint_transform(joint: Joint, values: dict[str, float]) -> list[list[float]]:
    out = matmul(trans(joint.xyz), rpy_mat(joint.rpy))
    value = joint_value(joint, values)
    if joint.joint_type in ("revolute", "continuous"):
        out = matmul(out, axis_rot(joint.axis, value))
    elif joint.joint_type == "prismatic":
        ax = joint.axis
        out = matmul(out, trans((ax[0] * value, ax[1] * value, ax[2] * value)))
    return out


def compute_tree(children: dict[str, list[Joint]], values: dict[str, float]) -> dict[str, list[list[float]]]:
    frames = {"world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}
    stack = ["world"]
    while stack:
        parent = stack.pop()
        for joint in children.get(parent, []):
            frames[joint.child] = matmul(frames[parent], joint_transform(joint, values))
            stack.append(joint.child)
    return frames


def transform_axis(frame: list[list[float]], axis: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(sum(frame[i][k] * axis[k] for k in range(3)) for i in range(3))


def line_distance(
    p1: tuple[float, float, float],
    d1: tuple[float, float, float],
    p2: tuple[float, float, float],
    d2: tuple[float, float, float],
) -> float:
    cross = (
        d1[1] * d2[2] - d1[2] * d2[1],
        d1[2] * d2[0] - d1[0] * d2[2],
        d1[0] * d2[1] - d1[1] * d2[0],
    )
    denom = math.sqrt(sum(v * v for v in cross))
    delta = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
    if denom < 1e-9:
        cd = (
            delta[1] * d1[2] - delta[2] * d1[1],
            delta[2] * d1[0] - delta[0] * d1[2],
            delta[0] * d1[1] - delta[1] * d1[0],
        )
        return math.sqrt(sum(v * v for v in cd))
    return abs(sum(delta[i] * cross[i] for i in range(3))) / denom


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--urdf", type=Path, default=DEFAULT_URDF)
    args = parser.parse_args()
    joints, children = parse_urdf(args.urdf)

    print(f"URDF: {args.urdf}")
    print("\nJoint chain:")
    for name, joint in joints.items():
        print(
            f"{name:20s} {joint.parent:10s} -> {joint.child:10s} "
            f"type={joint.joint_type:9s} xyz={joint.xyz} rpy={joint.rpy} "
            f"axis={joint.axis} limit={joint.limit}"
        )

    print("\nOfficial dimensions represented by joint origins:")
    checks = {
        "a1": abs(joints["L1"].xyz[2]),
        "a2": abs(joints["L2"].xyz[0]),
        "a3": abs(joints["L3"].xyz[0]),
        "a4": abs(joints["L4"].xyz[0]),
        "a5": abs(joints["L4"].xyz[1]),
        "L6 wrist offset": abs(joints["L6"].xyz[1]),
        "SSG48 TCP": abs(joints["tcp_fixed_joint"].xyz[2]),
    }
    for key, value in checks.items():
        print(f"{key:15s} {value:.6f} m")

    for label, degrees in POSES_DEG.items():
        values = {name: math.radians(degrees[name]) for name in ARM_JOINTS}
        values["jaw1_JOINT"] = 0.0
        frames = compute_tree(children, values)
        print(f"\nPose: {label}")
        print("link        parent_joint          world xyz                  world rpy")
        for link in ["world", "base_link", "L1", "L2", "L3", "L4", "L5", "L6", "gripper", "tcp", "jaw1", "jaw2"]:
            frame = frames.get(link)
            if frame is None:
                continue
            parent_joint = next((j.name for j in joints.values() if j.child == link), "-")
            xyz = (frame[0][3], frame[1][3], frame[2][3])
            rpy = rpy_from_mat(frame)
            print(
                f"{link:11s} {parent_joint:20s} "
                f"[{xyz[0]: .5f}, {xyz[1]: .5f}, {xyz[2]: .5f}] "
                f"[{rpy[0]: .5f}, {rpy[1]: .5f}, {rpy[2]: .5f}]"
            )

        if label == "home_real":
            print("\nHome_real wrist-axis line distances:")
            axis_lines: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {}
            for name in ("L4", "L5", "L6"):
                joint = joints[name]
                parent_frame = frames[joint.parent]
                joint_frame = matmul(parent_frame, matmul(trans(joint.xyz), rpy_mat(joint.rpy)))
                p = (joint_frame[0][3], joint_frame[1][3], joint_frame[2][3])
                d = transform_axis(joint_frame, joint.axis)
                n = math.sqrt(sum(v * v for v in d))
                axis_lines[name] = (p, (d[0] / n, d[1] / n, d[2] / n))
            for a, b in (("L4", "L5"), ("L5", "L6"), ("L4", "L6")):
                print(f"{a}-{b}: {line_distance(*axis_lines[a], *axis_lines[b]):.6f} m")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
