# Hardware Baseline and Roadmap

## Evidence-Graded Baseline

The baseline distinguishes documented capability from assumed availability. The distinction prevents the laboratory design from depending on an unverified model or interface.

| Hardware or capability | Evidence | Known state | Integration use | Required verification |
| --- | --- | --- | --- | --- |
| Management PC with Windows and WSL | Documented | Operational access point | Site orchestration and administration | Capacity, backup, and hardened service baseline |
| Reachable Raspberry Pis | Documented | Five nodes reached in the 2026-06-15 inspection | MQTT, adapters, outbox, health | Final inventory, operating-system target, broker role |
| Unreachable or absent Raspberry Pis | Documented | Several planned nodes are unavailable | Future scale-out | Physical location and cluster membership |
| Two Jetson devices | Documented | TCP access exists but hardware and services are unknown | Optional local vision | Model, OS, storage, services, and permission to modify |
| Arduino-class boards | Documented | One Nano is installed and ten are planned | Sensor acquisition | Wiring, firmware, framing, sampling, and timestamps |
| ESP boards for scales | Documented | Five boards are reported | Weight-sensor nodes | Board models, firmware, calibration, and MQTT behavior |
| Weight sensors | Documented | Several sensors support up to 30 kg | Presence, inventory, and mass checks | Accuracy, resolution, interface, and calibration |
| Network scale | Documented | Address known but live function unverified | Package and calibration evidence | Protocol, units, authentication, and tare procedure |
| Two IR cameras | Documented | Available but not implemented | Privacy-preserving heat or presence features | Resolution, interface, field of view, and lawful use |
| XIAO ESP32S3 Sense camera | Documented candidate | Candidate from source notes | Low-cost workpiece vision | Exact board, camera revision, firmware, and retention mode |
| XIAO 5 MP camera | Documented candidate | Candidate accessory | Higher-resolution workpiece image | Compatibility and optical requirements |
| Public-network camera | Documented | Address known | Room or workcell view | Model, owner, access, camera zone, and retention |
| Robot arm in TinyHouse | User-confirmed | Available | Handling, kitting, inspection, or collaborative assembly | Model, controller, payload, gripper, safety, and API |
| 3D printer in TinyHouse | User-confirmed | Available | Enclosure-base production | Model, controller, build volume, materials, and telemetry |
| Robot arm in Munich | User-confirmed | Available | Handling or inspection of remote component | Model, controller, payload, gripper, safety, and API |
| 3D printer in Munich | User-confirmed | Available | Lid or mount production | Model, controller, build volume, materials, and telemetry |
| Solar panels on TinyHouse | Image-observed | Electrical instrumentation is not documented | Future energy-aware scheduling | Electrical owner, meter, safety, and available data |
| Workcell or dome camera | Image-observed | Operational state is not documented | Workcell monitoring candidate | Model, owner, field of view, and access |
| Desktop 3D printer in interior image | Image-observed | User confirms a printer but model linkage is unknown | Additive manufacturing | Confirm that the imaged unit is the active printer |

## Sensor-Kit Visual Inventory

The sensor overview image depicts the modules below. The Markdown documentation does not confirm that every depicted module is physically present or working. The pilot must inventory each module before assigning an asset identifier.

| Group | Image-observed modules | Proposed process use |
| --- | --- | --- |
| Human input | Button switch, capacitive touch, joystick, rotary encoder, potentiometer | Task confirmation, configuration choice, manual control |
| Visual output | White LED, RGB LED, traffic light, magic light cup, four-digit display | Process state, privacy mode, alert, countdown |
| Audible output | Passive buzzer modules | Local task and exception prompt |
| Presence and motion | PIR motion, ultrasonic distance, obstacle avoidance, line tracking | Workpiece presence, station occupancy, robot approach evidence |
| Position and contact | Photo interrupter, reed switch, hall magnetic sensor, ball tilt, crash sensor, knock sensor | Door state, fixture state, container closure, vibration event |
| Optical and infrared | Photocell, IR receiver, IR transmitter | Light condition, simple object detection, device control |
| Environment | LM35 temperature, DHT11 temperature and humidity, flame, steam, soil moisture, water-level plate | Print environment, storage condition, spill or heat demonstration |
| Sound and vibration | Microphone, ceramic vibration sensor | Machine-state feature and handling evidence |
| Electrical | Voltage detection, relay | Battery state and low-voltage control |
| Biometric | Pulse-rate monitor | Exclude from baseline because the process does not require biometric data |

The flame and relay modules must not serve as certified safety devices. The biometric module should remain outside the baseline. A separate approved human-subject protocol would be required before biometric use.

## Buy-Nothing Pilot

