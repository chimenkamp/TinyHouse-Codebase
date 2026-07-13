# XIAO ESP32S3 Sense USB camera bridge

This folder now contains working source code for the XIAO ESP32S3 Sense camera board so it can send camera frames to this Mac over the direct USB-C connection.

The implementation uses the board's native USB serial interface, not USB webcam mode. That is the practical path on this hardware with the standard Arduino ESP32 stack and it keeps the protocol open for later robot-arm control messages.

## Added files

- `usb_serial_camera_bridge/usb_serial_camera_bridge.ino`: firmware for the microcontroller
- `usb_serial_camera_bridge/camera_pins_xiao_esp32s3.h`: fixed camera pin mapping for the Sense board
- `usb_serial_camera_viewer.py`: combined Python receiver for live view, Lego brick detection, and camera calibration on this Mac

## What the firmware does

- Initializes the OV3660 camera on the XIAO ESP32S3 Sense
- Captures JPEG frames continuously
- Streams them over the board's USB serial port at `921600` baud
- Accepts simple text commands from the Mac:
	- `PING`
	- `STREAM ON`
	- `STREAM OFF`
	- `SNAP`
	- `SET QUALITY <4-63>`
	- `SET FRAMESIZE QQVGA|QVGA|VGA|SVGA|XGA|SXGA|UXGA`
	- `ARM ...` reserved for later robot-arm control commands

## Flashing the board

1. Install Arduino IDE 2.x.
2. Add the ESP32 boards package from Espressif.
3. Select board `XIAO_ESP32S3`.
4. In board options, enable PSRAM.
5. Open `usb_serial_camera_bridge/usb_serial_camera_bridge.ino`.
6. Pick the XIAO serial port on macOS, usually something like `/dev/cu.usbmodem*`.
7. Upload the sketch.

If upload fails, hold the board's boot button while starting the upload, then release it once flashing begins.

## Running the combined host pipeline on this Mac

Install the required Python packages in your project environment:

```bash
pip install pyserial opencv-contrib-python numpy inference
```

The script is now configured in code instead of through CLI flags.

Edit `default_settings()` in `usb_serial_camera_viewer.py` or create your own `PipelineSettings(...)` object and call `run(settings)`.

Example:

```python
from pathlib import Path

from Xiao_ESP32S3_Sense.usb_serial_camera_viewer import Goal, PipelineSettings, run

settings = PipelineSettings(
	goal=Goal.DETECT_LEGO_BRICKS,
	port=None,
	framesize="SVGA",
	save_dir=Path("captures"),
	confidence=0.5,
)

run(settings)
```

Available goals:

- `Goal.VIEW_FEED`: show the live camera feed only
- `Goal.DETECT_LEGO_BRICKS`: run Roboflow Lego brick detection on the USB camera feed
- `Goal.CALIBRATE_INTRINSICS`: capture ChArUco observations and save `intrinsics`, `distortion`, and `reprojection_error` to an `.npz` file

If `port` is left as `None`, the script tries to auto-detect the XIAO serial device.

Viewer keys:

- `q`: quit
- `space`: toggle continuous streaming
- `s`: request a single extra frame
- `1`: set `QVGA`
- `2`: set `VGA`
- `3`: set `SVGA`
- `4`: set `XGA`
- `c`: save the current frame when `--save-dir` is set

Calibration notes:

- Use a printed ChArUco board and move it through different positions and angles in view of the camera.
- Press `space` only when the detected corners are visible on screen.
- Press `q` to finish calibration once enough captures have been collected.
- Set `goal=Goal.CALIBRATE_INTRINSICS` and adjust `calibration_output` and `min_captures` in `PipelineSettings` as needed.

## Protocol summary

Each packet from the board starts with a fixed binary header:

- `magic`: `0x4D414353` (`SCAM`)
- `msg_type`: `0x01` frame, `0x02` status
- `width`: `uint16`
- `height`: `uint16`
- `format`: `1` for JPEG
- `payload_length`: `uint32`
- `board_millis`: `uint32`
- `payload`: JPEG bytes or UTF-8 status text

This keeps the PC side simple and is a better fit than trying to force the board into unsupported native UVC webcam behavior.

## Next step for robot-arm control

When you are ready, the host application can analyze frames on the Mac and send commands like `ARM BASE 90` or `ARM GRIP OPEN` back over the same USB serial link. The current firmware already reserves that command path and acknowledges received arm commands.

## Hardware reference

Product link: https://www.reichelt.de/de/de/shop/produkt/xiao_esp32s3_sense_wifi_bt_kamera_ov3660_ohne_header-358353