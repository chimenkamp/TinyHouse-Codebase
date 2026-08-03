# Controlling the PAROL6 from Python

Two ways to talk to the PAROL6 from Python:

1. **High level (recommended): the official `parol6` Python package.** A controller process opens the serial port and exposes a clean UDP API (`ping`, `angles`, `pose`, `move_j`, `move_l`, ...). This is what you should use for application code.
2. **Low level: raw 3 Mbaud USB-serial frames.** The 59-byte command / 56-byte status protocol used by the PAROL6 commander GUI (`Serial_sender_good_latest.py`). Useful only if you cannot install the package or need to write firmware tools. Documented at the bottom.

---

## 1. High-level API

### Install

```bash
pip install parol6
# or, from a clone:
git clone https://github.com/PCrnjak/PAROL6-python-API.git
pip install -e ./PAROL6-python-API
```

Requires Python ≥ 3.11.

### Architecture

```
┌──────────────────┐  UDP   ┌─────────────────┐  3 Mbaud serial  ┌──────────┐
│ your script      │──────▶ │ parol6 server   │ ─────────────▶  │ PAROL6   │
│ (RobotClient)    │◀──────│ (controller)    │ ◀─────────────  │ control  │
└──────────────────┘        └─────────────────┘                  │ board    │
                                                                  └──────────┘
```

`Robot()` starts the controller as a subprocess; `RobotClient()` is a sync wrapper around the UDP API. For long-running programs you can also start the server once with `parol6-server --log-level=INFO` and just connect with `RobotClient`.

### Connecting

```python
from parol6 import Robot, RobotClient

HOST, PORT = "127.0.0.1", 5001

# Auto-start the controller and stop it on exit.
with Robot(host=HOST, port=PORT) as robot:
    with RobotClient(host=HOST, port=PORT, timeout=2.0) as client:
        if not client.wait_ready(timeout=5.0):
            raise SystemExit("server did not become ready")
        print("ping:", client.ping())
```

Override the serial port if auto-detection fails:

```bash
export PAROL6_COM_PORT=/dev/tty.usbmodem101    # macOS / Linux
# or set PAROL6_COM_PORT=COM5                  # Windows
```

### Reading state

| Call | Returns |
|---|---|
| `client.angles()` | list of 6 joint angles in **degrees** |
| `client.pose()` | 6-vector TCP pose `[x, y, z, rx, ry, rz]`. Translations in **mm**, rotations in **degrees** (Euler) |
| `client.get_status()` | dict with full telemetry: positions, speeds, IO, errors, gripper |
| `client.ping()` | round-trip latency in seconds |

```python
print("angles deg:", client.angles())
print("pose [mm, deg]:", client.pose())
status = client.get_status()
print("homed:", status.get("homed"))
print("e-stop:", status.get("estop"))
```

### Safety: simulator mode

Test without moving the real arm:

```python
client.simulator(True)     # no commands reach the hardware
client.move_j([0, -45, 90, 0, 30, 0], speed=0.3)
client.simulator(False)
```

### Motion commands

All speeds and accelerations are **fractions of the configured maximum (0.0 – 1.0)**, not percentages.

```python
# Joint move: 6 joint angles in degrees.
client.move_j([0, -45, 90, 0, 30, 0], speed=0.3, accel=0.3)

# Linear (Cartesian) move: [x, y, z, rx, ry, rz] in mm and degrees.
client.move_l([200, 0, 150, 180, 0, 0], speed=0.2, accel=0.5)

# Relative move: 5 mm up in Z.
client.move_l([0, 0, 5, 0, 0, 0], rel=True, duration=1.0)

# Home all joints (blocking).
client.home(wait=True)
```

By default `move_j` / `move_l` return when the command is accepted. Pass `wait=True` to block until the motion completes.

### Profiles

```python
client.set_profile("TOPPRA")    # default, time-optimal
client.set_profile("RUCKIG")    # jerk-limited, joint moves only
client.set_profile("QUINTIC")
```

