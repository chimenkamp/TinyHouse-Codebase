# Network Inventory

The inventory combines source data and live reachability. Source data came from PDFs, email notes, and Ansible files. Live reachability came from SSH, Ansible, and TCP checks on 2026-06-15.

## DNAT Table

| Device | Private IP | Public SSH endpoint | Source role | Live reachability |
| --- | --- | --- | --- | --- |
| JUMPHOST | `192.168.1.199` | `132.180.196.167:4050` | Planned jump host | Timed out |
| EMQX001 | `192.168.1.121` | `132.180.196.167:4021` | Raspberry Pi broker | SSH reachable from WSL |
| EMQX002 | `192.168.1.122` | `132.180.196.167:4022` | Raspberry Pi broker | Network unreachable |
| EMQX003 | `192.168.1.123` | `132.180.196.167:4023` | Raspberry Pi broker | SSH reachable from WSL |
| EMQX004 | `192.168.1.124` | `132.180.196.167:4024` | Raspberry Pi broker | SSH and Ansible reachable |
| EMQX005 | `192.168.1.125` | `132.180.196.167:4025` | Raspberry Pi broker | SSH and Ansible reachable |
| EMQX006 | `192.168.1.126` | `132.180.196.167:4026` | Raspberry Pi broker | SSH and Ansible reachable |
| EMQX007 | `192.168.1.127` | `132.180.196.167:4027` | Raspberry Pi broker | Network unreachable |
| EMAXAI001 | `192.168.1.131` | `132.180.196.167:4031` | AI Raspberry Pi | Timed out |
| EMQXAI002 | `192.168.1.132` | `132.180.196.167:4032` | AI Raspberry Pi | Timed out |
| JETSONAI001 | `192.168.1.141` | `132.180.196.167:4041` | Jetson Orin Nano | TCP open |
| JETSONAI002 | `192.168.1.142` | `132.180.196.167:4042` | Jetson Orin Nano | TCP open |

## Ansible Inventory

The active Ansible inventory manages four Raspberry Pis. The inventory file is `modules/administration/lab-ansible/hosts.admin.ini`. The same file exists on the management PC under `~/lab-ansible/hosts.admin.ini`.

| Ansible host | DNAT port | Live host name | Private IP | Live state |
| --- | --- | --- | --- | --- |
| `pi01` | `4022` | `EMQX002` from inventory | `192.168.1.122` | Unreachable |
| `pi02` | `4024` | `EMQX004` | `192.168.1.124` | Reachable |
| `pi03` | `4025` | `EMQX005` | `192.168.1.125` | Reachable |
| `pi04` | `4026` | `EMQX006` | `192.168.1.126` | Reachable |

The active Ansible inventory omits several reachable devices. The inventory omits `EMQX001` and `EMQX003`. The inventory also omits `EMQX007`, the AI Pis, the Jetsons, and the planned jump host. The omission may be intentional. The omission should be checked before automation grows.

## Source Conflicts

Older material contains conflicting management PC names. One older note maps `btq8x1` to `132.180.196.162`. The live management PC reports `BTQ8X1` at `132.180.196.164`. The live state should be treated as current until the chair IP assignment is verified.

The DNS server data also differs. One source lists `132.180.17.129` as the alternate DNS server. The live management PC reported `132.180.17.128`. The live state should be rechecked after the next network maintenance window.
