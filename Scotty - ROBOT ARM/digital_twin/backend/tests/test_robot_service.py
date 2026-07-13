from __future__ import annotations

from dataclasses import dataclass

from digital_twin.backend.models import FkRequest, MoveJointsRequest
from digital_twin.backend.robot_service import RobotBridge


@dataclass
class FakePing:
    hardware_connected: bool = True


class FakeClient:
    def __init__(self) -> None:
        self._angles = [0.0, -90.0, 180.0, 0.0, 0.0, 180.0]
        self.moves: list[list[float]] = []
        self.halted = False
        self.home_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def wait_ready(self, timeout=1.0):
        return True

    def resume(self):
        return 1

    def halt(self):
        self.halted = True
        return 1

    def home(self, wait=False, timeout=60.0):
        self.home_calls += 1
        return 42

    def move_j(self, angles, *, duration=0.0, accel=1.0, wait=False, timeout=10.0):
        self.moves.append(list(angles))
        self._angles = list(angles)
        return 99

    def angles(self):
        return list(self._angles)

    def pose(self):
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def io(self):
        return [1, 1, 0, 0, 1]

    def joint_speeds(self):
        return [0.0] * 6

    def ping(self):
        return FakePing()

    def activity(self):
        return None

    def error(self):
        return None

    def is_estop_pressed(self):
        return False

    def is_simulator(self):
        return False


def test_validate_rejects_out_of_range_target() -> None:
    bridge = RobotBridge(client=FakeClient())
    result = bridge.validate_joints([999.0, -90.0, 180.0, 0.0, 0.0, 180.0])
    assert not result.valid
    assert "L1 target" in result.errors[0]
    assert result.clamped_angles_deg[0] == bridge.joint_limits[0][1]


def test_move_rejected_until_live_enabled_homed_and_movement_enabled() -> None:
    client = FakeClient()
    bridge = RobotBridge(client=client)
    req = MoveJointsRequest(angles_deg=[1.0, -90.0, 180.0, 0.0, 0.0, 180.0])

    assert not bridge.move_joints(req).ok
    bridge.set_mode(live_enabled=True, movement_enabled=True)
    assert not bridge.move_joints(req).ok
    bridge.home()
    result = bridge.move_joints(req)

    assert result.ok
    assert client.moves == [[1.0, -90.0, 180.0, 0.0, 0.0, 180.0]]


def test_halt_disables_live_and_movement() -> None:
    client = FakeClient()
    bridge = RobotBridge(client=client)
    bridge.set_mode(live_enabled=True, movement_enabled=True)

    result = bridge.halt()

    assert result.ok
    assert client.halted
    assert not result.status.live_enabled
    assert not result.status.movement_enabled


def test_fk_home_uses_ssg48_tcp_frame() -> None:
    bridge = RobotBridge()
    result = bridge.fk(FkRequest(angles_deg=bridge.home_angles_deg))

    assert result.ok
    assert result.pose_m_rad is not None
    assert abs(result.pose_m_rad[0]) < 1e-6
    assert abs(result.pose_m_rad[1] - 0.3967707210610375) < 1e-6
    assert abs(result.pose_m_rad[2] - 0.334) < 1e-6
