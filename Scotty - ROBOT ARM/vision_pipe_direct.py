"""Live Lego brick detection using the Hex: Lego Roboflow model."""

import os
from typing import Self

import cv2
import numpy as np
from inference import get_model
from pathlib import Path

CHARUCO_DICT = cv2.aruco.DICT_5X5_100
SQUARES_X = 5
SQUARES_Y = 7
SQUARE_LENGTH_M = 0.030
MARKER_LENGTH_M = 0.022

MODEL_ID = "hex-lego/3"


class Camera:
    """OpenCV video capture paired with intrinsics for pose estimation."""

    def __init__(
        self,
        index: int,
        intrinsics: np.ndarray | None = None,
        distortion: np.ndarray | None = None,
    ) -> None:
        """Open a camera at the given OpenCV index.

        Args:
            index: OpenCV index of the camera to open.
            intrinsics: Optional 3x3 camera matrix K in float64.
            distortion: Optional distortion coefficient vector (length 4, 5, 8, 12, or 14).

        Raises:
            RuntimeError: If the camera cannot be opened.
        """
        self._capture = cv2.VideoCapture(index)
        if not self._capture.isOpened():
            raise RuntimeError(f"Cannot open camera at index {index}")
        self._intrinsics = intrinsics
        self._distortion = distortion

    @classmethod
    def first_available(
        cls,
        max_index: int = 10,
        intrinsics: np.ndarray | None = None,
        distortion: np.ndarray | None = None,
    ) -> Self:
        """Open the first camera whose index can be opened by OpenCV.

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

    def __enter__(self) -> Self:
        """Enter the context manager.

        Returns:
            This camera instance.
        """
        return self

    def __exit__(self, *_: object) -> None:
        """Release the underlying VideoCapture on exit."""
        self._capture.release()

    def read(self) -> np.ndarray:
        """Read the next frame from the camera.

        Returns:
            A BGR image as a ``(H, W, 3)`` uint8 array.

        Raises:
            RuntimeError: If the frame cannot be read.
        """
        ok, frame = self._capture.read()
        if not ok:
            raise RuntimeError("Failed to read frame from camera")
        return frame

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
        """
        width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return width, height


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
    with Camera.first_available() as camera:
        detect_bricks(camera)

# if __name__ == "__main__":
#     calibrate_intrinsics(Path("intrinsics.npz"))