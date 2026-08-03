# Sensor Layer

The sensor layer starts at Arduino class boards. Each board can read eight analog inputs and four digital inputs. Each board can provide five volt power for attached sensors. The current installation uses USB serial between the Nano and Raspberry Pi. An RX/TX connection is under development.

The Raspberry Pi receiver is the missing bridge. The receiver should parse the serial data. The receiver should publish readings into MQTT. The receiver software is not finished yet.

![Sensor overview](/images/sensors/overview.png)

## Available Sensors

| Sensor or device | Source state |
| --- | --- |
| Weight sensors | Several sensors are available and can measure up to 30 kg |
| Network scale | Reachable at `192.168.1.106` when the private network is reachable |
| IR cameras | Two devices are available but not implemented |
| XIAO ESP32S3 Sense camera | Candidate camera module from source notes |
| XIAO 5MP camera | Candidate camera accessory from source notes |

## Installed and Planned Boards

The installation currently has five ESP boards for the scales and one Arduino Nano for sensor reading. The plan calls for ten Nano boards. Each of ten Raspberry Pis should receive one Nano.

The current Nano connection uses USB serial. An RX/TX replacement is under development. The supplied answers do not map individual boards to Pis or document pins, wiring diagrams, firmware versions, serial protocol details, sampling rates, timestamp ownership, identifier assignment, calibration storage, or ownership of the Pi receiver implementation.

The network scale has a known private address. The source note lists `192.168.1.106`. The source note says the scale has no user and no password. The source note says the scale sends weight data.

The network scale has one important access condition. The management PC must be connected to the TinyHouse Wi-Fi to reach `192.168.1.106`. The live management PC Wi-Fi was disconnected during inspection. Therefore the scale was not verified during the live pass.

## Data Capture

The Arduino firmware uses a main loop. The loop interval is configurable. The loop reads all connected sensors. The loop sends the readings over RX/TX to the Pi.

The MQTT payload schema still needs final definition. The architecture proposal uses JSON style messages. The proposal shows `SensorValues` and machine topic names. A production schema should define units, timestamps, calibration metadata, and sensor IDs.

## Calibration Notes

The source note gives one scale calibration detail. The empty scale reported about `130 g`. The note says the scale was not exactly tared. Future experiments should record tare weight before each run.
