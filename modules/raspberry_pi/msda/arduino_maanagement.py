#!/usr/bin/env python3
"""
arduino_maanagement.py — Raspberry Pi IoT Management System
Entrypoint wrapper for the msda_hub package (Issue #3 refactor).

Usage:
    python3 arduino_maanagement.py [--config iot_config.ini] [--daemon] [--reset-db]
    python3 arduino_maanagement.py --port /dev/ttyAMA0 --baudrate 115200
"""

from msda_hub import main

if __name__ == "__main__":
    main()