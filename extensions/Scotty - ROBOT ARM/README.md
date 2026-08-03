# Scotty — PAROL6 Robot Arm

Scotty combines the PAROL6 desktop UI, serial-camera calibration, brick
detection and grasp planning. This directory also contains the standalone
digital twin and the imported ROS2/MoveIt sources.

Use the shared environment and launchers from the repository root:

```bash
./run_scotty.sh
./run_digital_twin.sh backend
./run_digital_twin.sh frontend
```

The digital-twin processes run in separate terminals. See
`digital_twin/README.md` for architecture and safety details. Camera firmware
and calibration notes are documented in `Xiao_ESP32S3_Sense/README.md` and
`camera_intrinsic_calibration.md`.
