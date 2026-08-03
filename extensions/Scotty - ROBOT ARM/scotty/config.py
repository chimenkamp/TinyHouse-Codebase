"""Central settings for the Scotty robot-arm suite. Edit values here."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import DATA_DIR


@dataclass
class CameraSettings:
    # ``None`` -> autodetect the XIAO via serial.tools.list_ports. Set an
    # explicit ``/dev/tty.usbmodem...`` (or COMx on Windows) to override.
    port: str | None = None
    baud: int = 921600
    timeout_s: float = 2.0
    framesize: str = "UXGA"
    jpeg_quality: int = 8  # lower = higher quality


@dataclass
class RobotSettings:
    serial_port: str = "/dev/tty.usbmodem308A388234331"
    host: str = "127.0.0.1"
    port: int = 5001
    client_timeout_s: float = 2.0
    ready_timeout_s: float = 8.0
    move_speed_deg_s: float = 25.0
    move_accel: float = 1.0
    # Small readback errors at a freshly homed limit should not trap a
    # joint forever. Targets are clamped inside hard limits when readback
    # is within this tolerance and the requested move is toward the safe side.
    joint_limit_release_tolerance_deg: float = 5.0
    # --- Homing workaround for PAROL6 firmware J6 wraparound bug.
    # Before sending the firmware `home` command we first rotate J6 to this
    # angle so the firmware homing seek always starts from a known side of
    # the J6 limit switch. Without this the homing routine sometimes spins
    # J6 the long way around and tangles the air-line / gripper cables.
    # Set to None to disable the pre-positioning step.
    # Default is None: enable from the UI checkbox and tune the angle until
    # firmware homing consistently picks the cable-safe direction. Try
    # values near both ends (e.g. 5°, 30°, 330°, 355°) — the right side of
    # the J6 limit switch depends on your cable routing.
    prehome_j6_deg: float | None = None
    prehome_j6_speed_deg_s: float = 30.0
    # --- Park pose. The Park button collapses the arm over the base in a
    # staged sequence (elbow folds, then shoulder lifts, then base rotates)
    # to avoid the swing-out-the-front-and-flip behaviour that a single
    # joint-space move from a limit-switch homing pose produces.
    # ``J1=None`` -> keep the current J1 (don't rotate the base).
    # Tune J2/J3 if your installation needs a tighter or looser tuck.
    park_pose_deg: list[float | None] = field(
        default_factory=lambda: [None, -100.0, 220.0, 0.0, 0.0, 180.0]
    )
    # Intermediate elbow value used as the first staging waypoint so the
    # elbow folds *before* the shoulder lifts (keeps swept volume small).
    park_elbow_fold_deg: float = 240.0


@dataclass
class CalibrationFiles:
    intrinsics: Path = field(default_factory=lambda: DATA_DIR / "intrinsics.npz")
    hand_eye: Path = field(default_factory=lambda: DATA_DIR / "hand_eye.npz")
    table_plane: Path = field(default_factory=lambda: DATA_DIR / "table_plane.npz")


@dataclass
class CharucoSettings:
    dict_id: int = 5         # cv2.aruco.DICT_5X5_100
    squares_x: int = 5
    squares_y: int = 7
    square_length_m: float = 0.022
    marker_length_m: float = 0.016


@dataclass
class IntrinsicCalibSettings:
    min_captures: int = 25
    auto_capture_interval_s: float = 1.5
    min_corners_per_capture: int = 8
    min_board_coverage: float = 0.03
    min_sharpness: float = 20.0
    max_rms_px: float = 1.0


@dataclass
class HandEyeSettings:
    min_samples: int = 15
    min_corners_per_sample: int = 8
    max_board_reprojection_px: float = 2.0
    min_pose_delta_m: float = 0.005
    min_pose_delta_deg: float = 2.0
    max_rms_rotation_deg: float = 5.0
    max_rms_translation_m: float = 0.03


@dataclass
class DetectionSettings:
    """Roboflow LEGO detection. Requires `inference` package + ROBOFLOW_API_KEY env var."""
    model_id: str = "hex-lego/3"
    confidence: float = 0.4


@dataclass
class GraspSettings:
    """Hover above the brick centre by `safe_height_m` before descending."""
    safe_height_m: float = 0.08
    descend_height_m: float = 0.005
    table_z_m: float = 0.0  # base-frame Z of the table top (override per setup)
    min_table_ray_z_abs: float = 0.15
    max_table_ray_distance_m: float = 1.5


@dataclass
class UISettings:
    window_title: str = "Scotty Suite"
    preview_max_width: int = 960
    frame_interval_ms: int = 33     # ~30 FPS UI
    robot_poll_ms: int = 250        # 4 Hz robot readback
    joint_slider_delta_deg: float = 15.0
    twin_drag_deg_per_px: float = 0.18
    twin_pick_radius_px: float = 18.0


@dataclass
class Settings:
    camera: CameraSettings = field(default_factory=CameraSettings)
    robot: RobotSettings = field(default_factory=RobotSettings)
    files: CalibrationFiles = field(default_factory=CalibrationFiles)
    charuco: CharucoSettings = field(default_factory=CharucoSettings)
    intrinsic: IntrinsicCalibSettings = field(default_factory=IntrinsicCalibSettings)
    hand_eye: HandEyeSettings = field(default_factory=HandEyeSettings)
    detection: DetectionSettings = field(default_factory=DetectionSettings)
    grasp: GraspSettings = field(default_factory=GraspSettings)
    ui: UISettings = field(default_factory=UISettings)


# Single shared instance (mutate fields here for global config).
SETTINGS = Settings()
