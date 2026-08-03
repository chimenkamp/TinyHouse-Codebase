# Data Platform

The data platform starts with sensor nodes. Each sensor node reads connected sensors through an Arduino or Nano class board. Each board can provide eight analog inputs and four digital inputs. Each board can also provide five volt power for connected sensors.

The Raspberry Pi layer receives sensor values. The planned receiver software reads serial RX/TX data from each Arduino. The receiver software should convert the readings into MQTT messages. The receiver software is not complete yet.

![TinyHouse data flow](/diagrams/data-flow.svg)

The MQTT broker layer has three documented designs. The first design uses one broker for all sensor nodes. The second design uses a broker cluster. The third design gives sensor nodes more compute capacity. The final design remains undecided and the follow-up answer recommends the cluster design.

The current live system implements mixed broker services. The management PC runs Mosquitto on loopback. Several Raspberry Pis run Mosquitto on `0.0.0.0:1883`. `EMQX003` runs EMQX on `0.0.0.0:1883`.

The target analytics layer remains a historical proposal. The architecture PDF names Kafka, stream processing, time series storage, and dashboarding. However, the current project constraint explicitly prohibits MQTT bridges to external brokers, Kafka, databases, and cloud services. The proposal cannot be implemented through an MQTT bridge unless the project changes that constraint.

## Message Shape

The architecture proposal shows JSON style MQTT messages. The proposal uses `SensorValues` as the payload field. The proposal uses machine names as topics. For example, a node can publish readings for `Machine A`.

The follow-up answer defines the message categories `sensor`, `devstatus`, `heartbeat`, and `data`. The answer also defines the field sets on the [MQTT overview](/mqtt/). The complete topic paths, units, value types, and timestamp policy still need a project decision.

## Implementation Gap

The main implementation gap is the Pi receiver. The Arduino firmware can read sensors and send values through RX/TX. The Pi software must still parse those values and publish them to MQTT. The gap blocks end to end sensor ingestion.

The second implementation gap is broker standardization. The live system currently mixes Mosquitto and EMQX. The next architecture decision should confirm whether EMQX replaces Mosquitto or whether Mosquitto remains the local edge broker.
