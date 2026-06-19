from __future__ import annotations

import copy
import shlex
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


BASE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BASE_DIR.parents[1]
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"
DASHBOARD_BUILD = "2026-06-18-native-terminal-login-helper"
DEFAULT_ADMIN_INVENTORY_PATH = (
    REPO_ROOT / "modules" / "administration" / "lab-ansible" / "hosts.admin.ini"
)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    return normalize_config(data)


def normalize_config(data: Dict[str, Any]) -> Dict[str, Any]:
    data.setdefault("server", {})
    data.setdefault("management_pc", {})
    data.setdefault("mqtt", {})
    data.setdefault("camera", {})
    data.setdefault("ansible", {})
    data.setdefault("targets", [])
    return data


def load_runtime_config(path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    return apply_ansible_inventory(load_config(path))


def save_config(config: Dict[str, Any], path: Path = DEFAULT_CONFIG_PATH) -> None:
    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config, file, sort_keys=False)


def apply_ansible_inventory(config: Dict[str, Any]) -> Dict[str, Any]:
    runtime = copy.deepcopy(config)
    ansible = runtime.get("ansible", {})
    inventory_path = Path(
        str(ansible.get("admin_inventory_path") or DEFAULT_ADMIN_INVENTORY_PATH)
    ).expanduser()

    if not inventory_path.is_absolute():
        inventory_path = (REPO_ROOT / inventory_path).resolve()

    hosts = read_ansible_inventory(inventory_path)

    if not hosts:
        return runtime

    targets = list(runtime.get("targets", []))

    for host in hosts:
        index = _find_inventory_target_index(targets, host)
        shell_data = _inventory_shell_data(host, inventory_path)

        if index is None:
            targets.append(
                {
                    "name": host.get("hostname") or host["name"],
                    "ip": "",
                    "role": "mqtt broker",
                    "ports": [22],
                    "public_host": host["ansible_host"],
                    "public_ports": [host["ansible_port"]],
                    **shell_data,
                }
            )
            continue

        merged = {**targets[index], **shell_data}
        merged.setdefault("public_host", host["ansible_host"])
        public_ports = [int(port) for port in merged.get("public_ports", [])]

        if host["ansible_port"] not in public_ports:
            public_ports.append(host["ansible_port"])

        merged["public_ports"] = public_ports
        targets[index] = merged

    runtime["targets"] = targets
    return runtime


def read_ansible_inventory(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    section = ""
    groups: Dict[str, List[Tuple[str, Dict[str, str]]]] = {}
    group_vars: Dict[str, Dict[str, str]] = {}

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or line.startswith(";"):
            continue

        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue

        if not section:
            continue

        group = section[:-5] if section.endswith(":vars") else section
        parts = shlex.split(line, comments=False, posix=True)

        if not parts:
            continue

        attrs: Dict[str, str] = {}

        for part in parts[1:] if not section.endswith(":vars") else parts:
            if "=" in part:
                key, value = part.split("=", 1)
                attrs[key] = value

        if section.endswith(":vars"):
            group_vars.setdefault(group, {}).update(attrs)
            continue

        groups.setdefault(group, []).append((parts[0], attrs))

    hosts: List[Dict[str, Any]] = []

    for name, attrs in groups.get("raspis", []):
        merged = {**group_vars.get("raspis", {}), **attrs}
        ansible_host = str(merged.get("ansible_host") or "").strip()

        if not ansible_host:
            continue

        try:
            ansible_port = int(merged.get("ansible_port") or 22)
        except ValueError:
            ansible_port = 22

        hosts.append(
            {
                "name": name,
                "hostname": str(merged.get("hostname") or "").strip(),
                "ansible_host": ansible_host,
                "ansible_port": ansible_port,
                "ansible_user": str(merged.get("ansible_user") or "admin").strip(),
                "ansible_ssh_private_key_file": str(
                    merged.get("ansible_ssh_private_key_file") or ""
                ).strip(),
            }
        )

    return hosts


def _find_inventory_target_index(
    targets: List[Dict[str, Any]],
    host: Dict[str, Any],
) -> int | None:
    ansible_host = str(host.get("ansible_host") or "")
    ansible_port = int(host.get("ansible_port") or 22)

    for index, target in enumerate(targets):
        public_ports = [int(port) for port in target.get("public_ports", [])]

        if (
            str(target.get("public_host") or "") == ansible_host
            and ansible_port in public_ports
        ):
            return index

    hostname = str(host.get("hostname") or "").lower()
    name = str(host.get("name") or "").lower()

    for index, target in enumerate(targets):
        target_names = {
            str(target.get("name") or "").lower(),
            str(target.get("ansible_name") or "").lower(),
            str(target.get("inventory_hostname") or "").lower(),
        }

        if name in target_names or (hostname and hostname in target_names):
            return index

    return None


def _inventory_shell_data(host: Dict[str, Any], inventory_path: Path) -> Dict[str, Any]:
    ansible_name = str(host.get("name") or "")
    hostname = str(host.get("hostname") or "")
    ansible_host = str(host.get("ansible_host") or "")
    ansible_port = int(host.get("ansible_port") or 22)
    ansible_user = str(host.get("ansible_user") or "admin")
    key_file = str(host.get("ansible_ssh_private_key_file") or "~/.ssh/id_ed25519")

    return {
        "shell_capable": True,
        "shell_transport": "management_wsl",
        "shell_target": ansible_name,
        "shell_description": (
            f"{ansible_name} via WSL Ansible inventory "
            f"({ansible_user}@{ansible_host}:{ansible_port})"
        ),
        "ansible_name": ansible_name,
        "inventory_hostname": hostname,
        "ansible_host": ansible_host,
        "ansible_port": ansible_port,
        "ansible_user": ansible_user,
        "ansible_ssh_private_key_file": key_file,
        "ansible_inventory_path": str(inventory_path),
    }


def public_config(config: Dict[str, Any], mode: str) -> Dict[str, Any]:
    safe = copy.deepcopy(config)
    management = safe.get("management_pc", {})

    if management.get("password"):
        management["password"] = "configured"

    camera = safe.get("camera", {})
    if camera.get("password"):
        camera["password"] = "configured"

    return {
        "dashboard": {
            "build": DASHBOARD_BUILD,
            "config_path": str(DEFAULT_CONFIG_PATH),
        },
        "mode": mode,
        "server": safe.get("server", {}),
        "management_pc": management,
        "mqtt": safe.get("mqtt", {}),
        "camera": camera,
        "targets": safe.get("targets", []),
    }
