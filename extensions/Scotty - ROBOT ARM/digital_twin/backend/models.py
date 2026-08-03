"""Pydantic models for the standalone PAROL6 Digital Twin API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JointLimit(BaseModel):
    name: str
    lower_deg: float
    upper_deg: float


class NamedState(BaseModel):
    name: str
    group: str
    values: dict[str, float]


class ModelInfo(BaseModel):
    urdf_url: str
    package_name: str
    package_url: str
    mesh_url: str
    joint_limits: list[JointLimit]
    home_angles_deg: list[float]
    named_states: list[NamedState] = Field(default_factory=list)


class ConnectRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5001
    serial_port: str | None = None
    timeout_s: float = 8.0
    client_timeout_s: float = 2.0
    start_controller: bool = True


class ModeRequest(BaseModel):
    live_enabled: bool | None = None
    movement_enabled: bool | None = None


class MoveJointsRequest(BaseModel):
    angles_deg: list[float] = Field(min_length=6, max_length=6)
    speed_scale: float = Field(default=0.5, ge=0.05, le=1.0)
    wait: bool = False


class PoseRequest(BaseModel):
    pose_m_rad: list[float] = Field(min_length=6, max_length=6)
    seed_angles_deg: list[float] | None = Field(default=None, min_length=6, max_length=6)


class MovePoseRequest(PoseRequest):
    speed_scale: float = Field(default=0.5, ge=0.05, le=1.0)
    wait: bool = False


class FkRequest(BaseModel):
    angles_deg: list[float] = Field(min_length=6, max_length=6)


class PoseResult(BaseModel):
    ok: bool
    message: str
    pose_m_rad: list[float] | None = None
    angles_deg: list[float] | None = None


class ValidateJointsRequest(BaseModel):
    angles_deg: list[float] = Field(min_length=6, max_length=6)


class ValidationResult(BaseModel):
    valid: bool
    clamped_angles_deg: list[float]
    errors: list[str] = Field(default_factory=list)


class CommandResult(BaseModel):
    ok: bool
    message: str
    command_index: int | None = None
    status: "RobotStatus"


class RobotStatus(BaseModel):
    connected: bool = False
    live_enabled: bool = False
    movement_enabled: bool = False
    homed: bool = False
    estop: bool = False
    error: str | None = None
    moving: bool = False
    simulator_active: bool | None = None
    hardware_connected: bool | None = None
    angles_deg: list[float] | None = None
    target_angles_deg: list[float] | None = None
    pose: list[float] | None = None
    tcp_pose_m_rad: list[float] | None = None
    speeds: list[float] | None = None
    io: list[int] | None = None
    activity: dict[str, Any] | None = None
    message: str = ""


CommandResult.model_rebuild()
