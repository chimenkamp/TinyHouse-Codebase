"""Safety-gated standalone bridge from the Digital Twin API to ``parol6``."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .models import (
    CommandResult,
    ConnectRequest,
    FkRequest,
    JointLimit,
    MoveJointsRequest,
    MovePoseRequest,
    PoseRequest,
    PoseResult,
    RobotStatus,
    ValidationResult,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MOVEIT_PAROL6_ROOT = REPO_ROOT / "PAROL6-ROS2-MOVEIT" / "ros_parol" / "src" / "parol6"
CONTROLLER_PAROL6_ROOT = REPO_ROOT / "parol6" / "urdf_model"
# The ROS2 MoveIt URDF in PAROL6-ROS2-MOVEIT uses a different zero/sign
# convention than the live controller. Render the controller URDF so homed
# telemetry and the digital twin share the same joint convention; this still
# keeps the app standalone and backed by the in-repo parol6 package.
URDF_PATH = CONTROLLER_PAROL6_ROOT / "urdf" / "PAROL6.urdf"
MESHES_PATH = CONTROLLER_PAROL6_ROOT / "meshes"

JOINT_NAMES = ("L1", "L2", "L3", "L4", "L5", "L6")
DEFAULT_MOVE_SPEED_DEG_S = 25.0
DEFAULT_MOVE_ACCEL = 1.0
READBACK_LIMIT_TOLERANCE_DEG = 5.0


class RobotClientLike(Protocol):
    def __enter__(self) -> Any: ...
    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any: ...
    def wait_ready(self, timeout: float = ...) -> bool: ...
    def resume(self) -> int: ...
    def halt(self) -> int: ...
    def home(self, wait: bool = ..., timeout: float = ...) -> int: ...
    def move_j(
        self,
        angles: list[float],
        *,
        duration: float = ...,
        accel: float = ...,
        wait: bool = ...,
        timeout: float = ...,
    ) -> int: ...
    def angles(self) -> list[float] | None: ...
    def pose(self) -> list[float] | None: ...
    def io(self) -> list[int] | None: ...
    def joint_speeds(self) -> list[float] | None: ...
    def ping(self) -> Any: ...
    def activity(self) -> Any: ...
    def error(self) -> Any: ...
    def is_estop_pressed(self) -> bool: ...
    def is_simulator(self) -> bool: ...


@dataclass
class RobotRuntime:
    robot: Any | None = None
    client: RobotClientLike | None = None
    owns_server: bool = False
    connected: bool = False
    live_enabled: bool = False
    movement_enabled: bool = False
    homed: bool = False
    target_angles_deg: list[float] | None = None
    last_message: str = ""
    connection: ConnectRequest = field(default_factory=ConnectRequest)


def _load_joint_limits() -> list[tuple[float, float]]:
    try:
        from parol6.PAROL6_ROBOT import _joint_limits_degree

        arr = np.asarray(_joint_limits_degree, dtype=float)
        if arr.shape == (6, 2):
            return [(float(lo), float(hi)) for lo, hi in arr]
    except Exception:
        pass
    return [
        (-123.046875, 123.046875),
        (-145.0088, -3.375),
        (107.866, 287.8675),
        (-105.46975, 105.46975),
        (-90.0, 90.0),
        (0.0, 360.0),
    ]


def _load_home_angles() -> list[float]:
    try:
        from parol6.PAROL6_ROBOT import _standby_deg

        arr = np.asarray(_standby_deg, dtype=float)
        if arr.shape == (6,):
            return [float(v) for v in arr]
    except Exception:
        pass
    return [90.0, -90.0, 180.0, 0.0, 0.0, 180.0]


class RobotBridge:
    """Owns live robot state and enforces standalone Digital Twin safety gates."""

    def __init__(self, client: RobotClientLike | None = None) -> None:
        self.runtime = RobotRuntime(client=client, connected=client is not None)
        self.joint_limits = _load_joint_limits()
        self.home_angles_deg = _load_home_angles()
        self._kinematics_robot: Any | None = None
        if client is not None:
            self.runtime.last_message = "fake/test client attached"

    @property
    def joint_limit_models(self) -> list[JointLimit]:
        return [
            JointLimit(name=name, lower_deg=lo, upper_deg=hi)
            for name, (lo, hi) in zip(JOINT_NAMES, self.joint_limits)
        ]

    def connect(self, req: ConnectRequest) -> RobotStatus:
        if self.runtime.connected:
            self.runtime.last_message = "already connected"
            return self.status()
        try:
            from parol6 import Robot, RobotClient

            if req.serial_port:
                os.environ["PAROL6_COM_PORT"] = req.serial_port
            robot = Robot(host=req.host, port=req.port, normalize_logs=True)
            owns_server = False
            if req.start_controller and not robot.is_available(host=req.host, port=req.port):
                robot.start(com_port=req.serial_port, host=req.host, port=req.port, timeout=req.timeout_s)
                owns_server = True
            client = RobotClient(host=req.host, port=req.port, timeout=req.client_timeout_s)
            client.__enter__()
            if hasattr(client, "wait_ready") and not client.wait_ready(timeout=req.timeout_s):
                client.__exit__(None, None, None)
                if owns_server:
                    robot.stop()
                self.runtime.last_message = "controller did not become ready"
                return self.status()
            try:
                client.resume()
            except Exception:
                pass
            self.runtime = RobotRuntime(
                robot=robot,
                client=client,
                owns_server=owns_server,
                connected=True,
                live_enabled=False,
                movement_enabled=False,
                homed=False,
                connection=req,
                last_message="connected; live movement disabled",
            )
        except Exception as exc:
            self.runtime.last_message = f"connect failed: {type(exc).__name__}: {exc}"
            self.disconnect()
        return self.status()

    def disconnect(self) -> RobotStatus:
        client = self.runtime.client
        robot = self.runtime.robot
        owns_server = self.runtime.owns_server
        if client is not None:
            try:
                client.__exit__(None, None, None)
            except Exception:
                pass
        if robot is not None and owns_server:
            try:
                robot.stop()
            except Exception:
                pass
        self.runtime = RobotRuntime(last_message="disconnected")
        return self.status()

    def set_mode(
        self,
        *,
        live_enabled: bool | None = None,
        movement_enabled: bool | None = None,
    ) -> RobotStatus:
        if live_enabled is not None:
            self.runtime.live_enabled = bool(live_enabled)
            if not self.runtime.live_enabled:
                self.runtime.movement_enabled = False
        if movement_enabled is not None:
            self.runtime.movement_enabled = bool(movement_enabled)
        self.runtime.last_message = self._mode_message()
        return self.status()

    def status(self) -> RobotStatus:
        client = self.runtime.client
        angles = pose = speeds = io = activity = None
        estop = False
        error_text = None
        moving = False
        simulator_active = None
        hardware_connected = None
        if self.runtime.connected and client is not None:
            angles = self._safe_call(client.angles)
            pose = self._safe_call(client.pose)
            speeds = self._safe_call(client.joint_speeds)
            io = self._safe_call(client.io)
            estop = bool(self._safe_call(client.is_estop_pressed, default=False))
            err = self._safe_call(client.error)
            error_text = self._error_to_text(err)
            activity_obj = self._safe_call(client.activity)
            activity = self._activity_to_dict(activity_obj)
            moving = self._is_moving(activity, speeds)
            simulator_active = self._safe_call(client.is_simulator)
            ping = self._safe_call(client.ping)
            hardware_connected = getattr(ping, "hardware_connected", None) if ping is not None else None
        return RobotStatus(
            connected=self.runtime.connected,
            live_enabled=self.runtime.live_enabled,
            movement_enabled=self.runtime.movement_enabled,
            homed=self.runtime.homed,
            estop=estop,
            error=error_text,
            moving=moving,
            simulator_active=simulator_active,
            hardware_connected=hardware_connected,
            angles_deg=list(map(float, angles)) if angles is not None else None,
            target_angles_deg=self.runtime.target_angles_deg,
            pose=list(map(float, pose)) if pose is not None else None,
            tcp_pose_m_rad=self._fk_pose_or_none(angles),
            speeds=list(map(float, speeds)) if speeds is not None else None,
            io=list(map(int, io)) if io is not None else None,
            activity=activity,
            message=self.runtime.last_message,
        )

    def validate_joints(self, angles_deg: list[float]) -> ValidationResult:
        errors: list[str] = []
        clamped: list[float] = []
        if len(angles_deg) != 6:
            return ValidationResult(valid=False, clamped_angles_deg=[], errors=["expected 6 joint angles"])
        for idx, raw in enumerate(angles_deg):
            value = float(raw)
            lo, hi = self.joint_limits[idx]
            if not math.isfinite(value):
                errors.append(f"{JOINT_NAMES[idx]} is not finite")
                value = lo
            if value < lo or value > hi:
                errors.append(f"{JOINT_NAMES[idx]} target {value:.2f} deg outside [{lo:.2f}, {hi:.2f}]")
            clamped.append(float(min(max(value, lo), hi)))
        return ValidationResult(valid=not errors, clamped_angles_deg=clamped, errors=errors)

    def home(self, *, wait: bool = False) -> CommandResult:
        client = self.runtime.client
        if not self.runtime.connected or client is None:
            return self._command(False, "not connected")
        try:
            client.resume()
            idx = client.home(wait=wait, timeout=60.0)
            if isinstance(idx, int) and idx < 0:
                return self._command(False, "home command rejected", command_index=idx)
            self.runtime.homed = True
            self.runtime.last_message = "home command accepted; homed latch set"
            return self._command(True, self.runtime.last_message, command_index=idx if isinstance(idx, int) else None)
        except Exception as exc:
            return self._command(False, f"home failed: {type(exc).__name__}: {exc}")

    def resume(self) -> CommandResult:
        client = self.runtime.client
        if not self.runtime.connected or client is None:
            return self._command(False, "not connected")
        try:
            client.resume()
            self.runtime.movement_enabled = True
            return self._command(True, "resume sent; movement enabled")
        except Exception as exc:
            return self._command(False, f"resume failed: {type(exc).__name__}: {exc}")

    def halt(self) -> CommandResult:
        client = self.runtime.client
        if not self.runtime.connected or client is None:
            return self._command(False, "not connected")
        try:
            client.halt()
            self.runtime.movement_enabled = False
            self.runtime.live_enabled = False
            return self._command(True, "halt sent; live movement disabled")
        except Exception as exc:
            return self._command(False, f"halt failed: {type(exc).__name__}: {exc}")

    def move_joints(self, req: MoveJointsRequest) -> CommandResult:
        client = self.runtime.client
        gate = self._movement_gate()
        if gate is not None:
            return self._command(False, gate)
        assert client is not None
        validation = self.validate_joints(req.angles_deg)
        if not validation.valid:
            return self._command(False, "; ".join(validation.errors))
        current = self._safe_call(client.angles)
        if current is None or not self._readback_valid(current):
            return self._command(False, "current joint readback is unavailable or outside safe limits")
        target = validation.clamped_angles_deg
        delta = max(abs(float(t) - float(c)) for t, c in zip(target, current))
        speed = DEFAULT_MOVE_SPEED_DEG_S * float(req.speed_scale)
        duration = max(0.4, delta / max(1.0, speed))
        try:
            idx = client.move_j(
                target,
                duration=duration,
                accel=DEFAULT_MOVE_ACCEL,
                wait=bool(req.wait),
                timeout=duration + 5.0,
            )
            self.runtime.target_angles_deg = target
            return self._command(
                True,
                f"move_j accepted duration={duration:.2f}s speed_scale={req.speed_scale:.2f}",
                command_index=idx if isinstance(idx, int) else None,
            )
        except Exception as exc:
            return self._command(False, f"move_j failed: {type(exc).__name__}: {exc}")

    def fk(self, req: FkRequest) -> PoseResult:
        validation = self.validate_joints(req.angles_deg)
        if not validation.valid:
            return PoseResult(ok=False, message="; ".join(validation.errors), angles_deg=validation.clamped_angles_deg)
        try:
            pose = self._fk_pose(validation.clamped_angles_deg)
        except Exception as exc:
            return PoseResult(ok=False, message=f"FK failed: {type(exc).__name__}: {exc}")
        return PoseResult(ok=True, message="FK solved", pose_m_rad=pose, angles_deg=validation.clamped_angles_deg)

    def ik(self, req: PoseRequest) -> PoseResult:
        seed = req.seed_angles_deg or self._current_or_home_angles()
        seed_validation = self.validate_joints(seed)
        if not seed_validation.valid:
            return PoseResult(ok=False, message=f"invalid IK seed: {'; '.join(seed_validation.errors)}")
        try:
            result = self._ik_solve(req.pose_m_rad, seed_validation.clamped_angles_deg)
        except Exception as exc:
            return PoseResult(ok=False, message=f"IK failed: {type(exc).__name__}: {exc}")
        if not result.get("ok"):
            return PoseResult(ok=False, message=str(result.get("message", "IK failed")))
        angles = list(map(float, result["angles_deg"]))
        return PoseResult(ok=True, message=str(result.get("message", "IK solved")), pose_m_rad=req.pose_m_rad, angles_deg=angles)

    def move_pose(self, req: MovePoseRequest) -> CommandResult:
        gate = self._movement_gate()
        if gate is not None:
            return self._command(False, gate)
        ik = self.ik(PoseRequest(pose_m_rad=req.pose_m_rad, seed_angles_deg=req.seed_angles_deg))
        if not ik.ok or ik.angles_deg is None:
            return self._command(False, ik.message)
        return self.move_joints(
            MoveJointsRequest(
                angles_deg=ik.angles_deg,
                speed_scale=req.speed_scale,
                wait=req.wait,
            )
        )

    def _movement_gate(self) -> str | None:
        if not self.runtime.connected or self.runtime.client is None:
            return "not connected"
        if not self.runtime.live_enabled:
            return "live mode is not enabled"
        if not self.runtime.movement_enabled:
            return "movement is not enabled"
        if not self.runtime.homed:
            return "home the robot from this app before live movement"
        status = self.status()
        if status.estop:
            return "emergency stop is active"
        if status.error:
            return f"robot error active: {status.error}"
        return None

    def _readback_valid(self, angles: list[float]) -> bool:
        if len(angles) != 6:
            return False
        for idx, raw in enumerate(angles):
            value = float(raw)
            lo, hi = self.joint_limits[idx]
            if not math.isfinite(value):
                return False
            if value < lo - READBACK_LIMIT_TOLERANCE_DEG or value > hi + READBACK_LIMIT_TOLERANCE_DEG:
                return False
        return True

    def _current_or_home_angles(self) -> list[float]:
        client = self.runtime.client
        if client is not None:
            angles = self._safe_call(client.angles)
            if angles is not None and self._readback_valid(angles):
                return list(map(float, angles))
        if self.runtime.target_angles_deg is not None:
            return list(self.runtime.target_angles_deg)
        return list(self.home_angles_deg)

    def _kinematics(self) -> Any:
        if self._kinematics_robot is None:
            from parol6 import Robot

            self._kinematics_robot = Robot()
        return self._kinematics_robot

    def _fk_pose(self, angles_deg: list[float]) -> list[float]:
        out = np.zeros(6, dtype=np.float64)
        pose = self._kinematics().fk(np.deg2rad(np.asarray(angles_deg, dtype=np.float64)), out)
        return [float(v) for v in pose]

    def _fk_pose_or_none(self, angles: list[float] | None) -> list[float] | None:
        if angles is None or len(angles) != 6:
            return None
        try:
            return self._fk_pose(list(map(float, angles)))
        except Exception:
            return None

    def _ik_solve(self, pose_m_rad: list[float], seed_angles_deg: list[float]) -> dict[str, Any]:
        if len(pose_m_rad) != 6:
            return {"ok": False, "message": "expected 6 pose values [x,y,z,rx,ry,rz] in meters/radians"}
        pose = np.asarray(pose_m_rad, dtype=np.float64)
        seed_rad = np.deg2rad(np.asarray(seed_angles_deg, dtype=np.float64))
        if not np.all(np.isfinite(pose)):
            return {"ok": False, "message": "pose contains non-finite values"}
        result = self._kinematics().ik(pose, seed_rad)
        if not getattr(result, "success", False):
            return {"ok": False, "message": getattr(result, "violations", None) or "IK failed"}
        angles_deg = np.rad2deg(np.asarray(result.q, dtype=np.float64)).tolist()
        validation = self.validate_joints(angles_deg)
        if not validation.valid:
            return {"ok": False, "message": "; ".join(validation.errors)}
        return {
            "ok": True,
            "message": f"IK solved residual={float(getattr(result, 'residual', 0.0)):.3g}",
            "angles_deg": validation.clamped_angles_deg,
        }

    def _command(self, ok: bool, message: str, command_index: int | None = None) -> CommandResult:
        self.runtime.last_message = message
        return CommandResult(ok=ok, message=message, command_index=command_index, status=self.status())

    def _mode_message(self) -> str:
        if not self.runtime.live_enabled:
            return "simulation mode; live movement disabled"
        if not self.runtime.movement_enabled:
            return "live mode armed; movement disabled"
        return "live movement enabled"

    @staticmethod
    def _safe_call(func: Any, default: Any = None) -> Any:
        try:
            return func()
        except Exception:
            return default

    @staticmethod
    def _error_to_text(error: Any) -> str | None:
        if error is None:
            return None
        code = getattr(error, "code", None)
        message = getattr(error, "message", None) or getattr(error, "detail", None)
        if code is not None and message is not None:
            return f"{code}: {message}"
        return str(error)

    @staticmethod
    def _activity_to_dict(activity: Any) -> dict[str, Any] | None:
        if activity is None:
            return None
        out: dict[str, Any] = {}
        for key in ("state", "command", "current", "next", "params", "error"):
            if hasattr(activity, key):
                value = getattr(activity, key)
                out[key] = str(value) if key == "state" else value
        return out or None

    @staticmethod
    def _is_moving(activity: dict[str, Any] | None, speeds: list[float] | None) -> bool:
        if activity:
            state = str(activity.get("state", "")).lower()
            if "execut" in state or "moving" in state:
                return True
        if speeds is None:
            return False
        return any(abs(float(v)) > 0.01 for v in speeds)
