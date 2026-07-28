# TinyHouse Codebase

This monorepo collects the TinyHouse documentation, operations dashboard,
SAGE sensor pipeline, administration tooling, and the Scotty/PAROL6 robot-arm
software.

## Setup

Python 3.11 or newer is required. The root environment is shared by the
Python projects:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Install the documentation dependencies and the digital-twin frontend
dependencies separately:

```bash
npm ci
npm ci --prefix "Scotty - ROBOT ARM/digital_twin/frontend"
npm ci --prefix modules/process-mining-frontend
```

The legacy local YOLOv7 model has its own requirements in
`Scotty - ROBOT ARM/models/yolov7/requirements.txt`. Install those in a
separate environment: its NumPy `<1.24` constraint is incompatible with the
current Scotty controller and digital-twin backend.

## Root launchers

All launchers can be called from any working directory.

```bash
./run_scotty.sh
./run_dashboard.sh local
./run_dashboard.sh tunnel
./run_dashboard.sh stop
npm run process-mining:dev
./run_sage.sh broker --broker localhost --port 1883
./run_sage.sh sensor
./run_sage.sh orchestrator
./run_sage.sh arduino
./run_sage.sh camera
./run_digital_twin.sh backend
./run_digital_twin.sh frontend
./run_docs.sh dev
```

The digital twin needs the backend and frontend in separate terminals. Open
`http://127.0.0.1:5173` after both are running. The dashboard is available at
`http://127.0.0.1:8088`. The standalone mock process-mining dashboard runs at
`http://127.0.0.1:5174` and does not require a backend or connected hardware.

Scotty starts in viewer/simulation mode and can run without robot hardware.
Hardware control needs a supported `pinokin` wheel and the configured PAROL6
serial connection. Cloud detection additionally uses `ROBOFLOW_API_KEY` from
`Scotty - ROBOT ARM/.env`; local color detection works without it.

## Documentation

```bash
./run_docs.sh dev
./run_docs.sh build
./run_docs.sh preview
```

The equivalent npm commands are `npm run docs:dev`, `npm run docs:build`, and
`npm run docs:preview`.

## Repository layout

- `docs/` — VitePress documentation.
- `modules/dashboard/` — FastAPI operations dashboard.
- `modules/process-mining-frontend/` — mock IoT process-mining dashboard with
  interactive signal, case-correlation, and BPMN visualizations.
- `modules/administration/` — Ansible and network collection tooling.
- `extensions/sage/` — sensor abstraction, MQTT, and XES pipeline.
- `Scotty - ROBOT ARM/` — Scotty desktop UI, PAROL6 controller, camera tools,
  ROS2/MoveIt sources, and the digital twin.

Project-specific details remain in the README files inside each project.
