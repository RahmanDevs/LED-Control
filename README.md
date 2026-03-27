# Arduino Mega LED Control

A real-time web interface for controlling an Arduino Mega LED over WebSocket. Any browser on the local network can toggle the LED and see live state updates instantly.

---

## Features

- **Real-time control** — LED ON/OFF synced across all connected browser tabs instantly
- **Connected clients panel** — see every IP on the network currently viewing the page
- **IP detail view** — click any IP to inspect browser, OS, device type, active tabs, and full command history
- **Serial console** — live log of all events (connects, disconnects, commands) with timestamps and IPs
- **Server controls** — restart or stop the Flask server directly from the web UI with a confirmation dialog
- **Initial state sync** — server queries Arduino on startup so the UI always reflects the real LED state

---

## Hardware

| Component | Detail |
|---|---|
| Board | Arduino Mega 2560 |
| LED Pin | Digital Pin 13 (built-in) |
| Serial Port | COM6 |
| Baud Rate | 9600 |

---

## Project Structure

```
LED Control/
├── app.py                  # Flask server, socket events, serial logic
├── main/
│   └── main.ino            # Arduino sketch
├── templates/
│   └── index.html          # HTML template
├── static/
│   ├── css/style.css       # Styles
│   └── js/main.js          # Client-side JavaScript
└── Scaffold_File/          # Earlier prototype versions
```

---

## Requirements

**Python**
```
flask
flask-socketio
eventlet
pyserial
```

Install with:
```bash
pip install flask flask-socketio eventlet pyserial
```

---

## Setup

### 1. Upload Arduino sketch

Open `main/main.ino` in the Arduino IDE and upload it to your Arduino Mega. The sketch listens on Serial for `ON` and `OFF` commands and responds on Pin 13.

> **Note:** To enable initial state detection, add a `STATE?` handler to your sketch — see the [Arduino Sketch](#arduino-sketch) section below.

### 2. Set your COM port

Edit `app.py` line 74 to match your system:
```python
arduino = serial.Serial("COM6", 9600)
```

### 3. Run the server

```bash
python app.py
```

### 4. Open the web UI

Navigate to `http://localhost:8000` — or from any device on the same network, `http://<your-ip>:8000`.

---

## Arduino Sketch

The current sketch handles `ON` and `OFF`. To also support initial state detection, add the `STATE?` command:

```cpp
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
    } else if (command == "OFF") {
      digitalWrite(13, LOW);
      Serial.println("LED OFF");
    } else if (command == "STATE?") {
      Serial.println(digitalRead(13) == HIGH ? "ON" : "OFF");
    }
  }
}
```

---

## License

MIT
