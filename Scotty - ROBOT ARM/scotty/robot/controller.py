"""PAROL6 controller wrapper.

Wraps the in-repo ``parol6`` package so the rest of the app sees a single
defensive interface (no exceptions leak out, all reads return ``None`` on
failure). Hardens against the package not being importable so the GUI can
still run in viewer-only mode.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np

from ..config import SETTINGS

# Make the in-repo parol6 package importable without pip install.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_repo_str = str(_REPO_ROOT)
if _repo_str not in sys.path:
    sys.path.insert(0, _repo_str)

try:
    from parol6 import Robot as _Robot, RobotClient as _RobotClient  # type: ignore
    from parol6.PAROL6_ROBOT import _joint_limits_degree as _LIMITS  # type: ignore
    from parol6.PAROL6_ROBOT import _standby_deg as _STANDBY  # type: ignore
    PAROL6_AVAILABLE = True
    JOINT_LIMITS_DEG: list[tuple[float, float]] = [(float(lo), float(hi)) for lo, hi in _LIMITS]
    JOINT_HOME_DEG: list[float] = [float(v) for v in _STANDBY]
except Exception as _exc:  # pragma: no cover - import-time guard
    _Robot = None  # type: ignore
    _RobotClient = None  # type: ignore
    PAROL6_AVAILABLE = False
    PAROL6_IMPORT_ERROR = _exc
    JOINT_LIMITS_DEG = [
        (-123.046875, 123.046875),
        (-145.0088, -3.375),
        (107.866, 287.8675),
        (-105.46975, 105.46975),
        (-90.0, 90.0),
        (0.0, 360.0),
    ]
    # Canonical PAROL6 standby pose (matches PAROL6_ROBOT._standby_deg).
    JOINT_HOME_DEG = [90.0, -90.0, 180.0, 0.0, 0.0, 180.0]


class Parol6Controller:
    """Owns the controller subprocess + sync client."""

    def __init__(self) -> None:
        self.robot: object | None = None
        self.client: object | None = None
        self.connected: bool = False
        self.last_error: str | None = None
        self.last_command_target_angles: list[float] | None = None
        self._owns_server: bool = False
        self.motion_enabled: bool = False

    # --- Lifecycle ---
    def connect(self) -> None:
        if not PAROL6_AVAILABLE:
            self.last_error = f"parol6 package not importable: {globals().get('PAROL6_IMPORT_ERROR')}"
            return
        cfg = SETTINGS.robot
        try:
            os.environ["PAROL6_COM_PORT"] = cfg.serial_port
            self.robot = _Robot(host=cfg.host, port=cfg.port, normalize_logs=True)  # type: ignore[misc]
            if self.robot.is_available(host=cfg.host, port=cfg.port):  # type: ignore[union-attr]
                self._owns_server = False
            else:
                self.robot.start(com_port=cfg.serial_port)  # type: ignore[union-attr]
                self._owns_server = True
            self.client = _RobotClient(  # type: ignore[misc]
                host=cfg.host, port=cfg.port, timeout=cfg.client_timeout_s,
            )
            self.client.__enter__()  # type: ignore[union-attr]
            if not self.client.wait_ready(timeout=cfg.ready_timeout_s):  # type: ignore[union-attr]
                self.last_error = "controller did not become ready"
                self.disconnect()
                return
            try:
                self.client.resume()  # type: ignore[union-attr]
            except Exception:
                pass
            self.connected = True
            self.motion_enabled = True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.disconnect()

    def disconnect(self) -> None:
        self.connected = False
        self.motion_enabled = False
        if self.client is not None:
            try:
                self.client.__exit__(None, None, None)  # type: ignore[union-attr]
            except Exception:
                pass
            self.client = None
        if self.robot is not None:
            if self._owns_server:
                try:
                    self.robot.stop()  # type: ignore[union-attr]
                except Exception:
                    pass
            self.robot = None
        self._owns_server = False

    def _motion_is_enabled(self) -> tuple[bool, str | None]:
        if self.client is None:
            return False, "not connected"
        try:
            self.client.resume()  # type: ignore[union-attr]
            self.motion_enabled = True
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            self.last_error = f"resume: {detail}"
            return False, f"could not enable controller: {detail}"
        return True, None

    def _motion_exception(self, exc: Exception) -> str:
        detail = f"{type(exc).__name__}: {exc}"
        if "Controller disabled" in detail:
            try:
                if self.client is not None:
                    self.client.resume()  # type: ignore[union-attr]
                    self.motion_enabled = True
                    return "controller was disabled; resume sent, retry movement"
            except Exception as resume_exc:
                self.motion_enabled = False
                return f"controller disabled; resume failed: {type(resume_exc).__name__}: {resume_exc}"
        return detail

    def _joint_target_from_delta(
        self, current: np.ndarray, idx: int, delta_deg: float
    ) -> tuple[list[float] | None, str | None]:
        """Build a limit-safe absolute target for an incremental joint move.

        Homing can leave J5/J6 a little outside the configured limits even
        though the only safe thing to do next is move them back inward. Sending
        absolute, clamped targets avoids the relative-command edge case where
        the planner still sees a target outside the hard stop and refuses all
        motion.
        """
        tol = float(SETTINGS.robot.joint_limit_release_tolerance_deg)
        delta = float(delta_deg)
        target = list(map(float, current))

        # Keep passive joints inside the command validator whenever readback
        # is only slightly outside. If a different joint is wildly invalid,
        # report that instead of building a move from bogus telemetry.
        for j, value in enumerate(target):
            lo, hi = JOINT_LIMITS_DEG[j]
            if value < lo:
                if lo - value <= tol:
                    target[j] = lo
                elif j != idx:
                    return None, (
                        f"J{j + 1} readback {value:.1f}° outside limits "
                        f"[{lo:.1f}, {hi:.1f}]"
                    )
            elif value > hi:
                if value - hi <= tol:
                    target[j] = hi
                elif j != idx:
                    return None, (
                        f"J{j + 1} readback {value:.1f}° outside limits "
                        f"[{lo:.1f}, {hi:.1f}]"
                    )

        current_value = float(current[idx])
        lo, hi = JOINT_LIMITS_DEG[idx]
        raw_target = current_value + delta

        if current_value < lo and delta <= 0:
            return None, f"J{idx + 1} is below its lower limit; move positive first"
        if current_value > hi and delta >= 0:
            return None, f"J{idx + 1} is above its upper limit; move negative first"

        if raw_target < lo:
            if lo - raw_target <= tol or current_value < lo:
                raw_target = lo
            else:
                return None, (
                    f"J{idx + 1} target {raw_target:.1f}° outside "
                    f"limits [{lo:.1f}, {hi:.1f}]"
                )
        elif raw_target > hi:
            if raw_target - hi <= tol or current_value > hi:
                raw_target = hi
            else:
                return None, (
                    f"J{idx + 1} target {raw_target:.1f}° outside "
                    f"limits [{lo:.1f}, {hi:.1f}]"
                )

        target[idx] = min(max(raw_target, lo), hi)
        return target, None

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
        """Return [x, y, z, rx, ry, rz] (mm + degrees, WRF). ``None`` if unavailable."""
        if self.client is None:
            return None
        try:
            p = self.client.pose()  # type: ignore[union-attr]
            return None if p is None else np.asarray(p, dtype=float)
        except Exception as exc:
            self.last_error = f"pose: {exc}"
            return None

    # --- Write ---
    def move_joint_delta(self, idx: int, delta_deg: float,
                         speed_deg_s: float | None = None,
                         accel: float | None = None) -> tuple[bool, str]:
        ok, disabled_detail = self._motion_is_enabled()
        if not ok:
            return False, disabled_detail or "not connected"
        if not (0 <= idx < 6):
            return False, f"invalid joint index {idx}"
        if abs(float(delta_deg)) < 0.05:
            return True, f"J{idx + 1}: skip (no movement)"
        speed = SETTINGS.robot.move_speed_deg_s if speed_deg_s is None else speed_deg_s
        accel = SETTINGS.robot.move_accel if accel is None else accel
        try:
            current = self.angles()
            if current is None:
                return False, "could not read current angles"
            target, limit_error = self._joint_target_from_delta(current, idx, delta_deg)
            if target is None:
                return False, limit_error or "joint target outside limits"
            actual_delta = float(target[idx]) - float(current[idx])
            if abs(actual_delta) < 0.05:
                return True, f"J{idx + 1}: already at limit"
            duration = max(0.2, abs(float(delta_deg)) / max(1.0, speed))
            self.client.move_j(  # type: ignore[union-attr]
                target, duration=duration, accel=accel, rel=False,
                wait=False, timeout=duration + 5.0,
            )
            self.last_command_target_angles = list(target)
            return True, (
                f"move_j J{idx + 1} delta={actual_delta:+.2f}° "
                f"target={target[idx]:.2f}° duration={duration:.2f}s"
            )
        except Exception as exc:
            return False, self._motion_exception(exc)

    def move_joint_to_angle(self, idx: int, target_deg: float,
                            speed_deg_s: float | None = None,
                            accel: float | None = None) -> tuple[bool, str]:
        current = self.angles()
        if current is None:
            return False, "could not read current angles"
        return self.move_joint_delta(
            idx, float(target_deg) - float(current[idx]),
            speed_deg_s=speed_deg_s, accel=accel,
        )

    def move_to_angles(self, angles_deg: list[float], speed_deg_s: float | None = None,
                       accel: float | None = None) -> tuple[bool, str]:
        ok, disabled_detail = self._motion_is_enabled()
        if not ok:
            return False, disabled_detail or "not connected"
        speed = SETTINGS.robot.move_speed_deg_s if speed_deg_s is None else speed_deg_s
        accel = SETTINGS.robot.move_accel if accel is None else accel
        try:
            current = self.angles()
            if current is None:
                return False, "could not read current angles"
            delta = float(max(abs(a - c) for a, c in zip(angles_deg, current)))
            duration = max(0.4, delta / max(1.0, speed))
            self.client.move_j(  # type: ignore[union-attr]
                angles_deg, duration=duration, accel=accel, wait=False, timeout=duration + 5.0,
            )
            self.last_command_target_angles = list(map(float, angles_deg))
            return True, f"move_j duration={duration:.2f}s"
        except Exception as exc:
            return False, self._motion_exception(exc)

    def move_to_pose(self, pose: list[float], duration: float = 2.0,
                     frame: str = "WRF", accel: float | None = None) -> tuple[bool, str]:
        ok, disabled_detail = self._motion_is_enabled()
        if not ok:
            return False, disabled_detail or "not connected"
        accel = SETTINGS.robot.move_accel if accel is None else accel
        try:
            self.client.move_l(  # type: ignore[union-attr]
                pose, frame=frame, duration=duration, accel=accel, wait=False,
                timeout=duration + 5.0,
            )
            return True, f"move_l duration={duration:.2f}s"
        except Exception as exc:
            return False, self._motion_exception(exc)

    def home(self, prehome_j6_deg: float | None = ..., park_first: bool = False,
             allow_unsafe: bool = False, watchdog: bool = False) -> tuple[bool, str]:  # type: ignore[assignment]
        """Trigger firmware homing.

        The PAROL6 firmware home routine is opaque (no per-joint or
        direction parameter) and sometimes makes J6 wrap the long way
        around — tangling gripper cables. Three host-side workarounds:

        * ``park_first=True``: first move every joint to ``JOINT_HOME_DEG``
          (the same pose the controller will seek). J6 is then already at
          ~180° — near its home position — so the firmware seek motion is
          minimal and never wraps. Recommended once the arm has been
          homed at least once (so the encoder readback is valid).
        * ``prehome_j6_deg``: rotate **only** J6 to the given angle first.
          Use this if you've found a single safe angle empirically.
        * **auto**: if neither workaround is requested but J6 is more than
          ~90° away from 180°, we still pre-rotate J6 to 180° before the
          firmware home — unless ``allow_unsafe=True`` is passed (the
          "Force firmware home (unsafe)" UI path).

        When ``watchdog=True`` after issuing ``client.home()`` we poll angles
        every 50 ms and abort with ``client.halt()`` if J6 swings more
        than ~120° (clearly wrapping the long way) or unwinds in the
        same direction for more than ~3 s.

        Workarounds (manual or auto) are skipped automatically when joint
        readback looks bogus (un-homed arm — some joints outside their
        valid range), in which case the bare firmware home is sent.
        """
        ok, disabled_detail = self._motion_is_enabled()
        if not ok:
            return False, disabled_detail or "not connected"
        if prehome_j6_deg is ...:  # type: ignore[comparison-overlap]
            prehome_j6_deg = SETTINGS.robot.prehome_j6_deg
        notes: list[str] = []

        current = self.angles()
        tol = max(0.5, float(SETTINGS.robot.joint_limit_release_tolerance_deg))
        readback_ok = current is not None and not any(
            not (JOINT_LIMITS_DEG[i][0] - tol <= float(a) <= JOINT_LIMITS_DEG[i][1] + tol)
            for i, a in enumerate(current)
        )

        # --- Auto-prehome: if no explicit workaround requested and J6 is
        # far from 180°, force a short J6 pre-rotate to 180° to avoid the
        # firmware wraparound. Caller may opt out with allow_unsafe=True.
        auto_prehome = False
        if (
            not park_first
            and prehome_j6_deg is None
            and not allow_unsafe
            and readback_ok
            and current is not None
            and abs(float(current[5]) - 180.0) > 90.0
        ):
            prehome_j6_deg = 180.0
            auto_prehome = True

        if (park_first or prehome_j6_deg is not None) and not readback_ok:
            notes.append("workaround skipped (un-homed: joint readback invalid)")
        else:
            try:
                if park_first:
                    delta = max(abs(t - float(c)) for t, c in zip(JOINT_HOME_DEG, current))  # type: ignore[arg-type]
                    if delta < 1.0:
                        notes.append("already at park pose")
                    else:
                        speed = SETTINGS.robot.move_speed_deg_s
                        duration = max(0.4, delta / max(1.0, speed))
                        self.client.move_j(  # type: ignore[union-attr]
                            JOINT_HOME_DEG, duration=duration, accel=SETTINGS.robot.move_accel,
                            wait=True, timeout=duration + 5.0,
                        )
                        notes.append(f"parked in {duration:.1f}s")
                elif prehome_j6_deg is not None:
                    lo, hi = JOINT_LIMITS_DEG[5]
                    target_j6 = float(min(max(prehome_j6_deg, lo), hi))
                    delta = abs(target_j6 - float(current[5]))  # type: ignore[index]
                    if delta < 1.0:
                        notes.append(f"J6 already at {target_j6:.1f}°")
                    else:
                        target, limit_error = self._joint_target_from_delta(
                            current, 5, target_j6 - float(current[5])  # type: ignore[index]
                        )
                        if target is None:
                            return False, limit_error or "J6 prehome target outside limits"
                        speed = SETTINGS.robot.prehome_j6_speed_deg_s
                        duration = max(0.4, delta / max(1.0, speed))
                        self.client.move_j(  # type: ignore[union-attr]
                            target, duration=duration, accel=SETTINGS.robot.move_accel,
                            wait=True, timeout=duration + 5.0,
                        )
                        tag = "auto-prehomed" if auto_prehome else "J6 prehomed"
                        notes.append(f"{tag} to {target_j6:.1f}°")
            except Exception as exc:
                return False, f"workaround failed: {self._motion_exception(exc)}"
        try:
            index = self.client.home(wait=False)  # type: ignore[union-attr]
            if isinstance(index, int) and index < 0:
                return False, "home command rejected by controller"
            notes.append(f"home command sent (index={index})")
        except Exception as exc:
            return False, self._motion_exception(exc)

        # --- Wrist watchdog: abort if firmware drives J5/J6 the long way.
        if watchdog:
            watchdog_msg = self._wrist_home_watchdog()
            if watchdog_msg:
                notes.append(watchdog_msg)
                return False, "; ".join(notes)
        return True, "; ".join(notes)

    def _wrist_home_watchdog(self, max_swing_deg: float = 120.0,
                             max_same_dir_s: float = 3.0,
                             poll_s: float = 0.05,
                             window_s: float = 12.0) -> str | None:
        """Poll J5/J6 during firmware homing; halt if a wrist axis runs away.

        Returns a non-None string describing the abort reason on trip,
        otherwise ``None`` once the homing window has elapsed without
        anomalous motion. Failures to read angles are tolerated.
        """
        if self.client is None:
            return None
        # Pump the Qt event loop while we poll so the HALT button stays
        # responsive. Falls back to a no-op when not running under Qt.
        try:
            from PySide6.QtWidgets import QApplication  # type: ignore
            _app = QApplication.instance()
        except Exception:
            _app = None
        start = time.monotonic()
        first = self.angles()
        if first is None:
            return None
        starts = {4: float(first[4]), 5: float(first[5])}
        same_dir_since: dict[int, float | None] = {4: None, 5: None}
        same_dir_sign = {4: 0, 5: 0}
        prev = dict(starts)
        while time.monotonic() - start < window_s:
            time.sleep(poll_s)
            if _app is not None:
                _app.processEvents()
            cur = self.angles()
            if cur is None:
                continue
            for idx in (4, 5):
                value = float(cur[idx])
                swing = abs(value - starts[idx])
                if swing > max_swing_deg:
                    self._safe_halt()
                    return f"WATCHDOG: J{idx + 1} swung {swing:.0f}° during homing - halted"
                step = value - prev[idx]
                sign = 1 if step > 0.05 else (-1 if step < -0.05 else 0)
                if sign != 0 and sign == same_dir_sign[idx]:
                    since = same_dir_since[idx]
                    if since is not None and (time.monotonic() - since) > max_same_dir_s:
                        self._safe_halt()
                        return (
                            f"WATCHDOG: J{idx + 1} unwinding same direction "
                            f">{max_same_dir_s:.0f}s - halted"
                        )
                elif sign != 0:
                    same_dir_sign[idx] = sign
                    same_dir_since[idx] = time.monotonic()
                else:
                    # Joint stopped moving - assume homing complete on this axis.
                    same_dir_since[idx] = None
                    same_dir_sign[idx] = 0
                prev[idx] = value
        return None

    def _safe_halt(self) -> None:
        try:
            if self.client is not None:
                self.client.halt()  # type: ignore[union-attr]
                self.motion_enabled = False
        except Exception:
            pass

    def halt(self) -> tuple[bool, str]:
        if self.client is None:
            return False, "not connected"
        try:
            self.client.halt()  # type: ignore[union-attr]
            self.motion_enabled = False
            return True, "halt sent"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    def resume(self) -> tuple[bool, str]:
        if self.client is None:
            return False, "not connected"
        try:
            self.client.resume()  # type: ignore[union-attr]
            self.motion_enabled = True
            return True, "resume sent"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    def park(self) -> tuple[bool, str]:
        """Collapse the arm over the base in a staged sequence.

        A single ``move_j`` from a limit-switch homing pose to the
        standby pose interpolates linearly in joint space — but in
        Cartesian space that traces a wide arc that fully extends the
        arm and can flip it to the back of the base. To avoid that we
        stage the motion:

        1. **Fold the elbow** (J3) and reset the wrist (J4/J5/J6) while
           keeping the shoulder where it is. This shrinks the arm's
           swept volume before anything else moves.
        2. **Lift the shoulder** (J2) to the parked value with the
           elbow already folded.
        3. **Rotate the base** (J1) only if a target is configured
           (``park_pose_deg[0] is not None``).

        The target pose is read from ``SETTINGS.robot.park_pose_deg``.
        Each ``None`` slot keeps the current joint angle. Tune the
        defaults in ``scotty/config.py`` for your installation.
        """
        if self.client is None:
            return False, "not connected"
        cfg = SETTINGS.robot
        current = self.angles()
        if current is None:
            return False, "could not read current angles"

        # Validate readback is within limits — bogus readback (un-homed
        # arm) would cause the staged move to plan from junk values.
        for i, a in enumerate(current):
            lo, hi = JOINT_LIMITS_DEG[i]
            if not (lo - 0.5 <= float(a) <= hi + 0.5):
                return False, (
                    f"refusing to park: J{i+1} readback {a:.1f}° outside "
                    f"limits [{lo:.1f}, {hi:.1f}] (arm not homed?)"
                )

        target_raw = list(cfg.park_pose_deg)
        if len(target_raw) != 6:
            return False, "park_pose_deg must have 6 entries"
        # Resolve None -> current value, then clip to limits.
        target = []
        for i, t in enumerate(target_raw):
            v = float(current[i]) if t is None else float(t)
            lo, hi = JOINT_LIMITS_DEG[i]
            target.append(min(max(v, lo), hi))

        # Clip the elbow-fold staging value to J3 limits too.
        lo3, hi3 = JOINT_LIMITS_DEG[2]
        elbow_fold = min(max(float(cfg.park_elbow_fold_deg), lo3), hi3)

        speed = max(1.0, cfg.move_speed_deg_s)
        accel = cfg.move_accel

        def _go(waypoint: list[float], label: str) -> tuple[bool, str]:
            delta = max(abs(w - float(c)) for w, c in zip(waypoint, current))  # type: ignore[arg-type]
            if delta < 0.5:
                return True, f"{label}: skip (already there)"
            duration = max(0.4, delta / speed)
            try:
                self.client.move_j(  # type: ignore[union-attr]
                    waypoint, duration=duration, accel=accel,
                    wait=True, timeout=duration + 5.0,
                )
            except Exception as exc:
                return False, f"{label} failed: {type(exc).__name__}: {exc}"
            return True, f"{label}: {duration:.1f}s"

        notes: list[str] = []

        # Stage 1: fold elbow + neutralise wrist; keep J1, J2 where they are.
        wp1 = [
            float(current[0]),       # J1 stay
            float(current[1]),       # J2 stay
            elbow_fold,              # J3 fold
            target[3],               # J4 wrist
            target[4],               # J5 wrist
            target[5],               # J6 wrist
        ]
        ok, msg = _go(wp1, "stage1 elbow+wrist")
        notes.append(msg)
        if not ok:
            return False, "; ".join(notes)
        # Refresh readback for accurate next-stage delta.
        c2 = self.angles()
        if c2 is not None:
            current = list(map(float, c2))

        # Stage 2: lift shoulder with elbow already folded; J3 → final target.
        wp2 = [
            float(current[0]),       # J1 stay
            target[1],               # J2 lift
            target[2],               # J3 final
            target[3], target[4], target[5],
        ]
        ok, msg = _go(wp2, "stage2 shoulder")
        notes.append(msg)
        if not ok:
            return False, "; ".join(notes)
        c3 = self.angles()
        if c3 is not None:
            current = list(map(float, c3))

        # Stage 3: rotate base last, only if a target was configured.
        if target_raw[0] is not None:
            wp3 = [target[0], target[1], target[2], target[3], target[4], target[5]]
            ok, msg = _go(wp3, "stage3 base")
            notes.append(msg)
            if not ok:
                return False, "; ".join(notes)

        return True, "; ".join(notes)
