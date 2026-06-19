# Data Platform

The data platform starts with sensor nodes. Each sensor node reads connected sensors through an Arduino or Nano class board. Each board can provide eight analog inputs and four digital inputs. Each board can also provide five volt power for connected sensors.

The Raspberry Pi layer receives sensor values. The planned receiver software reads serial RX/TX data from each Arduino. The receiver software should convert the readings into MQTT messages. The receiver software is not complete yet.

![TinyHouse data flow](/diagrams/data-flow.svg)

The MQTT broker layer has three documented designs. The first design uses one broker for all sensor nodes. The second design uses a broker cluster. The third design gives sensor nodes more compute capacity.

The current live system implements mixed broker services. The management PC runs Mosquitto on loopback. Several Raspberry Pis run Mosquitto on `0.0.0.0:1883`. `EMQX003` runs EMQX on `0.0.0.0:1883`.

The target analytics layer remains a proposal. The architecture PDF names Kafka, stream processing, time series storage, and dashboarding. Kafka can receive data through an MQTT bridge. Spark or Flink can process streams after Kafka receives messages.

## Message Shape

The architecture proposal shows JSON style MQTT messages. The proposal uses `SensorValues` as the payload field. The proposal uses machine names as topics. For example, a node can publish readings for `Machine A`.

The final topic convention still needs a project decision. A stable convention should include site, device, sensor, and unit. A stable convention should also include a timestamp policy. The policy should define whether the Pi or the sensor board owns the timestamp.

## Implementation Gap

The main implementation gap is the Pi receiver. The Arduino firmware can read sensors and send values through RX/TX. The Pi software must still parse those values and publish them to MQTT. The gap blocks end to end sensor ingestion.

The second implementation gap is broker standardization. The live system currently mixes Mosquitto and EMQX. The next architecture decision should confirm whether EMQX replaces Mosquitto or whether Mosquitto remains the local edge broker.
