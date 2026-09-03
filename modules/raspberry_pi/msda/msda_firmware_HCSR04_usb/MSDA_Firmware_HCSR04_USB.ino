/*
 * MSDA_Firmware_HCSR04_USB.ino
 * Issue #1 — HC-SR04 only, USB Serial test
 *
 * Setup:
 *   HC-SR04  VCC  → 5V  (breadboard power rail)
 *   HC-SR04  GND  → GND (breadboard power rail)
 *   HC-SR04  TRIG → Arduino D7
 *   HC-SR04  ECHO → Arduino D8
 *   Arduino  USB  → Raspberry Pi USB port
 *
 * Board: Arduino Nano Every (ATmega4809) or Nano ESP32
 * Baud:  115200
 *
 * Output format (one JSON line per reading):
 *   {"type":"DATA","ts":<ms>,"sensor":"HC_SR04","distance_cm":<float>,"raw_us":<long>}
 *   {"type":"HEARTBEAT","ts":<ms>}
 *   {"type":"STATUS","ts":<ms>,"message":"<text>"}
 *   {"type":"ERROR","ts":<ms>,"message":"<text>"}
 */

#define PIN_TRIG  7    // HC-SR04 Trigger pin (D7)
#define PIN_ECHO  8    // HC-SR04 Echo pin    (D8)

// Timing
#define SAMPLE_INTERVAL_MS   1000UL   // sensor poll rate
#define HEARTBEAT_INTERVAL_MS 5000UL  // keepalive rate
#define ECHO_TIMEOUT_US      30000UL  // ~5 m max range

unsigned long tLastSample    = 0;
unsigned long tLastHeartbeat = 0;

// ── JSON helpers ──────────────────────────────────────────────────
void jStr(const char* k, const char* v, bool last = false) {
  Serial.print('"'); Serial.print(k);
  Serial.print("\":\""); Serial.print(v); Serial.print('"');
  if (!last) Serial.print(',');
}
void jInt(const char* k, long v, bool last = false) {
  Serial.print('"'); Serial.print(k);
  Serial.print("\":"); Serial.print(v);
  if (!last) Serial.print(',');
}
void jFlt(const char* k, float v, bool last = false) {
  Serial.print('"'); Serial.print(k);
  Serial.print("\":"); Serial.print(v, 2);
  if (!last) Serial.print(',');
}

void sendStatus(const char* msg) {
  Serial.print('{');
  jStr("type", "STATUS");
  jInt("ts", millis());
  jStr("message", msg, true);
  Serial.println('}');
}

void sendHeartbeat() {
  Serial.print('{');
  jStr("type", "HEARTBEAT");
  jInt("ts", millis(), true);
  Serial.println('}');
}

// ── HC-SR04 reading ───────────────────────────────────────────────
void sampleHCSR04() {
  // Trigger pulse
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  // Measure echo pulse duration
  unsigned long dur = pulseIn(PIN_ECHO, HIGH, ECHO_TIMEOUT_US);

  // Convert: distance_cm = duration_us / 2 * speed_of_sound(cm/us)
  // speed of sound ~0.0343 cm/us at ~20°C
  float distCm = (dur > 0) ? (dur / 2.0f) * 0.0343f : -1.0f;

  Serial.print('{');
  jStr("type", "DATA");
  jInt("ts", millis());
  jStr("sensor", "HC_SR04");

  if (dur == 0) {
    // Timeout — nothing in range or sensor not responding
    jFlt("distance_cm", -1.0f);
    jInt("raw_us", 0);
    jStr("status", "TIMEOUT", true);
  } else {
    jFlt("distance_cm", distCm);
    jInt("raw_us", (long)dur);
    jStr("status", "OK", true);
  }
  Serial.println('}');
}

// ── Setup / Loop ──────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  while (!Serial) { /* wait for USB CDC to enumerate */ }

  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  digitalWrite(PIN_TRIG, LOW);

  sendStatus("MSDA HC-SR04 USB test ready — TRIG:D7 ECHO:D8");

  tLastSample    = millis();
  tLastHeartbeat = millis();
}

void loop() {
  unsigned long now = millis();

  if (now - tLastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
    sendHeartbeat();
    tLastHeartbeat = now;
  }

  if (now - tLastSample >= SAMPLE_INTERVAL_MS) {
    sampleHCSR04();
    tLastSample = now;
  }
}
