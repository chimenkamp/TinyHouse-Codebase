from __future__ import annotations

import os
import socket
import sys
from pathlib import Path


MODE = "tunnel"
HOST = "127.0.0.1"
PORT = 8088
CONFIG_FILE = "config.yaml"


BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"

    return VENV_DIR / "bin" / "python"


def ensure_venv() -> None:
    python_path = venv_python()

    if not python_path.exists():
        print(f"Dashboard venv was not found: {python_path}")
        print("Create it with: python -m venv .venv")
        print("Install dependencies with: .venv/bin/python -m pip install -r requirements.txt")
        sys.exit(1)

    if Path(sys.prefix).resolve() == VENV_DIR.resolve():
        return

    os.execv(str(python_path), [str(python_path), str(Path(__file__).resolve())])


def ensure_port_free(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)

        if sock.connect_ex((host, port)) != 0:
            return

    print(f"Port {host}:{port} is already in use.")
    print("Stop the old dashboard first with: python kill_dashboard.py")
    sys.exit(1)


def main() -> None:
    ensure_venv()
    sys.path.insert(0, str(BASE_DIR))

    import uvicorn

    from app.config import load_config
    from app.main import create_app

    config_path = BASE_DIR / CONFIG_FILE
    config = load_config(config_path)
    server = config.get("server", {})
    host = HOST or str(server.get("host") or "127.0.0.1")
    port = PORT or int(server.get("port") or 8088)
    ensure_port_free(host, port)
    app = create_app(mode=MODE, config_path=config_path)

    print(f"TinyHouse dashboard mode: {MODE}")
    print(f"TinyHouse dashboard URL: http://{host}:{port}/")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
