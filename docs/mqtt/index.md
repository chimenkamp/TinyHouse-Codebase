# MQTT Overview

The MQTT layer is the current data exchange layer. The layer uses Mosquitto on the management PC and most reachable Raspberry Pis. The layer uses EMQX as the serving broker on `EMQX003`. The collection report from 2026-06-15 is the current source of truth.

![MQTT overview](/diagrams/mqtt-overview.svg)

## Broker Summary

| Broker host | Private address | Public endpoint | Serving broker | Listener state |
| --- | --- | --- | --- | --- |
| Management PC `BTQ8X1` | Not on private network during inspection | `ssh tinyhouse` only | Mosquitto 2.1.2 | `127.0.0.1:1883`, `127.0.0.1:9883`, `[::1]:1883` |
| `EMQX001` | `192.168.1.121` | `132.180.196.167:4021` | Mosquitto | `0.0.0.0:1883`, `[::]:1883` |
| `EMQX003` | `192.168.1.123` | `132.180.196.167:4023` | EMQX Enterprise 5.8.0 | `0.0.0.0:1883`, `8883`, `8083`, `8084`, `18083` |
| `EMQX004` | `192.168.1.124` | `132.180.196.167:4024` | Mosquitto | `0.0.0.0:1883` |
| `EMQX005` | `192.168.1.125` | `132.180.196.167:4025` | Mosquitto | `0.0.0.0:1883` |
| `EMQX006` | `192.168.1.126` | `132.180.196.167:4026` | Mosquitto | `0.0.0.0:1883` |

The management PC broker is local only. The Windows service name is `mosquitto`. The service executable is `C:\Program Files\Mosquitto\mosquitto.exe`. The service starts automatically as `LocalSystem`. The broker reported Mosquitto version `2.1.2` through `$SYS/broker/version`.

The Pi Mosquitto brokers share the same edge configuration. Mosquitto uses `/etc/mosquitto/mosquitto.conf`. The service starts `/usr/sbin/mosquitto -c /etc/mosquitto/mosquitto.conf`. The listener binds to `0.0.0.0:1883`. The Pi brokers reported Mosquitto version `2.0.22` through `$SYS/broker/version`.

The EMQX broker serving traffic runs on `EMQX003`. EMQX starts through `emqx.service`. The service runs `/usr/bin/emqx foreground`. The broker reported `$SYS/brokers/emqx@127.0.0.1/version 5.8.0` during the topic probe.

## Installed Broker Packages

The reachable Pis have both broker stacks installed. Each reachable Pi reported `emqx-enterprise-5.8.0-1.el9.aarch64`. Each reachable Pi also reported `mosquitto-2.0.22-1.el9.aarch64`.

The serving broker differs from the installed packages. `EMQX003` is the only node where EMQX owns the MQTT listener ports. `EMQX001`, `EMQX004`, `EMQX005`, and `EMQX006` expose Mosquitto on port `1883`.

The EMQX service state needs cleanup. `EMQX001`, `EMQX004`, and `EMQX005` reported `emqx.service` as `activating`. `EMQX006` reported `emqx.service` as `active`, but Mosquitto still owned port `1883` and no EMQX listener ports were visible. Therefore listener ownership is the reliable indicator for the serving broker.

## Mosquitto Configuration

The Pi Mosquitto configuration is intentionally small. The configuration enables persistence. The configuration stores persistence data under `/var/lib/mosquitto/`. The configuration writes logs to syslog.

```text
pid_file /run/mosquitto/mosquitto.pid
persistence true
persistence_location /var/lib/mosquitto/
log_dest syslog
listener 1883 0.0.0.0
allow_anonymous true
```

The Mosquitto configuration allows anonymous access. This setup is practical for lab bring-up. This setup is not a final security posture for shared experiments.

## EMQX Listener Map

| Port | Observed owner | Meaning |
| --- | --- | --- |
| `1883` | `emqx.service` | MQTT TCP |
| `8883` | `emqx.service` | MQTT over TLS |
| `8083` | `emqx.service` | MQTT over WebSocket |
| `8084` | `emqx.service` | MQTT over secure WebSocket |
| `18083` | `emqx.service` | EMQX dashboard |
| `4370` | `emqx.service` | EMQX Erlang distribution |
| `5370` | `emqx.service` | EMQX cluster RPC |

The EMQX listener map applies to `EMQX003`. Other reachable Pis have the EMQX package and service file. Other reachable Pis did not expose these EMQX listener ports in the collection report.

## Topics

The live topic probe subscribed to `#` on reachable brokers. The Mosquitto brokers produced `$SYS/broker/...` system topics. The Mosquitto brokers did not produce application sensor topics during the probe window.

The EMQX broker produced EMQX system topics. The observed topics were `$SYS/brokers`, `$SYS/brokers/emqx@127.0.0.1/sysdescr`, and `$SYS/brokers/emqx@127.0.0.1/version`. The observed version payload was `5.8.0`.

The application topic scheme is not active yet. The architecture notes suggest machine topics and JSON messages with sensor values. The receiver software for Arduino to Pi data is still incomplete. Therefore no production sensor topic namespace was observed.

## Proposed Topic Convention

The MQTT topic convention should use stable lab identifiers. The convention should separate site, device, sensor, and measure. The convention should avoid spaces because many MQTT tools handle simple path tokens more reliably.

```text
tinyhouse/<device>/<sensor>/<measure>
```

The payload should be JSON. The payload should include timestamp, value, unit, device ID, sensor ID, and quality state. The payload should also include calibration metadata when a sensor needs tare or offset correction.

```json
{
  "timestamp": "2026-06-15T00:00:00Z",
  "device": "emqx004",
  "sensor": "scale-01",
  "measure": "weight",
  "value": 0.13,
  "unit": "kg",
  "quality": "raw"
}
```

## Next Actions

The MQTT inventory should be standardized. `EMQX001` and `EMQX003` should be added to Ansible if they are intended broker nodes. `pi01` should be repaired or removed from the inventory. `EMQX003` should be declared as the EMQX node or converted back to Mosquitto.

The broker service model should be simplified. Either EMQX should replace Mosquitto on all broker Pis, or EMQX should be disabled where Mosquitto remains the edge broker. The current mixed state makes operational behavior harder to reason about.

The MQTT security model should be decided before student access expands. Anonymous access is currently enabled on Mosquitto. EMQX dashboard exposure should be reviewed because port `18083` is active on the private network.

The topic namespace should be implemented in the Pi receiver. The receiver should publish one test topic before sensors are attached. A retained health topic per Pi would make broker discovery easier.