The first pilot should use existing equipment. QR labels can provide component, product, shipment, and workstation identity. Existing weight sensors can provide mass evidence. Existing buttons, traffic lights, buzzers, and displays can support human tasks.

The initial process does not require RFID. QR identity also creates visible and auditable handoffs. The existing camera candidates can scan QR codes after privacy zones are approved.

## Low-Cost Additions

The table lists optional additions in recommended order. Prices are manufacturer-listed United States dollar prices observed on 2026-08-03. Taxes, shipping, availability, and currency conversion are excluded. Procurement must recheck price and availability.

| Priority | Addition | Purpose | Current manufacturer evidence | Decision |
| --- | --- | --- | --- | --- |
| 1 | HX711 load-cell amplifier | Connect inexpensive load cells to a microcontroller | SparkFun lists the HX711 board at USD 4.95 and documents 2.7 V to 5 V operation with 10 or 80 samples per second | Buy only if existing scale boards lack a usable interface |
| 2 | XIAO ESP32S3 Sense | QR capture, local image features, microphone-free or camera-free variants | Seeed lists the board at USD 13.99 with camera, digital microphone, Wi-Fi, Bluetooth Low Energy, PSRAM, flash, and SD support | Strong low-cost candidate because the docs already name the board family |
| 3 | Raspberry Pi Camera Module 3 | Autofocus workpiece inspection on a compatible Pi | Raspberry Pi lists the standard camera from USD 25 with a 12 MP sensor and autofocus | Buy when repeatable close-range images exceed existing camera capability |
| 4 | NFC or RFID reader | Touch-free object identity after the QR baseline | Adafruit lists a PN532 shield at USD 39.95 but the official page reported out-of-stock status | Defer until QR limitations are measured |
| 5 | USB barcode scanner | Fast manual identity capture | No manufacturer and interface have been selected | Evaluate only after camera-based QR trials |
| 6 | Calibrated environmental sensor | Print-condition context | No model has been selected | Select against required accuracy and calibration evidence |
| 7 | Plug-level energy meter | Energy-aware scheduling and machine-state features | No model has been selected | Select with the university electrical and network owners |
| 8 | Tamper-evident seals and label printer | Shipment custody and object identity | Commodity supplies require local procurement | Add before real cross-site shipments |

## Manufacturer Sources

- [SparkFun HX711 load-cell amplifier](https://www.sparkfun.com/sparkfun-load-cell-amplifier-hx711.html)
- [Seeed Studio XIAO ESP32S3 Sense](https://www.seeedstudio.com/XIAO-ESP32S3-Sense-p-5639.html)
- [Raspberry Pi Camera Module 3](https://www.raspberrypi.com/products/camera-module-3/)
- [Adafruit PN532 NFC or RFID shield](https://www.adafruit.com/product/789)

## Station Design

| Station | Minimum hardware | Optional evidence | Human interaction |
| --- | --- | --- | --- |
| Order station | Browser and QR label output | Button or rotary selector | Configuration and consent check |
| Print station | Printer and adapter host | Camera, temperature, power | Material load and recovery |
| Inspection station | Camera or scale and stable lighting | Robot pose and fixture sensor | Review uncertain result |
| Packing station | QR scanner and package scale | Seal identifier | Pack and dispatch confirmation |
| Receiving station | QR scanner and scale | Camera-derived seal check | Custody and discrepancy review |
| Assembly station | Robot, fixture, scanner | Force or presence sensor | Electronics installation and approval |
| Calibration station | Reference and sensor interface | Network scale or load-cell trace | Guided calibration |
| Deployment station | Gateway and heartbeat monitor | Environmental context sensors | Placement and activation |

## Robot End Effector Strategy

The first robot task should avoid complex insertion. The arm can move a printed component between a tray, inspection fixture, scale, and kitting area. A simple printed parallel-gripper finger or vacuum cup can handle a standardized geometry.

The component design should include robot-friendly features. Recommended features include a flat grasp face, a known orientation, a fiducial area, and a fixture datum. The product should tolerate a manual fallback without changing object identity.

## Standard Test Artifact

The printed artifact should remain short and repeatable. The base and lid should include fit features, a QR area, a dimensional coupon, a mass target, and one controlled-defect region. The design revision must include the model hash and slicer-profile hash.

The artifact should avoid unnecessary material. The artifact should also avoid geometries that require unsafe robot access to the printer. Human unloading can remain the baseline when the printer was not designed for robotic unloading.

## Hardware Acceptance Record

Each device needs a one-page acceptance record before use. The record should contain the asset identifier, owner, model, serial number, firmware, network address class, controller protocol, adapter version, supported commands, safety boundary, calibration state, clock source, and known limitations.

