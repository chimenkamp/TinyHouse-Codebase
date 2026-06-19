from __future__ import annotations

import asyncio
import base64
import datetime as dt
import ipaddress
import json
import platform
import socket
import subprocess
from typing import Any, Dict, List

from .ssh_backend import SSHBackend


SHELL_STATUS_KEYS = [
    "shell_capable",
    "shell_target",
    "shell_transport",
    "shell_description",
    "shell_command",
    "ansible_name",
    "inventory_hostname",
    "ansible_host",
    "ansible_port",
    "ansible_user",
]

MQTT_STATUS_KEYS = [
    "mqtt_capable",
    "mqtt_target",
    "mqtt_host",
    "mqtt_port",
    "mqtt_topics",
    "mqtt_topic",
    "mqtt_description",
    "mqtt_tls",
]

TARGET_STATUS_KEYS = SHELL_STATUS_KEYS + MQTT_STATUS_KEYS


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def shell_status_metadata(target: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: target[key]
        for key in SHELL_STATUS_KEYS
        if key in target
    }


def target_status_metadata(target: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: target[key]
        for key in TARGET_STATUS_KEYS
        if key in target
    }


def _ping_command(ip: str) -> List[str]:
    if platform.system().lower().startswith("windows"):
        return ["ping", "-n", "1", "-w", "700", ip]

    return ["ping", "-c", "1", "-W", "1", ip]


