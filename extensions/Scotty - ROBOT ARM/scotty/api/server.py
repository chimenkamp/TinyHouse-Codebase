"""REST API service for Scotty and the PAROL6 robot arm."""

from __future__ import annotations

from enum import Enum 
import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

from ..robot.controller import Parol6Controller, JOINT_LIMITS_DEG, JOINT_HOME_DEG

class RobotErrorCode(str, Enum):
    ROBOT_CONNECTION_FAILED = "ROBOT_CONNECTION_FAILED"
    NOT_CONNECTED = "NOT_CONNECTED"
    JOINT_LIMIT_EXCEEDED = "JOINT_LIMIT_EXCEEDED"
    IK_SOLVER_FAILED = "IK_SOLVER_FAILED"
    MOTION_DISABLED = "MOTION_DISABLED"
    GRASP_FAILED = "GRASP_FAILED"
    OBJECT_DROPPED = "OBJECT_DROPPED"


class RobotErrorResponse(BaseModel):
    error_code: RobotErrorCode
    message: str
    recoverable: bool = True

class JointMoveRequest(BaseModel):
    angles_deg:list[float]
    speed_deg_s:float | None = None

class PoseMoveRequest(BaseModel):
    pose_m:list[float] #x_mm, y_mm, z_mm, rx_deg, ry_deg, rz_deg 
    duration_s:float = 2.0

def raise_robot_error(
    status_code: int,
    error_code: RobotErrorCode,
    message: str,
    recoverable: bool = True
) -> None:
    """Raises an HTTPException with a structured error payload for BPMN / CPEE."""
    raise HTTPException(
        status_code=status_code,
        detail={
            "error_code": error_code.value,
            "message": message,
            "recoverable": recoverable,
        }
    )

# 1. Initialize our web app
app = FastAPI(
    title="Scotty Robot API",
    description="HTTP API for orchestrating PAROL6 arm tasks from CPEE / BPMN",
    version="0.1.0",
)

# Allow calls from web browsers and local orchestrators
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Instantiate our robot controller wrapper
robot_controller = Parol6Controller()

def ensure_robot_connected() -> None:
    """Guards endpoints that require an active robot connection."""
    if not robot_controller.connected:
        raise_robot_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code=RobotErrorCode.NOT_CONNECTED,
            message="Robot arm is not connected. Call /robot/connect first.",
            recoverable=True,
        )
    

# 3. Status / Health Check Endpoint
@app.get("/status")
def get_status():
    """Returns the connection and motion status of the robot."""
    pose = robot_controller.pose()
    return {
        "status": "online",
        "robot_connected": robot_controller.connected,
        "motion_enabled": robot_controller.motion_enabled,
        "current_pose": pose.tolist() if pose is not None else None,
        "last_error": robot_controller.last_error,
    }


@app.get("/telemetry")
def get_telemetry():
    """Returns full real-time telemetry: joint angles, cartesian pose, and safety limits."""
    angles = robot_controller.angles()
    pose = robot_controller.pose()

    # Format Cartesian pose into structured coordinates if available
    cartesian = None
    if pose is not None:
        cartesian = {
            "x_mm": round(float(pose[0]), 2),
            "y_mm": round(float(pose[1]), 2),
            "z_mm": round(float(pose[2]), 2),
            "rx_deg": round(float(pose[3]), 2),
            "ry_deg": round(float(pose[4]), 2),
            "rz_deg": round(float(pose[5]), 2),
        }

    return {
        "robot_connected": robot_controller.connected,
        "motion_enabled": robot_controller.motion_enabled,
        "joint_angles_deg": [round(float(a), 2) for a in angles] if angles is not None else None,
        "cartesian_pose": cartesian,
        "standby_pose_deg": JOINT_HOME_DEG,
        "last_action": robot_controller.last_action,
        "last_error": robot_controller.last_error,
    }


@app.get("/robot/joints")
def get_joint_details():
    """Returns per-joint angles, hard limits, and distance-to-limit safety margins."""
    angles = robot_controller.angles()
    joints_data = []

    for idx, (lo, hi) in enumerate(JOINT_LIMITS_DEG):
        current_deg = round(float(angles[idx]), 2) if angles is not None else None
        
        # Calculate safety margins to mechanical limits
        margin_min = round(current_deg - lo, 2) if current_deg is not None else None
        margin_max = round(hi - current_deg, 2) if current_deg is not None else None
        within_limits = (lo <= current_deg <= hi) if current_deg is not None else None

        joints_data.append({
            "joint": idx + 1,
            "current_angle_deg": current_deg,
            "min_limit_deg": round(lo, 2),
            "max_limit_deg": round(hi, 2),
            "margin_to_min_deg": margin_min,
            "margin_to_max_deg": margin_max,
            "within_safe_limits": within_limits,
        })

    return {
        "robot_connected": robot_controller.connected,
        "joints": joints_data,
    }

# --- Live Web Dashboard Endpoint (Read-Only) ---

@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """Serves a real-time, read-only telemetry dashboard in the browser."""
    html_file = Path(__file__).parent / "templates" / "dashboard.html"
    if not html_file.is_file():
        return HTMLResponse(status_code=404, content="Dashboard HTML not found.")
    return html_file.read_text(encoding="utf-8")



# 4. Connect / Disconnect Endpoints
@app.post(
    "/robot/connect",
    responses={
        503: {"model": RobotErrorResponse, "description": "Robot connection failed"},
    },
)
def connect_robot():
    """Connects to the PAROL6 robot or local simulator server."""
    robot_controller.connect()

    if not robot_controller.connected:
        raise_robot_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code=RobotErrorCode.ROBOT_CONNECTION_FAILED,
            message="Could not connect to PAROL6 robot controller.",
            recoverable=True,
        )
        
    return {
        "connected": True,
        "status": "ready",
        "last_error": None,
    }


