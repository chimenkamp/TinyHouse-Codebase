"""Receive JPEG frames from the XIAO ESP32S3 Sense over USB serial.

Protocol:
  magic      uint32 little-endian, value 0x4D414353 ("SCAM")
  msg_type   uint8, 0x01 frame, 0x02 status
  width      uint16 little-endian
  height     uint16 little-endian
  format     uint8, 1 for JPEG
  payload    uint32 little-endian
  millis     uint32 little-endian
  data       payload bytes
"""

from __future__ import annotations

import os
import struct
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import serial
from serial.tools import list_ports

MAGIC = 0x4D414353
HEADER_STRUCT = struct.Struct("<IBHHBII")
MSG_FRAME = 0x01
MSG_STATUS = 0x02

CHARUCO_DICT = cv2.aruco.DICT_5X5_250
SQUARES_X = 5
SQUARES_Y = 7
SQUARE_LENGTH_M = 0.022
MARKER_LENGTH_M = 0.016

MODEL_ID = "hex-lego/3"
WINDOW_NAME = "XIAO ESP32S3 Sense"
FRAME_SIZE_FALLBACKS = ["UXGA", "SXGA", "XGA", "SVGA", "VGA", "QVGA"]


class Goal(str, Enum):
    VIEW_FEED = "view_feed"
    DETECT_LEGO_BRICKS = "detect_lego_bricks"
    CALIBRATE_INTRINSICS = "calibrate_intrinsics"


@dataclass(slots=True)
class PipelineSettings:
    goal: Goal = Goal.CALIBRATE_INTRINSICS
    port: str | None = None
    baud: int = 921600
    timeout: float = 2.0
    framesize: str = "UXGA"
    jpeg_quality: int = 20
    save_dir: Path | None = Path("Xiao_ESP32S3_Sense/captures")
    confidence: float = 0.5
    calibration_output: Path = Path("Xiao_ESP32S3_Sense/intrinsics.npz")
    min_captures: int = 20
    window_name: str = WINDOW_NAME



def default_settings() -> PipelineSettings:
    return PipelineSettings()


def autodetect_port() -> str:
    candidates: list[str] = []
    for port in list_ports.comports():
        device = port.device or ""
        description = (port.description or "").lower()
        manufacturer = (port.manufacturer or "").lower()
        if "usbmodem" in device or "seeed" in manufacturer or "esp32" in description:
            candidates.append(device)

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise RuntimeError("No likely XIAO serial port found. Pass --port explicitly.")
    raise RuntimeError(
        "Multiple possible serial ports found: " + ", ".join(candidates) + ". Pass --port explicitly."
    )


def open_serial(port: str, baud: int, timeout: float) -> serial.Serial:
    serial_port = serial.Serial(port=port, baudrate=baud, timeout=timeout)
    serial_port.reset_input_buffer()
    serial_port.reset_output_buffer()
    return serial_port


def send_command(serial_port: serial.Serial, command: str) -> None:
    serial_port.write((command.strip() + "\n").encode("utf-8"))
    serial_port.flush()


def decode_frame(payload: bytes) -> np.ndarray | None:
    encoded = np.frombuffer(payload, dtype=np.uint8)
    return cv2.imdecode(encoded, cv2.IMREAD_COLOR)


