from __future__ import annotations

import csv
import datetime
import html
import ipaddress
import json
import platform
import re
import shutil
import socket
import subprocess
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class InterfaceInfo:
    name: str
    ip: str
    subnet: str
    gateway: str


@dataclass
class PortInfo:
    port: str
    protocol: str
    state: str
    service: str


@dataclass
class HostInfo:
    ip: str
    hostname: str
    mac: str
    vendor: str
    status: str
    role: str
    ports: List[PortInfo]


def run_command(command: List[str], timeout: int = 20) -> str:
    """
    Run a command and return its combined output.

    :param command: Command with arguments.
    :param timeout: Timeout in seconds.
    :return : of objects.
    :return: Combined command output.
    """
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return f"{result.stdout}\n{result.stderr}".strip()
    except Exception as error:
        return str(error)


def command_exists(command: str) -> bool:
    """
    Check whether a command exists.

    :param command: Command name.
    :return : of objects.
    :return: True if the command exists.
    """
    return shutil.which(command) is not None


def get_default_gateway_linux() -> Tuple[str, str]:
    """
    Read the default gateway and interface on Linux.

    :return : of objects.
    :return: Tuple with gateway IP and interface name.
    """
    output: str = run_command(["ip", "route"], timeout=5)

    for line in output.splitlines():
        if not line.startswith("default "):
            continue

        gateway_match: Optional[re.Match[str]] = re.search(
            r"default via ([0-9.]+)",
            line,
        )
        interface_match: Optional[re.Match[str]] = re.search(
            r" dev ([^\s]+)",
            line,
        )

        gateway: str = gateway_match.group(1) if gateway_match else ""
        interface: str = interface_match.group(1) if interface_match else ""
        return gateway, interface

    return "", ""


def get_default_gateway_macos() -> Tuple[str, str]:
    """
    Read the default gateway and interface on macOS.

    :return : of objects.
    :return: Tuple with gateway IP and interface name.
    """
    route_output: str = run_command(["route", "-n", "get", "default"], timeout=5)
    gateway: str = ""
    interface: str = ""

    for line in route_output.splitlines():
        stripped: str = line.strip()

        if stripped.startswith("gateway:"):
            gateway = stripped.split(":", 1)[1].strip()

        if stripped.startswith("interface:"):
            interface = stripped.split(":", 1)[1].strip()

    return gateway, interface


def get_local_ip_for_gateway(gateway: str) -> str:
    """
    Resolve the local IP used to reach the gateway.

    :param gateway: Gateway IP address.
    :return : of objects.
    :return: Local IP address.
    """
    target: str = gateway if gateway else "8.8.8.8"
    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        sock.connect((target, 80))
        return str(sock.getsockname()[0])
    finally:
        sock.close()


def build_default_subnet(local_ip: str) -> str:
    """
    Build a default /24 subnet from a local IP address.

    :param local_ip: Local IP address.
    :return : of objects.
    :return: Subnet in CIDR notation.
    """
    interface: ipaddress.IPv4Interface = ipaddress.IPv4Interface(
        f"{local_ip}/24",
    )
    return str(interface.network)


def detect_interface_info() -> InterfaceInfo:
    """
    Detect the likely primary network interface.

    :return : of objects.
    :return: Interface information.
    """
    system_name: str = platform.system().lower()

    if "darwin" in system_name:
        gateway, interface_name = get_default_gateway_macos()
    else:
        gateway, interface_name = get_default_gateway_linux()

    local_ip: str = get_local_ip_for_gateway(gateway)
    subnet: str = build_default_subnet(local_ip)

    return InterfaceInfo(
        name=interface_name,
        ip=local_ip,
        subnet=subnet,
        gateway=gateway,
    )


def parse_args(args: List[str]) -> Tuple[Optional[str], bool]:
    """
    Parse command line arguments.

    :param args: Command line arguments.
    :return : of objects.
    :return: Tuple with subnet and deep scan flag.
    """
    subnet: Optional[str] = None
    deep_scan: bool = False

    for index, arg in enumerate(args):
        if arg == "--subnet" and index + 1 < len(args):
            subnet = args[index + 1]

        if arg == "--deep":
            deep_scan = True

    return subnet, deep_scan


