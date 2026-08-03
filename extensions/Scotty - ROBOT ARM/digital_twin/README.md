# PAROL6 Digital Twin

Standalone web UI for a PAROL6 digital twin. This app is intentionally separate
from the existing Scotty UI.

## Structure

- `backend/` - FastAPI API and safety-gated bridge to the in-repo `parol6` package.
- `frontend/` - Vite, React, TypeScript, Three.js, and `urdf-loader`.
- Robot model source - `../parol6/urdf_model/urdf/PAROL6.urdf`
- Mesh source - `../parol6/urdf_model/meshes`

## Setup

Use the shared virtual environment from the repository root:

```bash
cd ../..
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Install frontend dependencies:

```bash
npm ci --prefix "Scotty - ROBOT ARM/digital_twin/frontend"
```

## Run

Start the backend:

```bash
./run_digital_twin.sh backend
```

Start the frontend:

```bash
./run_digital_twin.sh frontend
```

Open `http://127.0.0.1:5173`.

## Safety Model

- The UI starts in simulation mode.
- Live robot movement requires explicit live mode and movement enable.
- The backend refuses live movement when disconnected, not homed in this app
  session, emergency stopped, in error, or outside hardware-safe joint limits.
- Joint limits are read from `parol6.PAROL6_ROBOT._joint_limits_degree`.
- The 3D model is loaded from the controller-aligned PAROL6 URDF and meshes
  bundled with the in-repo `parol6` package. This avoids the visible home-pose
  mismatch caused by the ROS2 MoveIt URDF using a different joint zero/sign
  convention than the live hardware telemetry.
- The TCP anchor uses backend FK/IK from the same `parol6` kinematic model and
  converts the solved Cartesian target back into a validated joint-space move.
- HALT is available whenever the robot is connected and disables live movement.

Cartesian controls are intentionally disabled until a safe IK or MoveIt bridge is
added.

## Checks

```bash
.venv/bin/python -m pytest "Scotty - ROBOT ARM/digital_twin/backend/tests"
npm run --prefix "Scotty - ROBOT ARM/digital_twin/frontend" typecheck
npm run --prefix "Scotty - ROBOT ARM/digital_twin/frontend" test
npm run --prefix "Scotty - ROBOT ARM/digital_twin/frontend" build
```
