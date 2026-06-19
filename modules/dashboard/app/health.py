from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any, Dict

from .ssh_backend import SSHBackend


MARKER = "TINYHOUSE_DASHBOARD_OK"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _management_label(config: Dict[str, Any]) -> str:
    management = config.get("management_pc", {})
    command = str(management.get("ssh_command") or "").strip()
    host = str(management.get("host") or "").strip()
    port = str(management.get("port") or "").strip()

    if command:
        return command

    if host and port:
        return f"{host}:{port}"

    return host or "management pc"


async def check_health(config: Dict[str, Any], mode: str) -> Dict[str, Any]:
    if mode == "local":
        return {
            "mode": mode,
            "connected": True,
            "label": "Local mode",
            "detail": "The dashboard runs checks from this machine.",
            "management": _management_label(config),
            "checked_at": _now(),
        }

    ssh = SSHBackend(config)
    details = ssh.public_connect_details()

    try:
        exit_code, stdout, stderr = await asyncio.to_thread(
            ssh.run_command,
            f"echo {MARKER}",
            12,
        )
    except Exception as error:
        return {
            "mode": mode,
            "connected": False,
            "label": "SSH failed",
            "detail": f"{str(error)}. Target: {details['username']}@{details['host']}:{details['port']}. Alias: {details['alias']}. SSH config found: {details['ssh_config_found']}. Key files: {', '.join(details['key_files']) or 'none'}. Password configured: {details['password_configured']}.",
            "management": _management_label(config),
            "ssh": details,
            "checked_at": _now(),
        }

    output = f"{stdout}\n{stderr}".strip()
    connected = exit_code == 0 and MARKER in output

    return {
        "mode": mode,
        "connected": connected,
        "label": "SSH connected" if connected else "SSH failed",
        "detail": (
            f"Connected to {details['username']}@{details['host']}:{details['port']} through {details['connection_backend']}."
            if connected
            else output if output else f"Exit code {exit_code}"
        ),
        "management": _management_label(config),
        "ssh": details,
        "checked_at": _now(),
    }
