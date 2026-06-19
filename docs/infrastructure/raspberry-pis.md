# Raspberry Pis

The Raspberry Pis act as edge broker nodes. The active Ansible inventory manages four Pis. The live inspection reached three inventory Pis, two extra broker Pis, and failed to reach one inventory Pi.

## Managed Pis

| Ansible host | Live name | Private IP | DNAT port | State |
| --- | --- | --- | --- | --- |
| `pi01` | `EMQX002` from inventory | `192.168.1.122` | `4022` | Unreachable |
| `pi02` | `EMQX004` | `192.168.1.124` | `4024` | Reachable |
| `pi03` | `EMQX005` | `192.168.1.125` | `4025` | Reachable |
| `pi04` | `EMQX006` | `192.168.1.126` | `4026` | Reachable |

## Extra Reachable Pis

| Device | Private IP | DNAT port | Broker state |
| --- | --- | --- | --- |
| `EMQX001` | `192.168.1.121` | `4021` | Mosquitto active |
| `EMQX003` | `192.168.1.123` | `4023` | EMQX active and Mosquitto failed |

The reachable Pis do not all run the same operating system version. `EMQX001` and `EMQX003` reported AlmaLinux 9.7. `EMQX004`, `EMQX005`, and `EMQX006` reported AlmaLinux 9.6. Each reachable Pi uses `eth0` on the private subnet. Each reachable Pi has `wlan0` down.

## Broker Services

| Service | State on reachable Pis | Port |
| --- | --- | --- |
| Mosquitto | Active on `EMQX001`, `EMQX004`, `EMQX005`, and `EMQX006` | `1883` |
| Cockpit socket | Active | `9090` |
| Docker | Active | No running containers |
| XRDP | Active | `3389` |
| MySQL daemon | Active | `3306` and `33060` |
| HTTP socket | Listening | `80` and `443` |
| EMQX Enterprise package | Installed on all reachable broker Pis | Not a listener by itself |
| EMQX service | Serving on `EMQX003` | `1883`, `8883`, `8083`, `8084`, `18083` |

Most reachable Pis currently implement serving broker traffic through Mosquitto. The Mosquitto configuration from Ansible allows anonymous access. The listener binds to `0.0.0.0:1883`.

`EMQX003` currently implements broker service through EMQX. EMQX listens on `1883`, `8883`, `8083`, `8084`, and `18083`. The service file starts `/usr/bin/emqx foreground`.

EMQX is installed beyond `EMQX003`. `EMQX001`, `EMQX004`, `EMQX005`, and `EMQX006` reported the `emqx-enterprise-5.8.0` package and the `emqx.service` unit. Those nodes did not expose EMQX listener ports in the collection report.

## Service Risks

The HTTP state needs review. The socket listens on `80` and `443`. The `httpd` service status returned `failed`. This state may be intentional socket activation or a broken service.

The MySQL state needs review. The daemon listens on the reachable Pis. The package query found `mysql-server-8.0.46` in the collection report. The service purpose should be identified before the nodes become production brokers.

The Pi reachability state needs review. `pi01` failed with no route to host. `EMQX001` and `EMQX003` are reachable but are not in the active Ansible inventory. The inventory should match the intended cluster membership.
