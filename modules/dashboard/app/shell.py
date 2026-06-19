from __future__ import annotations

import asyncio
import os
import platform
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import WebSocket, WebSocketDisconnect

from .ssh_backend import SSHBackend


class ShellTargetError(ValueError):
    pass


class NativeTerminalError(RuntimeError):
    pass


async def run_shell(
    websocket: WebSocket,
    config: Dict[str, Any],
    mode: str,
    target_id: Optional[str] = None,
) -> None:
    await websocket.accept()

    if target_id:
        try:
            await _run_target_shell(websocket, config, mode, target_id)
        except ShellTargetError as error:
            await websocket.send_text(f"{error}\r\n")
            await websocket.close()
        return

    if mode == "local":
        await _run_local_shell(websocket, config)
        return

    await _run_ssh_shell(websocket, config)


def launch_native_terminal(
    config: Dict[str, Any],
    mode: str,
    config_path: Path,
    target_id: Optional[str] = None,
) -> Dict[str, str]:
    label = native_terminal_label(config, mode, target_id)
    command = _native_terminal_helper_command(config_path, mode, target_id)
    _open_native_terminal(command)
    return {
        "label": label,
        "command": command,
    }


def native_terminal_label(
    config: Dict[str, Any],
    mode: str,
    target_id: Optional[str] = None,
) -> str:
    if target_id:
        target = _find_target(config, target_id)
        return str(
            target.get("name")
            or target.get("inventory_hostname")
            or target.get("ansible_name")
            or target.get("ip")
            or "target"
        )

    return "Local shell" if mode == "local" else "Management PC"


def native_terminal_command(
    config: Dict[str, Any],
    mode: str,
    target_id: Optional[str] = None,
) -> Tuple[List[str], str]:
    if target_id:
        target = _find_target(config, target_id)

        if target.get("shell_transport") == "management_wsl":
            return _native_management_wsl_target_command(config, mode, target)

        command_parts, _, label = _target_shell_command(config, target, mode)
        return command_parts, label

    if mode == "local":
        return _local_terminal_command(config), "Local shell"

    return SSHBackend(config)._ssh_command_parts(), "Management PC"


def run_native_terminal_session(
    config: Dict[str, Any],
    mode: str,
    target_id: Optional[str] = None,
) -> None:
    if target_id:
        target = _find_target(config, target_id)

        if target.get("shell_transport") == "management_wsl":
            _run_native_management_wsl_target_session(config, mode, target)
            return

        command_parts, password, label = _target_shell_command(config, target, mode)
        _run_native_command_session(
            command_parts=command_parts,
            password=password,
            label=label,
            login_helper=SSHBackend(config),
            drive_login=bool(password),
        )
        return

    if mode == "local":
        _exec_native_command(_local_terminal_command(config))
        return

    ssh = SSHBackend(config)
    _run_native_command_session(
        command_parts=ssh._ssh_command_parts(),
        password=str(config.get("management_pc", {}).get("password") or ""),
        label="Management PC",
        login_helper=ssh,
        drive_login=True,
    )


async def _run_ssh_shell(websocket: WebSocket, config: Dict[str, Any]) -> None:
    ssh = SSHBackend(config)

    if ssh._connection_backend() == "openssh":
        await _run_openssh_shell(
            websocket=websocket,
            command_parts=ssh._ssh_command_parts(),
            password=str(config.get("management_pc", {}).get("password") or ""),
            label="Management PC",
            login_helper=ssh,
            drive_login=True,
        )
        return

    client = await asyncio.to_thread(ssh.connect)
    channel = client.invoke_shell(width=120, height=36)

    async def reader() -> None:
        while True:
            if channel.recv_ready():
                data = channel.recv(4096).decode("utf-8", errors="replace")
                await websocket.send_text(data)
            elif channel.exit_status_ready():
                break
            else:
                await asyncio.sleep(0.03)

    async def writer() -> None:
        while True:
            text = await websocket.receive_text()
            channel.send(text)

    tasks = [
        asyncio.create_task(reader()),
        asyncio.create_task(writer()),
    ]

    try:
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            task.result()
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        channel.close()
        client.close()


