# Router and Switch

This page records the follow-up answers about the TinyHouse router and switch. Blank questionnaire fields remain undocumented. The network observations from 2026-06-15 remain available on the [Live Findings](/network/live-findings) page.

## Router

| Item | Documented value |
| --- | --- |
| Manufacturer | TP-Link |
| Model | Archer MR600 V3.0 |
| Serial number | `22412E3005278` |
| Firmware version | Not supplied |
| Management URL | Not supplied |
| Administrative access | Web UI and console through USB |
| Access boundary | Internal network only |
| Administrators | Wolfgang Reichelt and Christian Immenkamp |
| Credential storage | Not supplied |

### WAN Configuration

| Item | Value |
| --- | --- |
| Connection profile | `ipoe_1_s` |
| Assignment | Static |
| IPv4 address | `132.180.196.167` |
| Subnet mask | `255.255.255.0` |
| Gateway | `132.180.196.254` |
| Primary DNS | `132.180.17.1` |
| Secondary DNS | `132.180.17.129` |
| VLAN | None supplied (`na`) |

The questionnaire response for the LAN configuration repeated the WAN address, mask, gateway, and DNS values. The response did not confirm the documented private router address `192.168.1.1`. The DHCP range, static leases, NTP server, and local domain also remain undocumented.

The camera is documented at `132.180.196.165`. The answer did not identify whether the address is a DHCP reservation or a static configuration. No other DHCP reservations were supplied.

### Firewall and Forwarding

The router uses an IPv4 Stateful Packet Inspection (SPI) firewall. The supplied answer reports no source-IP restrictions or rate limits for DNAT access. The answer does not describe separate rules between the WAN, LAN, management PC, cameras, and sensor devices.

The supplied DNAT table contains only TCP forwarding to SSH port `22`. The questionnaire did not confirm additional forwarding for MQTT, Cockpit, the EMQX dashboard, HTTP, HTTPS, RTSP, or MJPEG. The complete supplied DNAT table is recorded in the [Network Inventory](/network/inventory).

A demilitarized zone (DMZ) rule is planned. The target, exposure, and activation criteria remain unspecified. No historical DNAT rules were identified for deletion.

### Configuration Backup

The router configuration has a backup in `RouterBackup/ArcherMR600V325091550622n.bin`. Restore the backup in the router Web UI through **Advanced → System Tools → Configuration Management** and the restore section. The backup date and a tested restore record were not supplied.

## Switch

| Item | Documented value |
| --- | --- |
| Name | `SW1-TH` |
| Model | HPE Aruba CX 6000 12G CL4 2SFP 139W |
| Firmware | `PL.10.10.1090` |
| Management address | `132.180.196.166` |
| Management access | Not supplied |
| Serial number | Not supplied |

The switch uses `VLAN10` for the internal network and also has `DEFAULT_VLAN_1`. Trunk configuration, access-port modes, port isolation, Spanning Tree Protocol settings, and other security settings remain undocumented.

| Port group | Current ports from the questionnaire |
| --- | --- |
| Public | `1/1/5`, `1/1/11`, `1/1/12`, `1/1/13`, `1/1/15`, `1/1/16` |
| Private | `1/1/1`, `1/1/2`, `1/1/3`, `1/1/4`, `1/1/6`, `1/1/7`, `1/1/8`, `1/1/9` |

The questionnaire confirms that current cable and port labels exist. The device-to-port and cable-to-port mapping was not supplied. The questionnaire also confirms that power-supply details such as Power over Ethernet (PoE), separate supplies, or an uninterruptible power supply exist. The answer does not identify which power arrangement applies to each device.

## University Network

The reserved TinyHouse addresses are `132.180.196.163` through `132.180.196.167` inclusive. Dr. Förster is the contact for changes to the university network, switch ports, firewall, or IP assignments.
