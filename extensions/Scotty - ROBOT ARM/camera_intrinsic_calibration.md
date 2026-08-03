 **camera intrinsic calibration**. Everything that comes after — pose estimation, the transform chain, grasping — requires the camera matrix `K` and distortion coefficients. It's a one-time setup; save the result to disk and load it into `Camera`.

### Procedure

1. Print a ChArUco board. The defaults below (5×7 squares of 30 mm, 22 mm markers, `DICT_5X5_100`) fit on A4 — generate with [calib.io](https://calib.io/pages/camera-calibrator) or OpenCV's `board.generateImage()`. **Measure the printed squares with a ruler and update the constants if they differ.**
2. Add the function below to your file, temporarily change `__main__` to call it, and run.
3. Move the board through ~25 varied views: different distances, strong tilts, corners of the frame. Press `SPACE` to capture, `Q` when done.
4. A reprojection error under 0.5 px is excellent; under 1.0 px is acceptable. If it's worse, recapture — most often the board wasn't tilted enough.
5. Change `__main__` back; load the file into `Camera` for all future runs.

### Code

Add this function to your file:

```python
from pathlib import Path

CHARUCO_DICT = cv2.aruco.DICT_5X5_100
SQUARES_X = 5
SQUARES_Y = 7
SQUARE_LENGTH_M = 0.030
MARKER_LENGTH_M = 0.022


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
```

Temporarily set the entry point to:

```python
if __name__ == "__main__":
    calibrate_intrinsics(Path("intrinsics.npz"))
```

Then restore it to use the saved file:

```python
if __name__ == "__main__":
    data = np.load("intrinsics.npz")
    with Camera.first_available(
        intrinsics=data["intrinsics"], distortion=data["distortion"]
    ) as camera:
        detect_bricks(camera)
```

### What this unlocks

With `K` and distortion in hand, the next step is **hand-eye calibration** — solving for the fixed transform `T_cam^ee` between the camera and the PAROL6 flange using `cv2.calibrateHandEye`. After that, you can combine a brick detection with `cv2.solvePnP` (using the known Lego dimensions we discussed) to get the brick's pose in the robot base frame, which is exactly what the PAROL6's IK needs.