async def _run_target_shell(
    websocket: WebSocket,
    config: Dict[str, Any],
    mode: str,
    target_id: str,
) -> None:
    target = _find_target(config, target_id)

    if target.get("shell_transport") == "management_wsl":
        await _run_management_wsl_target_shell(websocket, config, mode, target)
        return

    command_parts, password, label = _target_shell_command(config, target, mode)
    await _run_openssh_shell(
        websocket=websocket,
        command_parts=command_parts,
        password=password,
        label=label,
        login_helper=SSHBackend(config),
        drive_login=bool(password),
    )


async def _run_management_wsl_target_shell(
    websocket: WebSocket,
    config: Dict[str, Any],
    mode: str,
    target: Dict[str, Any],
) -> None:
    label = str(
        target.get("name")
        or target.get("inventory_hostname")
        or target.get("ansible_name")
        or "target"
    )
    wsl_command = _wsl_ssh_command(target, config)

    if mode == "local":
        command_parts = ["wsl.exe", "-e", "sh", "-lc", f"exec {wsl_command}"]
        await _run_openssh_shell(
            websocket=websocket,
            command_parts=command_parts,
            password="",
            label=label,
            login_helper=SSHBackend(config),
            drive_login=False,
        )
        return

    ssh = SSHBackend(config)
    await _run_openssh_shell(
        websocket=websocket,
        command_parts=ssh._ssh_command_parts(),
        password=str(config.get("management_pc", {}).get("password") or ""),
        label=label,
        login_helper=ssh,
        drive_login=True,
        startup_command=f'wsl.exe -e sh -lc "exec {wsl_command}"',
    )


def _native_management_wsl_target_command(
    config: Dict[str, Any],
    mode: str,
    target: Dict[str, Any],
) -> Tuple[List[str], str]:
    label = str(
        target.get("name")
        or target.get("inventory_hostname")
        or target.get("ansible_name")
        or "target"
    )
    wsl_command = _wsl_ssh_command(target, config)

    if mode == "local":
        return ["wsl.exe", "-e", "sh", "-lc", f"exec {wsl_command}"], label

    startup_command = f'wsl.exe -e sh -lc "exec {wsl_command}"'
    return SSHBackend(config)._ssh_command_parts() + [startup_command], label


def _run_native_management_wsl_target_session(
    config: Dict[str, Any],
    mode: str,
    target: Dict[str, Any],
) -> None:
    label = str(
        target.get("name")
        or target.get("inventory_hostname")
        or target.get("ansible_name")
        or "target"
    )
    wsl_command = _wsl_ssh_command(target, config)

    if mode == "local":
        _exec_native_command(["wsl.exe", "-e", "sh", "-lc", f"exec {wsl_command}"])
        return

    ssh = SSHBackend(config)
    _run_native_command_session(
        command_parts=ssh._ssh_command_parts(),
        password=str(config.get("management_pc", {}).get("password") or ""),
        label=label,
        login_helper=ssh,
        drive_login=True,
        startup_command=f'wsl.exe -e sh -lc "exec {wsl_command}"',
    )


async def _run_openssh_shell(
    websocket: WebSocket,
    command_parts: List[str],
    password: str,
    label: str,
    login_helper: SSHBackend,
    drive_login: bool,
    startup_command: Optional[str] = None,
) -> None:
    try:
        import pexpect
    except ImportError as error:
        await websocket.send_text(f"OpenSSH shell requires pexpect: {error}\r\n")
        await websocket.close()
        return

    if not command_parts:
        await websocket.send_text("No SSH command is configured.\r\n")
        await websocket.close()
        return

    await websocket.send_text(f"Connecting to {label}...\r\n")
    await websocket.send_text(f"$ {_quoted_command(command_parts)}\r\n")

    try:
        child = pexpect.spawn(
            command_parts[0],
            command_parts[1:],
            encoding="utf-8",
            timeout=8,
            dimensions=(40, 160),
        )
    except Exception as error:
        await websocket.send_text(f"SSH command could not start: {error}\r\n")
        await websocket.close()
        return

    child.setwinsize(40, 160)

    async def reader() -> None:
        while child.isalive():
            try:
                data = child.read_nonblocking(size=4096, timeout=0)
            except pexpect.exceptions.TIMEOUT:
                await asyncio.sleep(0.03)
                continue
            except pexpect.exceptions.EOF:
                break

            if data:
                await websocket.send_text(data)

    async def writer() -> None:
        while child.isalive():
            text = await websocket.receive_text()
            child.send(text)

    tasks: List[asyncio.Task[None]] = []

    try:
        if drive_login:
            transcript = await asyncio.to_thread(
                login_helper._drive_openssh_login,
                child,
                password,
                24,
            )

            if transcript.strip():
                await websocket.send_text(transcript)

        if startup_command:
            await websocket.send_text(f"$ {startup_command}\r\n")
            child.sendline(startup_command)

        tasks = [
            asyncio.create_task(reader()),
            asyncio.create_task(writer()),
        ]
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            task.result()
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    except pexpect.exceptions.ExceptionPexpect as error:
        await websocket.send_text(f"\r\nSSH shell failed: {error}\r\n")
    finally:
        for task in tasks:
            task.cancel()
        child.close(force=True)


