# Management PC

The management PC is the operational entry point. External access uses `ssh tinyhouse`. That SSH alias reaches the VPS at `46.224.118.171` and then enters the Windows host through a reverse tunnel.

The Windows host is `BTQ8X1`. The host uses Ethernet address `132.180.196.164`. The host uses the university gateway `132.180.196.254`. The Wi-Fi adapter was disconnected during inspection.

The WSL environment is the Linux controller. WSL runs Ubuntu 24.04.3 LTS. WSL runs as user `tiny_house`. The Ansible directory exists at `~/lab-ansible`.

## VPS

  <figure>
    <img src="/diagrams/tinyhouse_network_architecture.svg" alt="TinyHouse exterior entrance">
    <figcaption>VPS Architecture</figcaption>
  </figure>

## Windows Network

| Interface | State | Address |
| --- | --- | --- |
| Ethernet 4 | Up | `132.180.196.164/24` |
| WLAN | Disconnected | No active address |
| vEthernet Default Switch | Up | `172.17.128.1/20` |
| vEthernet WSL | Up | `172.18.160.1/20` |

The Windows route table uses the university network as default. The default route points to `132.180.196.254`. The route table does not show a direct route into `192.168.1.0/24`. Therefore direct private network access depends on Wi-Fi or router DNAT.

## WSL Controller

| Item | Value |
| --- | --- |
| Distribution | `Ubuntu` |
| WSL version | `2` |
| Linux host name | `btq8x1` |
| Linux user | `tiny_house` |
| Linux address | `172.18.168.140/20` |
| Controller path | `~/lab-ansible` |
| SSH key path | `~/.ssh/id_ed25519` |

The WSL controller owns the working admin key. Ansible probes from the Mac did not authenticate to the Pis. Ansible probes from WSL did authenticate to the reachable Pis.

## Local Services

| Service or port | Observed state |
| --- | --- |
| Windows SSH `22` | Listening |
| Windows HTTP `80` | Listening |
| Windows HTTPS `443` | Listening |
| Windows RDP `3389` | Listening |
| FileZilla FTP `21` | Listening |
| Local Mosquitto `127.0.0.1:1883` | Listening |
| Local Mosquitto `127.0.0.1:9883` | Listening |

The local service list should be reduced to an intentional baseline. SSH is required for access. MQTT may be required for local broker tests. HTTP, HTTPS, FTP, and RDP should be documented with owners or disabled if they are not needed.

## MQTT Role

The management PC runs Mosquitto as a Windows service. The service name is `mosquitto`. The executable path is `C:\Program Files\Mosquitto\mosquitto.exe`. The service starts automatically as `LocalSystem`.

The management PC broker is local only. The broker listens on `127.0.0.1:1883`, `127.0.0.1:9883`, and `[::1]:1883`. No non-loopback MQTT listener was observed on the management PC. The broker reported Mosquitto version `2.1.2` through `$SYS/broker/version`.
