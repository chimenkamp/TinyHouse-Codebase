from __future__ import annotations

import getpass
import re
import shlex
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import paramiko


class SSHBackend:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def _alias_from_command(self) -> str:
        ssh_config = self.config.get("management_pc", {})
        command = str(ssh_config.get("ssh_command") or "ssh tinyhouse")
        parts = shlex.split(command)

        for part in reversed(parts):
            if not part.startswith("-") and part != "ssh":
                return part

        return str(ssh_config.get("host") or "tinyhouse").strip()

    def _lookup_ssh_config(self, alias: str) -> Dict[str, Any]:
        path = Path.home() / ".ssh" / "config"

        if not path.exists():
            return {}

        with path.open("r", encoding="utf-8") as file:
            ssh_config = paramiko.SSHConfig()
            ssh_config.parse(file)
            return ssh_config.lookup(alias)

    def _key_filenames(self, config: Dict[str, Any], ssh_entry: Dict[str, Any]) -> List[str]:
        configured_key = config.get("private_key_file")
        identity_files = ssh_entry.get("identityfile") or []

        if configured_key:
            identity_files = [configured_key]

        if isinstance(identity_files, str):
            identity_files = [identity_files]

        return [
            str(Path(str(path)).expanduser())
            for path in identity_files
            if str(path).strip()
        ]

    def _connection_backend(self) -> str:
        config = self.config.get("management_pc", {})
        return str(config.get("connection_backend") or "paramiko").lower()

    def _ssh_command_parts(self) -> List[str]:
        config = self.config.get("management_pc", {})
        command = str(config.get("ssh_command") or "ssh tinyhouse")
        parts = shlex.split(command)

        if parts and Path(parts[0]).name == "ssh" and "-tt" not in parts:
            parts.insert(1, "-tt")

        return parts

    def _connect_details(self) -> Tuple[str, int, str, Optional[str], List[str]]:
        config = self.config.get("management_pc", {})
        alias = self._alias_from_command()
        ssh_entry = self._lookup_ssh_config(alias)
        configured_host = str(config.get("host") or "").strip()
        ssh_host = str(ssh_entry.get("hostname") or "").strip()
        host = ssh_host or configured_host or alias
        configured_port = config.get("port")
        ssh_port = ssh_entry.get("port")
        port = int(ssh_port or configured_port or 22)
        username = str(
            config.get("username")
            or ssh_entry.get("user")
            or getpass.getuser()
        )
        password = config.get("password") or None
        key_filenames = self._key_filenames(config, ssh_entry)
        return host, port, username, password, key_filenames

    def public_connect_details(self) -> Dict[str, Any]:
        config = self.config.get("management_pc", {})
        alias = self._alias_from_command()
        ssh_entry = self._lookup_ssh_config(alias)
        host, port, username, password, key_filenames = self._connect_details()
        return {
            "alias": alias,
            "host": host,
            "port": port,
            "username": username,
            "password_configured": bool(password),
            "key_files": key_filenames,
            "connection_backend": self._connection_backend(),
            "ssh_config_found": bool(ssh_entry),
            "ssh_config_hostname": str(ssh_entry.get("hostname") or ""),
            "configured_host": str(config.get("host") or ""),
        }

    def connect(self) -> paramiko.SSHClient:
        config = self.config.get("management_pc", {})
        host, port, username, password, key_filenames = self._connect_details()
        timeout = int(config.get("connect_timeout_seconds") or 8)
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            key_filename=key_filenames or None,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            allow_agent=True,
            look_for_keys=True,
        )
        return client

    def run_command(self, command: str, timeout: int = 30) -> Tuple[int, str, str]:
        if self._connection_backend() == "openssh":
            return self._run_command_with_openssh(command, timeout)

        client = self.connect()

        try:
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            exit_code = stdout.channel.recv_exit_status()
            return exit_code, out, err
        finally:
            client.close()

    def _run_command_with_openssh(self, command: str, timeout: int) -> Tuple[int, str, str]:
        try:
            import pexpect
        except ImportError as error:
            return 1, "", f"OpenSSH backend requires pexpect: {error}"

        config = self.config.get("management_pc", {})
        password = str(config.get("password") or "")
        command_parts = self._ssh_command_parts()
        end_marker = f"__TH_DASH_END_{uuid.uuid4().hex}__"
        child = pexpect.spawn(
            command_parts[0],
            command_parts[1:],
            encoding="utf-8",
            timeout=max(8, min(timeout, 90)),
            dimensions=(40, 2400),
        )
        child.setwinsize(40, 2400)
        transcript = ""

        try:
            transcript += self._drive_openssh_login(child, password, min(timeout, 18))
            child.send(f"{command}\r")
            child.send(f"echo {end_marker}\r")
            child.expect(end_marker, timeout=timeout)
            output = self._clean_pty_output(child.before, command)
            child.send("exit\r")
            return 0, output, transcript
        except pexpect.exceptions.TIMEOUT:
            return 124, self._clean_pty_output(child.before, command), transcript + "\nTimed out waiting for SSH command output."
        except pexpect.exceptions.EOF:
            return 1, self._clean_pty_output(child.before, command), transcript + "\nSSH session ended before command completed."
        finally:
            child.close(force=True)

    def _drive_openssh_login(self, child: Any, password: str, timeout: int) -> str:
        import pexpect

        transcript = ""
        deadline = time.monotonic() + max(6, timeout)
        prompt_pattern = r"(?i)(?:[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+\s+[A-Z]:\\[^\r\n>]*>|PS\s+[A-Z]:\\[^\r\n>]*>|[#$]\s*)"
        patterns = [
            r"(?i)are you sure you want to continue connecting",
            r"(?i)(?:password|passphrase).*:",
            prompt_pattern,
            pexpect.EOF,
            pexpect.TIMEOUT,
        ]

        while time.monotonic() < deadline:
            remaining = max(1, int(deadline - time.monotonic()))
            index = child.expect(patterns, timeout=min(4, remaining))
            transcript += child.before or ""
            transcript += child.after if isinstance(child.after, str) else ""

            if index == 0:
                child.sendline("yes")
                continue

            if index == 1:
                if not password:
                    return transcript + "\nPassword prompt appeared but no password is configured."
                child.sendline(password)
                continue

            if index == 2:
                return transcript

            if index == 3:
                return transcript + "\nSSH session ended during login."

            if index == 4:
                child.sendline("")
                continue

        return transcript + "\nSSH login prompt was not detected before timeout."

    def _clean_pty_output(self, text: str, command: str) -> str:
        text = self._strip_terminal_codes(text)
        lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
        cleaned: List[str] = []

        for line in lines:
            stripped = line.strip()

            if not stripped:
                continue

            if stripped == command.strip():
                continue

            if stripped.startswith("echo __TH_DASH_"):
                continue

            if stripped == "echo":
                continue

            if re.match(
                r"^(PS\s+[A-Z]:\\[^>]*>|[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+\s+[A-Z]:\\[^>]*>)\s*$",
                stripped,
            ):
                continue

            cleaned.append(stripped)

        return "\n".join(cleaned).strip()

    def _strip_terminal_codes(self, text: str) -> str:
        text = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", text)
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        return text