def nmap_ping_discovery(subnet: str) -> List[str]:
    """
    Discover hosts with nmap ping scan.

    :param subnet: Subnet in CIDR notation.
    :return : of objects.
    :return: List of discovered IP addresses.
    """
    if not command_exists("nmap"):
        return []

    output: str = run_command(
        ["nmap", "-sn", "-n", subnet],
        timeout=120,
    )
    hosts: List[str] = []

    for line in output.splitlines():
        match: Optional[re.Match[str]] = re.search(
            r"Nmap scan report for ([0-9.]+)",
            line,
        )

        if match:
            hosts.append(match.group(1))

    return sorted(set(hosts), key=lambda value: ipaddress.IPv4Address(value))


def ping_host(ip: str) -> bool:
    """
    Ping one host.

    :param ip: IP address.
    :return : of objects.
    :return: True if the host responds.
    """
    system_name: str = platform.system().lower()

    if "windows" in system_name:
        command: List[str] = ["ping", "-n", "1", "-w", "700", ip]
    else:
        command = ["ping", "-c", "1", "-W", "1", ip]

    output: str = run_command(command, timeout=3)
    lowered: str = output.lower()

    return "ttl=" in lowered or "bytes from" in lowered


def ping_sweep(subnet: str) -> List[str]:
    """
    Discover hosts with ping.

    :param subnet: Subnet in CIDR notation.
    :return : of objects.
    :return: List of discovered IP addresses.
    """
    network: ipaddress.IPv4Network = ipaddress.IPv4Network(
        subnet,
        strict=False,
    )
    hosts: List[str] = []

    for ip in network.hosts():
        ip_text: str = str(ip)

        if ping_host(ip_text):
            hosts.append(ip_text)

    return hosts


def parse_arp_table() -> Dict[str, str]:
    """
    Parse the local ARP table.

    :return : of objects.
    :return: Mapping from IP address to MAC address.
    """
    output: str = run_command(["arp", "-a"], timeout=5)
    mapping: Dict[str, str] = {}

    for line in output.splitlines():
        ip_match: Optional[re.Match[str]] = re.search(
            r"([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)",
            line,
        )
        mac_match: Optional[re.Match[str]] = re.search(
            r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}",
            line,
        )

        if ip_match and mac_match:
            ip_value: str = ip_match.group(1)
            mac_value: str = mac_match.group(0).replace("-", ":").lower()
            mapping[ip_value] = mac_value

    return mapping


def resolve_hostname(ip: str) -> str:
    """
    Resolve a hostname.

    :param ip: IP address.
    :return : of objects.
    :return: Hostname or empty string.
    """
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


def scan_ports(ip: str, deep_scan: bool) -> List[PortInfo]:
    """
    Scan common ports with nmap.

    :param ip: Target IP address.
    :param deep_scan: Whether to scan more ports.
    :return : of objects.
    :return: List of port information objects.
    """
    if not command_exists("nmap"):
        return []

    top_ports: str = "100" if deep_scan else "30"
    output: str = run_command(
        ["nmap", "-T3", "--top-ports", top_ports, "-oX", "-", ip],
        timeout=90,
    )
    ports: List[PortInfo] = []

    for line in output.splitlines():
        stripped: str = line.strip()

        if "<port " not in stripped:
            continue

        port_id: str = extract_xml_attr(stripped, "portid")
        protocol: str = extract_xml_attr(stripped, "protocol")
        state: str = extract_xml_attr(stripped, "state")
        service: str = extract_xml_attr(stripped, "name")

        if port_id:
            ports.append(
                PortInfo(
                    port=port_id,
                    protocol=protocol,
                    state=state,
                    service=service,
                )
            )

    return ports


def extract_xml_attr(text: str, attr: str) -> str:
    """
    Extract an XML attribute from a line.

    :param text: XML-like text.
    :param attr: Attribute name.
    :return : of objects.
    :return: Attribute value or empty string.
    """
    pattern: str = rf'{attr}="([^"]*)"'
    match: Optional[re.Match[str]] = re.search(pattern, text)

    if not match:
        return ""

    return match.group(1)


def guess_role(host: HostInfo, gateway: str) -> str:
    """
    Guess a host role from ports and IP.

    :param host: Host information.
    :param gateway: Gateway IP address.
    :return : of objects.
    :return: Guessed role.
    """
    if host.ip == gateway:
        return "gateway"

    services: List[str] = [port.service.lower() for port in host.ports]
    ports: List[str] = [port.port for port in host.ports]

    if "80" in ports or "443" in ports:
        return "web-device"

    if "22" in ports:
        return "linux-server-or-device"

    if "445" in ports or "139" in ports:
        return "windows-or-nas"

    if "631" in ports or "9100" in ports:
        return "printer"

    if "554" in ports:
        return "camera-or-media-device"

    if "mqtt" in services or "1883" in ports:
        return "iot-or-mqtt"

    return "unknown-device"


