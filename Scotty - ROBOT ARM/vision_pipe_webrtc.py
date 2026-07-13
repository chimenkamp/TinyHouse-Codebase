"""Live Lego brick detection using the Hex: Lego Roboflow model."""

import asyncio
import os
from pathlib import Path
import threading
from collections.abc import Callable
from typing import Self

import aiohttp
import cv2
import numpy as np
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from inference import get_model

MODEL_ID = "hex-lego/3"

CHARUCO_DICT = cv2.aruco.DICT_5X5_100
SQUARES_X = 5
SQUARES_Y = 7
SQUARE_LENGTH_M = 0.030
MARKER_LENGTH_M = 0.022

class Camera:
    """Video source (local webcam or WHEP stream) paired with intrinsics."""

    def __init__(
        self,
        index: int,
        intrinsics: np.ndarray | None = None,
        distortion: np.ndarray | None = None,
    ) -> None:
        """Open a local camera at the given OpenCV index.

        Args:
            index: OpenCV index of the camera to open.
            intrinsics: Optional 3x3 camera matrix K in float64.
            distortion: Optional distortion coefficient vector (length 4, 5, 8, 12, or 14).

        Raises:
            RuntimeError: If the camera cannot be opened.
        """
        self._capture: cv2.VideoCapture | None = cv2.VideoCapture(index)
        if not self._capture.isOpened():
            raise RuntimeError(f"Cannot open camera at index {index}")
        self._intrinsics = intrinsics
        self._distortion = distortion
        self._latest_frame: np.ndarray | None = None
        self._frame_lock = threading.Lock()
        self._webrtc_stop = threading.Event()
        self._webrtc_thread: threading.Thread | None = None

    @classmethod
    def first_available(
        cls,
        max_index: int = 10,
        intrinsics: np.ndarray | None = None,
        distortion: np.ndarray | None = None,
    ) -> Self:
        """Open the first local camera whose index can be opened by OpenCV.

        Args:
            max_index: Exclusive upper bound on indices to probe.
            intrinsics: Optional 3x3 camera matrix K in float64.
            distortion: Optional distortion coefficient vector.

        Returns:
            An opened Camera instance.

        Raises:
            RuntimeError: If no camera could be opened below ``max_index``.
        """
        for index in range(max_index):
            capture = cv2.VideoCapture(index)
            if capture.isOpened():
                capture.release()
                return cls(index, intrinsics=intrinsics, distortion=distortion)
        raise RuntimeError(f"No camera found below index {max_index}")

    @classmethod
    def from_whep(
        cls,
        url: str,
        intrinsics: np.ndarray | None = None,
        distortion: np.ndarray | None = None,
        timeout: float = 10.0,
    ) -> Self:
        """Open a WebRTC video stream via a WHEP endpoint.

        Args:
            url: HTTP(S) URL of the WHEP endpoint (e.g. ``http://host:8889/cam/whep``).
            intrinsics: Optional 3x3 camera matrix K in float64.
            distortion: Optional distortion coefficient vector.
            timeout: Seconds to wait for the first decoded frame before failing.

        Returns:
            A Camera instance streaming frames from the WHEP endpoint.

        Raises:
            RuntimeError: If no frame is received within ``timeout`` seconds.
        """
        camera = cls.__new__(cls)
        camera._capture = None
        camera._intrinsics = intrinsics
        camera._distortion = distortion
        camera._latest_frame = None
        camera._frame_lock = threading.Lock()
        camera._webrtc_stop = threading.Event()
        first_frame = threading.Event()

        def on_frame(frame: np.ndarray) -> None:
            """Store the latest frame and signal arrival of the first one.

            Args:
                frame: Decoded BGR frame as a ``(H, W, 3)`` uint8 array.

            Returns:
                None.
            """
            with camera._frame_lock:
                camera._latest_frame = frame
            first_frame.set()

        camera._webrtc_thread = threading.Thread(
            target=lambda: asyncio.run(_whep_client(url, on_frame, camera._webrtc_stop)),
            daemon=True,
        )
        camera._webrtc_thread.start()
        if not first_frame.wait(timeout):
            camera._webrtc_stop.set()
            raise RuntimeError(f"No frame received from {url} within {timeout}s")
        return camera

    def __enter__(self) -> Self:
        """Enter the context manager.

        Returns:
            This camera instance.
        """
        return self

    def __exit__(self, *_: object) -> None:
        """Release the underlying capture or WebRTC connection."""
        if self._capture is not None:
            self._capture.release()
        if self._webrtc_thread is not None:
            self._webrtc_stop.set()
            self._webrtc_thread.join(timeout=5.0)

    def read(self) -> np.ndarray:
        """Read the next frame from the camera.

        Returns:
            A BGR image as a ``(H, W, 3)`` uint8 array.

        Raises:
            RuntimeError: If no frame is available.
        """
        if self._capture is not None:
            ok, frame = self._capture.read()
            if not ok:
                raise RuntimeError("Failed to read frame from camera")
            return frame
        with self._frame_lock:
            if self._latest_frame is None:
                raise RuntimeError("No WebRTC frame available yet")
            return self._latest_frame.copy()

    @property
    def intrinsics(self) -> np.ndarray:
        """Camera matrix K used for pose estimation.

        Returns:
            The 3x3 intrinsic matrix provided at construction.

        Raises:
            RuntimeError: If intrinsics were not supplied.
        """
        if self._intrinsics is None:
            raise RuntimeError("Camera intrinsics not set; run calibration first")
        return self._intrinsics

    @property
    def distortion(self) -> np.ndarray:
        """Distortion coefficients used for pose estimation.

        Returns:
            The distortion coefficient vector provided at construction.

        Raises:
            RuntimeError: If distortion coefficients were not supplied.
        """
        if self._distortion is None:
            raise RuntimeError("Distortion coefficients not set; run calibration first")
        return self._distortion

    @property
    def resolution(self) -> tuple[int, int]:
        """Current capture resolution.

        Returns:
            The ``(width, height)`` of captured frames in pixels.

        Raises:
            RuntimeError: If the resolution cannot yet be determined.
        """
        if self._capture is not None:
            width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return width, height
        with self._frame_lock:
            if self._latest_frame is None:
                raise RuntimeError("No WebRTC frame available yet")
            height, width = self._latest_frame.shape[:2]
            return width, height


