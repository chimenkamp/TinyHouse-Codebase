"""Roboflow LEGO brick detector wrapper.

Importing the ``inference`` package is *expensive*; we therefore lazily
load the model on first use and surface clear errors when the API key or
package are missing.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Keep OpenCV / Torch from fighting Qt's main thread with oversized native
# thread pools. This is especially important on macOS where mixed OpenMP
# runtimes can hard-crash the process instead of raising a Python exception.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import cv2
import numpy as np

try:
    cv2.setNumThreads(1)
except Exception:
    pass

from ..config import SETTINGS

_REPO_ROOT = Path(__file__).resolve().parents[2]
_YOLOV7_ROOT = _REPO_ROOT / "models" / "yolov7"
_LEGO_YOLOV7_WEIGHTS = _REPO_ROOT / "models" / "lego-yolov7" / "zero-shot-1000-single-class.pt"


@dataclass
class Detection:
    class_name: str
    confidence: float
    cx: float
    cy: float
    w: float
    h: float

    @property
    def bbox_xyxy(self) -> tuple[int, int, int, int]:
        x1 = int(self.cx - self.w / 2)
        y1 = int(self.cy - self.h / 2)
        x2 = int(self.cx + self.w / 2)
        y2 = int(self.cy + self.h / 2)
        return x1, y1, x2, y2


class LegoDetector:
    def __init__(self) -> None:
        self._model: Any | None = None
        self.last_error: str | None = None

    def is_loaded(self) -> bool:
        return self._model is not None

    def ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        api_key = os.environ.get("ROBOFLOW_API_KEY")
        if not api_key:
            self.last_error = "ROBOFLOW_API_KEY env var not set"
            return False
        try:
            from inference import get_model  # type: ignore
        except Exception as exc:
            self.last_error = f"import inference failed: {exc}"
            return False
        try:
            self._model = get_model(model_id=SETTINGS.detection.model_id, api_key=api_key)
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = f"get_model failed: {exc}"
            return False

    def infer(self, frame_bgr: np.ndarray, confidence: float | None = None) -> list[Detection]:
        if not self.ensure_loaded():
            return []
        c = SETTINGS.detection.confidence if confidence is None else confidence
        try:
            result = self._model.infer(frame_bgr, confidence=c)[0]  # type: ignore[union-attr]
        except Exception as exc:
            self.last_error = f"infer failed: {exc}"
            return []
        out: list[Detection] = []
        for p in result.predictions:
            out.append(Detection(
                class_name=str(p.class_name),
                confidence=float(p.confidence),
                cx=float(p.x), cy=float(p.y),
                w=float(p.width), h=float(p.height),
            ))
        return out


class LocalColorLegoDetector:
    """Offline LEGO detector for the top-down table setup.

    Finds colored brick-like blobs with OpenCV. This deliberately avoids any
    cloud model/API so grabbing can continue when Roboflow is unavailable.
    """

    def __init__(self) -> None:
        self.last_error: str | None = None

    def infer(self, frame_bgr: np.ndarray, confidence: float | None = None) -> list[Detection]:
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]
        mask = np.zeros(sat.shape, dtype=np.uint8)
        mask[(sat > 45) & (val > 45)] = 255

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_area = float(frame_bgr.shape[0] * frame_bgr.shape[1])
        detections: list[Detection] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < max(250.0, frame_area * 0.0004):
                continue
            rect = cv2.minAreaRect(contour)
            (cx, cy), (w, h), _angle = rect
            if w <= 0 or h <= 0:
                continue
            ratio = max(w, h) / max(1.0, min(w, h))
            if ratio > 6.0:
                continue
            x, y, bw, bh = cv2.boundingRect(contour)
            confidence_score = min(0.99, 0.35 + area / max(1.0, bw * bh) * 0.6)
            detections.append(
                Detection(
                    class_name="lego-local",
                    confidence=confidence_score,
                    cx=float(x + bw / 2.0),
                    cy=float(y + bh / 2.0),
                    w=float(bw),
                    h=float(bh),
                )
            )

        detections.sort(key=lambda d: d.w * d.h, reverse=True)
        self.last_error = None if detections else "local detector: no colored bricks found"
        return detections


class LocalYoloV7LegoDetector:
    """Local pretrained YOLOv7 LEGO detector, no API key required."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._torch: Any | None = None
        self._letterbox: Any | None = None
        self._nms: Any | None = None
        self._scale_coords: Any | None = None
        self.last_error: str | None = None

    def ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        if not _YOLOV7_ROOT.exists() or not _LEGO_YOLOV7_WEIGHTS.exists():
            self.last_error = "local YOLOv7 model files missing under models/"
            return False
        try:
            os.environ.setdefault("MPLCONFIGDIR", str(_REPO_ROOT / ".matplotlib-cache"))
            if str(_YOLOV7_ROOT) not in sys.path:
                sys.path.insert(0, str(_YOLOV7_ROOT))
            import torch
            from models.experimental import attempt_load
            from utils.datasets import letterbox
            from utils.general import non_max_suppression, scale_coords

            torch.set_num_threads(1)
            try:
                torch.set_num_interop_threads(1)
            except RuntimeError:
                pass
            self._torch = torch
            self._letterbox = letterbox
            self._nms = non_max_suppression
            self._scale_coords = scale_coords
            self._model = attempt_load(str(_LEGO_YOLOV7_WEIGHTS), map_location="cpu")
            self._model.eval()
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = f"local YOLOv7 load failed: {exc}"
            return False

    def infer(self, frame_bgr: np.ndarray, confidence: float | None = None) -> list[Detection]:
        if not self.ensure_loaded():
            return []
        conf = SETTINGS.detection.confidence if confidence is None else float(confidence)
        try:
            torch = self._torch
            img = self._letterbox(frame_bgr, new_shape=640, stride=32)[0]
            img = img[:, :, ::-1].transpose(2, 0, 1)
            img = np.ascontiguousarray(img)
            tensor = torch.from_numpy(img).float() / 255.0
            if tensor.ndimension() == 3:
                tensor = tensor.unsqueeze(0)
            with torch.inference_mode():
                pred = self._model(tensor)[0]
            pred = self._nms(pred, conf_thres=conf, iou_thres=0.45)[0]
            if pred is None or len(pred) == 0:
                self.last_error = None
                return []
            pred[:, :4] = self._scale_coords(tensor.shape[2:], pred[:, :4], frame_bgr.shape).round()
            detections: list[Detection] = []
            names = getattr(self._model, "names", ["lego"])
            for *xyxy, score, cls in pred.tolist():
                x1, y1, x2, y2 = xyxy
                w = max(1.0, x2 - x1)
                h = max(1.0, y2 - y1)
                cls_idx = int(cls)
                class_name = names[cls_idx] if cls_idx < len(names) else "lego"
                detections.append(
                    Detection(
                        class_name=str(class_name),
                        confidence=float(score),
                        cx=float(x1 + w / 2.0),
                        cy=float(y1 + h / 2.0),
                        w=float(w),
                        h=float(h),
                    )
                )
            self.last_error = None
            return detections
        except Exception as exc:
            self.last_error = f"local YOLOv7 infer failed: {exc}"
            return []


def annotate(frame_bgr: np.ndarray, detections: list[Detection]) -> np.ndarray:
    for d in detections:
        x1, y1, x2, y2 = d.bbox_xyxy
        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            frame_bgr, f"{d.class_name} {d.confidence:.2f}",
            (x1, max(0, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
        )
    return frame_bgr
