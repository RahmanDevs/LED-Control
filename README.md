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
| Range | 3 cm – 30 cm |

### Shared

| Setting | Value |
|---|---|
| Serial Port | COM6 |
| Baud Rate | 9600 |

---

## Project Structure

```
LED Control/
├── app.py                        # Original server — serial (Arduino Mega via USB)
├── data_server.py                # Data server — REST API bridge for ESP-01 (port 5001)
├── ui_server.py                  # UI server — web dashboard polling data_server (port 8000)
├── main/
│   └── main.ino                  # Arduino sketch (LED + HC-SR04)
├── templates/
│   ├── index.html                # Project gallery / dashboard
│   ├── nav.html                  # Shared navigation partial
│   ├── led_control.html          # LED control page
│   └── distance_measurement.html # Distance measurement page
├── static/
│   ├── css/
│   │   ├── gallery.css           # Gallery styles
│   │   ├── nav.css               # Navigation styles
│   │   ├── style.css             # LED control styles
│   │   └── distance.css          # Distance measurement styles
│   └── js/
│       ├── main.js               # LED control client JS
│       └── distance.js           # Distance measurement client JS
└── Scaffold_File/                # Earlier prototype versions
```

---

## Requirements

**Python — original serial mode (`app.py`)**
```
flask
flask-socketio
eventlet
pyserial
```
```bash
pip install flask flask-socketio eventlet pyserial
```

**Python — ESP-01 mode (`data_server.py` + `ui_server.py`)**
```
flask
flask-socketio
eventlet
requests
```
```bash
pip install flask flask-socketio eventlet requests
```

---

## Setup

### Mode A — Arduino Mega via USB serial (`app.py`)

#### 1. Upload Arduino sketch

Open `main/main.ino` in the Arduino IDE and upload to your Arduino Mega.

Wire the HC-SR04:
- VCC → 5V
- GND → GND
- TRIG → Pin 9
- ECHO → Pin 10

#### 2. Set your COM port

Edit `app.py` to match your system (both occurrences):
```python
arduino = serial.Serial("COM6", 9600)
```

#### 3. Run the server

```bash
python app.py
```

#### 4. Open the web UI

Navigate to `http://localhost:8000` — or from any device on the same network, `http://<your-ip>:8000`.

---

### Mode B — ESP-01 over Wi-Fi (`data_server.py` + `ui_server.py`)

#### 1. Start the data server

```bash
python data_server.py   # listens on port 5001
```

#### 2. Start the UI server

```bash
python ui_server.py     # listens on port 8000
```

#### 3. Flash your ESP-01

The ESP-01 sketch must:
- `POST http://<server-ip>:5001/api/sensor` every ~500 ms with `{"distance_cm": 23.4, "led_state": "OFF"}`
- `GET  http://<server-ip>:5001/api/command` every ~500 ms to pick up queued LED commands
- `POST http://<server-ip>:5001/api/command/ack` after executing a command

#### 4. Open the web UI

Navigate to `http://localhost:8000`.

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
| `feature/esp01-api-server` | Separate data server + UI server for ESP-01 Wi-Fi mode |
