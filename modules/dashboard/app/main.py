from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi import Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .camera import CameraConfigError, camera_url, stream_camera
from .config import (
    DASHBOARD_BUILD,
    DEFAULT_CONFIG_PATH,
    load_config,
    load_runtime_config,
    public_config,
    save_config,
)
from .health import check_health
from .mqtt_stream import stream_mqtt
from .shell import (
    NativeTerminalError,
    ShellTargetError,
    launch_native_terminal,
    run_shell,
)
from .status import scan, target_status_metadata


BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static"


class CameraUpdate(BaseModel):
    ip: str = ""
    port: int = 80
    scheme: str = "http"
    path: str = "/"
    username: str = ""
    password: str = ""


class NativeTerminalRequest(BaseModel):
    target: str = ""


class DashboardState:
    def __init__(self, mode: str, config_path: Path) -> None:
        self.mode = mode
        self.config_path = config_path
        self.raw_config = load_config(config_path)
        self.config = load_runtime_config(config_path)

    def reload(self) -> None:
        self.raw_config = load_config(self.config_path)
        self.config = load_runtime_config(self.config_path)

    def update_camera(self, update: CameraUpdate) -> Dict[str, Any]:
        camera = self.raw_config.setdefault("camera", {})
        previous_password = str(camera.get("password") or "")
        scheme = update.scheme.strip().lower() or "http"

        if scheme not in {"http", "https"}:
            scheme = "http"

        camera.update(
            {
                "ip": update.ip.strip(),
                "port": update.port,
                "scheme": scheme,
                "path": update.path.strip() or "/",
                "username": update.username.strip(),
                "password": previous_password
                if update.password == "configured"
                else update.password,
            }
        )
        save_config(self.raw_config, self.config_path)
        self.config = load_runtime_config(self.config_path)
        return camera


def create_app(mode: str, config_path: Path = DEFAULT_CONFIG_PATH) -> FastAPI:
    state = DashboardState(mode=mode, config_path=config_path)
    app = FastAPI(title="TinyHouse Dashboard")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.middleware("http")
    async def add_no_cache_headers(request: Any, call_next: Any) -> Response:
        response = await call_next(request)

        if request.url.path.startswith("/static/") or request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"

        response.headers["X-TinyHouse-Dashboard-Build"] = DASHBOARD_BUILD
        return response

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/config")
    async def config() -> Dict[str, Any]:
        state.reload()
        payload = public_config(state.config, state.mode)
        payload["camera_url"] = camera_url(state.config)
        return payload

    @app.get("/api/version")
    async def version() -> Dict[str, Any]:
        return {
            "build": DASHBOARD_BUILD,
            "config_path": str(state.config_path),
            "mode": state.mode,
        }

    @app.get("/api/status")
    async def status() -> Dict[str, Any]:
        state.reload()
        health = await check_health(state.config, state.mode)

        if state.mode == "tunnel" and not health["connected"]:
            return {
                "mode": state.mode,
                "checked_at": health["checked_at"],
                "connection": health,
                "targets": [
                    {
                        "name": target.get("name", target.get("ip", "")),
                        "ip": target.get("ip", ""),
                        "role": target.get("role", ""),
                        "public_host": target.get("public_host", ""),
                        "reachable": False,
                        "ports": [
                            {
                                "port": int(port),
                                "open": False,
                            }
                            for port in target.get("ports", [])
                        ],
                        "checked_at": health["checked_at"],
                        "error": health["detail"],
                        **target_status_metadata(target),
                    }
                    for target in state.config.get("targets", [])
                ],
            }

        payload = await scan(state.config, state.mode)
        payload["connection"] = health
        return payload

    @app.get("/api/health")
    async def health() -> Dict[str, Any]:
        state.reload()
        return await check_health(state.config, state.mode)

    @app.post("/api/camera")
    async def update_camera(update: CameraUpdate) -> Dict[str, Any]:
        state.update_camera(update)
        return {
            "camera": public_config(state.config, state.mode)["camera"],
            "camera_url": camera_url(state.config),
        }

    @app.get("/api/camera/feed")
    async def camera_feed() -> StreamingResponse:
        state.reload()

        try:
            content_type, iterator = stream_camera(state.config, state.mode)
        except CameraConfigError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

        return StreamingResponse(iterator, media_type=content_type)

    @app.post("/api/shell/native-terminal")
    async def open_native_terminal(request: NativeTerminalRequest) -> Dict[str, str]:
        state.reload()

        try:
            return launch_native_terminal(
                state.config,
                state.mode,
                state.config_path,
                target_id=request.target.strip() or None,
            )
        except ShellTargetError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except NativeTerminalError as error:
            raise HTTPException(status_code=500, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error

    @app.get("/api/web-static/{asset_path:path}")
    async def camera_web_static(asset_path: str, request: Request) -> StreamingResponse:
        state.reload()
        query = request.url.query
        camera_path = f"/web-static/{asset_path}"

        if query:
            camera_path = f"{camera_path}?{query}"

        try:
            content_type, iterator = stream_camera(
                state.config,
                state.mode,
                path=camera_path,
            )
        except CameraConfigError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

        return StreamingResponse(iterator, media_type=content_type)

    @app.websocket("/ws/shell")
    async def shell_socket(websocket: WebSocket) -> None:
        state.reload()
        target_id = websocket.query_params.get("target")
        await run_shell(websocket, state.config, state.mode, target_id=target_id)

    @app.websocket("/ws/mqtt")
    async def mqtt_socket(websocket: WebSocket) -> None:
        state.reload()
        target_id = websocket.query_params.get("target")
        await stream_mqtt(websocket, state.config, state.mode, target_id=target_id)

    @app.exception_handler(Exception)
    async def unhandled(_: Any, error: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": str(error)},
        )

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the TinyHouse dashboard.")
    parser.add_argument(
        "--mode",
        choices=["local", "tunnel"],
        default="tunnel",
        help="Use local on the Management PC and tunnel outside the TinyHouse network.",
    )
    parser.add_argument(
        "--on-management-pc",
        action="store_true",
        help="Shortcut for --mode local.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the dashboard config file.",
    )
    parser.add_argument("--host", default=None, help="HTTP bind host.")
    parser.add_argument("--port", type=int, default=None, help="HTTP bind port.")
    return parser.parse_args()


def cli() -> None:
    args = parse_args()
    mode = "local" if args.on_management_pc else args.mode
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    server = config.get("server", {})
    host = args.host or str(server.get("host") or "127.0.0.1")
    port = args.port or int(server.get("port") or 8088)
    app = create_app(mode=mode, config_path=config_path)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli()
