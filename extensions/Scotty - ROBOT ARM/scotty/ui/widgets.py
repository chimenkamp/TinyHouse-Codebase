"""Reusable UI widgets: video display, joint sliders, status panel."""

from __future__ import annotations

from pathlib import Path
from typing import Callable
import xml.etree.ElementTree as ET

import numpy as np
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..config import SETTINGS
from ..robot import JOINT_LIMITS_DEG


_URDF_PATH = Path(__file__).resolve().parents[2] / "parol6" / "urdf_model" / "urdf" / "PAROL6.urdf"
_JOINT_NAMES = tuple(f"L{i}" for i in range(1, 7))
_FALLBACK_URDF_CHAIN = (
    ("L1", (0.0, 0.0, 0.1105), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ("L2", (0.0234207210610375, 0.0, 0.0), (-1.5707963267949, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ("L3", (0.18, 0.0, 0.0), (3.14159265358979, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ("L4", (-0.0435, 0.17635, 0.0), (1.5707963267949, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ("L5", (0.0, 0.0, 0.0), (-1.5707963267949, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ("L6", (0.0, 0.037, 0.0), (1.5707963267949, 0.0, 0.0), (0.0, 0.0, 1.0)),
)


def _load_urdf_joint_chain() -> tuple[tuple[str, tuple[float, ...], tuple[float, ...], tuple[float, ...]], ...]:
    try:
        root = ET.parse(_URDF_PATH).getroot()
    except Exception:
        return _FALLBACK_URDF_CHAIN
    loaded = []
    for name in _JOINT_NAMES:
        joint = root.find(f"./joint[@name='{name}']")
        if joint is None:
            return _FALLBACK_URDF_CHAIN
        origin = joint.find("origin")
        axis = joint.find("axis")
        if origin is None or axis is None:
            return _FALLBACK_URDF_CHAIN
        xyz = tuple(float(v) for v in origin.attrib.get("xyz", "0 0 0").split())
        rpy = tuple(float(v) for v in origin.attrib.get("rpy", "0 0 0").split())
        axis_xyz = tuple(float(v) for v in axis.attrib.get("xyz", "0 0 1").split())
        loaded.append((name, xyz, rpy, axis_xyz))
    return tuple(loaded)


_URDF_CHAIN = _load_urdf_joint_chain()


def _rpy_matrix(rpy: tuple[float, ...]) -> np.ndarray:
    rx, ry, rz = rpy
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    r_x = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]])
    r_y = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
    r_z = np.array([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]])
    return r_z @ r_y @ r_x


def _origin_transform(xyz: tuple[float, ...], rpy: tuple[float, ...]) -> np.ndarray:
    t = np.eye(4, dtype=float)
    t[:3, :3] = _rpy_matrix(rpy)
    t[:3, 3] = xyz
    return t


def _axis_rotation(axis: tuple[float, ...], angle_rad: float) -> np.ndarray:
    a = np.asarray(axis, dtype=float)
    norm = float(np.linalg.norm(a))
    if norm == 0.0:
        return np.eye(4, dtype=float)
    x, y, z = a / norm
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    omc = 1.0 - c
    r = np.array(
        [
            [c + x * x * omc, x * y * omc - z * s, x * z * omc + y * s],
            [y * x * omc + z * s, c + y * y * omc, y * z * omc - x * s],
            [z * x * omc - y * s, z * y * omc + x * s, c + z * z * omc],
        ],
        dtype=float,
    )
    t = np.eye(4, dtype=float)
    t[:3, :3] = r
    return t


# ---------------------------------------------------------------------------
# Video display: BGR ndarray → QPixmap; emits pixel-coordinate clicks
# ---------------------------------------------------------------------------
class VideoLabel(QLabel):
    pixel_clicked = Signal(float, float)  # original-image (u, v)

    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(480, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet("background-color: #202225; color: #aaa;")
        self.setText("(no frame)")
        self._last_size: tuple[int, int] | None = None

    def set_frame_bgr(self, frame_bgr: np.ndarray) -> None:
        h, w = frame_bgr.shape[:2]
        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(img)
        max_w = SETTINGS.ui.preview_max_width
        if pix.width() > max_w:
            pix = pix.scaledToWidth(max_w, Qt.TransformationMode.SmoothTransformation)
        self._last_size = (w, h)
        self.setPixmap(pix)
        self.setText("")

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # noqa: N802 (Qt naming)
        if self._last_size is None or self.pixmap() is None:
            return
        pix = self.pixmap()
        # Pixmap is centered inside the label.
        lw, lh = self.width(), self.height()
        pw, ph = pix.width(), pix.height()
        x_off = (lw - pw) / 2.0
        y_off = (lh - ph) / 2.0
        x = ev.position().x() - x_off
        y = ev.position().y() - y_off
        if x < 0 or y < 0 or x >= pw or y >= ph:
            return
        ow, oh = self._last_size
        u = x * ow / pw
        v = y * oh / ph
        self.pixel_clicked.emit(float(u), float(v))


# ---------------------------------------------------------------------------
# Joint slider row — replicates the "commit on release" semantics.
# ---------------------------------------------------------------------------
class JointSliderRow(QWidget):
    SCALE = 10  # 0.1° resolution
    committed = Signal(int, float)
    preview_changed = Signal(int, float)

    def __init__(
        self,
        idx: int,
        lo: float,
        hi: float,
        reverse_slider: bool = False,
        relative_slider: bool = False,
    ) -> None:
        super().__init__()
        self.idx = idx
        self.lo, self.hi = lo, hi
        self.reverse_slider = reverse_slider
        self.relative_slider = relative_slider
        self.slider_lo = -SETTINGS.ui.joint_slider_delta_deg if relative_slider else lo
        self.slider_hi = SETTINGS.ui.joint_slider_delta_deg if relative_slider else hi
        self._actual_value = 0.0

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(self.slider_lo * self.SCALE), int(self.slider_hi * self.SCALE))
        self.slider.setSingleStep(1)
        self.slider.setPageStep(int(self.SCALE * 2))
        self.slider.setMinimumWidth(210)

        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(2)
        self.spin.setRange(self.slider_lo, self.slider_hi)
        self.spin.setSingleStep(0.25 if relative_slider else 0.5)
        self.spin.setMinimumWidth(88)

        if relative_slider:
            self.range_label = QLabel(f"delta [{self.slider_lo:+.1f}, {self.slider_hi:+.1f}]")
        else:
            self.range_label = QLabel(f"[{lo:+.2f}°, {hi:+.2f}°]")
        self.range_label.setStyleSheet("color: #888;")

        self.title = QLabel(f"J{idx + 1}")
        self.title.setMinimumWidth(28)
        self.actual_label = QLabel("+000.0°")
        self.actual_label.setMinimumWidth(70)
        self.actual_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.actual_label.setStyleSheet("font-family: ui-monospace, monospace; color: #bbb;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.title)
        layout.addWidget(self.actual_label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)
        layout.addWidget(self.range_label)

        self.slider.valueChanged.connect(self._slider_to_spin)
        self.slider.valueChanged.connect(lambda _raw: self.preview_changed.emit(self.idx, self.value()))
        self.slider.sliderReleased.connect(self._commit_from_slider)
        self.spin.editingFinished.connect(self._commit_from_spin)

    def set_value_no_emit(self, v: float) -> None:
        self._actual_value = float(v)
        self.actual_label.setText(f"{self._actual_value:+06.1f}°")
        if self.relative_slider:
            self.reset_delta_no_emit()
            return
        self.slider.blockSignals(True)
        self.spin.blockSignals(True)
        v = max(self.lo, min(self.hi, v))
        self.slider.setValue(self._value_to_raw(v))
        self.spin.setValue(v)
        self.slider.blockSignals(False)
        self.spin.blockSignals(False)

    def reset_delta_no_emit(self) -> None:
        self.slider.blockSignals(True)
        self.spin.blockSignals(True)
        self.slider.setValue(0)
        self.spin.setValue(0.0)
        self.slider.blockSignals(False)
        self.spin.blockSignals(False)

    def value(self) -> float:
        return float(self.spin.value())

    def _raw_to_value(self, raw: int) -> float:
        value = raw / self.SCALE
        if self.reverse_slider and not self.relative_slider:
            value = self.lo + self.hi - value
        return max(self.slider_lo, min(self.slider_hi, value))

    def _value_to_raw(self, value: float) -> int:
        v = max(self.slider_lo, min(self.slider_hi, value))
        if self.reverse_slider and not self.relative_slider:
            v = self.lo + self.hi - v
        return int(round(v * self.SCALE))

    def _slider_to_spin(self, raw: int) -> None:
        self.spin.blockSignals(True)
        self.spin.setValue(self._raw_to_value(raw))
        self.spin.blockSignals(False)

    def _commit_from_slider(self) -> None:
        self.committed.emit(self.idx, self.value())
        if self.relative_slider:
            self.reset_delta_no_emit()

    def _commit_from_spin(self) -> None:
        v = self.spin.value()
        self.slider.blockSignals(True)
        self.slider.setValue(self._value_to_raw(v))
        self.slider.blockSignals(False)
        self.committed.emit(self.idx, v)
        if self.relative_slider:
            self.reset_delta_no_emit()


class JointSliderPanel(QGroupBox):
    """6 relative joint jog sliders + follow checkbox."""
    joint_committed = Signal(int, float)
    preview_changed = Signal(list)
    follow_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__("Joint jog")
        self.rows: list[JointSliderRow] = []
        self._latest_angles = [(lo + hi) / 2.0 for lo, hi in JOINT_LIMITS_DEG[:6]]
        layout = QVBoxLayout(self)
        for i, (lo, hi) in enumerate(JOINT_LIMITS_DEG[:6]):
            row = JointSliderRow(i, lo, hi, relative_slider=True)
            row.committed.connect(self.joint_committed)
            row.preview_changed.connect(self._on_row_preview)
            self.rows.append(row)
            layout.addWidget(row)
        self.follow_cb = QCheckBox("Follow robot")
        self.follow_cb.setChecked(True)
        self.follow_cb.toggled.connect(self.follow_changed)
        layout.addWidget(self.follow_cb)

    def follow_robot(self) -> bool:
        return self.follow_cb.isChecked()

    def set_angles_no_emit(self, angles_deg) -> None:
        for i, a in enumerate(angles_deg[: len(self.rows)]):
            self._latest_angles[i] = float(a)
            self.rows[i].set_value_no_emit(float(a))

    def apply_delta_no_emit(self, idx: int, delta_deg: float) -> None:
        if 0 <= idx < len(self._latest_angles):
            self._latest_angles[idx] += float(delta_deg)
            self.rows[idx].set_value_no_emit(self._latest_angles[idx])

    def values(self) -> list[float]:
        values = [r.value() for r in self.rows]
        for i, row in enumerate(self.rows):
            if row.relative_slider:
                values[i] = self._latest_angles[i]
        return values

    def is_relative(self, idx: int) -> bool:
        return 0 <= idx < len(self.rows) and self.rows[idx].relative_slider

    def preview_angles(self) -> list[float]:
        values = list(self._latest_angles)
        for i, row in enumerate(self.rows):
            if row.relative_slider:
                values[i] = self._latest_angles[i] + row.value()
            else:
                values[i] = row.value()
        return values

    def _on_row_preview(self, _idx: int, _value: float) -> None:
        self.preview_changed.emit(self.preview_angles())


# ---------------------------------------------------------------------------
# Lightweight digital twin: FK skeleton projected into a rotatable 3D view.
# ---------------------------------------------------------------------------
class DigitalTwinView(QWidget):
    joint_delta_preview = Signal(int, float)
    joint_delta_requested = Signal(int, float)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(340, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #16181c; border: 1px solid #333;")
        self.setMouseTracking(True)
        self._actual_angles = np.asarray(
            [(lo + hi) / 2.0 for lo, hi in JOINT_LIMITS_DEG[:6]], dtype=float
        )
        self._target_angles: np.ndarray | None = None
        self._yaw = np.radians(-38.0)
        self._pitch = np.radians(24.0)
        self._last_mouse: QPointF | None = None
        self._drag_joint: int | None = None
        self._drag_start_pos: QPointF | None = None
        self._drag_start_actual: np.ndarray | None = None
        self._drag_start_target: np.ndarray | None = None
        self._last_projected: list[QPointF] = []

    def set_angles(self, angles) -> None:
        self.set_actual_angles(angles)
        self.set_target_angles(None)

    def set_actual_angles(self, angles) -> None:
        arr = np.asarray(angles, dtype=float)
        if arr.shape == (6,):
            self._actual_angles = arr
            if self._target_angles is not None and np.max(np.abs(self._target_angles - arr)) < 0.8:
                self._target_angles = None
            self.update()

    def set_target_angles(self, angles) -> None:
        if angles is None:
            self._target_angles = None
            self.update()
            return
        arr = np.asarray(angles, dtype=float)
        if arr.shape == (6,):
            self._target_angles = self._clip_angles(arr)
            self.update()

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # noqa: N802
        pos = ev.position()
        picked = self._pick_joint(pos)
        if picked is None:
            self._last_mouse = pos
            return
        self._drag_joint = picked
        self._drag_start_pos = pos
        self._drag_start_actual = self._actual_angles.copy()
        self._drag_start_target = (
            self._target_angles.copy()
            if self._target_angles is not None
            else self._actual_angles.copy()
        )
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:  # noqa: N802
        pos = ev.position()
        if self._drag_joint is not None:
            self._preview_drag_target(pos)
            return
        if self._last_mouse is None:
            if self._pick_joint(pos) is None:
                self.unsetCursor()
            else:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            return
        if self._last_mouse is not None:
            delta = pos - self._last_mouse
            self._last_mouse = pos
            self._yaw += float(delta.x()) * 0.01
            self._pitch = float(np.clip(self._pitch + float(delta.y()) * 0.008, -1.1, 1.1))
            self.update()

    def mouseReleaseEvent(self, _ev: QMouseEvent) -> None:  # noqa: N802
        if (
            self._drag_joint is not None
            and self._target_angles is not None
            and self._drag_start_actual is not None
        ):
            idx = self._drag_joint
            delta = float(self._target_angles[idx] - self._drag_start_actual[idx])
            if abs(delta) >= 0.05:
                self.joint_delta_requested.emit(idx, delta)
        self._drag_joint = None
        self._drag_start_pos = None
        self._drag_start_actual = None
        self._drag_start_target = None
        self._last_mouse = None
        self.unsetCursor()

    def leaveEvent(self, _ev) -> None:  # noqa: N802
        if self._drag_joint is None:
            self.unsetCursor()

    def _clip_angles(self, angles: np.ndarray) -> np.ndarray:
        clipped = angles.astype(float, copy=True)
        for i, (lo, hi) in enumerate(JOINT_LIMITS_DEG[:6]):
            clipped[i] = float(np.clip(clipped[i], lo, hi))
        return clipped

    def _pick_joint(self, pos: QPointF) -> int | None:
        if not self._last_projected:
            self._last_projected = self._handle_points(self._project(self._joint_points(self._actual_angles)))
        best_idx: int | None = None
        best_dist = float(SETTINGS.ui.twin_pick_radius_px)
        # Skip the base point; J1 lives at point index 1.
        for point_idx, handle in enumerate(self._last_projected[1:], start=1):
            dist = float(np.hypot(pos.x() - handle.x(), pos.y() - handle.y()))
            if dist <= best_dist:
                best_dist = dist
                best_idx = point_idx - 1
        return best_idx

    def _preview_drag_target(self, pos: QPointF) -> None:
        if (
            self._drag_joint is None
            or self._drag_start_pos is None
            or self._drag_start_actual is None
            or self._drag_start_target is None
        ):
            return
        idx = self._drag_joint
        dx = float(pos.x() - self._drag_start_pos.x())
        dy = float(pos.y() - self._drag_start_pos.y())
        delta = (dx - 0.35 * dy) * float(SETTINGS.ui.twin_drag_deg_per_px)
        target = self._drag_start_target.copy()
        lo, hi = JOINT_LIMITS_DEG[idx]
        target[idx] = float(np.clip(self._drag_start_actual[idx] + delta, lo, hi))
        self._target_angles = target
        self.joint_delta_preview.emit(idx, float(target[idx] - self._drag_start_actual[idx]))
        self.update()

    def _joint_points(self, angles: np.ndarray) -> np.ndarray:
        points = [np.zeros(3, dtype=float)]
        T = np.eye(4, dtype=float)
        for i, (_name, xyz, rpy, axis) in enumerate(_URDF_CHAIN):
            T = T @ _origin_transform(xyz, rpy) @ _axis_rotation(axis, np.radians(angles[i]))
            points.append(T[:3, 3].copy())
        return np.asarray(points)

    def _camera_points(self, points: np.ndarray) -> np.ndarray:
        cy, sy = np.cos(self._yaw), np.sin(self._yaw)
        cp, sp = np.cos(self._pitch), np.sin(self._pitch)
        ry = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])
        rx = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]])
        return points @ (rx @ ry).T

    def _project_sets(self, *point_sets: np.ndarray) -> list[list[QPointF]]:
        cam_sets = [self._camera_points(points) for points in point_sets]
        all_cam = np.vstack(cam_sets)
        camera = 1.4
        all_depth = np.clip(camera - all_cam[:, 2], 0.35, 3.0)
        all_2d = all_cam[:, :2] * (camera / all_depth[:, None])
        span = max(0.35, float(np.ptp(all_2d, axis=0).max()))
        scale = min(self.width(), self.height()) * 0.72 / span
        center = QPointF(self.width() * 0.5, self.height() * 0.58)
        projected_sets = []
        for cam in cam_sets:
            depth = np.clip(camera - cam[:, 2], 0.35, 3.0)
            pts2 = cam[:, :2] * (camera / depth[:, None])
            projected_sets.append(
                [QPointF(center.x() + p[0] * scale, center.y() - p[1] * scale) for p in pts2]
            )
        return projected_sets

    def _project(self, points: np.ndarray) -> list[QPointF]:
        return self._project_sets(points)[0]

    def _handle_points(self, projected: list[QPointF]) -> list[QPointF]:
        handles = [QPointF(p) for p in projected]
        for i in range(1, len(handles)):
            for j in range(1, i):
                if np.hypot(handles[i].x() - handles[j].x(), handles[i].y() - handles[j].y()) < 13.0:
                    angle = 0.9 + i * 1.35
                    handles[i] = handles[i] + QPointF(np.cos(angle) * 16.0, np.sin(angle) * 16.0)
                    break
        return handles

    def _trajectory_points(self, target_angles: np.ndarray) -> np.ndarray:
        samples = []
        for t in np.linspace(0.0, 1.0, 18):
            angles = (1.0 - t) * self._actual_angles + t * target_angles
            samples.append(self._joint_points(angles)[-1])
        return np.asarray(samples)

    def _draw_target_path(self, painter: QPainter, projected: list[QPointF]) -> None:
        color = QColor("#f6d365")
        color.setAlpha(175)
        painter.setPen(QPen(color, 2, Qt.PenStyle.DotLine, Qt.PenCapStyle.RoundCap))
        for a, b in zip(projected[:-1], projected[1:]):
            painter.drawLine(a, b)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        for point in projected[::3]:
            painter.drawEllipse(point, 3, 3)

    def _draw_arm(
        self,
        painter: QPainter,
        projected: list[QPointF],
        *,
        link_color: str,
        joint_color: str,
        width: int,
        dashed: bool = False,
        label_joints: bool = False,
        handles: list[QPointF] | None = None,
    ) -> None:
        handles = handles or projected
        style = Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine
        painter.setPen(QPen(QColor(link_color), width, style, Qt.PenCapStyle.RoundCap))
        for a, b in zip(projected[:-1], projected[1:]):
            painter.drawLine(a, b)

        painter.setPen(QPen(QColor("#d9edf0"), 2))
        painter.setBrush(QBrush(QColor(joint_color)))
        for i, p in enumerate(handles):
            radius = 9 if i in (0, len(projected) - 1) else 7
            if i > 0 and self._drag_joint == i - 1:
                painter.setBrush(QBrush(QColor("#f6d365")))
                radius += 3
            painter.drawEllipse(p, radius, radius)
            painter.setBrush(QBrush(QColor(joint_color)))
            if label_joints and i > 0:
                painter.drawText(p + QPointF(9, -9), f"J{i}")

        tcp = handles[-1]
        painter.setPen(QPen(QColor("#f6d365"), 2))
        painter.drawLine(tcp + QPointF(-10, 0), tcp + QPointF(10, 0))
        painter.drawLine(tcp + QPointF(0, -10), tcp + QPointF(0, 10))

    def paintEvent(self, _ev) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#16181c"))

        actual_points = self._joint_points(self._actual_angles)
        target_points = self._joint_points(self._target_angles) if self._target_angles is not None else None
        path_points = self._trajectory_points(self._target_angles) if self._target_angles is not None else None

        if target_points is not None and path_points is not None:
            actual_projected, target_projected, path_projected = self._project_sets(
                actual_points, target_points, path_points
            )
        else:
            actual_projected = self._project(actual_points)
            target_projected = None
            path_projected = None

        actual_handles = self._handle_points(actual_projected)
        self._last_projected = actual_handles

        grid_pen = QPen(QColor("#2c3036"), 1)
        painter.setPen(grid_pen)
        baseline = int(self.height() * 0.82)
        for x in range(30, self.width(), 40):
            painter.drawLine(x, baseline - 12, x + 22, baseline)
        painter.drawLine(24, baseline, self.width() - 24, baseline)

        if path_projected is not None:
            self._draw_target_path(painter, path_projected)
        if target_projected is not None:
            self._draw_arm(
                painter,
                target_projected,
                link_color="#8f9aa6",
                joint_color="#323840",
                width=4,
                dashed=True,
                label_joints=False,
            )
        self._draw_arm(
            painter,
            actual_projected,
            link_color="#66c2a5",
            joint_color="#242a30",
            width=8,
            dashed=False,
            label_joints=True,
            handles=actual_handles,
        )

        painter.setPen(QColor("#aeb7c2"))
        painter.drawText(12, 22, "Digital twin")
        if self._target_angles is not None:
            err = float(np.max(np.abs(self._target_angles - self._actual_angles)))
            painter.drawText(12, 42, f"target delta {err:.1f}°")


# ---------------------------------------------------------------------------
# Status panel — shows camera + robot live state
# ---------------------------------------------------------------------------
class StatusPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Status")
        self.cam_label = QLabel("Camera: disconnected")
        self.robot_label = QLabel("Robot: disconnected")
        self.angles_label = QLabel("Angles: —")
        self.pose_label = QLabel("Pose: —")
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        for lab in (self.cam_label, self.robot_label, self.angles_label,
                    self.pose_label, self.message_label):
            lab.setStyleSheet("font-family: ui-monospace, monospace;")
        layout = QVBoxLayout(self)
        layout.addWidget(self.cam_label)
        layout.addWidget(self.robot_label)
        layout.addWidget(self.angles_label)
        layout.addWidget(self.pose_label)
        layout.addWidget(self.message_label)

    def set_camera(self, ok: bool, detail: str = "") -> None:
        self.cam_label.setText(f"Camera: {'OK' if ok else 'disconnected'} {detail}".strip())
        self.cam_label.setStyleSheet(
            f"color: {'#3c3' if ok else '#c33'}; font-family: ui-monospace, monospace;"
        )

    def set_robot(self, ok: bool, detail: str = "") -> None:
        self.robot_label.setText(f"Robot: {'OK' if ok else 'disconnected'} {detail}".strip())
        self.robot_label.setStyleSheet(
            f"color: {'#3c3' if ok else '#c33'}; font-family: ui-monospace, monospace;"
        )

    def set_angles(self, angles) -> None:
        if angles is None:
            self.angles_label.setText("Angles: —")
        else:
            self.angles_label.setText(
                "Angles: " + " ".join(f"{a:+7.2f}" for a in angles)
            )

    def set_pose(self, pose) -> None:
        if pose is None:
            self.pose_label.setText("Pose: —")
        else:
            self.pose_label.setText(
                "Pose : " + " ".join(f"{v:+8.2f}" for v in pose)
            )

    def set_message(self, msg: str, error: bool = False) -> None:
        self.message_label.setText(msg)
        self.message_label.setStyleSheet(
            f"color: {'#e66' if error else '#aaa'}; font-family: ui-monospace, monospace;"
        )


# ---------------------------------------------------------------------------
# Quick HBox builder for buttons.
# ---------------------------------------------------------------------------
def button_row(*buttons: tuple[str, Callable[[], None]]) -> QWidget:
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    for label, slot in buttons:
        btn = QPushButton(label)
        btn.clicked.connect(slot)
        layout.addWidget(btn)
    return w
