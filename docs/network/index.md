# Network Overview

The TinyHouse network has a public side and a private side. The public side uses the university subnet `132.180.196.0/24`. The private side uses `192.168.1.0/24` behind the TinyHouse router. DNAT rules expose selected private devices through the router WAN address.

The management PC currently sits on the public side. The live host name is `BTQ8X1`. The live Ethernet address is `132.180.196.164`. The Wi-Fi adapter was disconnected during inspection.

The router bridges access into the private side. The router WAN address is `132.180.196.167`. The router LAN address is `192.168.1.1`. The router exposes Raspberry Pis, Jetsons, and planned jump hosts through SSH ports.

The switch separates public and private port groups. The switch management address is `132.180.196.166`. The documented public port group is `1/1/11`, `1/1/13`, `1/1/15`, and `1/1/16`. The documented private port group is `1/1/1` through `1/1/10`, plus `1/1/12` and `1/1/14`.

![TinyHouse access model](/diagrams/access-model.svg)

## Physical Connection

The physical uplink is part of the network baseline. The installation photos show the fiber connection area. The photos are kept as documentation assets rather than as loose source files.

<div class="tinyhouse-photo-grid">
  <figure>
    <img src="/images/tinyhouse/fiber-connection-1.jpg" alt="TinyHouse fiber connection detail">
    <figcaption>Fiber connection detail</figcaption>
  </figure>
  <figure>
    <img src="/images/tinyhouse/fiber-connection-2.jpg" alt="TinyHouse fiber connection overview">
    <figcaption>Fiber connection overview</figcaption>
  </figure>
</div>

## Public Network

| Device | Address | Role | Live note |
| --- | --- | --- | --- |
| Management PC | `132.180.196.164` | Windows and WSL controller | Live host reported `BTQ8X1` |
| TinyHouse router WAN | `132.180.196.167` | DNAT endpoint | Several DNAT ports are reachable |
| Switch `SW1-TH` | `132.180.196.166` | Managed switch | Source PDF lists this address |
| University gateway | `132.180.196.254` | Default gateway | Live route uses this gateway |
| DNS server | `132.180.17.1` | DNS | Live management PC uses this server |
| DNS server | `132.180.17.128` | DNS | Live management PC uses this server |

## Private Network

| Network item | Value |
| --- | --- |
| Private subnet | `192.168.1.0/24` |
| Router LAN address | `192.168.1.1` |
| Management PC private address from source | `192.168.1.100` |
| Scale address from source | `192.168.1.106` |
| Raspberry Pi range from source | `192.168.1.121` to `192.168.1.127` |
| AI Raspberry Pi range from source | `192.168.1.131` to `192.168.1.132` |
| Jetson range from source | `192.168.1.141` to `192.168.1.142` |

The private network was not directly reachable from the management PC during inspection. The Wi-Fi adapter was disconnected. Therefore direct checks against `192.168.1.x` devices were not possible from the management PC.