@app.post("/robot/disconnect")
def disconnect_robot():
    """Disconnects from the robot."""
    robot_controller.disconnect()
    return {"connected": False}

@app.post(
    "/robot/move_to_angles",
    responses={
        400: {"model": RobotErrorResponse, "description": "Joint limit exceeded"},
        409: {"model": RobotErrorResponse, "description": "Motion disabled"},
        503: {"model": RobotErrorResponse, "description": "Robot not connected"},
    },
)
def move_to_angles(req: JointMoveRequest):
    """Moves arm to target joint angles, validating against safety limits."""
    ensure_robot_connected()
    robot_controller.last_action = "move_to_angles"

    # 1. Validate count
    if len(req.angles_deg) != 6:
        raise_robot_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=RobotErrorCode.JOINT_LIMIT_EXCEEDED,
            message="Target must contain exactly 6 joint angles.",
            recoverable=False,
        )

    # 2. Check each joint against mechanical hardware limits
    for idx, (lo, hi) in enumerate(JOINT_LIMITS_DEG):
        val = req.angles_deg[idx]
        if val < lo or val > hi:
            raise_robot_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=RobotErrorCode.JOINT_LIMIT_EXCEEDED,
                message=f"Joint {idx + 1} angle {val:.1f}° is outside limits [{lo:.1f}°, {hi:.1f}°]",
                recoverable=False,
            )

    # 3. Execute motion
    ok, msg = robot_controller.move_to_angles(req.angles_deg, speed_deg_s=req.speed_deg_s)
    if not ok:
        raise_robot_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code=RobotErrorCode.MOTION_DISABLED,
            message=f"Motion failed: {msg}",
            recoverable=True,
        )

    return {"status": "moving", "target_angles": req.angles_deg, "message": msg}

@app.post(
    "/robot/move_to_pose",
    responses={
        422: {"model": RobotErrorResponse, "description": "Inverse Kinematics failed (unreachable)"},
        409: {"model": RobotErrorResponse, "description": "Motion disabled"},
        503: {"model": RobotErrorResponse, "description": "Robot not connected"},
    },
)
def move_to_pose(req: PoseMoveRequest):
    """Moves end-effector linearly in Cartesian space [x, y, z, rx, ry, rz]."""
    ensure_robot_connected()
    robot_controller.last_action = "move_to_pose"

    # 1. Validate vector length
    if len(req.pose_m) != 6:
        raise_robot_error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code=RobotErrorCode.IK_SOLVER_FAILED,
            message="Cartesian pose must contain exactly 6 values [x, y, z, rx, ry, rz].",
            recoverable=False,
        )

    # 2. Execute Cartesian move
    ok, msg = robot_controller.move_to_pose(req.pose_m, duration=req.duration_s)
    if not ok:
        is_ik = "ik" in msg.lower() or "unreachable" in msg.lower() or "solution" in msg.lower()
        err_code = RobotErrorCode.IK_SOLVER_FAILED if is_ik else RobotErrorCode.MOTION_DISABLED
        err_status = status.HTTP_422_UNPROCESSABLE_ENTITY if is_ik else status.HTTP_409_CONFLICT

        raise_robot_error(
            status_code=err_status,
            error_code=err_code,
            message=f"Cartesian motion failed: {msg}",
            recoverable=False,
        )

    return {"status": "moving", "target_pose": req.pose_m, "message": msg}

@app.post(
    "/robot/park",
    responses={
        409: {"model": RobotErrorResponse, "description": "Motion disabled"},
        503: {"model": RobotErrorResponse, "description": "Robot not connected"},
    },
)
def park_robot():
    """Moves arm to safe standby / park pose. Called by BPMN error recovery branches."""
    ensure_robot_connected()
    robot_controller.last_action = "park"

    ok, msg = robot_controller.park()
    if not ok:
        raise_robot_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code=RobotErrorCode.MOTION_DISABLED,
            message=f"Failed to park robot: {msg}",
            recoverable=True,
        )
    return {"status": "parked", "message": msg}


@app.post(
    "/robot/halt",
    responses={
        503: {"model": RobotErrorResponse, "description": "Robot not connected"},
    },
)
def halt_robot():
    """Emergency Stop: immediately halts arm motion."""
    ensure_robot_connected()
    robot_controller.last_action = "halt"

    ok, msg = robot_controller.halt()
    if not ok:
        raise_robot_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code=RobotErrorCode.NOT_CONNECTED,
            message=f"Halt failed: {msg}",
            recoverable=False,
        )
    return {"status": "halted", "motion_enabled": False, "message": msg}


@app.post(
    "/robot/resume",
    responses={
        409: {"model": RobotErrorResponse, "description": "Could not enable motion"},
        503: {"model": RobotErrorResponse, "description": "Robot not connected"},
    },
)
def resume_robot():
    """Clears halt state and re-enables robot motion."""
    ensure_robot_connected()
    robot_controller.last_action = "resume"

    ok, msg = robot_controller.resume()
    if not ok:
        raise_robot_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code=RobotErrorCode.MOTION_DISABLED,
            message=f"Resume failed: {msg}",
            recoverable=True,
        )
    return {"status": "resumed", "motion_enabled": True, "message": msg}



# 5. Allow running directly with: python -m scotty.api.server
if __name__ == "__main__":
    uvicorn.run("scotty.api.server:app", host="0.0.0.0", port=8100, reload=True)