def _find_target(config: Dict[str, Any], target_id: str) -> Dict[str, Any]:
    target_id = target_id.strip().lower()

    for target in config.get("targets", []):
        names = {
            str(target.get("ip") or "").lower(),
            str(target.get("name") or "").lower(),
            str(target.get("shell_target") or "").lower(),
            str(target.get("ansible_name") or "").lower(),
            str(target.get("inventory_hostname") or "").lower(),
            _slug(str(target.get("name") or "")),
            _slug(str(target.get("ansible_name") or "")),
            _slug(str(target.get("inventory_hostname") or "")),
        }

        if target_id in names:
            return target

    raise ShellTargetError(f"No configured shell target matches {target_id}.")


def _target_shell_command(
    config: Dict[str, Any],
    target: Dict[str, Any],
    mode: str,
) -> Tuple[List[str], str, str]:
    label = str(target.get("name") or target.get("ip") or "target")
    shell_config = config.get("shell", {})
    password = str(target.get("shell_password") or "")
    identity_file = str(
        target.get("shell_identity_file")
        or shell_config.get("identity_file")
        or ""
    ).strip()
    identities_only = _bool_option(
        target.get("shell_identities_only", shell_config.get("identities_only")),
        default=False,
    )
    password_authentication = _bool_option(
        target.get(
            "shell_password_authentication",
            shell_config.get("password_authentication"),
        ),
        default=False,
    )
    keyboard_authentication = _bool_option(
        target.get(
            "shell_keyboard_interactive_authentication",
            shell_config.get("keyboard_interactive_authentication"),
        ),
        default=False,
    )
    strict_host_key = str(
        shell_config.get("strict_host_key_checking")
        or "accept-new"
    )

    if target.get("shell_command"):
        command_parts = _expand_command_paths(
            _ensure_tty(shlex.split(str(target["shell_command"])))
        )
        command_parts = _apply_ssh_auth_options(
            command_parts=command_parts,
            identity_file=identity_file,
            identities_only=identities_only,
            password=password,
            password_authentication=password_authentication,
            keyboard_authentication=keyboard_authentication,
            strict_host_key=strict_host_key,
        )
        return command_parts, password, label

    if _is_management_target(target):
        ssh = SSHBackend(config)
        return (
            ssh._ssh_command_parts(),
            str(config.get("management_pc", {}).get("password") or ""),
            label,
        )

    user = str(
        target.get("shell_user")
        or config.get("shell", {}).get("default_user")
        or "admin"
    )

    if mode == "local":
        host = str(target.get("ip") or "").strip()
        port = _private_shell_port(target)
    else:
        host = str(target.get("public_host") or "").strip()
        port = _public_shell_port(target)

    if not host or not port:
        raise ShellTargetError(f"{label} has no configured SSH route for {mode} mode.")

    command_parts = [
        "ssh",
        "-tt",
        "-o",
        f"StrictHostKeyChecking={strict_host_key}",
        "-o",
        "ServerAliveInterval=20",
        "-o",
        "ServerAliveCountMax=3",
    ]

    if identity_file:
        command_parts.extend(
            [
                "-i",
                os.path.expanduser(identity_file),
            ]
        )

    if identities_only:
        command_parts.extend(
            [
                "-o",
                "IdentitiesOnly=yes",
            ]
        )

    if not password:
        preferred_authentications = ["publickey"]

        if password_authentication:
            preferred_authentications.append("password")

        if keyboard_authentication:
            preferred_authentications.append("keyboard-interactive")

        command_parts.extend(
            [
                "-o",
                f"PasswordAuthentication={'yes' if password_authentication else 'no'}",
                "-o",
                f"KbdInteractiveAuthentication={'yes' if keyboard_authentication else 'no'}",
                "-o",
                f"PreferredAuthentications={','.join(preferred_authentications)}",
            ]
        )

    command_parts.extend(
        [
            "-p",
            str(port),
            f"{user}@{host}",
        ]
    )

    return command_parts, password, label