def _ping(ip: str) -> bool:
    try:
        output = subprocess.run(
            _ping_command(ip),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return False

    text = f"{output.stdout}\n{output.stderr}".lower()
    return "ttl=" in text or "bytes from" in text


def _port_open(ip: str, port: int, timeout: float = 0.7) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _target_status(target: Dict[str, Any]) -> Dict[str, Any]:
    ip = str(target.get("ip") or "")
    ports = [int(port) for port in target.get("ports", [])]
    public_host = str(target.get("public_host") or "")
    public_ports = [int(port) for port in target.get("public_ports", [])]

    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return {
            "name": target.get("name", ip),
            "ip": ip,
            "role": target.get("role", ""),
            "public_host": target.get("public_host", ""),
            "reachable": False,
            "ports": [],
            "checked_at": _now(),
            "error": "invalid ip",
            **target_status_metadata(target),
        }

    port_results = [
        {
            "port": port,
            "host": ip,
            "scope": "private",
            "open": _port_open(ip, port),
        }
        for port in ports
    ]
    public_port_results = [
        {
            "port": port,
            "host": public_host,
            "scope": "public",
            "open": _port_open(public_host, port),
        }
        for port in public_ports
        if public_host
    ]
    all_ports = port_results + public_port_results

    return {
        "name": target.get("name", ip),
        "ip": ip,
        "role": target.get("role", ""),
        "public_host": public_host,
        "reachable": _ping(ip) or any(result["open"] for result in all_ports),
        "ports": all_ports,
        "checked_at": _now(),
        "error": "",
        **target_status_metadata(target),
    }


async def scan_local(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    targets = config.get("targets", [])
    tasks = [asyncio.to_thread(_target_status, target) for target in targets]
    return await asyncio.gather(*tasks)


def _windows_status_command(targets: List[Dict[str, Any]]) -> str:
    payload = json.dumps(targets)
    script = f"""
$targets = @'
{payload}
'@ | ConvertFrom-Json

function Test-Port {{
    param([string]$HostName, [int]$Port)
    try {{
        $client = [System.Net.Sockets.TcpClient]::new()
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        $success = $async.AsyncWaitHandle.WaitOne(700, $false)
        if ($success) {{
            $client.EndConnect($async) | Out-Null
        }}
        $client.Close()
        return [bool]$success
    }} catch {{
        return $false
    }}
}}

function Test-Ping {{
    param([string]$HostName)
    try {{
        $ping = [System.Net.NetworkInformation.Ping]::new()
        $reply = $ping.Send($HostName, 700)
        return $reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success
    }} catch {{
        return $false
    }}
}}

$output = @()
foreach ($target in $targets) {{
    $ports = @()
    foreach ($port in @($target.ports)) {{
        if ($null -eq $port) {{
            continue
        }}
        $ports += [PSCustomObject]@{{
            port = [int]$port
            host = $target.ip
            scope = "private"
            open = (Test-Port -HostName $target.ip -Port ([int]$port))
        }}
    }}
    foreach ($port in @($target.public_ports)) {{
        if ($null -eq $port -or [string]::IsNullOrWhiteSpace([string]$target.public_host)) {{
            continue
        }}
        $ports += [PSCustomObject]@{{
            port = [int]$port
            host = $target.public_host
            scope = "public"
            open = (Test-Port -HostName $target.public_host -Port ([int]$port))
        }}
    }}
    $reachable = $false
    try {{
        $reachable = Test-Ping -HostName $target.ip
    }} catch {{
        $reachable = $false
    }}
    if (-not $reachable) {{
        foreach ($portState in $ports) {{
            if ($portState.open) {{
                $reachable = $true
            }}
        }}
    }}
    $output += [PSCustomObject]@{{
        name = $target.name
        ip = $target.ip
        role = $target.role
        public_host = $target.public_host
        reachable = [bool]$reachable
        ports = $ports
        checked_at = (Get-Date).ToUniversalTime().ToString("o")
        error = ""
    }}
}}
$output | ConvertTo-Json -Depth 8 -Compress
"""
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return f"powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand {encoded}"


def _linux_status_command(targets: List[Dict[str, Any]]) -> str:
    payload = json.dumps(targets)
    script = r"""
import json
import socket
import subprocess
import datetime
targets = json.loads(%r)
def ping(ip):
    try:
        out = subprocess.run(["ping", "-c", "1", "-W", "1", ip], capture_output=True, text=True, timeout=3)
        text = (out.stdout + "\n" + out.stderr).lower()
        return "ttl=" in text or "bytes from" in text
    except Exception:
        return False
def port_open(ip, port):
    try:
        with socket.create_connection((ip, int(port)), timeout=0.7):
            return True
    except OSError:
        return False
out = []
for target in targets:
    ports = [
        {
            "port": int(port),
            "host": target["ip"],
            "scope": "private",
            "open": port_open(target["ip"], port),
        }
        for port in target.get("ports", [])
    ]
    public_host = target.get("public_host", "")
    ports.extend([
        {
            "port": int(port),
            "host": public_host,
            "scope": "public",
            "open": port_open(public_host, port),
        }
        for port in target.get("public_ports", [])
        if public_host
    ])
    out.append({
        "name": target.get("name", target.get("ip", "")),
        "ip": target.get("ip", ""),
        "role": target.get("role", ""),
        "public_host": public_host,
        "reachable": ping(target.get("ip", "")) or any(item["open"] for item in ports),
        "ports": ports,
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "error": "",
    })
print(json.dumps(out))
""" % payload
    return "python3 -c " + json.dumps(script)


async def scan_tunnel(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    targets = list(config.get("targets", []))
    remote_platform = str(
        config.get("management_pc", {}).get("remote_platform") or "windows"
    ).lower()
    management = config.get("management_pc", {})
    default_chunk_size = 3 if remote_platform.startswith("win") else 8
    chunk_size = max(1, int(management.get("status_chunk_size") or default_chunk_size))
    ssh = SSHBackend(config)
    command_timeout = int(management.get("status_timeout_seconds") or 180)
    statuses: List[Dict[str, Any]] = []

    for chunk in _chunks(targets, chunk_size):
        statuses.extend(
            await _scan_tunnel_chunk(
                ssh=ssh,
                targets=chunk,
                remote_platform=remote_platform,
                command_timeout=command_timeout,
            )
        )

    return await _merge_public_statuses(config, statuses)


async def _scan_tunnel_chunk(
    ssh: SSHBackend,
    targets: List[Dict[str, Any]],
    remote_platform: str,
    command_timeout: int,
) -> List[Dict[str, Any]]:
    command = (
        _windows_status_command(targets)
        if remote_platform.startswith("win")
        else _linux_status_command(targets)
    )

    try:
        exit_code, stdout, stderr = await asyncio.to_thread(
            ssh.run_command,
            command,
            command_timeout,
        )
    except Exception as error:
        return _error_statuses(targets, str(error))

    if exit_code != 0:
        return _error_statuses(
            targets,
            stderr.strip() or f"remote scan failed with {exit_code}",
        )

    try:
        statuses = _load_remote_json(stdout)
        return statuses if isinstance(statuses, list) else [statuses]
    except json.JSONDecodeError:
        return _error_statuses(targets, _private_scan_json_error(stdout))


def _chunks(items: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
    return [
        items[index : index + size]
        for index in range(0, len(items), size)
    ]


def _private_scan_json_error(stdout: str) -> str:
    text = stdout.strip()

    if "Die eingegebene Zeile ist zu lang" in text:
        return "private scan command was too long for Windows"

    if not text:
        return "private scan returned empty output"

    return "private scan returned invalid json"


async def scan(config: Dict[str, Any], mode: str) -> Dict[str, Any]:
    statuses = await scan_local(config) if mode == "local" else await scan_tunnel(config)
    return {
        "mode": mode,
        "checked_at": _now(),
        "targets": statuses,
    }


def _load_remote_json(stdout: str) -> Any:
    text = stdout.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    return json.loads(text)


def _error_statuses(targets: List[Dict[str, Any]], error: str) -> List[Dict[str, Any]]:
    return [
        {
            "name": target.get("name", target.get("ip", "")),
            "ip": target.get("ip", ""),
            "role": target.get("role", ""),
            "public_host": target.get("public_host", ""),
            "reachable": False,
            "ports": [],
            "checked_at": _now(),
            "error": error,
            **target_status_metadata(target),
        }
        for target in targets
    ]


async def _merge_public_statuses(
    config: Dict[str, Any],
    statuses: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    target_by_ip = {
        str(target.get("ip") or ""): target
        for target in config.get("targets", [])
    }
    tasks = [
        asyncio.to_thread(_public_port_results, target_by_ip.get(str(status.get("ip") or ""), {}))
        for status in statuses
    ]
    public_results = await asyncio.gather(*tasks)

    for status, ports in zip(statuses, public_results):
        target = target_by_ip.get(str(status.get("ip") or ""), {})
        status.update(target_status_metadata(target))

        if not ports:
            continue

        existing = status.get("ports") or []
        private_ports = [
            port
            for port in existing
            if port.get("scope") != "public"
        ]
        status["ports"] = private_ports + ports
        status["public_host"] = ports[0].get("host", "")

        if any(port.get("open") for port in ports):
            status["reachable"] = True

            if str(status.get("error") or "").startswith("private scan"):
                status["error"] = "private scan unavailable; public route open"

    return statuses


def _public_port_results(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    public_host = str(target.get("public_host") or "")

    if not public_host:
        return []

    return [
        {
            "port": int(port),
            "host": public_host,
            "scope": "public",
            "open": _port_open(public_host, int(port), timeout=1.5),
        }
        for port in target.get("public_ports", [])
    ]