def discover_hosts(subnet: str, interface: InterfaceInfo) -> List[str]:
    """
    Discover hosts using multiple methods.

    :param subnet: Subnet in CIDR notation.
    :param interface: Detected interface information.
    :return : of objects.
    :return: Sorted list of discovered hosts.
    """
    discovered: List[str] = []

    nmap_hosts: List[str] = nmap_ping_discovery(subnet)
    discovered.extend(nmap_hosts)

    if not discovered:
        discovered.extend(ping_sweep(subnet))

    arp_table: Dict[str, str] = parse_arp_table()
    discovered.extend(list(arp_table.keys()))

    if interface.ip:
        discovered.append(interface.ip)

    if interface.gateway:
        discovered.append(interface.gateway)

    network: ipaddress.IPv4Network = ipaddress.IPv4Network(
        subnet,
        strict=False,
    )

    filtered: List[str] = [
        ip for ip in set(discovered) if ipaddress.IPv4Address(ip) in network
    ]

    return sorted(filtered, key=lambda value: ipaddress.IPv4Address(value))


def build_hosts(
    ips: List[str],
    interface: InterfaceInfo,
    deep_scan: bool,
) -> List[HostInfo]:
    """
    Build full host information.

    :param ips: Discovered IP addresses.
    :param interface: Interface information.
    :param deep_scan: Whether to scan more ports.
    :return : of objects.
    :return: List of host information objects.
    """
    arp_table: Dict[str, str] = parse_arp_table()
    hosts: List[HostInfo] = []

    for ip in ips:
        host: HostInfo = HostInfo(
            ip=ip,
            hostname=resolve_hostname(ip),
            mac=arp_table.get(ip, ""),
            vendor="",
            status="online",
            role="unknown-device",
            ports=scan_ports(ip, deep_scan),
        )
        host.role = guess_role(host, interface.gateway)
        hosts.append(host)

    return hosts