### Tools / gripper

```python
client.set_tool("SSG-48", variant_key="finger")
client.tool_action(open=False, position=50, force=0.4)   # close to 50%
```

### Forward / inverse kinematics (no robot needed)

```python
from parol6 import Robot
robot = Robot()
T = robot.fk([0, -45, 90, 0, 30, 0])    # 4x4 numpy array, base -> flange
joints = robot.ik(T)
```

### Common pitfalls

- **Units**: `angles()` is degrees, `pose()` is **mm + degrees**. The FK matrix from `Robot.fk()` is in **meters**.
- **wait_ready**: always call it before sending commands; the controller takes ~1 s to boot.
- **E-stop**: pressing the E-stop disables the motors. Call `client.resume()` after release.
- **Simulator**: when `simulator(True)`, kinematics still run but the robot stays still. Toggle off before moving the real arm.

---

## 2. Low-level wire protocol (reference)

If you can't use the package, here is the raw protocol from `Serial_sender_good_latest.py`.

### Connection

| Setting | Value |
|---|---|
| Baud | `3_000_000` |
| Timeout | `0` (non-blocking) |
| Port (macOS/Linux) | `/dev/tty.usbmodem*` (try `/dev/ttyACM0` on Linux) |
| Port (Windows) | `COM3+` |
| Loop period | **10 ms (100 Hz)** — the PC must keep transmitting or the robot times out |

### Command frame (PC → robot, 59 bytes)

```
[0xFF 0xFF 0xFF] [0x34] [data 52 B] [CRC 1 B] [0x01 0x02]
```

| Field | Bytes | Encoding |
|---|---|---|
| Joint positions × 6 | 18 | Each joint = signed 24-bit big-endian motor steps |
| Joint speeds × 6 | 18 | Same encoding (steps/s) |
| Command opcode | 1 | See table below |
| Affected joints | 1 | Bitfield, bits 0–5 = J1..J6 |
| IO control | 1 | Bitfield (IN1, IN2, OUT1, OUT2, E-stop, ...) |
| Timeout | 1 | |
| Gripper position / speed / current | 6 | 3 × uint16 BE |
| Gripper command / mode / id | 3 | |
| CRC | 1 | Currently fixed at `228` (not validated) |

Opcodes:

| Code | Meaning |
|---|---|
| `100` | HOME |
| `101` | ENABLE motors |
| `102` | DISABLE / E-stop |
| `103` | CLEAR_ERROR |
| `123` | JOG (joint or Cartesian) |
| `156` | MOVE_J |
| `255` | NOP / dummy |

### Status frame (robot → PC, 56 bytes)

Same start (`0xFF 0xFF 0xFF`) and end (`0x01 0x02`) bytes. Payload contains 6 joint positions (signed 24-bit, motor steps), 6 joint speeds, homed bitfield, IO bitfield, error bitfields, timing, and gripper status.

### Helpers

```python
import struct

START = bytes([0xFF, 0xFF, 0xFF])
END   = bytes([0x01, 0x02])

def split24(value: int) -> bytes:
    return struct.pack(">I", value & 0xFFFFFF)[1:]    # drop high byte

def fuse24(b: bytes) -> int:
    v = struct.unpack(">I", b"\x00" + b)[0]
    return v - (1 << 24) if v >= (1 << 23) else v
```

### Steps ↔ degrees

Conversion factors (`steps-per-revolution × gear-ratio`) live in the `PAROL6_ROBOT.py` file inside the official Python API. **Do not hard-code them** — pull them from that module so they stay in sync with firmware changes.

---

## TL;DR

For our project, use the high-level API:

```python
from parol6 import Robot, RobotClient

with Robot() as _, RobotClient(timeout=2.0) as c:
    c.wait_ready(5.0)
    print(c.angles())   # 6 joint angles in degrees
    print(c.pose())     # [x, y, z, rx, ry, rz] in mm, degrees
```

That's all the hand-eye calibration script needs.
