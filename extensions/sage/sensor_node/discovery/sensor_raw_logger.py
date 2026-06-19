"""to  get live readings from a sensor to understand sensor output"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from datetime import date, datetime
from pathlib import Path

import serial

# Configuration

DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUD = 9600
DEFAULT_OUTDIR = "sensor_logs"
RECONNECT_DELAY = 5  # seconds between reconnect trys
SERIAL_TIMEOUT = 2  # seconds timeout for serial.readline

# logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

log = logging.getLogger("sensor_raw_logger")

# global shutdown flag

shutdown_requested = False


def handle_signal(signum, frame):
    global shutdown_requested
    log.info("Sginal %d received, shutdown...", signum)
    shutdown_requested = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# File handling with daily rotation


class DailyFileWriter:
    "writes a daily JSONL-file, opens a new one each day at midnight"

    def __init__(self, outdir: Path):
        self.outdir = outdir
        self.outdir.mkdir(parents=True, exist_ok=True)
        self._current_date: date | None = None
        self._file = None

    def _filename_for(self, d: date) -> Path:
        return self.outdir / f"sensor_raw_{d.isoformat()}.jsonl"

    def _ensure_file(self, now: datetime):
        today = now.date()
        if self._current_date == today and self._file is not None:
            return

        # new day, new file
        if self._file is not None:
            log.info("Daychange - close %s", self._filename_for(self._current_date))
            self._file.close()

        self._current_date = today
        path = self._filename_for(today)
        self._file = open(path, "a", encoding="utf-8")
        log.info("Write into: %s", path)

    def write_entry(self, now: datetime, raw_line: str):
        self._ensure_file(now)
        entry = {
            "ts": now.isoformat(),
            "raw": raw_line,
        }
        self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None


# Open serial connection with auto reconnect


def open_serial(port: str, baud: int) -> serial.Serial | None:
    """Versucht die serielle Verbindung zu oeffnen. Gibt None bei Fehler zurueck."""
    try:
        ser = serial.Serial(port, baud, timeout=SERIAL_TIMEOUT)
        log.info("Verbunden mit %s @ %d baud", port, baud)
        return ser
    except serial.SerialException as e:
        log.warning("Kann %s nicht oeffnen: %s", port, e)
        return None


def find_serial_port(preferred: str) -> str | None:
    """Sucht nach verfuegbaren seriellen Ports, bevorzugt den konfigurierten."""
    candidates = [
        preferred,
        "/dev/ttyACM0",
        "/dev/ttyACM1",
        "/dev/ttyUSB0",
        "/dev/ttyUSB1",
    ]
    seen = set()
    for port in candidates:
        if port in seen:
            continue
        seen.add(port)
        p = Path(port)
        if p.exists():
            return port
    return None


# main loop


def run(port: str, baud: int, outdir: Path):
    writer = DailyFileWriter(outdir)
    ser: serial.Serial | None = None
    lines_total = 0

    try:
        while not shutdown_requested:
            # Verbindung herstellen
            if ser is None or not ser.is_open:
                actual_port = find_serial_port(port)
                if actual_port is None:
                    log.warning(
                        "Kein serieller Port gefunden, warte %ds...", RECONNECT_DELAY
                    )
                    time.sleep(RECONNECT_DELAY)
                    continue

                ser = open_serial(actual_port, baud)
                if ser is None:
                    time.sleep(RECONNECT_DELAY)
                    continue

                # Erste Zeilen nach Connect sind oft Muell — kurz warten
                time.sleep(1)
                ser.reset_input_buffer()

            # Zeile lesen
            try:
                raw_bytes = ser.readline()
                if not raw_bytes:
                    # Timeout, kein Problem — einfach weiter
                    continue

                raw_line = raw_bytes.decode("utf-8", errors="replace").strip()
                if not raw_line:
                    continue

                now = datetime.now()
                writer.write_entry(now, raw_line)

                lines_total += 1
                if lines_total % 100 == 0:
                    log.info("%d Zeilen geschrieben", lines_total)

            except serial.SerialException as e:
                log.warning("Serial-Fehler: %s — versuche Reconnect", e)
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                time.sleep(RECONNECT_DELAY)

            except UnicodeDecodeError as e:
                log.warning("Decode-Fehler: %s — Zeile uebersprungen", e)

    finally:
        log.info("Beende nach %d Zeilen total", lines_total)
        writer.close()
        if ser is not None and ser.is_open:
            ser.close()


# CLI


def main():
    parser = argparse.ArgumentParser(
        description="Sensor Raw Logger — liest Arduino Serial und schreibt JSONL"
    )
    parser.add_argument(
        "--port", default=DEFAULT_PORT, help=f"Serieller Port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=DEFAULT_BAUD,
        help=f"Baudrate (default: {DEFAULT_BAUD})",
    )
    parser.add_argument(
        "--outdir",
        default=DEFAULT_OUTDIR,
        help=f"Ausgabeverzeichnis (default: {DEFAULT_OUTDIR})",
    )
    args = parser.parse_args()

    log.info("Sensor Raw Logger gestartet")
    log.info("Port: %s | Baud: %d | Outdir: %s", args.port, args.baud, args.outdir)

    run(args.port, args.baud, Path(args.outdir))


if __name__ == "__main__":
    main()
