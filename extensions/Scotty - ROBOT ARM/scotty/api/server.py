"""REST API service for Scotty and the PAROL6 robot arm."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

from ..robot.controller import Parol6Controller, JOINT_LIMITS_DEG, JOINT_HOME_DEG

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
@app.post("/robot/connect")
def connect_robot():
    """Connects to the PAROL6 robot or local simulator server."""
    robot_controller.connect()
    return {
        "connected": robot_controller.connected,
        "last_error": robot_controller.last_error,
    }


@app.post("/robot/disconnect")
def disconnect_robot():
    """Disconnects from the robot."""
    robot_controller.disconnect()
    return {"connected": False}


# 5. Allow running directly with: python -m scotty.api.server
if __name__ == "__main__":
    uvicorn.run("scotty.api.server:app", host="0.0.0.0", port=8100, reload=True)
