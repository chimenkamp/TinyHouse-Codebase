#!/usr/bin/env python3
"""
test_hcsr04_usb.py — Issue #1 Hardware Verification
Reads live HC-SR04 distance data from an Arduino connected via USB.

Firmware required on Arduino:
    MSDA_Firmware_HCSR04_USB/MSDA_Firmware_HCSR04_USB.ino
    Pins: TRIG → D7, ECHO → D8

Usage:
    python3 test_hcsr04_usb.py [--port /dev/ttyACM0] [--duration 30] [--min-readings 5]

Exit codes:
    0 — PASSED  (received enough valid, non-timeout readings)
    1 — FAILED  (serial error, no messages, or too many timeouts)
"""

import argparse
import json
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[ERROR] pyserial not installed. Run:  pip install pyserial")
    sys.exit(1)

# ── CLI arguments ─────────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="MSDA Issue #1 — HC-SR04 USB Serial Verification",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser.add_argument("--port",         default=None,   help="Serial port (auto-detected if omitted)")
parser.add_argument("--baudrate",     default=115200,  type=int)
parser.add_argument("--duration",     default=30,      type=int, help="Test duration in seconds")
parser.add_argument("--min-readings", default=5,       type=int, dest="min_readings",
                    help="Minimum valid (non-timeout) readings to PASS")
parser.add_argument("--list-ports",   action="store_true", help="List available serial ports and exit")
args = parser.parse_args()

# ── Port listing helper ───────────────────────────────────────────
def list_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("  (no serial ports found)")
    for p in ports:
        print(f"  {p.device:20s}  {p.description}")

if args.list_ports:
    print("\nAvailable serial ports:")
    list_ports()
    sys.exit(0)

# ── Auto-detect port if not given ─────────────────────────────────
def auto_detect_port():
    """Return the first Arduino-like USB serial port found."""
    keywords = ["arduino", "usb serial", "acm", "usbmodem", "ch340", "cp210"]
    for p in serial.tools.list_ports.comports():
        desc = p.description.lower()
        if any(k in desc for k in keywords) or "ACM" in p.device or "USB" in p.device:
            return p.device
    # Fallback: first available port
    ports = list(serial.tools.list_ports.comports())
    return ports[0].device if ports else None

port = args.port
if port is None:
    port = auto_detect_port()
    if port is None:
        print("[ERROR] No serial port found. Plug in the Arduino or use --port /dev/ttyACMx")
        print("\nAvailable ports:")
        list_ports()
        sys.exit(1)
    print(f"[AUTO] Using port: {port}")

# ── Banner ────────────────────────────────────────────────────────
SEP = "=" * 60
print(f"\n{SEP}")
print(f"  MSDA Issue #1 — HC-SR04 USB Verification")
print(f"  Port: {port}   Baud: {args.baudrate}   Duration: {args.duration}s")
print(f"{SEP}\n")

# ── Open port ─────────────────────────────────────────────────────
try:
    ser = serial.Serial(port=port, baudrate=args.baudrate, timeout=1.0)
    print(f"[OK] Opened {port}")
except serial.SerialException as e:
    print(f"[FAIL] Cannot open {port}: {e}")
    sys.exit(1)

# Arduino resets on USB open; wait for it to boot
time.sleep(2.5)
print("[..] Waiting for Arduino boot message...\n")

# ── Counters / state ──────────────────────────────────────────────
readings_ok      = []   # valid distance readings (cm)
readings_timeout = 0    # sensor returned -1 / TIMEOUT
got_boot         = False
line_buf         = ""
start_time       = time.time()

# ── Read loop ─────────────────────────────────────────────────────
try:
    while time.time() - start_time < args.duration:
        raw = ser.read(ser.in_waiting or 1)
        if not raw:
            continue

        line_buf += raw.decode("utf-8", errors="replace")

        # Process complete newline-terminated JSON lines
        while "\n" in line_buf:
            line, line_buf = line_buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            # Parse JSON
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                print(f"[RAW] {line}")
                continue

            msg_type = msg.get("type", "?")
            ts       = msg.get("ts", 0)

            if msg_type == "STATUS":
                got_boot = True
                text = msg.get("message", "")
                print(f"[BOOT] @ {ts:6d}ms  {text}")

            elif msg_type == "HEARTBEAT":
                elapsed = int(time.time() - start_time)
                print(f"[HB  ] @ {ts:6d}ms  (elapsed: {elapsed}s)")

            elif msg_type == "DATA" and msg.get("sensor") == "HC_SR04":
                dist   = msg.get("distance_cm", -1)
                raw_us = msg.get("raw_us", 0)
                status = msg.get("status", "?")

                if status == "TIMEOUT" or dist < 0:
                    readings_timeout += 1
                    print(f"[TOUT] @ {ts:6d}ms  TIMEOUT — nothing in range or bad wiring")
                else:
                    readings_ok.append(dist)
                    # Sanity range for HC-SR04: 2 cm – 400 cm
                    range_ok = 2.0 <= dist <= 400.0
                    tag = "OK  " if range_ok else "RNGE"
                    print(f"[{tag}] @ {ts:6d}ms  {dist:7.2f} cm   (raw={raw_us} µs)")

            elif msg_type == "ERROR":
                print(f"[ERR ] @ {ts:6d}ms  {msg.get('message', '')}")

            else:
                print(f"[MSG ] {line}")

except KeyboardInterrupt:
    print("\n[..] Interrupted by user")

finally:
    ser.close()
    print(f"\n[..] Port closed")

# ── Summary ───────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  Results")
print(f"{SEP}")
passed = len(readings_ok) >= args.min_readings

# Boot message note
if got_boot:
    print(f"  Boot message received  : YES ✔")
else:
    if passed:
        # Arduino was already running before the script connected — normal
        print(f"  Boot message received  : not seen (Arduino was already running — OK)")
    else:
        print(f"  Boot message received  : NO  ✘")

print(f"  Valid readings         : {len(readings_ok)}  (need ≥ {args.min_readings})")
print(f"  Timeout readings       : {readings_timeout}")

if readings_ok:
    print(f"  Distance range         : {min(readings_ok):.2f} – {max(readings_ok):.2f} cm")
    avg = sum(readings_ok) / len(readings_ok)
    print(f"  Average distance       : {avg:.2f} cm")
    out_of_range = [d for d in readings_ok if not (2.0 <= d <= 400.0)]
    if out_of_range:
        print(f"  ⚠  Out-of-range values: {out_of_range}")

# Diagnose failures only
if not passed:
    if not got_boot:
        print("\n  ⚠  No boot message — possible causes:")
        print("       - Wrong firmware (not MSDA_Firmware_HCSR04_USB.ino)")
        print("       - Wrong port (use --list-ports to check)")
        print("       - Arduino not powered")
    if readings_timeout > 0 and not readings_ok:
        print("\n  ⚠  All readings timed out — possible causes:")
        print("       - TRIG/ECHO wires swapped (should be TRIG→D7, ECHO→D8)")
        print("       - HC-SR04 VCC not connected (needs 5V, not 3.3V)")
        print("       - Object out of sensor range (2 – 400 cm)")

# Pass / Fail
print(f"\n{SEP}")
if passed:
    print(f"  ✔  PASSED — Issue #1 HC-SR04 hardware verification OK")
    print(f"{SEP}\n")
    sys.exit(0)
else:
    print(f"  ✘  FAILED — got {len(readings_ok)} valid readings, need ≥ {args.min_readings}")
    print(f"{SEP}\n")
    sys.exit(1)
