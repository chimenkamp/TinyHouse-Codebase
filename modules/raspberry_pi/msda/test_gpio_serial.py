#!/usr/bin/env python3
"""
test_gpio_serial.py — Issue #2 Hardware Verification
Tests bidirectional GPIO UART communication between Raspberry Pi and Arduino.

Setup (Issue #2):
  Arduino powered by USB phone charger → Arduino USB port
  Arduino GND     → Pi Pin 6  (GND)
  Pi Pin 8 TX     → Arduino RX pin      (direct, no resistor)
  Arduino TX pin  → 1kΩ → 1kΩ → GND   (voltage divider)
  Voltage divider midpoint → Pi Pin 10  (GPIO15/RX)
  HC-SR04 VCC     → Arduino 5V pin
  HC-SR04 GND     → Arduino GND
  HC-SR04 TRIG    → Arduino D7
  HC-SR04 ECHO    → Arduino D8
  Pi config.txt   → dtoverlay=uart0-pi5

Usage:
  python3 test_gpio_serial.py [--port /dev/ttyAMA0] [--duration 30]
"""

import argparse
import json
import serial
import sys
import time

SEP = "=" * 60
DEFAULT_PORT = "/dev/ttyAMA0"
DEFAULT_BAUD = 115200

def parse_args():
    p = argparse.ArgumentParser(description="Issue #2 GPIO Serial Verification")
    p.add_argument("--port",     default=DEFAULT_PORT, help="Serial port (default: /dev/ttyAMA0)")
    p.add_argument("--baud",     default=DEFAULT_BAUD, type=int)
    p.add_argument("--duration", default=30, type=int, help="Test duration in seconds")
    return p.parse_args()

def main():
    args = parse_args()

    print(f"\n{SEP}")
    print(f"  MSDA Issue #2 — GPIO Serial Verification")
    print(f"  Port: {args.port}   Baud: {args.baud}   Duration: {args.duration}s")
    print(f"{SEP}\n")

    # Open port
    try:
        s = serial.Serial(args.port, args.baud, timeout=2)
        print(f"[OK] Opened {args.port}")
    except Exception as e:
        print(f"[ERR] Cannot open {args.port}: {e}")
        print("  → Check dtoverlay=uart0-pi5 is in /boot/config.txt and Pi rebooted")
        sys.exit(1)

    s.reset_input_buffer()

    # Counters
    got_heartbeat = False
    got_inventory = False
    got_pong      = False
    hcsr04_readings = []
    start = time.time()
    ping_sent = False

    print(f"[..] Listening for {args.duration}s — press Arduino reset button if no data appears\n")

    while time.time() - start < args.duration:
        # Send PING once after 3 seconds
        if not ping_sent and time.time() - start > 3:
            s.write(b"PING\n")
            print("[TX ] Sent PING")
            ping_sent = True

        line = s.readline().decode("utf-8", errors="replace").strip()
        if not line:
            continue

        elapsed_ms = int((time.time() - start) * 1000)

        try:
            obj = json.loads(line)
            t = obj.get("type", "?")

            if t == "HEARTBEAT":
                got_heartbeat = True
                print(f"[HB  ] @{elapsed_ms:6d}ms  heartbeat (Arduino alive)")

            elif t == "INVENTORY":
                got_inventory = True
                sensors = list(obj.get("sensors", {}).keys())
                print(f"[INV ] @{elapsed_ms:6d}ms  sensors detected: {sensors}")

            elif t == "LOG" and "PONG" in obj.get("message", ""):
                got_pong = True
                print(f"[PONG] @{elapsed_ms:6d}ms  PONG received — Pi TX→Arduino RX works ✔")

            elif t == "DATA" and obj.get("sensor") == "HC_SR04":
                d = obj["values"].get("distance_cm", 0)
                hcsr04_readings.append(d)
                print(f"[DIST] @{elapsed_ms:6d}ms  {d:.2f} cm")

        except json.JSONDecodeError:
            print(f"[RAW ] @{elapsed_ms:6d}ms  {line!r}")

    s.close()
    print(f"\n[..] Port closed\n")

    # Results
    print(SEP)
    print("  Results")
    print(SEP)
    print(f"  Heartbeat received     : {'YES ✔' if got_heartbeat else 'NO  ✘'}")
    print(f"  Inventory received     : {'YES ✔' if got_inventory else 'NO  ✘'}")
    print(f"  PING→PONG (Pi TX→RX)  : {'YES ✔' if got_pong else 'NO  ✘'}")
    print(f"  HC-SR04 readings       : {len(hcsr04_readings)}")
    if hcsr04_readings:
        print(f"  Distance range         : {min(hcsr04_readings):.2f} – {max(hcsr04_readings):.2f} cm")

    passed = got_heartbeat and got_pong
    print(f"\n{SEP}")
    if passed:
        print(f"  ✔  PASSED — Issue #2 GPIO serial verification OK")
    else:
        print(f"  ✘  FAILED")
        if not got_heartbeat:
            print("     → No heartbeat: check wiring and Arduino power")
        if not got_pong:
            print("     → No PONG: check Pi Pin 8 (TX) → Arduino RX wire")
        if not hcsr04_readings:
            print("     → No HC-SR04 data: check sensor wiring and press Arduino reset")
    print(f"{SEP}\n")
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
