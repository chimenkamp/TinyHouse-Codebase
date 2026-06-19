// sensor_sketch.ino
// Zwei Drucksensoren (FSR) an A0 und A1
// Ausgabe: eine CSV-Zeile pro Sensor pro Zyklus
// Format: <ID>,<VOUT>,<RC>
//   ID   = P1, P2, ...
//   VOUT = Spannung in Volt (3 Dezimalstellen)
//   RC   = Widerstand in kOhm (3 Dezimalstellen), -1 wenn ungültig

const int NUM_SENSORS = 2;
const int SENSOR_PINS[NUM_SENSORS] = {A0, A1};
const char* SENSOR_IDS[NUM_SENSORS] = {"P1", "P2"};

const float VCC = 5.0;
const float R_FIXED = 510.0; // Vorwiderstand in kOhm

void setup() {
  for (int i = 0; i < NUM_SENSORS; i++) {
    pinMode(SENSOR_PINS[i], INPUT);
  }
  Serial.begin(9600);
}

void loop() {
  for (int i = 0; i < NUM_SENSORS; i++) {
    int raw = analogRead(SENSOR_PINS[i]);
    float vout = (raw / 1023.0) * VCC;
    float rc = -1.0;

    if (vout > 0) {
      rc = (R_FIXED * VCC / vout) - R_FIXED;
    }

    Serial.print(SENSOR_IDS[i]);
    Serial.print(",");
    Serial.print(vout, 3);
    Serial.print(",");
    if (rc >= 0) {
      Serial.println(rc, 3);
    } else {
      Serial.println("-1");
    }
  }

  delay(500);
}
