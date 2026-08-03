# Network Inventory

The inventory combines source data and live reachability. Source data came from PDFs, email notes, and Ansible files. Live reachability came from SSH, Ansible, and TCP checks on 2026-06-15.

## DNAT Table

Every supplied rule forwards TCP to SSH port `22`. The router status comes from the follow-up questionnaire. The reachability results come from the separate inspection on 2026-06-15 and may not represent the current router state.

| ID | Router device name | Private IP | Public endpoint | Purpose | Router status | Owner | 2026-06-15 observation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `EMQX001` | `192.168.1.121` | `132.180.196.167:4021` | Raspberry Pi | Active | `WR` | SSH reachable from WSL |
| 2 | `EMQX002` | `192.168.1.122` | `132.180.196.167:4022` | Raspberry Pi | Inactive | `WR` | Network unreachable |
| 3 | `EMQX003` | `192.168.1.123` | `132.180.196.167:4023` | Raspberry Pi | Active | `WR` | SSH reachable from WSL |
| 4 | `EMQX004` | `192.168.1.124` | `132.180.196.167:4024` | Raspberry Pi | Active | `WR` | SSH and Ansible reachable |
| 5 | `EMQX005` | `192.168.1.125` | `132.180.196.167:4025` | Raspberry Pi | Active | `WR` | SSH and Ansible reachable |
| 6 | `EMQX006` | `192.168.1.126` | `132.180.196.167:4026` | Raspberry Pi | Active | `WR` | SSH and Ansible reachable |
| 7 | `EMQX007` | `192.168.1.127` | `132.180.196.167:4027` | Raspberry Pi | Inactive | `WR` | Network unreachable |
| 8 | `JETSON001` | `192.168.1.141` | `132.180.196.167:4041` | AI | Active | `WR` | TCP open |
| 9 | `JETSON002` | `192.168.1.142` | `132.180.196.167:4042` | AI | Active | `WR` | TCP open |
| 10 | `EMQX001AI` | `192.168.1.131` | `132.180.196.167:4061` | Raspberry Pi | Inactive | `WR` | Port `4031` timed out; `4061` was not tested |
| 11 | `EMQX002AI` | `192.168.1.132` | `132.180.196.167:4062` | Raspberry Pi | Inactive | `WR` | Port `4032` timed out; `4062` was not tested |
| 12 | `XXXXXXXXX` | `192.168.1.133` | `132.180.196.167:4063` | Raspberry Pi | Inactive | Dresden | Not tested |
| 13 | `JumpHost` | `192.168.1.150` | `132.180.196.167:4050` | SSH; Raspberry Pi with 8 GB memory | Inactive | `WR` | Timed out |

The questionnaire does not expand the owner abbreviation `WR`. The AI Raspberry Pis at `192.168.1.131` and `192.168.1.132` are reported as absent. Their physical location is unknown and they may have been sent to Dresden.

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

The AI Raspberry Pi port data also differs. The older inspection tested ports `4031` and `4032`. The supplied router table uses inactive ports `4061` and `4062`. No current reachability test confirms either mapping.
