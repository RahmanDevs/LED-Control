// Arduino Mega Telegram LED Control

void setup() {
  Serial.begin(9600);
  pinMode(13, OUTPUT);

  Serial.println("Arduino Ready");
}

void loop() {

  if (Serial.available()) {

    String command = Serial.readStringUntil('\n');

    command.trim();

    if (command == "ON") {

      digitalWrite(13, HIGH);
      Serial.println("LED ON");

    }

    else if (command == "OFF") {

      digitalWrite(13, LOW);
      Serial.println("LED OFF");

    }

  }
}
