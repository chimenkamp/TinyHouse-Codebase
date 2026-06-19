#!/usr/bin/env python3
"""
Collect TinyHouse network, infrastructure, MQTT, Docker, WSL, and Ansible facts.

Run this script directly on the TinyHouse management PC when possible.
The script uses only the Python standard library. It calls local tools when they
exist and writes a timestamped report directory plus a zip archive.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import ipaddress
import json
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path
from typing import Any


RELEVANT_PORTS = [
    21,
    22,
    53,
    80,
    443,
    1883,
    3306,
    33060,
    3389,
    4370,
    5370,
    8083,
    8084,
    8883,
    9090,
    9883,
    18083,
]

DEFAULT_DNAT_PORTS = [
    4021,
    4022,
    4023,
    4024,
    4025,
    4026,
    4027,
    4031,
    4032,
    4041,
    4042,
    4050,
]

DEFAULT_PRIVATE_HOSTS = [
    "192.168.1.1",
    "192.168.1.100",
    "192.168.1.106",
    "192.168.1.121",
    "192.168.1.122",
    "192.168.1.123",
    "192.168.1.124",
    "192.168.1.125",
    "192.168.1.126",
    "192.168.1.127",
    "192.168.1.131",
    "192.168.1.132",
    "192.168.1.141",
    "192.168.1.142",
    "192.168.1.199",
]

SECRET_LINE_RE = re.compile(
    r"(?i)\b("
    r"ansible_(?:become_)?password|"
    r"password|passwd|kennwort|"
    r"wlan key(?: for both bandwidths)?|"
    r"router\s*-->\s*password|"
    r"secret|token|api[_ -]?key"
    r")\b(\s*[:=>-]+\s*)([^\s,;\"']+)"
)


def now_slug() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return value.strip("._") or "unnamed"


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def is_linux() -> bool:
    return platform.system().lower() == "linux"


def is_macos() -> bool:
    return platform.system().lower() == "darwin"


def redact_text(text: str, include_secrets: bool) -> str:
    if include_secrets:
        return text
    text = SECRET_LINE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}<REDACTED>", text)
    text = re.sub(
        r"(?i)(User:\s*[^\r\n]+[\r\n]+Password:\s*)([^\r\n]+)",
        r"\1<REDACTED>",
        text,
    )
    text = re.sub(
        r"(?i)(Password\s+[\"“]?[:=]\s*[\"“]?)([^\"”\r\n]+)",
        r"\1<REDACTED>",
        text,
    )
    return text


class Collector:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.started_at = _dt.datetime.now().isoformat(timespec="seconds")
        self.hostname = socket.gethostname()
        base = Path(args.output_dir) if args.output_dir else Path.cwd()
        self.output_dir = base / f"tinyhouse_collection_{now_slug()}_{safe_name(self.hostname)}"
        self.commands_dir = self.output_dir / "commands"
        self.files_dir = self.output_dir / "files"
        self.remote_dir = self.output_dir / "remote"
        self.network_dir = self.output_dir / "network"
        self.inventory_dir = self.output_dir / "inventories"
        self.command_index: list[dict[str, Any]] = []
        self.summary: dict[str, Any] = {
            "started_at": self.started_at,
            "host": self.hostname,
            "platform": platform.platform(),
            "python": sys.version,
            "output_dir": str(self.output_dir),
            "notes": [],
            "inventories": [],
            "remote_targets": [],
        }

    def prepare(self) -> None:
        for path in [
            self.output_dir,
            self.commands_dir,
            self.files_dir,
            self.remote_dir,
            self.network_dir,
            self.inventory_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def write_text(self, rel_path: str, content: str) -> Path:
        path = self.output_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(redact_text(content, self.args.include_secrets), encoding="utf-8")
        return path

    def write_json(self, rel_path: str, data: Any) -> Path:
        path = self.output_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, indent=2, sort_keys=True, default=str)
        path.write_text(redact_text(text, self.args.include_secrets), encoding="utf-8")
        return path

    def run(
        self,
        name: str,
        command: list[str] | str,
        timeout: int = 30,
        shell: bool = False,
        cwd: Path | None = None,
        rel_dir: str = "commands",
    ) -> dict[str, Any]:
        started = _dt.datetime.now()
        output = ""
        exit_code: int | None = None
        timed_out = False
        error = None
        try:
            proc = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                shell=shell,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                errors="replace",
            )
            output = proc.stdout or ""
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = None
            output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            output += f"\n[TIMEOUT after {timeout}s]\n"
        except Exception as exc:  # noqa: BLE001
            error = repr(exc)
            output = f"[ERROR] {error}\n"

        finished = _dt.datetime.now()
        rel_name = f"{rel_dir}/{safe_name(name)}.txt"
        rendered_command = command if isinstance(command, str) else " ".join(shlex.quote(x) for x in command)
        header = [
            f"name: {name}",
            f"started: {started.isoformat(timespec='seconds')}",
            f"finished: {finished.isoformat(timespec='seconds')}",
            f"timeout_seconds: {timeout}",
            f"exit_code: {exit_code}",
            f"timed_out: {timed_out}",
            f"command: {rendered_command}",
            "",
            "----- output -----",
            "",
        ]
        self.write_text(rel_name, "\n".join(header) + output)
        meta = {
            "name": name,
            "command": rendered_command,
            "timeout_seconds": timeout,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "error": error,
            "output_file": rel_name,
        }
        self.command_index.append(meta)
        return meta

    def command_exists(self, executable: str) -> bool:
        return shutil.which(executable) is not None

    def powershell(self, name: str, script: str, timeout: int = 30) -> None:
        self.run(
            name,
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            timeout=timeout,
        )

    def wsl(self, name: str, script: str, timeout: int = 60) -> None:
        if self.command_exists("wsl.exe"):
            self.run(name, ["wsl.exe", "-e", "sh", "-lc", script], timeout=timeout)

    def collect_local_baseline(self) -> None:
        self.write_json(
            "summary/host_python.json",
            {
                "hostname": self.hostname,
                "fqdn": socket.getfqdn(),
                "platform": platform.platform(),
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python": sys.version,
                "cwd": str(Path.cwd()),
                "script": str(Path(__file__).resolve()),
                "user": os.environ.get("USERNAME") or os.environ.get("USER"),
            },
        )

        common_commands = [
            ("local_hostname", ["hostname"]),
            ("local_whoami", ["whoami"]),
        ]
        for name, cmd in common_commands:
            if self.command_exists(cmd[0]):
                self.run(name, cmd, timeout=10)

        if is_windows():
            self.collect_windows()
        else:
            self.collect_posix()

        self.collect_tool_versions()
        self.collect_local_config_files()
        self.collect_local_mqtt()
        self.collect_docker()

    def collect_tool_versions(self) -> None:
        tools = [
            "python",
            "python3",
            "ssh",
            "scp",
            "ansible",
            "ansible-inventory",
            "docker",
            "mosquitto",
            "mosquitto_sub",
            "mosquitto_pub",
            "emqx",
            "curl",
            "nc",
            "nmap",
        ]
        for tool in tools:
            found = shutil.which(tool)
            if not found:
                continue
            if tool in {"python", "python3"}:
                cmd = [found, "--version"]
            elif tool == "docker":
                cmd = [found, "version"]
            elif tool == "ansible":
                cmd = [found, "--version"]
            elif tool == "ansible-inventory":
                cmd = [found, "--version"]
            elif tool.startswith("mosquitto"):
                cmd = [found, "-h"]
            elif tool == "emqx":
                cmd = [found, "version"]
            else:
                cmd = [found, "-h"]
            self.run(f"tool_{tool}", cmd, timeout=12)

    def collect_windows(self) -> None:
        self.run("windows_ver", ["cmd", "/c", "ver"], timeout=10)
        self.run("windows_ipconfig_all", ["ipconfig", "/all"], timeout=30)
        self.run("windows_route_print", ["route", "print"], timeout=30)
        self.run("windows_arp_a", ["arp", "-a"], timeout=30)
        self.run("windows_netstat_ano", ["netstat", "-ano"], timeout=45)
        self.run("windows_portproxy", ["netsh", "interface", "portproxy", "show", "all"], timeout=20)
        self.run("windows_where_tools", ["cmd", "/c", "where python & where ssh & where docker & where mosquitto & where mosquitto_sub & where emqx & where ansible"], timeout=20)

        self.powershell(
            "windows_computer_info",
            "Get-ComputerInfo | Select-Object CsName,WindowsProductName,WindowsVersion,OsHardwareAbstractionLayer,OsArchitecture | Format-List",
            timeout=30,
        )
        self.powershell("windows_net_adapter", "Get-NetAdapter | Format-Table -AutoSize", timeout=30)
        self.powershell("windows_net_ip_config", "Get-NetIPConfiguration | Format-List *", timeout=30)
        self.powershell(
            "windows_net_routes_ipv4",
            "Get-NetRoute -AddressFamily IPv4 | Sort-Object DestinationPrefix,RouteMetric | Format-Table -AutoSize",
            timeout=30,
        )
        self.powershell(
            "windows_dns_servers",
            "Get-DnsClientServerAddress | Format-Table -AutoSize",
            timeout=30,
        )
        self.powershell(
            "windows_listening_ports",
            "Get-NetTCPConnection -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess | Sort-Object LocalPort | Format-Table -AutoSize",
            timeout=45,
        )
        self.powershell(
            "windows_relevant_processes",
            "Get-Process | Where-Object { $_.ProcessName -match 'mosquitto|emqx|mqtt|docker|ssh|ansible|python|node|http|mysql|mariadb|xrdp|filezilla' } | Select-Object Id,ProcessName,Path | Format-List",
            timeout=30,
        )
        self.powershell(
            "windows_relevant_services",
            "Get-Service | Where-Object { $_.Name -match 'mosquitto|emqx|mqtt|docker|ssh|http|mysql|mariadb|filezilla' -or $_.DisplayName -match 'mosquitto|emqx|mqtt|docker|ssh|http|mysql|mariadb|filezilla' } | Sort-Object Name | Format-Table -AutoSize",
            timeout=30,
        )
        self.powershell(
            "windows_relevant_firewall_rules",
            "Get-NetFirewallRule -Enabled True | Where-Object { $_.DisplayName -match 'ssh|mqtt|mosquitto|emqx|docker|http|https|rdp|mysql|filezilla' } | Select-Object DisplayName,Direction,Action,Profile | Format-Table -AutoSize",
            timeout=45,
        )
        self.run("windows_mosquitto_service_config", ["sc", "qc", "mosquitto"], timeout=15)
        self.run("windows_mosquitto_service_state", ["sc", "queryex", "mosquitto"], timeout=15)

        if self.command_exists("wsl.exe"):
            self.run("wsl_list_verbose", ["wsl.exe", "-l", "-v"], timeout=20)
            self.wsl(
                "wsl_linux_baseline",
                "hostname; whoami; uname -a; cat /etc/os-release 2>/dev/null || true; ip -brief addr 2>/dev/null || true; ip route 2>/dev/null || true; ss -tulpen 2>/dev/null || true; command -v ansible || true; command -v ssh || true; command -v mosquitto_sub || true; command -v docker || true",
                timeout=60,
            )
            self.wsl(
                "wsl_lab_ansible_files",
                "if [ -d ~/lab-ansible ]; then find ~/lab-ansible -maxdepth 2 -type f -print; fi",
                timeout=20,
            )
            self.wsl(
                "wsl_lab_ansible_content_redacted",
                "if [ -d ~/lab-ansible ]; then for f in ~/lab-ansible/*; do [ -f \"$f\" ] && echo \"===== $f\" && sed -n '1,260p' \"$f\"; done; fi",
                timeout=45,
            )
            self.wsl(
                "wsl_ansible_inventory_admin",
                "if [ -d ~/lab-ansible ]; then cd ~/lab-ansible && ansible-inventory -i hosts.admin.ini --list --yaml 2>/dev/null || ansible-inventory -i hosts.admin.ini --list 2>/dev/null || true; fi",
                timeout=45,
            )
            self.wsl(
                "wsl_ansible_ping_admin",
                "if [ -d ~/lab-ansible ]; then cd ~/lab-ansible && ANSIBLE_NOCOLOR=1 ansible -i hosts.admin.ini all -m ping; fi",
                timeout=90,
            )

    def collect_posix(self) -> None:
        posix_commands = [
            ("posix_uname", ["uname", "-a"]),
            ("posix_os_release", ["sh", "-lc", "cat /etc/os-release 2>/dev/null || true"]),
            ("posix_ip_addr", ["sh", "-lc", "ip -brief addr 2>/dev/null || ifconfig -a 2>/dev/null || true"]),
            ("posix_ip_route", ["sh", "-lc", "ip route 2>/dev/null || netstat -rn 2>/dev/null || true"]),
            ("posix_dns", ["sh", "-lc", "resolvectl status 2>/dev/null || scutil --dns 2>/dev/null || cat /etc/resolv.conf 2>/dev/null || true"]),
            ("posix_neighbors", ["sh", "-lc", "ip neigh 2>/dev/null || arp -a 2>/dev/null || true"]),
            ("posix_listening_ports", ["sh", "-lc", "ss -tulpen 2>/dev/null || lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null || netstat -anv 2>/dev/null || true"]),
            ("posix_relevant_processes", ["sh", "-lc", "ps auxww | grep -Ei 'mosquitto|emqx|mqtt|docker|ansible|ssh|http|mysql|mariadb|xrdp' | grep -v grep || true"]),
            ("posix_relevant_services", ["sh", "-lc", "systemctl list-units --type=service --all 2>/dev/null | grep -Ei 'mosquitto|emqx|mqtt|docker|ssh|cockpit|http|mysql|mariadb|xrdp' || true"]),
            ("posix_package_query", ["sh", "-lc", "rpm -qa 2>/dev/null | grep -Ei 'mosquitto|emqx|mqtt|docker|ansible|mysql|mariadb|httpd|xrdp' || dpkg -l 2>/dev/null | grep -Ei 'mosquitto|emqx|mqtt|docker|ansible|mysql|mariadb|apache|xrdp' || true"]),
        ]
        for name, cmd in posix_commands:
            self.run(name, cmd, timeout=45)

        if is_macos():
            self.run("macos_networksetup_list", ["networksetup", "-listallhardwareports"], timeout=30)
            self.run("macos_scutil_proxy", ["scutil", "--proxy"], timeout=20)

    def collect_local_config_files(self) -> None:
        candidates = [
            Path("/etc/mosquitto/mosquitto.conf"),
            Path("/etc/emqx/emqx.conf"),
            Path("/etc/hosts"),
            Path.home() / "lab-ansible" / "hosts.admin.ini",
            Path.home() / "lab-ansible" / "hosts.bootstrap.ini",
            Path.home() / "lab-ansible" / "hosts.ini",
        ]
        if is_windows():
            candidates.extend(
                [
                    Path("C:/Program Files/Mosquitto/mosquitto.conf"),
                    Path("C:/ProgramData/mosquitto/mosquitto.conf"),
                    Path.home() / ".ssh" / "config",
                ]
            )
        else:
            candidates.append(Path.home() / ".ssh" / "config")

        for path in candidates:
            if path.exists() and path.is_file():
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except Exception as exc:  # noqa: BLE001
                    text = f"[ERROR reading {path}: {exc!r}]\n"
                rel = f"files/{safe_name(str(path))}.txt"
                self.write_text(rel, f"source: {path}\n\n{text}")

    def collect_local_mqtt(self) -> None:
        candidate_subs = []
        found = shutil.which("mosquitto_sub")
        if found:
            candidate_subs.append(found)
        if is_windows():
            win_sub = Path("C:/Program Files/Mosquitto/mosquitto_sub.exe")
            if win_sub.exists():
                candidate_subs.append(str(win_sub))

        for index, sub in enumerate(dict.fromkeys(candidate_subs)):
            self.run(
                f"local_mqtt_subscribe_all_{index}",
                [sub, "-h", "127.0.0.1", "-p", "1883", "-t", "#", "-v", "-C", "20", "-W", str(self.args.mqtt_timeout)],
                timeout=self.args.mqtt_timeout + 10,
            )
            self.run(
                f"local_mqtt_subscribe_sys_{index}",
                [sub, "-h", "127.0.0.1", "-p", "1883", "-t", "$SYS/#", "-v", "-C", "20", "-W", str(self.args.mqtt_timeout)],
                timeout=self.args.mqtt_timeout + 10,
            )

    def collect_docker(self) -> None:
        docker = shutil.which("docker")
        if not docker:
            return
        docker_commands = [
            ("docker_info", [docker, "info"]),
            ("docker_ps_all", [docker, "ps", "-a"]),
            ("docker_network_ls", [docker, "network", "ls"]),
            ("docker_volume_ls", [docker, "volume", "ls"]),
            ("docker_context_ls", [docker, "context", "ls"]),
        ]
        for name, cmd in docker_commands:
            self.run(name, cmd, timeout=45)

    def find_inventory_dirs(self) -> list[Path]:
        script_path = Path(__file__).resolve()
        candidates = [
            script_path.parent.parent / "lab-ansible",
            Path.cwd() / "modules" / "administration" / "lab-ansible",
            Path.cwd() / "lab-ansible",
            Path.home() / "lab-ansible",
        ]
        seen: set[str] = set()
        result: list[Path] = []
        for path in candidates:
            try:
                resolved = str(path.resolve())
            except Exception:  # noqa: BLE001
                resolved = str(path)
            if resolved in seen:
                continue
            seen.add(resolved)
            if path.exists() and path.is_dir():
                result.append(path)
        return result

    def parse_inventory_file(self, path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8", errors="replace")
        section = None
        groups: dict[str, list[dict[str, Any]]] = {}
        group_vars: dict[str, dict[str, str]] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                continue
            if section is None:
                continue

            target_group = section
            is_vars = False
            if section.endswith(":vars"):
                target_group = section[:-5]
                is_vars = True

            parts = shlex.split(line, comments=False, posix=True)
            if not parts:
                continue
            if is_vars:
                for part in parts:
                    if "=" in part:
                        key, value = part.split("=", 1)
                        group_vars.setdefault(target_group, {})[key] = value
                continue

            host = parts[0]
            attrs: dict[str, str] = {}
            for part in parts[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    attrs[key] = value
            groups.setdefault(target_group, []).append({"name": host, "attrs": attrs, "group": target_group})

        hosts: list[dict[str, Any]] = []
        for group, entries in groups.items():
            defaults = group_vars.get(group, {})
            for entry in entries:
                attrs = {**defaults, **entry["attrs"]}
                hosts.append({"name": entry["name"], "group": group, "attrs": attrs})
        return {"path": str(path), "groups": groups, "group_vars": group_vars, "hosts": hosts}

    def collect_inventories(self) -> list[dict[str, Any]]:
        inventories: list[dict[str, Any]] = []
        for inv_dir in self.find_inventory_dirs():
            for path in sorted(inv_dir.glob("hosts*.ini")):
                try:
                    parsed = self.parse_inventory_file(path)
                    inventories.append(parsed)
                    rel_name = f"inventories/{safe_name(str(path))}.json"
                    self.write_json(rel_name, parsed)
                    self.summary["inventories"].append({"path": str(path), "hosts": len(parsed["hosts"])})
                except Exception as exc:  # noqa: BLE001
                    self.write_text(f"inventories/{safe_name(str(path))}_error.txt", repr(exc))
        return inventories

    def build_remote_targets(self, inventories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        targets: dict[tuple[str, int, str], dict[str, Any]] = {}
        for inv in inventories:
            for host in inv.get("hosts", []):
                attrs = host.get("attrs", {})
                ansible_host = attrs.get("ansible_host")
                ansible_port = attrs.get("ansible_port", "22")
                ansible_user = attrs.get("ansible_user", "admin")
                if not ansible_host:
                    continue
                try:
                    port = int(ansible_port)
                except ValueError:
                    port = 22
                key = (ansible_host, port, ansible_user)
                targets.setdefault(
                    key,
                    {
                        "label": host.get("name"),
                        "host": ansible_host,
                        "port": port,
                        "user": ansible_user,
                        "key_file": attrs.get("ansible_ssh_private_key_file"),
                        "source": inv.get("path"),
                    },
                )

        if self.args.include_default_dnat:
            for port in range(4021, 4028):
                key = (self.args.router_host, port, "admin")
                targets.setdefault(
                    key,
                    {
                        "label": f"default_dnat_{port}",
                        "host": self.args.router_host,
                        "port": port,
                        "user": "admin",
                        "key_file": "~/.ssh/id_ed25519",
                        "source": "default-dnat",
                    },
                )
        result = list(targets.values())
        self.summary["remote_targets"] = result
        self.write_json("summary/remote_targets.json", result)
        return result

    def remote_probe_command(self) -> str:
        topic_seconds = int(self.args.remote_topic_seconds)
        return textwrap.dedent(
            f"""
            echo SECTION=identity
            hostname
            whoami
            uname -a 2>/dev/null || true
            cat /etc/os-release 2>/dev/null || true
            echo SECTION=network
            ip -brief addr 2>/dev/null || true
            ip route 2>/dev/null || true
            ip neigh 2>/dev/null || true
            echo SECTION=listeners
            ss -tulpen 2>/dev/null || true
            echo SECTION=services
            systemctl is-active mosquitto emqx docker cockpit.socket mysqld mysql mariadb httpd xrdp sshd 2>/dev/null || true
            systemctl cat mosquitto 2>/dev/null || true
            systemctl cat emqx 2>/dev/null || true
            echo SECTION=configs
            sudo -n cat /etc/mosquitto/mosquitto.conf 2>/dev/null || true
            sudo -n find /etc/mosquitto -maxdepth 2 -type f -print 2>/dev/null || true
            sudo -n find /etc/emqx -maxdepth 2 -type f -print 2>/dev/null || true
            sudo -n sed -n '1,260p' /etc/emqx/emqx.conf 2>/dev/null || true
            echo SECTION=packages
            rpm -qa 2>/dev/null | grep -Ei 'mosquitto|emqx|mqtt|paho|docker|mysql|mariadb|httpd|xrdp' || true
            dpkg -l 2>/dev/null | grep -Ei 'mosquitto|emqx|mqtt|paho|docker|mysql|mariadb|apache|xrdp' || true
            python3 -m pip show paho-mqtt 2>/dev/null || true
            echo SECTION=processes
            pgrep -a mosquitto 2>/dev/null || true
            pgrep -a emqx 2>/dev/null || true
            pgrep -a mqtt 2>/dev/null || true
            ps auxww | grep -Ei 'mosquitto|emqx|mqtt|docker|mysql|mariadb|httpd|xrdp' | grep -v grep || true
            echo SECTION=docker
            docker ps -a 2>/dev/null || true
            docker network ls 2>/dev/null || true
            docker volume ls 2>/dev/null || true
            echo SECTION=emqx
            sudo -n emqx ctl status 2>/dev/null || true
            sudo -n emqx ctl listeners 2>/dev/null || true
            sudo -n emqx ctl clients list 2>/dev/null || true
            sudo -n emqx ctl topics list 2>/dev/null || true
            echo SECTION=mqtt_topics_all
            timeout {topic_seconds} mosquitto_sub -h 127.0.0.1 -p 1883 -t '#' -v -C 20 2>/dev/null || true
            echo SECTION=mqtt_topics_sys
            timeout {topic_seconds} mosquitto_sub -h 127.0.0.1 -p 1883 -t '$SYS/#' -v -C 20 2>/dev/null || true
            echo SECTION=done
            """
        ).strip()

    def collect_remote_hosts(self, targets: list[dict[str, Any]]) -> None:
        if not self.args.remote:
            self.summary["notes"].append("Remote SSH collection disabled by --no-remote.")
            return

        remote_cmd = self.remote_probe_command()
        prefer_wsl = is_windows() and self.command_exists("wsl.exe")
        native_ssh = shutil.which("ssh")
        if not prefer_wsl and not native_ssh:
            self.summary["notes"].append("No ssh executable found for remote probes.")
            return

        for target in targets:
            label = safe_name(f"{target['label']}_{target['host']}_{target['port']}")
            user_host = f"{target['user']}@{target['host']}"
            key_file = target.get("key_file")
            if prefer_wsl:
                key_part = ""
                if key_file:
                    key_part = f" -i {shlex.quote(str(key_file))}"
                ssh_cmd = (
                    "ssh -o BatchMode=yes "
                    f"-o ConnectTimeout={int(self.args.ssh_timeout)} "
                    "-o StrictHostKeyChecking=accept-new "
                    f"-p {int(target['port'])}{key_part} "
                    f"{shlex.quote(user_host)} {shlex.quote(remote_cmd)}"
                )
                self.run(
                    f"remote_{label}",
                    ["wsl.exe", "-e", "sh", "-lc", ssh_cmd],
                    timeout=int(self.args.remote_timeout),
                    rel_dir="remote",
                )
            else:
                cmd = [
                    str(native_ssh),
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    f"ConnectTimeout={int(self.args.ssh_timeout)}",
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                    "-p",
                    str(target["port"]),
                ]
                if key_file:
                    cmd.extend(["-i", str(Path(str(key_file)).expanduser())])
                cmd.extend([user_host, remote_cmd])
                self.run(f"remote_{label}", cmd, timeout=int(self.args.remote_timeout), rel_dir="remote")

    def tcp_probe(self, host: str, port: int, timeout: float) -> dict[str, Any]:
        result: dict[str, Any] = {"host": host, "port": port, "open": False}
        started = _dt.datetime.now()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                result["open"] = True
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
        result["elapsed_ms"] = int((_dt.datetime.now() - started).total_seconds() * 1000)
        return result

    def collect_port_probes(self) -> None:
        if not self.args.port_probe:
            self.summary["notes"].append("TCP port probing disabled by --no-port-probe.")
            return

        probes: list[dict[str, Any]] = []
        for port in DEFAULT_DNAT_PORTS:
            probes.append(self.tcp_probe(self.args.router_host, port, self.args.port_timeout))

        private_hosts = list(DEFAULT_PRIVATE_HOSTS)
        if self.args.deep_scan:
            try:
                subnet = ipaddress.ip_network(self.args.private_subnet, strict=False)
                private_hosts = [str(ip) for ip in subnet.hosts()]
            except ValueError as exc:
                self.summary["notes"].append(f"Invalid private subnet {self.args.private_subnet}: {exc}")

        for host in private_hosts:
            for port in RELEVANT_PORTS:
                probes.append(self.tcp_probe(host, port, self.args.port_timeout))

        self.write_json("network/tcp_probes.json", probes)
        open_lines = [
            f"{item['host']}:{item['port']}"
            for item in probes
            if item.get("open")
        ]
        self.write_text("network/open_ports.txt", "\n".join(open_lines) + ("\n" if open_lines else ""))

    def finish(self) -> None:
        self.write_json("summary/commands_index.json", self.command_index)
        self.summary["finished_at"] = _dt.datetime.now().isoformat(timespec="seconds")
        self.summary["command_count"] = len(self.command_index)
        zip_path = self.output_dir.with_suffix(".zip")
        if not self.args.no_zip:
            self.summary["zip_path"] = str(zip_path)
        self.write_json("summary.json", self.summary)
        self.write_text(
            "README.txt",
            textwrap.dedent(
                f"""
                TinyHouse collection report
                ===========================

                Created on: {self.summary['finished_at']}
                Host: {self.hostname}

                Please provide the whole directory or the zip archive to the assistant.

                Important files:
                - summary.json
                - summary/commands_index.json
                - network/tcp_probes.json
                - network/open_ports.txt
                - inventories/*.json
                - remote/*.txt
                - commands/*.txt

                Secrets are redacted by default. Re-run with --include-secrets only if
                you intentionally want raw credentials in the output.
                """
            ).strip()
            + "\n",
        )

        if not self.args.no_zip:
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in self.output_dir.rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(self.output_dir.parent))
            print(f"Created report directory: {self.output_dir}")
            print(f"Created zip archive:      {zip_path}")
        else:
            print(f"Created report directory: {self.output_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect TinyHouse management PC, network, MQTT, and Raspberry Pi facts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--output-dir", default=None, help="Directory where the timestamped report folder is created.")
    parser.add_argument("--router-host", default="132.180.196.167", help="Public TinyHouse router or DNAT host.")
    parser.add_argument("--private-subnet", default="192.168.1.0/24", help="Private TinyHouse subnet for deep scans.")
    parser.add_argument("--ssh-timeout", type=int, default=10, help="SSH connect timeout in seconds.")
    parser.add_argument("--remote-timeout", type=int, default=120, help="Timeout for each remote host probe.")
    parser.add_argument("--mqtt-timeout", type=int, default=10, help="Local MQTT subscription wait time.")
    parser.add_argument("--remote-topic-seconds", type=int, default=8, help="Remote MQTT topic subscription wait time.")
    parser.add_argument("--port-timeout", type=float, default=0.8, help="TCP connect timeout for port probes.")
    parser.add_argument("--no-remote", action="store_false", dest="remote", help="Disable SSH remote host probes.")
    parser.add_argument("--no-port-probe", action="store_false", dest="port_probe", help="Disable TCP port probes.")
    parser.add_argument("--deep-scan", action="store_true", help="Probe relevant ports on every host in the private subnet.")
    parser.add_argument("--no-default-dnat", action="store_false", dest="include_default_dnat", help="Do not add default DNAT Pi ports 4021-4027 as SSH targets.")
    parser.add_argument("--include-secrets", action="store_true", help="Do not redact password-like values from outputs.")
    parser.add_argument("--no-zip", action="store_true", help="Do not create a zip archive.")
    parser.set_defaults(remote=True, port_probe=True, include_default_dnat=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    collector = Collector(args)
    collector.prepare()
    collector.collect_local_baseline()
    inventories = collector.collect_inventories()
    targets = collector.build_remote_targets(inventories)
    collector.collect_port_probes()
    collector.collect_remote_hosts(targets)
    collector.finish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
