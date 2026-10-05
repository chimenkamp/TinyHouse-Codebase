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
| Keyestudio 37-in-1 Sensor Kit V3.0 | Five complete kits are inventory-listed; contents, identity, completeness, and operation are not physically verified |
| Keyestudio Hall Magnetic module | Candidate digital proximity module shown in the documented kit overview; verify the actual module before assignment |

## WA-1 Tool-Rack Presence Sensing

The WA-1 rack concept uses one Keyestudio Hall Magnetic module behind one designated tool slot. The official KS0487 documentation specifies digital on/off output, magnetic detection up to 3 cm, and a nominal 30 x 20 mm module envelope:

`https://docs.keyestudio.com/projects/KS0487/en/latest/ks0487.html`

The removable tool needs a securely retained magnet or equivalent magnetic tag. Commissioning must measure the actual PCB, Hall-element position, connector envelope, magnet distance, resting orientation, and tool wobble. It must also test debouncing, disconnect, stuck-high, and stuck-low behavior. An invalid or disconnected reading is `unknown`; an empty slot is evidence of removal only and does not prove correct tool use, inspection completion, or operator identity.

The sensor is research telemetry and is not a safety interlock. It must not control the printer or any protective function. Monitoring all seven rack slots requires seven sensor channels. The documented Arduino-class interface exposes four digital inputs, so full-rack coverage needs additional verified input capacity. The workbook lists five complete kits, not seven commissioned Hall modules.

### Removable seven-position adapter

The additional `wa1_tool_rack_sensor_adapter` attaches with two small C-shaped clamps on the rear bar of the rack's existing top cassette, without drilling the rack. It holds seven nominal 30 x 20 mm Hall modules in separate bays, provides a cable trough above them with exits at both ends, and leaves the Arduino boards separately mounted at the sides. See the [adapter files and assembly instructions](https://github.com/chimenkamp/TinyHouse-Codebase/tree/main/assets/3D/Workareas/wa1_tool_rack_sensor_adapter).

The rack's flat base sits against the wall, its support arms point outward, and tools pass vertically through the gaps. In the original CAD coordinates, x runs across the rack, y upward, and z outward from the wall at z = 0. The adapter stays above the rack with its sensor row near the wall and its printed geometry at z ≥ 8, so it needs no additional rack-to-wall spacing. The rack's independent wall attachment remains responsible for supporting the rack and tools.

Fit and wire the boards before mounting the adapter. Each uses two 150 mm nonconductive ties, no wider than 2.5 mm and no thicker than 1.2 mm, looped through separate upper slots and around the carrier floor with their heads at the front above the boards. Two nylon M3 x 8 screws gently retain the cassette clamps in tapped 2.6 mm pilot holes.

Place securely retained tool magnets on the wall-facing side at repeatable positions near the slot roots, around z = 26 and y = 75. Verify the actual Hall-element face, magnetic polarity and working gap. A magnet near the outer arm ends at z = 68 can exceed the documented maximum detection range; full-depth detection is not established. The neighbouring tool centres are only 22–26 mm apart, so test that one tool's magnet cannot report an adjacent empty slot as occupied. Printed fit and reliable sensing require physical commissioning.

The workbook lists five sensor kits (`Tabelle1!A2/C2`), so seven-slot coverage needs at least two additional Hall modules if each complete kit supplies one. A proposed arrangement routes four signals to one side Arduino and three to the other, subject to verified pin allocation and node capacity. No firmware or commissioned sensing integration is included with the printable adapter.

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
