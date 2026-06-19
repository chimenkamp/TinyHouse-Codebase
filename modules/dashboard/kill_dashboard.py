from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path


PID_FILE = "dashboard.pid"


BASE_DIR = Path(__file__).resolve().parent


def kill_from_pid_file() -> bool:
    pid_path = BASE_DIR / PID_FILE

    if not pid_path.exists():
        return False

    pid_text = pid_path.read_text(encoding="utf-8").strip()

    if not pid_text.isdigit():
        pid_path.unlink()
        return False

    pid = int(pid_text)

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Stopped dashboard process {pid}.")
    except ProcessLookupError:
        print(f"Dashboard process {pid} was already stopped.")
    finally:
        pid_path.unlink(missing_ok=True)

    return True


def fallback_kill() -> None:
    if os.name == "nt":
        command = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process "
                "| Where-Object { $_.CommandLine -match 'run_dashboard_(local|tunnel).py|server.py --mode|server.py --on-management-pc' } "
                "| Where-Object { $_.CommandLine -notmatch 'kill_dashboard.py' } "
                "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
            ),
        ]
        result = subprocess.run(command, check=False)

        if result.returncode == 0:
            print("Stopped dashboard processes by process search.")
            return

        print("No dashboard process was found.")
        return

    result = subprocess.run(
        ["ps", "-axo", "pid=,command="],
        capture_output=True,
        check=False,
        text=True,
    )

    if result.returncode != 0:
        print("No dashboard process was found.")
        return

    own_pid = os.getpid()
    stopped = False

    for line in result.stdout.splitlines():
        stripped = line.strip()

        if not stripped:
            continue

        pid_text, _, command = stripped.partition(" ")

        if not pid_text.isdigit():
            continue

        pid = int(pid_text)

        if pid == own_pid:
            continue

        if "kill_dashboard.py" in command:
            continue

        is_dashboard = (
            "run_dashboard_local.py" in command
            or "run_dashboard_tunnel.py" in command
            or "server.py --mode" in command
            or "server.py --on-management-pc" in command
        )

        if not is_dashboard:
            continue

        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped dashboard process {pid}.")
            stopped = True
        except ProcessLookupError:
            pass
        except PermissionError:
            print(f"Permission denied while stopping dashboard process {pid}.")

    if stopped:
        return

    print("No dashboard process was found.")


def main() -> None:
    if kill_from_pid_file():
        return

    fallback_kill()


if __name__ == "__main__":
    main()