def _wsl_ssh_command(target: Dict[str, Any], config: Dict[str, Any]) -> str:
    shell_config = config.get("shell", {})
    host = str(target.get("ansible_host") or target.get("public_host") or "").strip()
    port = int(target.get("ansible_port") or _public_shell_port(target) or 22)
    user = str(
        target.get("ansible_user")
        or target.get("shell_user")
        or shell_config.get("default_user")
        or "admin"
    )
    identity_file = str(
        target.get("ansible_ssh_private_key_file")
        or target.get("shell_identity_file")
        or shell_config.get("identity_file")
        or "~/.ssh/id_ed25519"
    ).strip()
    strict_host_key = str(
        shell_config.get("strict_host_key_checking")
        or "accept-new"
    )

    if not host:
        raise ShellTargetError("Inventory target has no ansible_host/public_host.")

    parts = [
        "ssh",
        "-tt",
        "-o",
        f"StrictHostKeyChecking={strict_host_key}",
        "-o",
        "ServerAliveInterval=20",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "KbdInteractiveAuthentication=no",
        "-o",
        "PreferredAuthentications=publickey",
    ]

    if identity_file:
        parts.extend(["-i", identity_file])

    parts.extend(["-p", str(port), f"{user}@{host}"])
    return " ".join(_quote_wsl_shell_part(part) for part in parts)


def _quote_wsl_shell_part(part: str) -> str:
    if part.startswith("~/"):
        return part

    return shlex.quote(part)


def _is_management_target(target: Dict[str, Any]) -> bool:
    name = str(target.get("name") or "").lower()
    role = str(target.get("role") or "").lower()
    return "management" in name or role == "management"


def _public_shell_port(target: Dict[str, Any]) -> Optional[int]:
    configured = target.get("shell_public_port")

    if configured:
        return int(configured)

    public_ports = target.get("public_ports", [])
    return int(public_ports[0]) if public_ports else None


def _private_shell_port(target: Dict[str, Any]) -> Optional[int]:
    configured = target.get("shell_port")

    if configured:
        return int(configured)

    ports = [int(port) for port in target.get("ports", [])]
    return 22 if 22 in ports else None


def _ensure_tty(command_parts: List[str]) -> List[str]:
    if command_parts and os.path.basename(command_parts[0]) == "ssh" and "-tt" not in command_parts:
        command_parts.insert(1, "-tt")

    return command_parts


def _expand_command_paths(command_parts: List[str]) -> List[str]:
    return [
        os.path.expanduser(part) if part == "~" or part.startswith("~/") else part
        for part in command_parts
    ]


def _apply_ssh_auth_options(
    command_parts: List[str],
    identity_file: str,
    identities_only: bool,
    password: str,
    password_authentication: bool,
    keyboard_authentication: bool,
    strict_host_key: str,
) -> List[str]:
    if not command_parts or os.path.basename(command_parts[0]) != "ssh":
        return command_parts

    options: List[str] = []

    if strict_host_key and not _has_ssh_option(command_parts, "StrictHostKeyChecking"):
        options.extend(["-o", f"StrictHostKeyChecking={strict_host_key}"])

    if identity_file and not _has_identity_file(command_parts):
        options.extend(["-i", os.path.expanduser(identity_file)])

    if identities_only and not _has_ssh_option(command_parts, "IdentitiesOnly"):
        options.extend(["-o", "IdentitiesOnly=yes"])

    if not password:
        preferred_authentications = ["publickey"]

        if password_authentication:
            preferred_authentications.append("password")

        if keyboard_authentication:
            preferred_authentications.append("keyboard-interactive")

        if not _has_ssh_option(command_parts, "PasswordAuthentication"):
            options.extend(
                [
                    "-o",
                    f"PasswordAuthentication={'yes' if password_authentication else 'no'}",
                ]
            )

        if not _has_ssh_option(command_parts, "KbdInteractiveAuthentication"):
            options.extend(
                [
                    "-o",
                    f"KbdInteractiveAuthentication={'yes' if keyboard_authentication else 'no'}",
                ]
            )

        if not _has_ssh_option(command_parts, "PreferredAuthentications"):
            options.extend(
                [
                    "-o",
                    f"PreferredAuthentications={','.join(preferred_authentications)}",
                ]
            )

    if not options:
        return command_parts

    insert_at = _ssh_option_insert_index(command_parts)
    return command_parts[:insert_at] + options + command_parts[insert_at:]


