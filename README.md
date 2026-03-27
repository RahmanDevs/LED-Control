# Arduino Mega IoT Control

A real-time web dashboard for controlling an Arduino Mega over WebSocket. Supports LED control and live HC-SR04 ultrasonic distance measurement, accessible from any browser on the local network.

---

## Projects

### LED Control — `/lcd-control/`

Toggle an Arduino LED in real time. State is synced instantly across all connected browser tabs.

### Distance Measurement — `/distance-measurement/`

Live HC-SR04 ultrasonic distance readings streamed over WebSocket. Displays current distance with a range bar, min/max stats, reading count, and a scrollable log. Unit toggle between cm and inches.

---

## Features

- **Real-time WebSocket** — state synced across all connected clients instantly
- **Connected clients panel** — see every IP currently viewing the LED control page
- **IP detail view** — click any IP to inspect browser, OS, device, active tabs, and command history
- **Serial console** — live log of all events with timestamps and IPs
- **Server controls** — restart or stop the Flask server from the web UI with confirmation
- **Initial state sync** — server queries Arduino on startup to reflect the real LED state
- **Distance live stream** — HC-SR04 readings parsed from serial and broadcast via socket every 500 ms

---

## Hardware

### LED Control

| Component | Detail |
|---|---|
| Board | Arduino Mega 2560 |
| LED Pin | Digital Pin 13 (built-in) |

### Distance Measurement

| Component | Detail |
|---|---|
| Sensor | HC-SR04 Ultrasonic |
| TRIG Pin | Digital Pin 9 |
| ECHO Pin | Digital Pin 10 |
| Range | 2 cm – 400 cm |

### Shared

| Setting | Value |
|---|---|
| Serial Port | COM6 |
| Baud Rate | 9600 |

---

## Project Structure

```
LED Control/
├── app.py                        # Flask server, socket events, serial logic
├── main/
│   └── main.ino                  # Arduino sketch (LED + HC-SR04)
├── templates/
│   ├── index.html                # Project gallery / dashboard
│   ├── led_control.html          # LED control page
│   └── distance_measurement.html # Distance measurement page
├── static/
│   ├── css/
│   │   ├── gallery.css           # Gallery styles
│   │   ├── style.css             # LED control styles
│   │   └── distance.css          # Distance measurement styles
│   └── js/
│       ├── main.js               # LED control client JS
│       └── distance.js           # Distance measurement client JS
└── Scaffold_File/                # Earlier prototype versions
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

Open `main/main.ino` in the Arduino IDE and upload to your Arduino Mega.

Wire the HC-SR04:
- VCC → 5V
- GND → GND
- TRIG → Pin 9
- ECHO → Pin 10

### 2. Set your COM port

Edit `app.py` to match your system (both occurrences):
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

The sketch handles LED commands (`ON`, `OFF`, `STATE?`) and streams distance readings every 500 ms:

```cpp
// TRIG = Pin 9, ECHO = Pin 10, LED = Pin 13

DIST:23.4    // normal reading (cm)
DIST:-1.0    // out of range or no echo
```

Serial protocol summary:

| Direction | Message | Description |
|---|---|---|
| Host → Arduino | `ON\n` | Turn LED on |
| Host → Arduino | `OFF\n` | Turn LED off |
| Host → Arduino | `STATE?\n` | Query current LED state |
| Arduino → Host | `LED ON` / `LED OFF` | LED command acknowledgement |
| Arduino → Host | `ON` / `OFF` | Response to `STATE?` |
| Arduino → Host | `DIST:XX.X` | Distance reading in cm (every 500 ms) |

---

## Branches

| Branch | Description |
|---|---|
| `main` | LED control only |
| `feature/distance-measurement` | LED control + HC-SR04 distance measurement |