class SerialCamera:
    def __init__(self, port: str, baud: int, timeout: float, framesize: str, window_name: str) -> None:
        self._serial_port = open_serial(port, baud, timeout)
        self._framesize = framesize
        self._last_status_at = 0.0
        self._window_name = window_name
        self._streaming_enabled = True
        self._last_status_message: str | None = None
        self._buffer = bytearray()

    def __enter__(self) -> SerialCamera:
        cv2.namedWindow(self._window_name, cv2.WINDOW_NORMAL)
        self.send_command(f"SET FRAMESIZE {self._framesize}")
        return self

    def __exit__(self, *_: object) -> None:
        cv2.destroyAllWindows()
        self._serial_port.close()

    def send_command(self, command: str) -> None:
        send_command(self._serial_port, command)

    def set_streaming(self, enabled: bool) -> None:
        self.send_command("STREAM ON" if enabled else "STREAM OFF")
        self._streaming_enabled = enabled
        if not enabled:
            time.sleep(0.05)

    def set_framesize(self, framesize: str) -> None:
        self.send_command(f"SET FRAMESIZE {framesize}")
        self._framesize = framesize
        time.sleep(0.05)

    @property
    def framesize(self) -> str:
        return self._framesize

    @property
    def pending_bytes(self) -> int:
        """Return the total number of unread bytes available from the stream.

        :return: Sum of the internal buffer length and the driver's input queue.
        """
        return self._serial_port.in_waiting + len(self._buffer)

    def _fill_buffer(self, size: int) -> None:
        """Ensure the internal buffer holds at least ``size`` bytes.

        :param size: Minimum number of bytes required in the buffer.
        :raises TimeoutError: If the serial port does not deliver the requested bytes.
        """
        while len(self._buffer) < size:
            needed = size - len(self._buffer)
            chunk = self._serial_port.read(max(self._serial_port.in_waiting, needed))
            if not chunk:
                raise TimeoutError(f"Timed out while reading {size} bytes from serial")
            self._buffer.extend(chunk)

    def _take(self, size: int) -> bytes:
        """Consume and return ``size`` bytes from the head of the internal buffer.

        :param size: Number of bytes to consume.
        :return: Exactly ``size`` bytes from the head of the buffer.
        """
        self._fill_buffer(size)
        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data

    def _sync_to_magic(self) -> None:
        """Advance the internal buffer past the next occurrence of the frame magic.

        :raises TimeoutError: If the frame magic is not seen within the serial timeout.
        """
        pattern = struct.pack("<I", MAGIC)
        while True:
            index = self._buffer.find(pattern)
            if index >= 0:
                del self._buffer[: index + len(pattern)]
                return
            if len(self._buffer) > 3:
                del self._buffer[:-3]
            chunk = self._serial_port.read(max(self._serial_port.in_waiting, 4096))
            if not chunk:
                raise TimeoutError("Timed out waiting for frame header")
            self._buffer.extend(chunk)

    def read_snapshot(self) -> tuple[np.ndarray, int, int, int]:
        if self._streaming_enabled:
            self.set_streaming(False)
        self._serial_port.reset_input_buffer()
        self._buffer.clear()
        for _ in range(3):
            self._last_status_message = None
            self.send_command("SNAP")
            try:
                return self.read()
            except TimeoutError:
                time.sleep(0.05)
                continue
        raise RuntimeError("The camera did not return a frame after 3 snapshot attempts")

    def read(self) -> tuple[np.ndarray, int, int, int]:
        while True:
            self._sync_to_magic()
            header_rest = self._take(HEADER_STRUCT.size - 4)
            packet = HEADER_STRUCT.unpack(struct.pack("<I", MAGIC) + header_rest)
            _, msg_type, width, height, pixel_format, payload_length, timestamp_ms = packet
            payload = self._take(payload_length)

            if msg_type == MSG_STATUS:
                now = time.time()
                self._last_status_message = payload.decode("utf-8", errors="replace")
                if now - self._last_status_at > 0.2:
                    print(f"[board] {self._last_status_message}")
                    self._last_status_at = now
                continue

            if msg_type != MSG_FRAME or pixel_format != 1:
                print(
                    f"Skipping unsupported packet type={msg_type} format={pixel_format}",
                    file=sys.stderr,
                )
                continue

            frame = decode_frame(payload)
            if frame is None:
                print("Failed to decode JPEG frame", file=sys.stderr)
                continue

            return frame, width, height, timestamp_ms


def fallback_framesize(current_framesize: str) -> str | None:
    try:
        index = FRAME_SIZE_FALLBACKS.index(current_framesize)
    except ValueError:
        return None
    if index + 1 >= len(FRAME_SIZE_FALLBACKS):
        return None
    return FRAME_SIZE_FALLBACKS[index + 1]


def load_detection_model() -> Any:
    from inference import get_model

    return get_model(model_id=MODEL_ID, api_key=os.environ["ROBOFLOW_API_KEY"])


