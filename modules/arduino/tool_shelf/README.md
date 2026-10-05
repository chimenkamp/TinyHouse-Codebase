# Tool shelf Hall sensor monitor

Open `tool_shelf.ino` in Arduino IDE, select **Arduino Uno** and the connected board's port, then upload. Open Serial Monitor at **9600 baud**. The sketch prints the raw digital state of all three connected sensors every 500 ms:

```text
A0=HIGH
A1=LOW
A2=HIGH
```

This is an output-format example, not a hardware capture. A0, A1 and A2 are used as digital inputs for the Hall modules' `S` signals. Connect each module's `+` to the Uno's 5 V and `−` to common GND. The sketch enables weak input pull-ups. Check the readings with each tool magnet present and absent before interpreting `HIGH` or `LOW` as tool presence; the sketch reports signal levels only.

`HALL_A3_PIN` through `HALL_A6_PIN` are deliberately unassigned (`UNCONNECTED_PIN = -1`), so those channels are neither initialized nor sampled or printed. Replace A3–A5's sentinel with the corresponding pin constant when connecting additional modules.

The [Uno has only six analog inputs, A0–A5](https://store.arduino.cc/products/arduino-uno-rev3). `HALL_A6_PIN` is an empty reserved channel, not an invented physical A6 connection. A seventh sensor will need a separately chosen available digital pin and an updated output label. This sketch is a standalone console monitor; it does not publish events or use the pressure-sensor serial protocol.

## PlatformIO

Open this folder as a PlatformIO project. [platformio.ini](platformio.ini) selects the [Arduino Uno board](https://docs.platformio.org/en/latest/boards/atmelavr/uno.html), Atmel AVR platform, Arduino framework and 9600-baud Serial Monitor. The source directory points to the existing sketch, so it also remains usable in Arduino IDE. Upload protocol and speed use the Uno board defaults; the USB port is detected automatically rather than tied to one computer.

From this directory:

```bash
pio run
pio run --target upload
pio device monitor
```

If several serial devices are connected, select the Uno's port in PlatformIO or supply `--upload-port` for uploading and `--port` for monitoring.

## Verification

From the repository root, compile for the actual Uno core:

```bash
'/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli' compile --fqbn arduino:avr:uno --build-path /private/tmp/tool-shelf-uno-build modules/arduino/tool_shelf
```

Run the host logic check:

```bash
clang++ -std=c++11 -Wall -Wextra -Werror modules/arduino/tests/tool_shelf_test.cpp -o /private/tmp/tool_shelf_test
/private/tmp/tool_shelf_test
```

The host check exercises all eight three-input combinations and verifies that only A0–A2 are configured and read. It substitutes Arduino I/O to test sketch logic; it does not establish physical sensor behavior. Real compilation checks compatibility with `arduino:avr:uno`. No upload or physical sensor test has been performed by this addition.

Both checks passed with Arduino AVR core 1.8.6 and the local host compiler. The Uno build uses 2,152 bytes of flash and 194 bytes of static RAM. The host check failed on the absent sketch before implementation and passed after the sketch was added; `git diff --check` also passed.

The PlatformIO build also passed with `pio run --project-dir modules/arduino/tool_shelf`, using Atmel AVR platform 5.3.0 and Arduino AVR framework package 5.4.0. It produces `.pio/build/uno/firmware.hex` with the same flash and RAM usage. Uploading and USB-port detection require a connected board and have not been tested.