def create_output_dir() -> Path:
    """
    Create a timestamped output directory.

    :return : of objects.
    :return: Output directory path.
    """
    timestamp: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir: Path = Path.cwd() / f"network_map_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_json(path: Path, interface: InterfaceInfo, hosts: List[HostInfo]) -> None:
    """
    Write JSON output.

    :param path: Output path.
    :param interface: Interface information.
    :param hosts: Host information.
    :return : of objects.
    :return: None.
    """
    payload: Dict[str, Any] = {
        "created_at": datetime.datetime.now().isoformat(),
        "interface": asdict(interface),
        "hosts": [host_to_dict(host) for host in hosts],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def host_to_dict(host: HostInfo) -> Dict[str, Any]:
    """
    Convert host data to dictionary.

    :param host: Host information.
    :return : of objects.
    :return: Host dictionary.
    """
    return {
        "ip": host.ip,
        "hostname": host.hostname,
        "mac": host.mac,
        "vendor": host.vendor,
        "status": host.status,
        "role": host.role,
        "ports": [asdict(port) for port in host.ports],
    }


def write_csv(path: Path, hosts: List[HostInfo]) -> None:
    """
    Write CSV output.

    :param path: Output path.
    :param hosts: Host information.
    :return : of objects.
    :return: None.
    """
    with path.open("w", encoding="utf-8", newline="") as file:
        writer: csv.DictWriter[str] = csv.DictWriter(
            file,
            fieldnames=[
                "ip",
                "hostname",
                "mac",
                "status",
                "role",
                "ports",
            ],
        )
        writer.writeheader()

        for host in hosts:
            writer.writerow(
                {
                    "ip": host.ip,
                    "hostname": host.hostname,
                    "mac": host.mac,
                    "status": host.status,
                    "role": host.role,
                    "ports": format_ports(host.ports),
                }
            )


def format_ports(ports: List[PortInfo]) -> str:
    """
    Format ports for CSV and reports.

    :param ports: List of port information.
    :return : of objects.
    :return: Formatted port text.
    """
    return "; ".join(
        [
            f"{port.port}/{port.protocol} {port.service} {port.state}"
            for port in ports
        ]
    )


def group_for_role(role: str) -> int:
    """
    Map a role to a visual group ID.

    :param role: Host role.
    :return : of objects.
    :return: Group ID.
    """
    groups: Dict[str, int] = {
        "gateway": 1,
        "web-device": 2,
        "linux-server-or-device": 3,
        "windows-or-nas": 4,
        "printer": 5,
        "camera-or-media-device": 6,
        "iot-or-mqtt": 7,
        "unknown-device": 8,
    }
    return groups.get(role, 8)


def build_html(interface: InterfaceInfo, hosts: List[HostInfo]) -> str:
    """
    Build an interactive HTML network map.

    :param interface: Interface information.
    :param hosts: Host information.
    :return : of objects.
    :return: HTML document.
    """
    nodes: List[Dict[str, Any]] = [
        {
            "id": "internet",
            "label": "Internet",
            "shape": "cloud",
            "group": 9,
        },
        {
            "id": "subnet",
            "label": f"Subnet\\n{interface.subnet}",
            "shape": "box",
            "group": 10,
        },
    ]

    edges: List[Dict[str, Any]] = [
        {
            "from": "internet",
            "to": "subnet",
            "dashes": True,
        }
    ]

    for host in hosts:
        label: str = host.ip

        if host.hostname:
            label = f"{host.ip}\\n{host.hostname}"

        if host.ip == interface.ip:
            label = f"{label}\\nTHIS MACHINE"

        title: str = build_node_title(host)
        nodes.append(
            {
                "id": host.ip,
                "label": label,
                "title": title,
                "group": group_for_role(host.role),
                "shape": "dot",
                "value": 20 + len(host.ports) * 4,
            }
        )

        parent: str = interface.gateway if interface.gateway else "subnet"

        if host.role == "gateway":
            edges.append(
                {
                    "from": "subnet",
                    "to": host.ip,
                    "width": 3,
                }
            )
        elif parent != host.ip:
            edges.append(
                {
                    "from": parent,
                    "to": host.ip,
                    "width": 1,
                }
            )
        else:
            edges.append(
                {
                    "from": "subnet",
                    "to": host.ip,
                    "width": 2,
                }
            )

    nodes_json: str = json.dumps(nodes)
    edges_json: str = json.dumps(edges)

    return f"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Network Map</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
body {{
    margin: 0;
    font-family: Arial, sans-serif;
    background: #111827;
    color: #f9fafb;
}}
header {{
    padding: 16px 24px;
    background: #020617;
    border-bottom: 1px solid #334155;
}}
main {{
    display: grid;
    grid-template-columns: 280px 1fr;
    height: calc(100vh - 88px);
}}
aside {{
    padding: 16px;
    background: #0f172a;
    border-right: 1px solid #334155;
    overflow: auto;
}}
#network {{
    height: 100%;
    background: #f8fafc;
}}
.card {{
    padding: 12px;
    margin-bottom: 12px;
    background: #1e293b;
    border-radius: 10px;
}}
.small {{
    color: #cbd5e1;
    font-size: 13px;
}}
.legend {{
    line-height: 1.8;
}}
</style>
</head>
<body>
<header>
<h2>Network Architecture Map</h2>
<div class="small">
Interface: {html.escape(interface.name)} |
Local IP: {html.escape(interface.ip)} |
Gateway: {html.escape(interface.gateway)} |
Subnet: {html.escape(interface.subnet)}
</div>
</header>
<main>
<aside>
<div class="card">
<strong>Summary</strong>
<div class="small">Hosts: {len(hosts)}</div>
<div class="small">Generated: {html.escape(datetime.datetime.now().isoformat())}</div>
</div>
<div class="card legend">
<strong>Legend</strong><br>
Gateway<br>
Web device<br>
Linux/server/device<br>
Windows/NAS<br>
Printer<br>
Camera/media<br>
IoT/MQTT<br>
Unknown
</div>
<div class="card">
<strong>Tip</strong>
<div class="small">
Use <code>--deep</code> to scan more ports.
Use <code>--subnet</code> if the detected subnet is wrong.
</div>
</div>
</aside>
<div id="network"></div>
</main>
<script>
const nodes = new vis.DataSet({nodes_json});
const edges = new vis.DataSet({edges_json});
const container = document.getElementById("network");

const data = {{
    nodes: nodes,
    edges: edges
}};

const options = {{
    nodes: {{
        font: {{
            size: 14
        }},
        scaling: {{
            min: 16,
            max: 48
        }}
    }},
    edges: {{
        smooth: true,
        color: {{
            color: "#64748b"
        }}
    }},
    groups: {{
        1: {{ color: "#ef4444" }},
        2: {{ color: "#3b82f6" }},
        3: {{ color: "#22c55e" }},
        4: {{ color: "#a855f7" }},
        5: {{ color: "#f97316" }},
        6: {{ color: "#14b8a6" }},
        7: {{ color: "#eab308" }},
        8: {{ color: "#94a3b8" }},
        9: {{ color: "#0ea5e9" }},
        10: {{ color: "#64748b" }}
    }},
    physics: {{
        stabilization: true,
        barnesHut: {{
            gravitationalConstant: -18000,
            springLength: 180,
            springConstant: 0.04
        }}
    }},
    interaction: {{
        hover: true,
        tooltipDelay: 100,
        navigationButtons: true,
        keyboard: true
    }}
}};

