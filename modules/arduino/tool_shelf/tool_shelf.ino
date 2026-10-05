// Three digital Hall-module signals on an Arduino Uno's analog-capable pins.
// Open Serial Monitor at 9600 baud. Unconnected channels are never read.

constexpr int8_t UNCONNECTED_PIN = -1;
constexpr int8_t HALL_A0_PIN = A0;
constexpr int8_t HALL_A1_PIN = A1;
constexpr int8_t HALL_A2_PIN = A2;
constexpr int8_t HALL_A3_PIN = UNCONNECTED_PIN;  // Assign A3 when connected.
constexpr int8_t HALL_A4_PIN = UNCONNECTED_PIN;  // Assign A4 when connected.
constexpr int8_t HALL_A5_PIN = UNCONNECTED_PIN;  // Assign A5 when connected.
constexpr int8_t HALL_A6_PIN = UNCONNECTED_PIN;  // Reserved slot; Uno has no A6 pin.

constexpr int8_t HALL_PINS[] = {
  HALL_A0_PIN, HALL_A1_PIN, HALL_A2_PIN, HALL_A3_PIN,
  HALL_A4_PIN, HALL_A5_PIN, HALL_A6_PIN,
};
constexpr uint8_t SENSOR_COUNT = sizeof(HALL_PINS) / sizeof(HALL_PINS[0]);
constexpr unsigned long SERIAL_BAUD = 9600;
constexpr unsigned long REPORT_INTERVAL_MS = 500;

/**
 * Configure only the connected Hall inputs with weak pull-ups.
 * :return: None.
 */
void configureSensors() {
  for (uint8_t index = 0; index < SENSOR_COUNT; ++index) {
    const int8_t pin = HALL_PINS[index];
    if (pin != UNCONNECTED_PIN) {
      pinMode(pin, INPUT_PULLUP);
    }
  }
}

/**
 * Report raw digital levels without assuming the sensor's magnetic polarity.
 * :return: None.
 */
void printSensorStates() {
  for (uint8_t index = 0; index < SENSOR_COUNT; ++index) {
    const int8_t pin = HALL_PINS[index];
    if (pin == UNCONNECTED_PIN) {
      continue;
    }
    const int state = digitalRead(pin);
    Serial.print(F("A"));
    Serial.print(index);
    Serial.print(F("="));
    Serial.println(state == HIGH ? F("HIGH") : F("LOW"));
  }
}

/**
 * Start Serial and initialize the connected sensors.
 * :return: None.
 */
void setup() {
  Serial.begin(SERIAL_BAUD);
  configureSensors();
}

/**
 * Print the three connected states once per reporting cycle.
 * :return: None.
 */
void loop() {
  printSensorStates();
  delay(REPORT_INTERVAL_MS);
}