def annotate(frame: np.ndarray, model: Any, confidence: float) -> np.ndarray:
    result = model.infer(frame, confidence=confidence)[0]
    for prediction in result.predictions:
        x1 = int(prediction.x - prediction.width / 2)
        y1 = int(prediction.y - prediction.height / 2)
        x2 = int(prediction.x + prediction.width / 2)
        y2 = int(prediction.y + prediction.height / 2)
        label = f"{prediction.class_name} {prediction.confidence:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            frame,
            label,
            (x1, max(0, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
        )
    return frame


def handle_common_keys(key: int, camera: SerialCamera, latest_frame: np.ndarray | None, save_dir: Path | None) -> bool:
    if key == ord("q"):
        return False
    if key == ord("s"):
        camera.send_command("SNAP")
    elif key == ord("1"):
        camera.send_command("SET FRAMESIZE QVGA")
    elif key == ord("2"):
        camera.send_command("SET FRAMESIZE VGA")
    elif key == ord("3"):
        camera.send_command("SET FRAMESIZE SVGA")
    elif key == ord("4"):
        camera.send_command("SET FRAMESIZE XGA")
    elif key == ord("c") and latest_frame is not None and save_dir is not None:
        target = save_dir / f"xiao_capture_{int(time.time())}.jpg"
        cv2.imwrite(str(target), latest_frame)
        print(f"Saved {target}")
    return True


def run_view(camera: SerialCamera, settings: PipelineSettings) -> None:
    frame_index = 0
    streaming = True
    latest_frame: np.ndarray | None = None

    camera.set_streaming(True)

    while True:
        frame, width, height, timestamp_ms = camera.read()
        while streaming and camera.pending_bytes >= HEADER_STRUCT.size:
            frame, width, height, timestamp_ms = camera.read()
        latest_frame = frame
        frame_index += 1
        overlay = frame.copy()
        cv2.putText(
            overlay,
            f"{width}x{height}  frame={frame_index}  board_ms={timestamp_ms}",
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )
        cv2.imshow(settings.window_name, overlay)

        key = cv2.waitKey(1) & 0xFF
        if key == ord(" "):
            streaming = not streaming
            camera.send_command("STREAM ON" if streaming else "STREAM OFF")
            continue
        if not handle_common_keys(key, camera, latest_frame, settings.save_dir):
            return


def run_detection(camera: SerialCamera, settings: PipelineSettings) -> None:
    """Annotate the streamed feed with Roboflow predictions.

    Runs inference on the newest available frame, discarding frames that
    accumulated in the serial buffer while the previous prediction was
    being computed.

    :param camera: Open serial camera.
    :param settings: Pipeline settings controlling display and inference.
    """
    model = load_detection_model()
    frame_index = 0
    latest_frame: np.ndarray | None = None

    camera.set_streaming(True)

    while True:
        frame, width, height, timestamp_ms = camera.read()
        while camera.pending_bytes >= HEADER_STRUCT.size:
            frame, width, height, timestamp_ms = camera.read()

        latest_frame = frame.copy()
        annotated = annotate(frame, model, settings.confidence)
        frame_index += 1
        cv2.putText(
            annotated,
            f"{width}x{height}  frame={frame_index}  board_ms={timestamp_ms}",
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )
        cv2.imshow(settings.window_name, annotated)

        key = cv2.waitKey(1) & 0xFF
        if not handle_common_keys(key, camera, latest_frame, settings.save_dir):
            return

def run_calibration(camera: SerialCamera, settings: PipelineSettings) -> None:
    """Collect ChArUco captures and solve for camera intrinsics.

    :param camera: Open serial camera.
    :param settings: Pipeline settings controlling captures and output paths.
    :raises RuntimeError: If too few captures or correspondences are collected.
    """
    dictionary = cv2.aruco.getPredefinedDictionary(CHARUCO_DICT)
    board = cv2.aruco.CharucoBoard(
        (SQUARES_X, SQUARES_Y), SQUARE_LENGTH_M, MARKER_LENGTH_M, dictionary
    )
    # Tune the ArUco detector for small / JPEG-compressed markers.
    aruco_params = cv2.aruco.DetectorParameters()
    aruco_params.adaptiveThreshWinSizeMin = 5
    aruco_params.adaptiveThreshWinSizeMax = 45
    aruco_params.adaptiveThreshWinSizeStep = 4
    aruco_params.minMarkerPerimeterRate = 0.01
    aruco_params.polygonalApproxAccuracyRate = 0.05
    aruco_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    aruco_params.cornerRefinementWinSize = 5
    if hasattr(aruco_params, "useAruco3Detection"):
        aruco_params.useAruco3Detection = True
    aruco_params.errorCorrectionRate = 0.8
    aruco_detector = cv2.aruco.ArucoDetector(dictionary, aruco_params)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    captures: list[tuple[np.ndarray, np.ndarray]] = []
    object_points: list[np.ndarray] = []
    image_points: list[np.ndarray] = []
    image_size: tuple[int, int] | None = None
    latest_frame: np.ndarray | None = None
    diag_dicts = {
        "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
        "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
        "DICT_5X5_250": cv2.aruco.DICT_5X5_250,
        "DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
        "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
        "DICT_4X4_250": cv2.aruco.DICT_4X4_250,
        "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
        "DICT_APRILTAG_36h11": cv2.aruco.DICT_APRILTAG_36h11,
    }
    last_diag_at = 0.0
    capture_armed = False
    auto_capture = False
    last_auto_capture_at = 0.0

    camera.send_command("SET QUALITY 8")
    # Streaming gives us continuous frames so the UI loop can keep polling
    # the keyboard while frames flow in via a background thread.
    camera.set_streaming(True)

    print("Calibration mode: show the ChArUco board, press space to arm a capture, q to finish.")
    print("Press 'a' to toggle auto-capture (one frame every ~1.5s when board is detected).")
    print("Press 'd' to run a dictionary-detection diagnostic on the current frame.")

    latest_lock = threading.Lock()
    latest_raw_frame: list[np.ndarray | None] = [None]
    reader_stop = threading.Event()
    reader_error: list[BaseException | None] = [None]

    def reader_loop() -> None:
        try:
            while not reader_stop.is_set():
                try:
                    f, _, _, _ = camera.read()
                except (TimeoutError, RuntimeError) as exc:
                    reader_error[0] = exc
                    time.sleep(0.05)
                    continue
                with latest_lock:
                    latest_raw_frame[0] = f
        except BaseException as exc:  # pragma: no cover - background failure surface
            reader_error[0] = exc

    reader_thread = threading.Thread(target=reader_loop, daemon=True)
    reader_thread.start()

    try:
        while True:
            with latest_lock:
                raw = latest_raw_frame[0]
                latest_raw_frame[0] = None
            if raw is None:
                # No new frame yet; still service the UI so keys remain responsive.
                key = cv2.waitKey(15) & 0xFF
                if key == 0xFF:
                    continue
                if key == ord("q"):
                    break
                if key == ord(" "):
                    capture_armed = True
                    print("Capture armed: will grab the next frame with a detected board.")
                    continue
                if key == ord("a"):
                    auto_capture = not auto_capture
                    print(f"Auto-capture {'ON' if auto_capture else 'OFF'}")
                continue
            # The OV2640 on the XIAO ESP32S3 Sense delivers a horizontally mirrored
            # image. ArUco markers are chirality-sensitive, so mirrored markers will
            # never decode. Un-mirror before detection (and capture the un-mirrored
            # frame for calibration so the intrinsics match what we will use later).
            frame = cv2.flip(raw, 1)
            latest_frame = frame.copy()
            image_size = frame.shape[1], frame.shape[0]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = clahe.apply(gray)
            marker_corners, marker_ids, rejected = aruco_detector.detectMarkers(gray)
            corners: np.ndarray | None = None
            ids: np.ndarray | None = None
            if marker_ids is not None and len(marker_ids) > 0:
                try:
                    _, corners, ids = cv2.aruco.interpolateCornersCharuco(
                        marker_corners, marker_ids, gray, board
                    )
                except cv2.error as exc:
                    print(f"interpolateCornersCharuco failed: {exc}")
                    corners, ids = None, None
            display = frame.copy()
            corner_count = 0 if ids is None else len(ids)
            marker_count = 0 if marker_ids is None else len(marker_ids)
            rejected_count = 0 if rejected is None else len(rejected)
            detected = corner_count >= 4
            if rejected is not None and len(rejected) > 0:
                cv2.aruco.drawDetectedMarkers(
                    display, rejected, borderColor=(0, 0, 255)
                )
            if marker_ids is not None:
                cv2.aruco.drawDetectedMarkers(display, marker_corners, marker_ids)
            if ids is not None:
                cv2.aruco.drawDetectedCornersCharuco(display, corners, ids)
            status = ""
            if capture_armed:
                status = "  [ARMED]"
            elif auto_capture:
                status = "  [AUTO]"
            cv2.putText(
                display,
                f"captures: {len(captures)} / {settings.min_captures}  corners: {corner_count}  markers: {marker_count}  rejected: {rejected_count}{status}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0) if detected else (0, 0, 255),
                2,
            )
            cv2.imshow(settings.window_name, display)

            # Auto-capture: take a frame whenever the board is detected and a
            # cooldown has passed, so you can simply move the board around.
            now = time.time()
            should_capture = False
            if capture_armed and detected:
                should_capture = True
                capture_armed = False
            elif auto_capture and detected and now - last_auto_capture_at > 1.5:
                should_capture = True
                last_auto_capture_at = now

            if should_capture:
                captures.append((corners, ids))
                print(f"Captured calibration frame {len(captures)} ({corner_count} corners)")
                if settings.save_dir is not None:
                    target = settings.save_dir / f"calib_capture_{int(now)}.jpg"
                    cv2.imwrite(str(target), frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord(" "):
                capture_armed = True
                print("Capture armed: will grab the next frame with a detected board.")
                continue
            if key == ord("a"):
                auto_capture = not auto_capture
                print(f"Auto-capture {'ON' if auto_capture else 'OFF'}")
                continue
            if key == ord("q"):
                break
            if key == ord("d"):
                now = time.time()
                if now - last_diag_at > 0.2:
                    last_diag_at = now
                    print("--- dictionary diagnostic on current frame ---")
                    for name, dict_id in diag_dicts.items():
                        test_dict = cv2.aruco.getPredefinedDictionary(dict_id)
                        test_detector = cv2.aruco.ArucoDetector(test_dict, aruco_params)
                        _, t_ids, _ = test_detector.detectMarkers(gray)
                        found = 0 if t_ids is None else len(t_ids)
                        if found:
                            ids_list = sorted(int(i) for i in t_ids.flatten())
                            print(f"  {name}: {found} markers, ids={ids_list}")
                        else:
                            print(f"  {name}: 0 markers")
                    if settings.save_dir is not None:
                        target = settings.save_dir / f"calib_diag_{int(time.time())}.jpg"
                        cv2.imwrite(str(target), frame)
                        print(f"Saved diagnostic frame to {target}")
                continue
            if not handle_common_keys(key, camera, latest_frame, settings.save_dir):
                return
    finally:
        reader_stop.set()
        reader_thread.join(timeout=2.0)
        camera.set_streaming(False)

    if len(captures) < settings.min_captures:
        raise RuntimeError(
            f"Collected {len(captures)} captures, need at least {settings.min_captures}"
        )

    for corners, ids in captures:
        obj_pts, img_pts = board.matchImagePoints(corners, ids)
        if obj_pts is not None and len(obj_pts) >= 4:
            object_points.append(obj_pts)
            image_points.append(img_pts)

    if len(object_points) < settings.min_captures or image_size is None:
        raise RuntimeError("Too few valid 3D-2D correspondences for calibration")

    settings.calibration_output.parent.mkdir(parents=True, exist_ok=True)
    error, intrinsics, distortion, _, _ = cv2.calibrateCamera(
        object_points, image_points, image_size, None, None
    )
    np.savez(
        settings.calibration_output,
        intrinsics=intrinsics,
        distortion=distortion,
        reprojection_error=error,
    )
    print(f"Reprojection error: {error:.4f} px -> saved to {settings.calibration_output}")

def run(settings: PipelineSettings) -> int:
    port = settings.port or autodetect_port()

    if settings.save_dir is not None:
        settings.save_dir.mkdir(parents=True, exist_ok=True)

    print(f"Opening {port} at {settings.baud} baud", flush=True)
    print(
        f"Goal={settings.goal.value}. Controls: q quit, space toggle stream, s snap, 1/2/3/4 set resolution, c capture JPG",
        flush=True,
    )

    with SerialCamera(port, settings.baud, settings.timeout, settings.framesize, settings.window_name) as camera:
        camera.send_command(f"SET QUALITY {settings.jpeg_quality}")
        if settings.goal == Goal.VIEW_FEED:
            run_view(camera, settings)
        elif settings.goal == Goal.DETECT_LEGO_BRICKS:
            run_detection(camera, settings)
        else:
            run_calibration(camera, settings)

    return 0


def main() -> int:
    settings = default_settings()
    return run(settings)


if __name__ == "__main__":
    raise SystemExit(main())