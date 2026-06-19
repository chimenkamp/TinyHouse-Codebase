# Live Findings

The live inspection ran on 2026-06-15. The first inspection used `ssh tinyhouse`. The second inspection used the collector output in `docs/tinyhouse_collection_20260615_072208_btq8x1`. The collector output is the newer source for this page.

## Management PC

| Item | Observed value |
| --- | --- |
| Windows host name | `BTQ8X1` |
| Windows user | `btq8x1\bt309633` |
| Windows version | `10.0.26200.8655` |
| Ethernet IPv4 | `132.180.196.164/24` |
| Ethernet gateway | `132.180.196.254` |
| Ethernet DNS | `132.180.17.1`, `132.180.17.128` |
| Wi-Fi state | Disconnected |
| WSL distribution | `Ubuntu` |
| WSL version | WSL2 |
| WSL OS | Ubuntu 24.04.3 LTS |
| WSL IPv4 | `172.18.168.140/20` |

The management PC exposes several local services. Windows listens on SSH port `22`. Windows also listens on RDP port `3389`. A local Mosquitto process listens on `127.0.0.1:1883`, `[::1]:1883`, and `127.0.0.1:9883`.

## Raspberry Pis

| Host | OS | Private IP | Broker | Management | Extra services |
| --- | --- | --- | --- | --- | --- |
| `EMQX001` | AlmaLinux 9.7 | `192.168.1.121` | Mosquitto active | Cockpit active | Docker active, XRDP active, MySQL active, HTTP socket listening |
| `EMQX003` | AlmaLinux 9.7 | `192.168.1.123` | EMQX active | Cockpit active | Docker active, XRDP active, MySQL active, HTTP socket listening |
| `EMQX004` | AlmaLinux 9.6 | `192.168.1.124` | Mosquitto active | Cockpit active | Docker active, XRDP active, MySQL active, HTTP socket listening |
| `EMQX005` | AlmaLinux 9.6 | `192.168.1.125` | Mosquitto active | Cockpit active | Docker active, XRDP active, MySQL active, HTTP socket listening |
| `EMQX006` | AlmaLinux 9.6 | `192.168.1.126` | Mosquitto active | Cockpit active | Docker active, XRDP active, MySQL active, HTTP socket listening |

The reachable Pis share the same network shape. Each Pi uses `eth0` on `192.168.1.0/24`. Each Pi uses `192.168.1.1` as the default gateway. Each Pi has `wlan0` down.

The reachable Pis do not share the same serving broker state. `EMQX001`, `EMQX004`, `EMQX005`, and `EMQX006` run Mosquitto on port `1883`. `EMQX003` runs EMQX on port `1883` and exposes TLS MQTT, WebSocket, secure WebSocket, and dashboard ports. EMQX Enterprise is installed on all reachable broker Pis.

The reachable Pis show one service mismatch. `httpd.socket` listens on ports `80` and `443`. The `httpd` service check returned `failed`. This state should be reviewed because socket activation may hide the real HTTP service state.

## Private Network Observations

The management PC could not directly scan the private subnet. Every direct TCP probe to `192.168.1.x` timed out from Windows. The Wi-Fi adapter was disconnected during the collection.

`EMQX003` saw additional private-neighbor addresses. The neighbor table included stale entries for `192.168.1.103`, `192.168.1.105`, `192.168.1.121`, and `192.168.1.125`. The neighbor table included failed entries for `192.168.1.101`, `192.168.1.102`, `192.168.1.106`, `192.168.1.107`, `192.168.1.108`, and `192.168.1.113`.

## Reachability Summary

![Pi service state](/diagrams/pi-service-state.svg)

| Endpoint | Result |
| --- | --- |
| `132.180.196.167:4021` | SSH reachable from WSL |
| `132.180.196.167:4022` | Network unreachable |
| `132.180.196.167:4023` | SSH reachable from WSL |
| `132.180.196.167:4024` | SSH reachable from WSL |
| `132.180.196.167:4025` | SSH reachable from WSL |
| `132.180.196.167:4026` | SSH reachable from WSL |
| `132.180.196.167:4027` | Network unreachable |
| `132.180.196.167:4031` | Timed out |
| `132.180.196.167:4032` | Timed out |
| `132.180.196.167:4041` | TCP open |
| `132.180.196.167:4042` | TCP open |
| `132.180.196.167:4050` | Timed out |
