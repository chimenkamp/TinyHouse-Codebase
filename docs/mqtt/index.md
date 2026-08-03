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

The follow-up answer attributes the EMQX migration to Maximilian and identifies the migrated EMQX instance as the broker. The answer does not document the migration procedure or define the intended role of each remaining Pi.

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

## Architecture Decision State

The final broker architecture remains undecided. The follow-up answer recommends an EMQX cluster. The project has not yet accepted that recommendation or decided whether Mosquitto remains on `EMQX001`, `EMQX004`, `EMQX005`, and `EMQX006`.

The initial transport policy uses MQTT over TCP on port `1883`. MQTT over Transport Layer Security (TLS) on port `8883` is an allowed future option. No TLS certificates, users, access-control lists, or client certificates were reported.

External bridges are prohibited under the supplied project constraint. No MQTT bridge to an external broker, Kafka, database, or cloud service is configured or planned under the current constraint.

The respondent does not use the EMQX dashboard and reports that the dashboard was not installed. However, the 2026-06-15 inspection observed an EMQX listener on private port `18083` on `EMQX003`. The difference requires a current service check. The respondent uses MQTT Explorer instead.

## Topics

The live topic probe subscribed to `#` on reachable brokers. The Mosquitto brokers produced `$SYS/broker/...` system topics. The Mosquitto brokers did not produce application sensor topics during the probe window.

The EMQX broker produced EMQX system topics. The observed topics were `$SYS/brokers`, `$SYS/brokers/emqx@127.0.0.1/sysdescr`, and `$SYS/brokers/emqx@127.0.0.1/version`. The observed version payload was `5.8.0`.

The application topic scheme was not observed during the 2026-06-15 inspection. The follow-up answer defines four application categories and their field sets. The receiver software for Arduino to Pi data is still incomplete.

## Supplied Topic and Field Convention

The supplied convention names `sensor`, `devstatus`, `heartbeat`, and `data`. The answer specifies field names but does not specify the complete MQTT topic paths, value types, units, timestamp format, Quality of Service levels, retained-message behavior, or Last Will and Testament behavior.

| Category | Required fields from the supplied answer |
| --- | --- |
| `sensor` | `device_id`, `drawer`, `timestamp`, `weight`, `batvoltage`, `wifi_connencted`, `mqtt_connected` |
| `devstatus` | `device_id`, `drawer`, `timestamp`, `wifi_rssi`, `wifi_ssid`, `ip_address`, `free_heap`, `uptime`, `batvoltage` |
| `heartbeat` | `device_id`, `drawer`, `timestamp`, `uptime`, `status`, `wifi_connencted`, `mqtt_connected` |
| `data` | `device_id`, `drawer`, `timestamp`, `wifi_rssi`, `wifi_ssid`, `ip_address`, `free_heap`, `wifi_ant_m`, `batvoltage` |

The field name `wifi_connencted` preserves the spelling in the supplied contract. A compatibility decision is required before correcting the spelling because deployed producers or consumers may already depend on the field name.

## Earlier Proposed Topic Convention

The earlier documentation proposed stable lab identifiers. The proposal is not the supplied binding convention because the follow-up answer only names the four categories above. The proposal separates site, device, sensor, and measure.

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

The MQTT inventory should be standardized. `EMQX001` and `EMQX003` should be added to Ansible if they are intended broker nodes. `pi01` should be repaired or removed from the inventory. The project should accept or reject the recommended EMQX cluster before changing broker services.

The broker service model should be simplified. Either EMQX should replace Mosquitto on all broker Pis, or EMQX should be disabled where Mosquitto remains the edge broker. The current mixed state makes operational behavior harder to reason about.

The MQTT security model should be decided before student access expands. Anonymous access is currently enabled on Mosquitto. EMQX dashboard exposure should be reviewed because the 2026-06-15 inspection found port `18083` active on the private network.

The topic namespace should be implemented in the Pi receiver. The receiver should publish one test topic before sensors are attached. A retained health topic per Pi would make broker discovery easier.