new vis.Network(container, data, options);
</script>
</body>
</html>
"""


def build_node_title(host: HostInfo) -> str:
    """
    Build HTML tooltip text for a node.

    :param host: Host information.
    :return : of objects.
    :return: Tooltip HTML.
    """
    lines: List[str] = [
        f"<strong>{html.escape(host.ip)}</strong>",
        f"Hostname: {html.escape(host.hostname)}",
        f"MAC: {html.escape(host.mac)}",
        f"Role: {html.escape(host.role)}",
        f"Status: {html.escape(host.status)}",
    ]

    if host.ports:
        lines.append("<br><strong>Open ports</strong>")
        for port in host.ports:
            lines.append(
                html.escape(
                    f"{port.port}/{port.protocol} "
                    f"{port.service} {port.state}"
                )
            )

    return "<br>".join(lines)


def write_html(path: Path, interface: InterfaceInfo, hosts: List[HostInfo]) -> None:
    """
    Write the HTML network map.

    :param path: Output path.
    :param interface: Interface information.
    :param hosts: Host information.
    :return : of objects.
    :return: None.
    """
    path.write_text(build_html(interface, hosts), encoding="utf-8")


def write_markdown(
    path: Path,
    interface: InterfaceInfo,
    hosts: List[HostInfo],
) -> None:
    """
    Write a Markdown report.

    :param path: Output path.
    :param interface: Interface information.
    :param hosts: Host information.
    :return : of objects.
    :return: None.
    """
    lines: List[str] = [
        "# Network Scan Report",
        "",
        f"- Interface: `{interface.name}`",
        f"- Local IP: `{interface.ip}`",
        f"- Gateway: `{interface.gateway}`",
        f"- Subnet: `{interface.subnet}`",
        f"- Hosts: `{len(hosts)}`",
        "",
        "## Hosts",
        "",
    ]

    for host in hosts:
        lines.extend(
            [
                f"### {host.ip}",
                "",
                f"- Hostname: `{host.hostname}`",
                f"- MAC: `{host.mac}`",
                f"- Role: `{host.role}`",
                f"- Status: `{host.status}`",
                f"- Ports: `{format_ports(host.ports)}`",
                "",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def zip_output(output_dir: Path, zip_path: Path) -> None:
    """
    Zip generated output files.

    :param output_dir: Output directory.
    :param zip_path: ZIP file path.
    :return : of objects.
    :return: None.
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                archive.write(
                    file_path,
                    arcname=str(file_path.relative_to(output_dir)),
                )


def main() -> None:
    """
    Run the network mapper.

    :return : of objects.
    :return: None.
    """
    subnet_arg, deep_scan = parse_args(sys.argv[1:])
    interface: InterfaceInfo = detect_interface_info()

    if subnet_arg:
        interface.subnet = subnet_arg

    print(f"Interface: {interface.name}")
    print(f"Local IP: {interface.ip}")
    print(f"Gateway: {interface.gateway}")
    print(f"Subnet: {interface.subnet}")

    if not command_exists("nmap"):
        print("")
        print("nmap is not installed. Results will be weaker.")
        print("Install it with: sudo apt install nmap")
        print("On macOS: brew install nmap")

    output_dir: Path = create_output_dir()
    discovered_ips: List[str] = discover_hosts(interface.subnet, interface)
    hosts: List[HostInfo] = build_hosts(discovered_ips, interface, deep_scan)

    write_json(output_dir / "network_scan.json", interface, hosts)
    write_csv(output_dir / "network_scan.csv", hosts)
    write_html(output_dir / "network_map.html", interface, hosts)
    write_markdown(output_dir / "network_report.md", interface, hosts)

    zip_path: Path = Path.cwd() / f"{output_dir.name}.zip"
    zip_output(output_dir, zip_path)

    print("")
    print(f"Discovered hosts: {len(hosts)}")
    print(f"Output folder: {output_dir}")
    print(f"ZIP archive: {zip_path}")
    print(f"Open: {output_dir / 'network_map.html'}")


if __name__ == "__main__":
    main()