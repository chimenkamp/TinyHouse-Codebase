"""REST API service for Scotty and the PAROL6 robot arm."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>Scotty PAROL6 | Telemetry Dashboard</title>
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
      <style>
        :root {
          --bg: #0b0f19;
          --card: #111827;
          --card-border: #1f293d;
          --text-main: #f3f4f6;
          --text-muted: #9ca3af;
          --accent: #3b82f6;
          --green: #10b981;
          --red: #ef4444;
          --amber: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background: var(--bg); color: var(--text-main); padding: 24px; min-height: 100vh; }
        .container { max-width: 1100px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
        
        /* Header */
        header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 12px; border-bottom: 1px solid var(--card-border); }
        .logo-group h1 { font-size: 1.4rem; font-weight: 700; color: #fff; }
        .logo-group span { font-size: 0.85rem; color: var(--text-muted); }
        .badge { display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; background: #1f2937; }
        .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--red); box-shadow: 0 0 10px var(--red); }
        .dot.connected { background: var(--green); box-shadow: 0 0 10px var(--green); }

        /* Grid */
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
        .card { background: var(--card); border: 1px solid var(--card-border); border-radius: 12px; padding: 20px; }
        .card-title { font-size: 0.95rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 16px; }

        /* Coordinates */
        .coords-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
        .coord-box { background: #0c1322; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; text-align: center; }
        .coord-label { font-size: 0.75rem; color: var(--text-muted); font-weight: 600; }
        .coord-val { font-family: 'JetBrains Mono', monospace; font-size: 1.25rem; font-weight: 600; color: #fff; margin-top: 4px; }
        .coord-unit { font-size: 0.7rem; color: var(--text-muted); margin-left: 2px; }

        /* Joint Bars */
        .joint-list { display: flex; flex-direction: column; gap: 14px; }
        .joint-header { display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px; }
        .joint-val { font-family: 'JetBrains Mono', monospace; font-weight: 600; }
        .track { height: 10px; background: #1e293b; border-radius: 999px; position: relative; overflow: hidden; }
        .fill { height: 100%; background: var(--accent); border-radius: 999px; transition: width 0.3s ease; }
        .limits-sub { display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-muted); margin-top: 3px; }

        /* Footer */
        .footer-bar { display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted); }
      </style>
    </head>
    <body>
      <div class="container">
        <header>
          <div class="logo-group">
            <h1>PAROL6 Robotic Arm</h1>
            <span>Read-Only Telemetry & Safe Monitoring</span>
          </div>
          <div class="badge" id="connBadge">
            <span class="dot" id="connDot"></span>
            <span id="connText">Disconnected</span>
          </div>
        </header>

        <!-- Coordinates Section -->
        <div class="card">
          <div class="card-title">Cartesian End-Effector Pose (World Reference Frame)</div>
          <div class="coords-grid">
            <div class="coord-box"><div class="coord-label">X</div><div class="coord-val" id="valX">--</div><div class="coord-unit">mm</div></div>
            <div class="coord-box"><div class="coord-label">Y</div><div class="coord-val" id="valY">--</div><div class="coord-unit">mm</div></div>
            <div class="coord-box"><div class="coord-label">Z</div><div class="coord-val" id="valZ">--</div><div class="coord-unit">mm</div></div>
            <div class="coord-box"><div class="coord-label">Rx (Roll)</div><div class="coord-val" id="valRx">--</div><div class="coord-unit">°</div></div>
            <div class="coord-box"><div class="coord-label">Ry (Pitch)</div><div class="coord-val" id="valRy">--</div><div class="coord-unit">°</div></div>
            <div class="coord-box"><div class="coord-label">Rz (Yaw)</div><div class="coord-val" id="valRz">--</div><div class="coord-unit">°</div></div>
          </div>
        </div>

        <!-- Joint Angles & Limits -->
        <div class="card">
          <div class="card-title">Joint Positions & Safety Boundaries (J1 - J6)</div>
          <div class="joint-list" id="jointsContainer">Loading joint configuration...</div>
        </div>

        <div class="footer-bar">
          <span id="pollStatus">Live polling active (500 ms)</span>
          <span id="lastUpdated">Updated: --</span>
        </div>
      </div>

      <script>
        async function fetchTelemetry() {
          try {
            const [telemRes, jointsRes] = await Promise.all([
              fetch('/telemetry'),
              fetch('/robot/joints')
            ]);
            const telem = await telemRes.json();
            const joints = await jointsRes.json();

            // 1. Connection Status
            const connDot = document.getElementById('connDot');
            const connText = document.getElementById('connText');
            if (telem.robot_connected) {
              connDot.classList.add('connected');
              connText.textContent = 'Connected (Online)';
              connText.style.color = '#10b981';
            } else {
              connDot.classList.remove('connected');
              connText.textContent = 'Robot Standby / Offline';
              connText.style.color = '#ef4444';
            }

            // 2. Cartesian Coordinates
            if (telem.cartesian_pose) {
              document.getElementById('valX').textContent = telem.cartesian_pose.x_mm;
              document.getElementById('valY').textContent = telem.cartesian_pose.y_mm;
              document.getElementById('valZ').textContent = telem.cartesian_pose.z_mm;
              document.getElementById('valRx').textContent = telem.cartesian_pose.rx_deg;
              document.getElementById('valRy').textContent = telem.cartesian_pose.ry_deg;
              document.getElementById('valRz').textContent = telem.cartesian_pose.rz_deg;
            }

            // 3. Joints Limits and Progress Bars
            if (joints.joints && joints.joints.length) {
              const container = document.getElementById('jointsContainer');
              container.innerHTML = joints.joints.map(j => {
                const min = j.min_limit_deg;
                const max = j.max_limit_deg;
                const cur = j.current_angle_deg !== null ? j.current_angle_deg : (min + max) / 2;
                const range = max - min;
                const pct = Math.min(100, Math.max(0, ((cur - min) / range) * 100));
                const displayVal = j.current_angle_deg !== null ? `${j.current_angle_deg}°` : 'Offline';

                return `
                  <div>
                    <div class="joint-header">
                      <strong>Joint ${j.joint}</strong>
                      <span class="joint-val">${displayVal}</span>
                    </div>
                    <div class="track">
                      <div class="fill" style="width: ${pct}%"></div>
                    </div>
                    <div class="limits-sub">
                      <span>Min: ${min}°</span>
                      <span>Safe Range</span>
                      <span>Max: ${max}°</span>
                    </div>
                  </div>
                `;
              }).join('');
            }

            document.getElementById('lastUpdated').textContent = 'Updated: ' + new Date().toLocaleTimeString();
          } catch (err) {
            console.error('Polling error:', err);
          }
        }

        // Fetch immediately and poll every 500ms
        fetchTelemetry();
        setInterval(fetchTelemetry, 500);
      </script>
    </body>
    </html>
    """



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
