# TinyHouse Lab Documentation

The TinyHouse Lab is a real world lab for sensor data. The lab connects sensors, Arduino based sensor nodes, Raspberry Pi brokers, Jetson edge computers, and a management PC. The documentation describes the current infrastructure and the intended data platform. The documentation also records the live network state from 2026-06-15.

<div class="tinyhouse-photo-grid">
  <figure>
    <img src="/images/tinyhouse/exterior-entrance.jpg" alt="TinyHouse exterior entrance">
    <figcaption>TinyHouse (Right View)</figcaption>
  </figure>
  <figure>
    <img src="/images/tinyhouse/exterior-side.jpg" alt="TinyHouse exterior side">
    <figcaption>TinyHouse (Screen)</figcaption>
  </figure>
  <figure>
    <img src="/images/tinyhouse/lab-interior.jpg" alt="TinyHouse lab interior">
    <figcaption>TinyHouse (Outside)</figcaption>
  </figure>
  <figure>
    <img src="/images/tinyhouse/equipment-wall.jpg" alt="TinyHouse equipment wall">
    <figcaption>TinyHouse (Left)</figcaption>
  </figure>
</div>

The current infrastructure has two layers. The university network exposes the management PC, the switch, and the router WAN side. The private TinyHouse network uses `192.168.1.0/24` behind the router. The router publishes selected devices through DNAT ports on `132.180.196.167`.

![TinyHouse network topology](/diagrams/network-topology.svg)

The current software state is mixed. Mosquitto runs on the management PC and several Raspberry Pis. EMQX runs on `EMQX003`. Docker runs on the reachable Raspberry Pis but no containers were running during inspection.

The documentation separates observed state from planned state. Older notes describe more devices than the Ansible inventory currently manages. Live probes reached `EMQX001`, `EMQX003`, `pi02`, `pi03`, and `pi04`. Live probes did not reach `pi01` on DNAT port `4022`.

## Reading Order

First read the network overview. The network overview explains the public network, the private network, and the DNAT boundary. Next read the inventory. The inventory maps device names to IP addresses, ports, sockets, and live reachability.

Second read the infrastructure pages. The management PC page describes Windows, WSL, and the controller role. The Raspberry Pi page describes the broker nodes and their live services.

Third read the MQTT page. The MQTT page describes brokers, addresses, listeners, and observed topics. Then read the operations pages. The Ansible page describes provisioning and daily administration.

## Main Status

| Area | Current state |
| --- | --- |
| Management PC | Windows host `BTQ8X1` reachable through `ssh tinyhouse` |
| WSL controller | Ubuntu 24.04.3 with `~/lab-ansible` |
| Private network | `192.168.1.0/24` behind the TinyHouse router |
| Router WAN | `132.180.196.167` |
| Switch | `SW1-TH` at `132.180.196.166` |
| Reachable Pis | `EMQX001`, `EMQX003`, `EMQX004`, `EMQX005`, and `EMQX006` |
| MQTT services | Mosquitto and EMQX |
| Main MQTT port | `1883` |
| Sensor bridge | Arduino to Pi receiver software is not complete |