def _has_identity_file(command_parts: List[str]) -> bool:
    if "-i" in command_parts:
        return True

    return _has_ssh_option(command_parts, "IdentityFile")


def _has_ssh_option(command_parts: List[str], name: str) -> bool:
    for index, part in enumerate(command_parts):
        if part.startswith(f"-o{name}="):
            return True

        if part == "-o" and index + 1 < len(command_parts):
            option = command_parts[index + 1]

            if option == name or option.startswith(f"{name}="):
                return True

    return False


def _ssh_option_insert_index(command_parts: List[str]) -> int:
    options_with_values = {
        "-b",
        "-c",
        "-D",
        "-E",
        "-e",
        "-F",
        "-I",
        "-i",
        "-J",
        "-L",
        "-l",
        "-m",
        "-O",
        "-o",
        "-p",
        "-Q",
        "-R",
        "-S",
        "-W",
        "-w",
    }
    index = 1

    while index < len(command_parts):
        part = command_parts[index]

        if not part.startswith("-"):
            return index

        if part in options_with_values and index + 1 < len(command_parts):
            index += 2
            continue

        index += 1

    return len(command_parts)


def _bool_option(value: Any, default: bool) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _quoted_command(command_parts: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in command_parts)


def _platform_command_text(command_parts: List[str]) -> str:
    if platform.system().lower().startswith("windows"):
        return subprocess.list2cmdline(command_parts)

    return _quoted_command(command_parts)


def _native_terminal_helper_command(
    config_path: Path,
    mode: str,
    target_id: Optional[str],
) -> str:
    base_dir = Path(__file__).resolve().parents[1]
    parts = [
        sys.executable,
        "-m",
        "app.native_terminal",
        "--mode",
        mode,
        "--config",
        str(config_path),
    ]

    if target_id:
        parts.extend(["--target", target_id])

    if platform.system().lower().startswith("windows"):
        return (
            f"cd /d {subprocess.list2cmdline([str(base_dir)])} && "
            f"{subprocess.list2cmdline(parts)}"
        )

    return f"cd {shlex.quote(str(base_dir))} && {_quoted_command(parts)}"


def _run_native_command_session(
    command_parts: List[str],
    password: str,
    label: str,
    login_helper: SSHBackend,
    drive_login: bool,
    startup_command: Optional[str] = None,
) -> None:
    try:
        import pexpect
    except ImportError as error:
        raise NativeTerminalError(f"Native terminal SSH requires pexpect: {error}") from error

    if not command_parts:
        raise NativeTerminalError("No SSH command is configured.")

    print(f"Connecting to {label}...")
    print(f"$ {_quoted_command(command_parts)}")
    child = pexpect.spawn(
        command_parts[0],
        command_parts[1:],
        encoding="utf-8",
        timeout=8,
        dimensions=(40, 160),
    )
    child.setwinsize(40, 160)

    try:
        if drive_login:
            transcript = login_helper._drive_openssh_login(child, password, 24)

            if transcript.strip():
                print(transcript, end="" if transcript.endswith("\n") else "\n")

        if startup_command:
            print(f"$ {startup_command}")
            child.sendline(startup_command)

        child.interact()
    finally:
        child.close(force=True)


def _exec_native_command(command_parts: List[str]) -> None:
    if not command_parts:
        raise NativeTerminalError("No terminal command is configured.")

    os.execvp(command_parts[0], command_parts)


