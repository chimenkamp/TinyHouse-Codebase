#include <Arduino.h>
#include <esp_camera.h>

#include "camera_pins_xiao_esp32s3.h"

namespace {

constexpr uint32_t SERIAL_BAUD = 921600;
constexpr uint32_t STARTUP_DELAY_MS = 1200;
constexpr uint32_t IDLE_POLL_DELAY_MS = 5;
constexpr uint32_t HEARTBEAT_INTERVAL_MS = 2000;
constexpr size_t MAX_COMMAND_LEN = 96;

constexpr uint32_t FRAME_MAGIC = 0x4D414353UL;  // "SCAM" little-endian on the wire.
constexpr uint8_t MSG_FRAME = 0x01;
constexpr uint8_t MSG_STATUS = 0x02;

bool streaming_enabled = true;
framesize_t current_frame_size = FRAMESIZE_UXGA;
uint8_t current_jpeg_quality = 12;
uint32_t last_heartbeat_ms = 0;

char command_buffer[MAX_COMMAND_LEN + 1];
size_t command_length = 0;

void write_u16(uint16_t value) {
  uint8_t bytes[2] = {
      static_cast<uint8_t>(value & 0xFF),
      static_cast<uint8_t>((value >> 8) & 0xFF),
  };
  Serial.write(bytes, sizeof(bytes));
}

void write_u32(uint32_t value) {
  uint8_t bytes[4] = {
      static_cast<uint8_t>(value & 0xFF),
      static_cast<uint8_t>((value >> 8) & 0xFF),
      static_cast<uint8_t>((value >> 16) & 0xFF),
      static_cast<uint8_t>((value >> 24) & 0xFF),
  };
  Serial.write(bytes, sizeof(bytes));
}

void send_status(const String& message) {
  write_u32(FRAME_MAGIC);
  Serial.write(MSG_STATUS);
  write_u16(0);
  write_u16(0);
  Serial.write(static_cast<uint8_t>(0));
  write_u32(static_cast<uint32_t>(message.length()));
  write_u32(millis());
  Serial.write(reinterpret_cast<const uint8_t*>(message.c_str()), message.length());
  Serial.flush();
}

bool apply_sensor_defaults(sensor_t* sensor) {
  if (sensor == nullptr) {
    return false;
  }

  if (sensor->id.PID == OV3660_PID) {
    sensor->set_vflip(sensor, 1);
    sensor->set_brightness(sensor, 1);
    sensor->set_saturation(sensor, -2);
  }

  sensor->set_framesize(sensor, current_frame_size);
  sensor->set_quality(sensor, current_jpeg_quality);
  return true;
}

bool init_camera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = current_frame_size;
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = current_jpeg_quality;
  config.fb_count = 2;

  if (!psramFound()) {
    config.frame_size = FRAMESIZE_QVGA;
    config.fb_location = CAMERA_FB_IN_DRAM;
    config.fb_count = 1;
  }

  const esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    send_status(String("camera_init_failed:") + String(static_cast<int>(err)));
    return false;
  }

  if (!apply_sensor_defaults(esp_camera_sensor_get())) {
    send_status("sensor_unavailable");
    return false;
  }

  send_status("camera_ready");
  return true;
}

framesize_t parse_frame_size(const String& token) {
  if (token == "QQVGA") {
    return FRAMESIZE_QQVGA;
  }
  if (token == "QVGA") {
    return FRAMESIZE_QVGA;
  }
  if (token == "VGA") {
    return FRAMESIZE_VGA;
  }
  if (token == "SVGA") {
    return FRAMESIZE_SVGA;
  }
  if (token == "XGA") {
    return FRAMESIZE_XGA;
  }
  if (token == "SXGA") {
    return FRAMESIZE_SXGA;
  }
  if (token == "UXGA") {
    return FRAMESIZE_UXGA;
  }
  return FRAMESIZE_INVALID;
}

void send_frame() {
  camera_fb_t* frame_buffer = esp_camera_fb_get();
  if (frame_buffer == nullptr) {
    send_status("frame_error");
    return;
  }

  write_u32(FRAME_MAGIC);
  Serial.write(MSG_FRAME);
  write_u16(static_cast<uint16_t>(frame_buffer->width));
  write_u16(static_cast<uint16_t>(frame_buffer->height));
  Serial.write(static_cast<uint8_t>(1));
  write_u32(static_cast<uint32_t>(frame_buffer->len));
  write_u32(millis());
  Serial.write(frame_buffer->buf, frame_buffer->len);
  Serial.flush();

  esp_camera_fb_return(frame_buffer);
}

void handle_command(const String& raw_command) {
  String command = raw_command;
  command.trim();
  command.toUpperCase();

  if (command.isEmpty()) {
    return;
  }

  if (command == "PING") {
    send_status("pong");
    return;
  }

  if (command == "STREAM ON") {
    streaming_enabled = true;
    send_status("stream_on");
    return;
  }

  if (command == "STREAM OFF") {
    streaming_enabled = false;
    send_status("stream_off");
    return;
  }

  if (command == "SNAP") {
    send_frame();
    return;
  }

  if (command.startsWith("SET QUALITY ")) {
    const int quality = command.substring(12).toInt();
    if (quality < 4 || quality > 63) {
      send_status("quality_range_4_63");
      return;
    }

    sensor_t* sensor = esp_camera_sensor_get();
    if (sensor == nullptr || sensor->set_quality(sensor, quality) != 0) {
      send_status("quality_set_failed");
      return;
    }

    current_jpeg_quality = static_cast<uint8_t>(quality);
    send_status(String("quality=") + String(quality));
    return;
  }

  if (command.startsWith("SET FRAMESIZE ")) {
    const framesize_t frame_size = parse_frame_size(command.substring(14));
    if (frame_size == FRAMESIZE_INVALID) {
      send_status("framesize_invalid");
      return;
    }

    sensor_t* sensor = esp_camera_sensor_get();
    if (sensor == nullptr || sensor->set_framesize(sensor, frame_size) != 0) {
      send_status("framesize_set_failed");
      return;
    }

    current_frame_size = frame_size;
    send_status(String("framesize=") + command.substring(14));
    return;
  }

  if (command.startsWith("ARM ")) {
    send_status(String("arm_command_received:") + raw_command.substring(4));
    return;
  }

  send_status(String("unknown_command:") + raw_command);
}

void poll_serial_commands() {
  while (Serial.available() > 0) {
    const int next_byte = Serial.read();
    if (next_byte < 0) {
      return;
    }

    if (next_byte == '\n' || next_byte == '\r') {
      if (command_length > 0) {
        command_buffer[command_length] = '\0';
        handle_command(String(command_buffer));
        command_length = 0;
      }
      continue;
    }

    if (command_length < MAX_COMMAND_LEN) {
      command_buffer[command_length++] = static_cast<char>(next_byte);
    } else {
      command_length = 0;
      send_status("command_too_long");
    }
  }
}

}  // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(STARTUP_DELAY_MS);
  send_status("booting");
  init_camera();
}

void loop() {
  poll_serial_commands();

  const uint32_t now = millis();
  if (now - last_heartbeat_ms >= HEARTBEAT_INTERVAL_MS) {
    last_heartbeat_ms = now;
    send_status(streaming_enabled ? "heartbeat_streaming" : "heartbeat_idle");
  }

  if (streaming_enabled) {
    send_frame();
  } else {
    delay(IDLE_POLL_DELAY_MS);
  }
}
