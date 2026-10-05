// Host-side logic checks; the real Uno compilation is a separate check.
#include <array>
#include <cassert>
#include <cstdint>
#include <string>
#include <vector>

constexpr int A0 = 14;
constexpr int A1 = 15;
constexpr int A2 = 16;
constexpr int HIGH = 1;
constexpr int LOW = 0;
constexpr int INPUT_PULLUP = 2;
constexpr unsigned long EXPECTED_BAUD = 9600;
constexpr unsigned long EXPECTED_INTERVAL_MS = 500;
constexpr unsigned int INPUT_COMBINATIONS = 8;

std::array<int, 3> inputLevels = {{LOW, LOW, LOW}};
std::vector<int> configuredPins;
std::vector<int> readPins;
std::string serialOutput;
unsigned long serialBaud = 0;

/**
 * Provide ordinary strings for the host's flash-string test substitute.
 * :param text: Sketch string literal.
 * :return: The same literal for host-only testing.
 */
const char* F(const char* text) {
  return text;
}

struct SerialRecorder {
  /**
   * Record Serial initialization for the startup assertion.
   * :param baud: Requested connection rate.
   * :return: None.
   */
  void begin(unsigned long baud) { serialBaud = baud; }
  /**
   * Capture text for the observable-output assertion.
   * :param value: Text emitted by the sketch.
   * :return: None.
   */
  void print(const char* value) { serialOutput += value; }
  /**
   * Capture a numeric label with Arduino Serial's decimal formatting.
   * :param value: Sensor-channel number.
   * :return: None.
   */
  void print(unsigned int value) { serialOutput += std::to_string(value); }
  /**
   * Capture a terminated Serial line.
   * :param value: Final text before the line ending.
   * :return: None.
   */
  void println(const char* value) { serialOutput += std::string(value) + "\n"; }
};

SerialRecorder Serial;

/**
 * Record pin configuration and reject unintended output or floating-input modes.
 * :param pin: Configured Arduino pin.
 * :param mode: Requested input mode.
 * :return: None.
 */
void pinMode(int pin, int mode) {
  assert(mode == INPUT_PULLUP);
  configuredPins.push_back(pin);
}

/**
 * Supply test input levels while rejecting reads of inactive channels.
 * :param pin: Requested input pin.
 * :return: Current injected logic level.
 */
int digitalRead(int pin) {
  assert(pin >= A0 && pin <= A2);
  readPins.push_back(pin);
  return inputLevels.at(static_cast<std::size_t>(pin - A0));
}

/**
 * Check the reporting interval without waiting in a host test.
 * :param interval: Requested pause in milliseconds.
 * :return: None.
 */
void delay(unsigned long interval) {
  assert(interval == EXPECTED_INTERVAL_MS);
}

#include "../tool_shelf/tool_shelf.ino"

/**
 * Exercise all eight three-sensor states and the disabled-channel boundary.
 * :return: Zero when every assertion passes.
 */
int main() {
  setup();
  const std::vector<int> connectedPins = {A0, A1, A2};
  assert(serialBaud == EXPECTED_BAUD);
  assert(configuredPins == connectedPins);
  assert(HALL_A3_PIN == UNCONNECTED_PIN && HALL_A4_PIN == UNCONNECTED_PIN);
  assert(HALL_A5_PIN == UNCONNECTED_PIN && HALL_A6_PIN == UNCONNECTED_PIN);

  for (unsigned int combination = 0; combination < INPUT_COMBINATIONS; ++combination) {
    std::string expected;
    for (unsigned int channel = 0; channel < inputLevels.size(); ++channel) {
      inputLevels[channel] = (combination >> channel) & 1U;
      expected += "A" + std::to_string(channel) + "=";
      expected += inputLevels[channel] == HIGH ? "HIGH\n" : "LOW\n";
    }
    serialOutput.clear();
    readPins.clear();
    loop();
    assert(readPins == connectedPins);
    assert(serialOutput == expected);
  }
  return 0;
}
