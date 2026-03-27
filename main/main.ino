// Arduino Mega — LED Control + HC-SR04 Distance Measurement
// LED     : Pin 13
// HC-SR04 : TRIG = Pin 9, ECHO = Pin 10

#define TRIG_PIN 9
#define ECHO_PIN 10

unsigned long lastDistTime = 0;
const unsigned long DIST_INTERVAL = 500; // send reading every 500 ms

void setup() {
  Serial.begin(9600);
  pinMode(13, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  Serial.println("Arduino Ready");
}

float measureDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000UL); // 30 ms timeout (~5 m)
  if (duration == 0) return -1.0;                   // out of range / no echo
  return (duration * 0.034) / 2.0;
}

void loop() {

  // ── Handle incoming serial commands ──────────────────────────────────────
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "ON") {
      digitalWrite(13, HIGH);
      Serial.println("LED ON");
    } else if (command == "OFF") {
      digitalWrite(13, LOW);
      Serial.println("LED OFF");
    } else if (command == "STATE?") {
      // report current LED pin state
      Serial.println(digitalRead(13) ? "ON" : "OFF");
    }
  }

  // ── Send distance reading every DIST_INTERVAL ms ─────────────────────────
  unsigned long now = millis();
  if (now - lastDistTime >= DIST_INTERVAL) {
    lastDistTime = now;
    float dist = measureDistance();
    Serial.print("DIST:");
    if (dist > 0.0 && dist < 400.0) {
      Serial.println(dist, 1);     // e.g. "DIST:23.4"
    } else {
      Serial.println(-1.0f, 1);    // out of range → "DIST:-1.0"
    }
  }
}
