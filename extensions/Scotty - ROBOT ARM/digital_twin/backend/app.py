"""FastAPI application for the standalone PAROL6 Digital Twin."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    CommandResult,
    ConnectRequest,
    FkRequest,
    ModeRequest,
    ModelInfo,
    MoveJointsRequest,
    MovePoseRequest,
    PoseRequest,
    PoseResult,
    RobotStatus,
    ValidateJointsRequest,
    ValidationResult,
)
from .robot_service import CONTROLLER_PAROL6_ROOT, MESHES_PATH, MOVEIT_PAROL6_ROOT, URDF_PATH, RobotBridge


bridge = RobotBridge()

app = FastAPI(title="PAROL6 Digital Twin", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if MOVEIT_PAROL6_ROOT.is_dir():
    app.mount("/assets/parol6", StaticFiles(directory=MOVEIT_PAROL6_ROOT), name="parol6-assets")
if CONTROLLER_PAROL6_ROOT.is_dir():
    app.mount(
        "/assets/controller-parol6",
        StaticFiles(directory=CONTROLLER_PAROL6_ROOT),
        name="controller-parol6-assets",
    )
if MESHES_PATH.is_dir():
    app.mount("/assets/meshes", StaticFiles(directory=MESHES_PATH), name="parol6-meshes")


@app.get("/api/model", response_model=ModelInfo)
def model_info() -> ModelInfo:
    return ModelInfo(
        urdf_url="/api/model/urdf",
        package_name="parol6",
        package_url="/assets/controller-parol6/",
        mesh_url="/assets/meshes/",
        joint_limits=bridge.joint_limit_models,
        home_angles_deg=bridge.home_angles_deg,
        named_states=[
            {
                "name": "home_real",
                "group": "arm",
                "values": {
                    "L1": 90.0,
                    "L2": -90.0,
                    "L3": 180.0,
                    "L4": 0.0,
                    "L5": 0.0,
                    "L6": 180.0,
                },
            },
            {
                "name": "standby_official",
                "group": "arm",
                "values": {
                    "L1": 0.0,
                    "L2": -90.0,
                    "L3": 180.0,
                    "L4": 0.0,
                    "L5": 0.0,
                    "L6": 180.0,
                },
            },
            {
                "name": "gripper_open",
                "group": "gripper",
                "values": {
                    "jaw1_JOINT": -0.024,
                    "jaw2_JOINT": 0.024,
                },
            },
            {
                "name": "gripper_closed",
                "group": "gripper",
                "values": {
                    "jaw1_JOINT": 0.0,
                    "jaw2_JOINT": 0.0,
                },
            },
        ],
    )


@app.get("/api/model/urdf")
def model_urdf() -> FileResponse:
    return FileResponse(URDF_PATH, media_type="application/xml", filename="parol6.urdf")


@app.get("/api/status", response_model=RobotStatus)
def status() -> RobotStatus:
    return bridge.status()


@app.post("/api/connect", response_model=RobotStatus)
def connect(req: ConnectRequest) -> RobotStatus:
    return bridge.connect(req)


@app.post("/api/disconnect", response_model=RobotStatus)
def disconnect() -> RobotStatus:
    return bridge.disconnect()


@app.post("/api/mode", response_model=RobotStatus)
def set_mode(req: ModeRequest) -> RobotStatus:
    return bridge.set_mode(
        live_enabled=req.live_enabled,
        movement_enabled=req.movement_enabled,
    )


@app.post("/api/validate", response_model=ValidationResult)
def validate_joints(req: ValidateJointsRequest) -> ValidationResult:
    return bridge.validate_joints(req.angles_deg)


@app.post("/api/fk", response_model=PoseResult)
def fk(req: FkRequest) -> PoseResult:
    return bridge.fk(req)


@app.post("/api/ik", response_model=PoseResult)
def ik(req: PoseRequest) -> PoseResult:
    return bridge.ik(req)


@app.post("/api/home", response_model=CommandResult)
def home(wait: bool = False) -> CommandResult:
    return bridge.home(wait=wait)


@app.post("/api/resume", response_model=CommandResult)
def resume() -> CommandResult:
    return bridge.resume()


@app.post("/api/halt", response_model=CommandResult)
def halt() -> CommandResult:
    return bridge.halt()


@app.post("/api/move-joints", response_model=CommandResult)
def move_joints(req: MoveJointsRequest) -> CommandResult:
    return bridge.move_joints(req)


@app.post("/api/move-pose", response_model=CommandResult)
def move_pose(req: MovePoseRequest) -> CommandResult:
    return bridge.move_pose(req)
