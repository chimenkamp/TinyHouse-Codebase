"""Hand-eye calibration GUI for the PAROL6 + XIAO ESP32S3 Sense camera.

This is a full PySide6 application:

    +--------------------------------------+----------------------------------+
    |                                      |  Connection status               |
    |        live camera view              |  ----------------                |
    |        (ChArUco overlay)             |  Joint sliders J1..J6 [deg]      |
    |                                      |    (commit on release)           |
    |                                      |  Cartesian readout (XYZ + RPY)   |
    |                                      |  ---------------                 |
    |                                      |  [ Capture ] [ Drop last ]       |
    |                                      |  [ Solve & Save ]                |
    |                                      |  [ Home ] [ Halt ] [ Quit ]      |
    |                                      |  Sample list / log               |
    +--------------------------------------+----------------------------------+

While the application is running the robot is held energized so the operator
*cannot* push it by hand: every position change goes through the sliders.
Captures use the live joint readback from PAROL6 and the latest detected
ChArUco pose. Press "Solve & Save" to write ``hand_eye.npz`` next to the
repository root.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Path setup so we can import the in-repo ``parol6`` package even when it is
# not pip-installed. The package lives at <repo_root>/parol6/.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
for _p in (_REPO_ROOT, _SCRIPT_DIR):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

# Reuse the serial camera + ChArUco constants from the existing viewer.
from usb_serial_camera_viewer import (  # noqa: E402
    CHARUCO_DICT,
    MARKER_LENGTH_M,
    SQUARES_X,
    SQUARES_Y,
    SQUARE_LENGTH_M,
    SerialCamera,
)

try:
    from parol6 import Robot as _Parol6Robot, RobotClient as _Parol6Client  # type: ignore
    _PAROL6_AVAILABLE = True
except Exception as _exc:  # pragma: no cover
    _Parol6Robot = None  # type: ignore
    _Parol6Client = None  # type: ignore
    _PAROL6_AVAILABLE = False
    _PAROL6_IMPORT_ERROR = _exc
    raise ImportError( f"Failed to import parol6 package: {_exc}") from _exc

from PySide6.QtCore import Qt, QTimer, Signal, QObject  # noqa: E402
from PySide6.QtGui import QImage, QPixmap, QFont  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@dataclass
class Settings:
    """All tunables for the hand-eye calibration run. Edit values here."""

    # --- Camera (XIAO ESP32S3 Sense over USB serial) ---
    camera_port: str = "/dev/tty.usbmodem101"
    camera_baud: int = 921600
    camera_timeout_s: float = 2.0
    camera_framesize: str = "UXGA"
    camera_jpeg_quality: int = 8  # lower number = higher quality

    # --- Files ---
    intrinsics_path: Path = field(default_factory=lambda: _SCRIPT_DIR / "intrinsics.npz")
    output_path: Path = field(default_factory=lambda: _REPO_ROOT / "hand_eye.npz")

    # --- UI ---
    window_title: str = "PAROL6 Hand-Eye Calibration"
    min_samples: int = 15
    preview_max_width: int = 960  # cap the displayed frame width

    # --- PAROL6 ---
    parol6_serial_port: str = "/dev/tty.usbmodem308A388234331"
    parol6_host: str = "127.0.0.1"
    parol6_port: int = 5001
    parol6_client_timeout_s: float = 2.0
    parol6_ready_timeout_s: float = 8.0
    move_speed_deg_s: float = 25.0   # joint speed for slider commits
    move_accel: float = 1.0


SETTINGS = Settings()


# ---------------------------------------------------------------------------
# Joint limits — match parol6/PAROL6_ROBOT.py:_joint_limits_degree
# ---------------------------------------------------------------------------
JOINT_LIMITS_DEG: list[tuple[float, float]] = [
    (-123.046875, 123.046875),  # J1
    (-145.0088, -3.375),        # J2
    (107.866, 287.8675),        # J3
    (-105.46975, 105.46975),    # J4
    (-90.0, 90.0),              # J5
    (0.0, 360.0),               # J6
]
JOINT_HOME_DEG: list[float] = [0.0, -90.0, 180.0, 0.0, 0.0, 180.0]


# ---------------------------------------------------------------------------
# PAROL6 forward kinematics (modified DH chain — fallback if Robot.fk fails)
# ---------------------------------------------------------------------------
PAROL6_DH = np.array(
    [
        # alpha_{i-1},    a_{i-1},  d_i,      theta_offset
        [0.0,             0.0,      0.1105,   0.0],            # J1
        [-np.pi / 2,      0.0,      0.0,      -np.pi / 2],     # J2
        [0.0,             0.180,    0.0,      0.0],            # J3
        [-np.pi / 2,      0.0,      0.17655,  0.0],            # J4
        [np.pi / 2,       0.0,      0.0,      0.0],            # J5
        [-np.pi / 2,      0.0,      0.06542,  0.0],            # J6 (flange)
    ],
    dtype=float,
)


def _dh_transform(alpha: float, a: float, d: float, theta: float) -> np.ndarray:
    ca, sa = np.cos(alpha), np.sin(alpha)
    ct, st = np.cos(theta), np.sin(theta)
    return np.array(
        [
            [ct,      -st,     0.0,    a],
            [st * ca, ct * ca, -sa,   -sa * d],
            [st * sa, ct * sa,  ca,    ca * d],
            [0.0,     0.0,     0.0,    1.0],
        ],
        dtype=float,
    )


def parol6_fk(joint_angles_deg: np.ndarray) -> np.ndarray:
    """Forward kinematics: 6 joint angles (degrees) -> T_base_gripper (4x4, m)."""
    if joint_angles_deg.shape != (6,):
        raise ValueError(f"Expected 6 joint angles, got shape {joint_angles_deg.shape}")
    thetas = np.deg2rad(joint_angles_deg)
    T = np.eye(4)
    for i in range(6):
        alpha, a, d, off = PAROL6_DH[i]
        T = T @ _dh_transform(alpha, a, d, thetas[i] + off)
    return T


# ---------------------------------------------------------------------------
# Calibration data + ChArUco helpers
# ---------------------------------------------------------------------------
@dataclass
class Sample:
    joints_deg: np.ndarray            # (6,)
    T_base_gripper: np.ndarray        # (4, 4)
    rvec_target_cam: np.ndarray       # (3, 1)
    tvec_target_cam: np.ndarray       # (3, 1)


def load_intrinsics() -> tuple[np.ndarray, np.ndarray]:
    path = SETTINGS.intrinsics_path
    if not path.exists():
        raise FileNotFoundError(
            f"Intrinsics file not found at {path}. "
            "Run the camera intrinsic calibration first."
        )
    data = np.load(path)
    return data["intrinsics"], data["distortion"]


def make_detector() -> tuple[cv2.aruco.ArucoDetector, cv2.aruco.CharucoBoard, cv2.CLAHE]:
    dictionary = cv2.aruco.getPredefinedDictionary(CHARUCO_DICT)
    board = cv2.aruco.CharucoBoard(
        (SQUARES_X, SQUARES_Y), SQUARE_LENGTH_M, MARKER_LENGTH_M, dictionary
    )
    params = cv2.aruco.DetectorParameters()
    params.adaptiveThreshWinSizeMin = 5
    params.adaptiveThreshWinSizeMax = 45
    params.adaptiveThreshWinSizeStep = 4
    params.minMarkerPerimeterRate = 0.01
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    if hasattr(params, "useAruco3Detection"):
        params.useAruco3Detection = True
    detector = cv2.aruco.ArucoDetector(dictionary, params)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return detector, board, clahe


def estimate_board_pose(
    frame: np.ndarray,
    detector: cv2.aruco.ArucoDetector,
    board: cv2.aruco.CharucoBoard,
    clahe: cv2.CLAHE,
    K: np.ndarray,
    dist: np.ndarray,
):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = clahe.apply(gray)
    marker_corners, marker_ids, _ = detector.detectMarkers(gray)
    if marker_ids is None or len(marker_ids) == 0:
        return None, None, 0, 0, None, None
    _, corners, ids = cv2.aruco.interpolateCornersCharuco(
        marker_corners, marker_ids, gray, board
    )
    n_corners = 0 if ids is None else len(ids)
    if n_corners < 6:
        return None, None, n_corners, len(marker_ids), corners, ids
    obj_pts, img_pts = board.matchImagePoints(corners, ids)
    if obj_pts is None or len(obj_pts) < 6:
        return None, None, n_corners, len(marker_ids), corners, ids
    ok, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, K, dist, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        return None, None, n_corners, len(marker_ids), corners, ids
    return rvec, tvec, n_corners, len(marker_ids), corners, ids


def solve_hand_eye(samples: list[Sample]) -> tuple[np.ndarray, float, float]:
    """Run cv2.calibrateHandEye + AX=XB residual. Returns (T_cam_gripper, rms_rot_deg, rms_trans_m)."""
    if len(samples) < 5:
        raise ValueError(f"Need at least 5 samples, have {len(samples)}.")

    R_gripper2base, t_gripper2base = [], []
    R_target2cam, t_target2cam = [], []
    for s in samples:
        T_b_g = s.T_base_gripper
        R_gripper2base.append(T_b_g[:3, :3])
        t_gripper2base.append(T_b_g[:3, 3].reshape(3, 1))
        R_tc, _ = cv2.Rodrigues(s.rvec_target_cam)
        R_target2cam.append(R_tc)
        t_target2cam.append(s.tvec_target_cam.reshape(3, 1))

    R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
        R_gripper2base, t_gripper2base,
        R_target2cam, t_target2cam,
        method=cv2.CALIB_HAND_EYE_PARK,
    )
    T_cam_gripper = np.eye(4)
    T_cam_gripper[:3, :3] = R_cam2gripper
    T_cam_gripper[:3, 3] = t_cam2gripper.flatten()

    T_base_target_ref = None
    rot_errs: list[float] = []
    trans_errs: list[float] = []
    for s in samples:
        T_t_c = np.eye(4)
        R_tc, _ = cv2.Rodrigues(s.rvec_target_cam)
        T_t_c[:3, :3] = R_tc
        T_t_c[:3, 3] = s.tvec_target_cam.flatten()
        T_b_t = s.T_base_gripper @ T_cam_gripper @ np.linalg.inv(T_t_c)
        if T_base_target_ref is None:
            T_base_target_ref = T_b_t
            continue
        delta = np.linalg.inv(T_base_target_ref) @ T_b_t
        rot_errs.append(np.degrees(np.arccos(np.clip((np.trace(delta[:3, :3]) - 1) / 2, -1, 1))))
        trans_errs.append(float(np.linalg.norm(delta[:3, 3])))

    rms_rot = float(np.sqrt(np.mean(np.square(rot_errs)))) if rot_errs else 0.0
    rms_trans = float(np.sqrt(np.mean(np.square(trans_errs)))) if trans_errs else 0.0
    return T_cam_gripper, rms_rot, rms_trans


def save_hand_eye(T_cam_gripper: np.ndarray, n_samples: int,
                  rms_rot_deg: float, rms_trans_m: float) -> Path:
    rvec, _ = cv2.Rodrigues(T_cam_gripper[:3, :3])
    np.savez(
        SETTINGS.output_path,
        T_cam_gripper=T_cam_gripper,
        rvec=rvec,
        tvec=T_cam_gripper[:3, 3].reshape(3, 1),
        method="PARK",
        n_samples=n_samples,
        rms_rotation_deg=rms_rot_deg,
        rms_translation_m=rms_trans_m,
    )
    return SETTINGS.output_path.resolve()


# ---------------------------------------------------------------------------
# Background camera reader (latest-frame slot, identical pattern to the viewer)
# ---------------------------------------------------------------------------
class CameraReader(QObject):
    error = Signal(str)
    stopped = Signal()

    def __init__(self, camera: SerialCamera) -> None:
        super().__init__()
        self._camera = camera
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest: np.ndarray | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        self.stopped.emit()

    def latest(self) -> np.ndarray | None:
        with self._lock:
            f = self._latest
            self._latest = None
            return f

    def _run(self) -> None:
        last_err_t = 0.0
        while not self._stop.is_set():
            try:
                f, _, _, _ = self._camera.read()
            except (TimeoutError, RuntimeError) as exc:
                if time.time() - last_err_t > 2.0:
                    self.error.emit(f"{type(exc).__name__}: {exc}")
                    last_err_t = time.time()
                time.sleep(0.05)
                continue
            except BaseException as exc:
                self.error.emit(f"FATAL {type(exc).__name__}: {exc}")
                return
            with self._lock:
                self._latest = f


# ---------------------------------------------------------------------------
# PAROL6 controller wrapper
# ---------------------------------------------------------------------------
class Parol6Controller:
    """Owns the controller subprocess + sync client. Kept tiny and defensive."""

    def __init__(self) -> None:
        self.robot: object | None = None
        self.client: object | None = None
        self.connected: bool = False
        self.last_error: str | None = None

    def connect(self) -> None:
        if not _PAROL6_AVAILABLE:
            self.last_error = f"parol6 package not importable: {globals().get('_PAROL6_IMPORT_ERROR')}"
            return
        try:
            os.environ["PAROL6_COM_PORT"] = SETTINGS.parol6_serial_port
            self.robot = _Parol6Robot(  # type: ignore[misc]
                host=SETTINGS.parol6_host, port=SETTINGS.parol6_port, normalize_logs=True
            )
            self.robot.start()  # type: ignore[union-attr]
            self.client = _Parol6Client(  # type: ignore[misc]
                host=SETTINGS.parol6_host, port=SETTINGS.parol6_port,
                timeout=SETTINGS.parol6_client_timeout_s,
            )
            self.client.__enter__()  # type: ignore[union-attr]
            if not self.client.wait_ready(timeout=SETTINGS.parol6_ready_timeout_s):  # type: ignore[union-attr]
                self.last_error = "PAROL6 controller did not become ready"
                self.disconnect()
                return
            self.connected = True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.disconnect()

    def disconnect(self) -> None:
        self.connected = False
        if self.client is not None:
            try:
                self.client.__exit__(None, None, None)  # type: ignore[union-attr]
            except Exception:
                pass
            self.client = None
        if self.robot is not None:
            try:
                self.robot.stop()  # type: ignore[union-attr]
            except Exception:
                pass
            self.robot = None

    # --- Read ---
    def angles(self) -> np.ndarray | None:
        if self.client is None:
            return None
        try:
            a = self.client.angles()  # type: ignore[union-attr]
            if a is None:
                return None
            arr = np.asarray(a, dtype=float)
            return arr if arr.shape == (6,) else None
        except Exception as exc:
            self.last_error = f"angles: {exc}"
            return None

    def pose(self) -> np.ndarray | None:
        if self.client is None:
            return None
        try:
            p = self.client.pose()  # type: ignore[union-attr]
            return None if p is None else np.asarray(p, dtype=float)
        except Exception as exc:
            self.last_error = f"pose: {exc}"
            return None

    # --- Move ---
    def move_to(self, angles_deg: list[float], speed_deg_s: float, accel: float) -> tuple[bool, str]:
        if self.client is None:
            return False, "not connected"
        try:
            # speed in deg/s => parol6 expects scalar 0..1 for speed *or* duration.
            # We use ``duration`` derived from the largest joint delta for predictable feel.
            current = self.angles()
            if current is None:
                return False, "could not read current angles"
            delta = float(max(abs(a - c) for a, c in zip(angles_deg, current)))
            duration = max(0.4, delta / max(1.0, speed_deg_s))
            self.client.move_j(  # type: ignore[union-attr]
                angles_deg, duration=duration, accel=accel, wait=False, timeout=duration + 5.0,
            )
            return True, f"move_j duration={duration:.2f}s"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    def home(self) -> tuple[bool, str]:
        if self.client is None:
            return False, "not connected"
        try:
            self.client.home(wait=False)  # type: ignore[union-attr]
            return True, "home command sent"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    def halt(self) -> tuple[bool, str]:
        if self.client is None:
            return False, "not connected"
        try:
            self.client.halt()  # type: ignore[union-attr]
            return True, "halt sent"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class JointSliderRow(QWidget):
    """One row: label, slider (0.1° resolution), spinbox, sync-from-robot toggle.

    The slider only commits a target to the parent on ``sliderReleased`` to avoid
    flooding the controller with move commands.
    """

    committed = Signal(int, float)  # joint_idx, value_deg

    SCALE = 10  # slider integer = degrees * 10

    def __init__(self, idx: int, lo: float, hi: float, initial: float):
        super().__init__()
        self.idx = idx
        self.lo, self.hi = lo, hi
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.label = QLabel(f"J{idx + 1}")
        self.label.setFixedWidth(28)
        self.label.setFont(QFont("Menlo", 11, QFont.Bold))

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(int(round(lo * self.SCALE)))
        self.slider.setMaximum(int(round(hi * self.SCALE)))
        self.slider.setValue(int(round(initial * self.SCALE)))
        self.slider.setTracking(True)

        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(2)
        self.spin.setRange(lo, hi)
        self.spin.setSingleStep(0.5)
        self.spin.setValue(initial)
        self.spin.setFixedWidth(100)
        self.spin.setSuffix(" °")

        self.range_label = QLabel(f"[{lo:.1f}, {hi:.1f}]")
        self.range_label.setStyleSheet("color: #888;")
        self.range_label.setFixedWidth(120)

        layout.addWidget(self.label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)
        layout.addWidget(self.range_label)

        # Wire slider <-> spinbox, but only emit `committed` on release / spin commit.
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.slider.sliderReleased.connect(self._on_commit)
        self.spin.editingFinished.connect(self._on_spin_finished)

        self._suppress = False

    # --- Sync helpers ---
    def set_value(self, deg: float, *, from_robot: bool = False) -> None:
        deg = max(self.lo, min(self.hi, float(deg)))
        self._suppress = True
        self.slider.setValue(int(round(deg * self.SCALE)))
        self.spin.setValue(deg)
        self._suppress = False

    def value(self) -> float:
        return float(self.spin.value())

    def _on_slider_changed(self, v: int) -> None:
        if self._suppress:
            return
        self._suppress = True
        self.spin.setValue(v / self.SCALE)
        self._suppress = False

    def _on_spin_finished(self) -> None:
        if self._suppress:
            return
        self._suppress = True
        self.slider.setValue(int(round(self.spin.value() * self.SCALE)))
        self._suppress = False
        self._on_commit()

    def _on_commit(self) -> None:
        self.committed.emit(self.idx, self.value())


class CalibrationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(SETTINGS.window_title)
        self.resize(1500, 820)

        # --- Calibration state ---
        try:
            self.K, self.dist = load_intrinsics()
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "Intrinsics missing", str(exc))
            raise
        self.detector, self.board, self.clahe = make_detector()
        self.samples: list[Sample] = []
        self.last_pose: tuple[np.ndarray, np.ndarray] | None = None
        self.last_pose_age = time.time()
        self.detected = False

        # --- Robot ---
        self.robot = Parol6Controller()
        self.robot.connect()

        # --- Camera ---
        try:
            self.camera = SerialCamera(
                port=SETTINGS.camera_port,
                baud=SETTINGS.camera_baud,
                timeout=SETTINGS.camera_timeout_s,
                framesize=SETTINGS.camera_framesize,
                window_name=SETTINGS.window_title,
            )
            self.camera.__enter__()
            self.camera.send_command(f"SET QUALITY {SETTINGS.camera_jpeg_quality}")
            self.camera.set_streaming(True)
        except Exception as exc:
            QMessageBox.critical(self, "Camera failed", str(exc))
            raise
        self.reader = CameraReader(self.camera)
        self.reader.error.connect(self._on_camera_error)
        self.reader.start()

        # --- Build UI ---
        self._build_ui()

        # Initialise sliders to the current robot pose if connected.
        if self.robot.connected:
            ang = self.robot.angles()
            if ang is not None:
                for i, v in enumerate(ang):
                    self.slider_rows[i].set_value(float(v))

        # --- Timers ---
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(33)  # ~30 FPS
        self._frame_timer.timeout.connect(self._on_frame_tick)
        self._frame_timer.start()

        self._robot_timer = QTimer(self)
        self._robot_timer.setInterval(250)  # 4 Hz
        self._robot_timer.timeout.connect(self._on_robot_tick)
        self._robot_timer.start()

        self._update_status()

    # ---------------- UI construction ----------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        # --- Left: video preview ---
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("background:#111; color:#aaa;")
        self.video_label.setText("Waiting for first frame from camera…")
        root.addWidget(self.video_label, 3)

        # --- Right: control panel ---
        right = QVBoxLayout()
        right.setSpacing(8)
        root.addLayout(right, 2)

        # Status group
        status_group = QGroupBox("Status")
        status_layout = QGridLayout(status_group)
        self.lbl_camera = QLabel("Camera: connecting…")
        self.lbl_robot = QLabel("Robot: connecting…")
        self.lbl_detect = QLabel("Board: -")
        self.lbl_pose = QLabel("Pose: -")
        for w in (self.lbl_camera, self.lbl_robot, self.lbl_detect, self.lbl_pose):
            w.setFont(QFont("Menlo", 10))
        status_layout.addWidget(self.lbl_camera, 0, 0)
        status_layout.addWidget(self.lbl_robot, 1, 0)
        status_layout.addWidget(self.lbl_detect, 2, 0)
        status_layout.addWidget(self.lbl_pose, 3, 0)
        right.addWidget(status_group)

        # Joint sliders
        joint_group = QGroupBox("Joint targets (commit on release)")
        joint_layout = QVBoxLayout(joint_group)
        self.slider_rows: list[JointSliderRow] = []
        for i in range(6):
            lo, hi = JOINT_LIMITS_DEG[i]
            initial = JOINT_HOME_DEG[i]
            initial = max(lo, min(hi, initial))
            row = JointSliderRow(i, lo, hi, initial)
            row.committed.connect(self._on_joint_commit)
            joint_layout.addWidget(row)
            self.slider_rows.append(row)

        # Live readout row
        self.lbl_live = QLabel("live: —")
        self.lbl_live.setFont(QFont("Menlo", 10))
        self.lbl_live.setStyleSheet("color:#357;")
        joint_layout.addWidget(self.lbl_live)

        sync_row = QHBoxLayout()
        self.chk_follow = QCheckBox("Sliders follow robot when idle")
        self.chk_follow.setChecked(True)
        sync_row.addWidget(self.chk_follow)
        sync_row.addStretch(1)
        btn_sync = QPushButton("Sync sliders ← robot")
        btn_sync.clicked.connect(self._sync_sliders_from_robot)
        sync_row.addWidget(btn_sync)
        joint_layout.addLayout(sync_row)
        right.addWidget(joint_group)

        # Action buttons
        action_group = QGroupBox("Calibration")
        ag = QGridLayout(action_group)
        self.btn_capture = QPushButton("Capture sample")
        self.btn_capture.setStyleSheet("background:#3a7;color:white;font-weight:bold;padding:8px;")
        self.btn_capture.clicked.connect(self._on_capture)

        self.btn_drop = QPushButton("Drop last")
        self.btn_drop.clicked.connect(self._on_drop)

        self.btn_solve = QPushButton("Solve && Save")
        self.btn_solve.setStyleSheet("background:#37a;color:white;font-weight:bold;padding:8px;")
        self.btn_solve.clicked.connect(self._on_solve)

        self.lbl_samples = QLabel(f"0 / {SETTINGS.min_samples} samples")
        self.lbl_samples.setFont(QFont("Menlo", 11, QFont.Bold))

        ag.addWidget(self.btn_capture, 0, 0)
        ag.addWidget(self.btn_drop, 0, 1)
        ag.addWidget(self.btn_solve, 1, 0, 1, 2)
        ag.addWidget(self.lbl_samples, 2, 0, 1, 2)
        right.addWidget(action_group)

        # Robot control buttons
        rc_group = QGroupBox("Robot control")
        rc = QHBoxLayout(rc_group)
        self.btn_home = QPushButton("Home")
        self.btn_home.clicked.connect(self._on_home)
        self.btn_halt = QPushButton("HALT")
        self.btn_halt.setStyleSheet("background:#c33;color:white;font-weight:bold;padding:8px;")
        self.btn_halt.clicked.connect(self._on_halt)
        self.btn_quit = QPushButton("Quit")
        self.btn_quit.clicked.connect(self.close)
        rc.addWidget(self.btn_home)
        rc.addWidget(self.btn_halt)
        rc.addStretch(1)
        rc.addWidget(self.btn_quit)
        right.addWidget(rc_group)

        # Sample log
        log_group = QGroupBox("Captured samples")
        log_layout = QVBoxLayout(log_group)
        self.sample_list = QListWidget()
        log_layout.addWidget(self.sample_list)
        right.addWidget(log_group, 1)

    # ---------------- Frame loop ----------------
    def _on_frame_tick(self) -> None:
        raw = self.reader.latest()
        if raw is None:
            return
        frame = cv2.flip(raw, 1)
        rvec, tvec, n_corners, n_markers, corners, ids = estimate_board_pose(
            frame, self.detector, self.board, self.clahe, self.K, self.dist
        )
        display = frame.copy()
        if ids is not None:
            cv2.aruco.drawDetectedCornersCharuco(display, corners, ids)
        if rvec is not None:
            cv2.drawFrameAxes(display, self.K, self.dist, rvec, tvec, SQUARE_LENGTH_M * 3)
            self.last_pose = (rvec, tvec)
            self.last_pose_age = time.time()
            self.detected = True
        else:
            self.detected = False

        # Detection status text
        col = "#3c3" if self.detected else "#c33"
        if self.detected:
            dist_mm = float(np.linalg.norm(tvec)) * 1000.0
            self.lbl_detect.setText(
                f"Board: detected   markers={n_markers}  corners={n_corners}  dist={dist_mm:.0f} mm"
            )
        else:
            self.lbl_detect.setText(
                f"Board: NOT detected   markers={n_markers}  corners={n_corners}"
            )
        self.lbl_detect.setStyleSheet(f"color:{col};")
        self.btn_capture.setEnabled(self.detected and self.robot.connected)

        self._show_frame(display)

    def _show_frame(self, bgr: np.ndarray) -> None:
        h, w = bgr.shape[:2]
        if w > SETTINGS.preview_max_width:
            scale = SETTINGS.preview_max_width / w
            bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)))
            h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        img = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(img.copy()))

    # ---------------- Robot poll ----------------
    def _on_robot_tick(self) -> None:
        ang = self.robot.angles()
        if ang is None:
            self.lbl_live.setText("live: (no readback)")
        else:
            self.lbl_live.setText(
                "live: " + "  ".join(f"J{i+1}={a:+7.2f}°" for i, a in enumerate(ang))
            )
            if self.chk_follow.isChecked() and not self._any_slider_pressed():
                for i, v in enumerate(ang):
                    if abs(self.slider_rows[i].value() - float(v)) > 0.05:
                        self.slider_rows[i].set_value(float(v))
        pose = self.robot.pose()
        if pose is not None and pose.shape[0] >= 6:
            self.lbl_pose.setText(
                f"TCP: x={pose[0]:+7.1f} y={pose[1]:+7.1f} z={pose[2]:+7.1f} mm  "
                f"rx={pose[3]:+6.1f} ry={pose[4]:+6.1f} rz={pose[5]:+6.1f}°"
            )
        self._update_status()

    def _any_slider_pressed(self) -> bool:
        return any(r.slider.isSliderDown() for r in self.slider_rows)

    def _update_status(self) -> None:
        cam_ok = self.reader._thread.is_alive()  # noqa: SLF001
        self.lbl_camera.setText(f"Camera: {'OK' if cam_ok else 'DEAD'}  port={SETTINGS.camera_port}")
        self.lbl_camera.setStyleSheet("color:#3c3;" if cam_ok else "color:#c33;")
        if self.robot.connected:
            self.lbl_robot.setText(
                f"Robot: connected  serial={SETTINGS.parol6_serial_port}  "
                f"udp={SETTINGS.parol6_host}:{SETTINGS.parol6_port}"
            )
            self.lbl_robot.setStyleSheet("color:#3c3;")
        else:
            self.lbl_robot.setText(f"Robot: OFFLINE  ({self.robot.last_error or 'not connected'})")
            self.lbl_robot.setStyleSheet("color:#c33;")
        self.lbl_samples.setText(f"{len(self.samples)} / {SETTINGS.min_samples} samples")
        for b in (self.btn_home, self.btn_halt):
            b.setEnabled(self.robot.connected)
        for r in self.slider_rows:
            r.setEnabled(self.robot.connected)
        self.btn_solve.setEnabled(len(self.samples) >= 5)

    # ---------------- Slot handlers ----------------
    def _on_joint_commit(self, idx: int, _value: float) -> None:
        if not self.robot.connected:
            return
        targets = [r.value() for r in self.slider_rows]
        ok, msg = self.robot.move_to(targets, SETTINGS.move_speed_deg_s, SETTINGS.move_accel)
        prefix = "→" if ok else "!"
        self._log(f"{prefix} J{idx+1} commit  targets={[f'{t:+.2f}' for t in targets]}  ({msg})")

    def _sync_sliders_from_robot(self) -> None:
        ang = self.robot.angles()
        if ang is None:
            self._log("! sync failed (no readback)")
            return
        for i, v in enumerate(ang):
            self.slider_rows[i].set_value(float(v))
        self._log(f"→ sliders synced  {[round(float(a),2) for a in ang]}")

    def _on_capture(self) -> None:
        if not self.detected or self.last_pose is None:
            self._log("! capture aborted: board not detected")
            return
        ang = self.robot.angles()
        if ang is None:
            self._log("! capture aborted: could not read angles")
            return
        T_bg = parol6_fk(ang)
        rv, tv = self.last_pose
        s = Sample(
            joints_deg=ang.copy(),
            T_base_gripper=T_bg,
            rvec_target_cam=rv.copy(),
            tvec_target_cam=tv.copy(),
        )
        self.samples.append(s)
        self.sample_list.addItem(
            f"#{len(self.samples):02d}  J=[{', '.join(f'{a:+6.1f}' for a in ang)}]  "
            f"gxyz(mm)={(T_bg[:3,3]*1000).round(0).tolist()}  "
            f"board(mm)={float(np.linalg.norm(tv))*1000:.0f}"
        )
        self.sample_list.scrollToBottom()
        self._update_status()

    def _on_drop(self) -> None:
        if not self.samples:
            return
        self.samples.pop()
        self.sample_list.takeItem(self.sample_list.count() - 1)
        self._update_status()

    def _on_solve(self) -> None:
        if len(self.samples) < 5:
            QMessageBox.warning(self, "Not enough samples",
                                f"Need at least 5 samples, have {len(self.samples)}.")
            return
        try:
            T, rms_rot, rms_trans = solve_hand_eye(self.samples)
            path = save_hand_eye(T, len(self.samples), rms_rot, rms_trans)
        except Exception as exc:
            QMessageBox.critical(self, "Solve failed", f"{type(exc).__name__}: {exc}")
            return
        msg = (
            f"Saved to {path}\n\n"
            f"T_cam_gripper (4x4, m):\n{np.array2string(T, precision=4, suppress_small=True)}\n\n"
            f"Samples: {len(self.samples)}\n"
            f"Consistency RMS: rot={rms_rot:.3f}°  trans={rms_trans*1000:.2f} mm"
        )
        self._log(f"✓ saved {path.name}  rot_rms={rms_rot:.2f}°  trans_rms={rms_trans*1000:.1f}mm")
        QMessageBox.information(self, "Hand-eye solved", msg)

    def _on_home(self) -> None:
        ok, msg = self.robot.home()
        self._log(("→ " if ok else "! ") + f"home: {msg}")

    def _on_halt(self) -> None:
        ok, msg = self.robot.halt()
        self._log(("→ " if ok else "! ") + f"halt: {msg}")

    # ---------------- Misc ----------------
    def _on_camera_error(self, msg: str) -> None:
        self._log(f"[camera] {msg}")

    def _log(self, msg: str) -> None:
        # Prepend timestamp; keep newest at the bottom of the sample list isn't right
        # — use stdout for verbose log, plus a small status update.
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)

    def closeEvent(self, ev) -> None:  # noqa: N802 (Qt signature)
        try:
            self._frame_timer.stop()
            self._robot_timer.stop()
        except Exception:
            pass
        try:
            self.reader.stop()
        except Exception:
            pass
        try:
            self.camera.set_streaming(False)
            self.camera.__exit__(None, None, None)
        except Exception:
            pass
        try:
            self.robot.disconnect()
        except Exception:
            pass
        super().closeEvent(ev)


def main() -> None:
    app = QApplication(sys.argv)
    win = CalibrationWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