def _local_terminal_command(config: Dict[str, Any]) -> List[str]:
    shell_config = config.get("local", {}).get("shell", {})

    if os.name == "nt":
        return [str(shell_config.get("windows") or "powershell.exe")]

    return [str(shell_config.get("unix") or os.environ.get("SHELL") or "/bin/bash")]


def _open_native_terminal(command: str) -> None:
    system = platform.system().lower()

    if system == "darwin":
        _open_macos_terminal(command)
        return

    if system.startswith("windows"):
        _open_windows_terminal(command)
        return

    _open_linux_terminal(command)


def _open_macos_terminal(command: str) -> None:
    script = (
        'tell application "Terminal"\n'
        "  activate\n"
        f"  do script {_applescript_string(command)}\n"
        "end tell"
    )
    subprocess.Popen(
        ["osascript", "-e", script],
        close_fds=True,
        start_new_session=True,
    )


def _applescript_string(value: str) -> str:
    escaped = (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


def _open_windows_terminal(command: str) -> None:
    subprocess.Popen(
        [
            "cmd.exe",
            "/c",
            "start",
            "",
            "powershell.exe",
            "-NoExit",
            "-Command",
            command,
        ],
        close_fds=True,
    )


def _open_linux_terminal(command: str) -> None:
    shell_command = f"{command}; exec $SHELL"
    candidates = [
        ["x-terminal-emulator", "-e", "sh", "-lc", shell_command],
        ["gnome-terminal", "--", "sh", "-lc", shell_command],
        ["konsole", "-e", "sh", "-lc", shell_command],
        ["xfce4-terminal", "-e", f"sh -lc {shlex.quote(shell_command)}"],
        ["xterm", "-e", "sh", "-lc", shell_command],
    ]

    for candidate in candidates:
        try:
            subprocess.Popen(
                candidate,
                close_fds=True,
                start_new_session=True,
            )
            return
        except FileNotFoundError:
            continue

    raise NativeTerminalError("No supported desktop terminal command was found.")


def _slug(value: str) -> str:
    return value.lower().replace(" ", "-")


async def _run_local_shell(websocket: WebSocket, config: Dict[str, Any]) -> None:
    if os.name == "nt":
        await _run_local_pipe_shell(websocket, config)
        return

    await _run_local_pty_shell(websocket, config)


async def _run_local_pty_shell(websocket: WebSocket, config: Dict[str, Any]) -> None:
    import fcntl
    import pty

    shell_config = config.get("local", {}).get("shell", {})
    shell = str(shell_config.get("unix") or os.environ.get("SHELL") or "/bin/bash")
    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        [shell],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )
    os.close(slave_fd)
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    async def reader() -> None:
        while process.poll() is None:
            try:
                data = os.read(master_fd, 4096)
            except BlockingIOError:
                await asyncio.sleep(0.03)
                continue

            if data:
                await websocket.send_text(data.decode("utf-8", errors="replace"))
            else:
                await asyncio.sleep(0.03)

    async def writer() -> None:
        while process.poll() is None:
            text = await websocket.receive_text()
            os.write(master_fd, text.encode("utf-8"))

    tasks = [
        asyncio.create_task(reader()),
        asyncio.create_task(writer()),
    ]

    try:
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            task.result()
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        os.close(master_fd)
        _terminate_process(process)


async def _run_local_pipe_shell(websocket: WebSocket, config: Dict[str, Any]) -> None:
    shell_config = config.get("local", {}).get("shell", {})
    shell = str(shell_config.get("windows") or "powershell.exe")
    process = subprocess.Popen(
        [shell],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
    )

    async def reader() -> None:
        assert process.stdout is not None
        while process.poll() is None:
            data = await asyncio.to_thread(process.stdout.read, 1)
            if data:
                await websocket.send_text(data.decode("utf-8", errors="replace"))

    async def writer() -> None:
        assert process.stdin is not None
        while process.poll() is None:
            text = await websocket.receive_text()
            process.stdin.write(text.encode("utf-8"))
            process.stdin.flush()

    tasks = [
        asyncio.create_task(reader()),
        asyncio.create_task(writer()),
    ]

    try:
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            task.result()
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        _terminate_process(process)


def _terminate_process(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return

    if platform.system().lower().startswith("windows"):
        process.terminate()
        return

    process.terminate()