async def _whep_client(
    url: str,
    on_frame: Callable[[np.ndarray], None],
    stop_event: threading.Event,
) -> None:
    """Consume a WebRTC video stream via WHEP and forward frames to a callback.

    Args:
        url: WHEP endpoint URL.
        on_frame: Callback invoked with each decoded BGR frame.
        stop_event: Threading event signalling the client should close.

    Returns:
        None.
    """
    pc = RTCPeerConnection()
    pc.addTransceiver("video", direction="recvonly")
    drain_tasks: list[asyncio.Task[None]] = []

    @pc.on("track")
    def _(track: MediaStreamTrack) -> None:
        """Spawn a coroutine to drain frames from an incoming track.

        Args:
            track: The incoming aiortc MediaStreamTrack.

        Returns:
            None.
        """
        drain_tasks.append(asyncio.ensure_future(_drain_track(track, on_frame, stop_event)))

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=pc.localDescription.sdp,
            headers={"Content-Type": "application/sdp"},
        ) as response:
            response.raise_for_status()
            answer_sdp = await response.text()
    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer_sdp, type="answer"))

    while not stop_event.is_set():
        await asyncio.sleep(0.1)
    for task in drain_tasks:
        task.cancel()
    await pc.close()


async def _drain_track(
    track: MediaStreamTrack,
    on_frame: Callable[[np.ndarray], None],
    stop_event: threading.Event,
) -> None:
    """Decode frames from ``track`` and forward them to ``on_frame``.

    Args:
        track: aiortc MediaStreamTrack delivering video frames.
        on_frame: Callback invoked with each decoded BGR frame.
        stop_event: Threading event signalling decoding should stop.

    Returns:
        None.
    """
    while not stop_event.is_set():
        try:
            frame = await track.recv()
        except Exception:
            break
        on_frame(frame.to_ndarray(format="bgr24"))


def detect_bricks(camera: Camera, confidence: float = 0.5) -> None:
    """Run Lego brick detection on a live camera feed until the user quits.

    Loads the Hex: Lego model, reads frames from ``camera``, draws bounding
    boxes with class labels and confidences, and displays the annotated stream.
    Press 'q' to exit.

    Args:
        camera: An opened Camera instance.
        confidence: Minimum detection confidence in the range [0, 1].

    Returns:
        None.

    Raises:
        KeyError: If the ROBOFLOW_API_KEY environment variable is not set.
    """
    model = get_model(model_id=MODEL_ID, api_key=os.environ["ROBOFLOW_API_KEY"])
    try:
        while True:
            frame = camera.read()
            annotated = annotate(frame, model, confidence)
            cv2.imshow("Hex: Lego", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cv2.destroyAllWindows()


def annotate(frame: np.ndarray, model: object, confidence: float) -> np.ndarray:
    """Draw bounding boxes for Lego bricks detected in a single frame.

    Args:
        frame: BGR image from OpenCV as a ``(H, W, 3)`` array.
        model: A Roboflow inference model returned by ``get_model``.
        confidence: Minimum detection confidence in the range [0, 1].

    Returns:
        A copy of ``frame`` with bounding boxes and labels drawn in place.
    """
    result = model.infer(frame, confidence=confidence)[0]
    for prediction in result.predictions:
        x1 = int(prediction.x - prediction.width / 2)
        y1 = int(prediction.y - prediction.height / 2)
        x2 = int(prediction.x + prediction.width / 2)
        y2 = int(prediction.y + prediction.height / 2)
        label = f"{prediction.class_name} {prediction.confidence:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, label, (x1, max(0, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    return frame



def calibrate_intrinsics(output_path: Path, min_captures: int = 20) -> None:
    """Interactively collect ChArUco views and save camera intrinsics to disk.

    Opens the first available camera, shows a live preview with detected
    ChArUco corners overlaid, and lets the user capture views by pressing
    SPACE. Pressing Q runs the calibration and writes ``intrinsics``,
    ``distortion`` and ``reprojection_error`` to ``output_path`` as an .npz.

    Args:
        output_path: Destination .npz file for the calibration results.
        min_captures: Minimum number of accepted views before calibration runs.

    Returns:
        None.

    Raises:
        RuntimeError: If fewer than ``min_captures`` views were collected or
            no valid 3D-2D correspondences could be extracted.
    """
    dictionary = cv2.aruco.getPredefinedDictionary(CHARUCO_DICT)
    board = cv2.aruco.CharucoBoard(
        (SQUARES_X, SQUARES_Y), SQUARE_LENGTH_M, MARKER_LENGTH_M, dictionary
    )
    detector = cv2.aruco.CharucoDetector(board)
    captures: list[tuple[np.ndarray, np.ndarray]] = []
    image_size: tuple[int, int] | None = None

    with Camera.first_available() as camera:
        while True:
            frame = camera.read()
            image_size = frame.shape[1], frame.shape[0]
            corners, ids, _, _ = detector.detectBoard(frame)
            display = frame.copy()
            detected = ids is not None and len(ids) >= 4
            if detected:
                cv2.aruco.drawDetectedCornersCharuco(display, corners, ids)
            cv2.putText(display, f"captures: {len(captures)}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Calibration", display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" ") and detected:
                captures.append((corners, ids))
            elif key == ord("q"):
                break
    cv2.destroyAllWindows()

    if len(captures) < min_captures:
        raise RuntimeError(
            f"Collected {len(captures)} captures, need at least {min_captures}"
        )

    object_points: list[np.ndarray] = []
    image_points: list[np.ndarray] = []
    for corners, ids in captures:
        obj_pts, img_pts = board.matchImagePoints(corners, ids)
        if obj_pts is not None and len(obj_pts) >= 4:
            object_points.append(obj_pts)
            image_points.append(img_pts)

    if len(object_points) < min_captures:
        raise RuntimeError("Too few valid 3D-2D correspondences for calibration")

    error, intrinsics, distortion, _, _ = cv2.calibrateCamera(
        object_points, image_points, image_size, None, None
    )
    np.savez(output_path, intrinsics=intrinsics, distortion=distortion,
             reprojection_error=error)
    print(f"Reprojection error: {error:.4f} px -> saved to {output_path}")




if __name__ == "__main__":
    calibrate_intrinsics(Path("intrinsics.npz"))

# if __name__ == "__main__":
#     with Camera.from_whep("http://localhost:8889/cam/whep") as camera:
#         detect_bricks(camera)