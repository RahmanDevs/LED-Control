"""
Data Server — Arduino serial bridge (temporary) + future ESP-01 HTTP bridge
Currently reads from COM6 serial. When ESP-01 is ready, serial_reader/monitor
threads can be removed and the POST /api/sensor endpoint takes over.

Requires: pip install flask pyserial python-socketio[client]
Run:      python data_server.py
"""

from flask import Flask, request, jsonify
import serial
import threading
import time
import socketio as sio_client
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────

SERIAL_PORT    = "COM6"
BAUD_RATE      = 9600
UI_SERVER_URL  = "http://127.0.0.1:8000"

# ── App + state ───────────────────────────────────────────────────────────────

app = Flask(__name__)

_lock = threading.Lock()

_state = {
    "distance_cm":     -1.0,
    "led_state":       "OFF",
    "esp_connected":   False,   # True = Arduino (or future ESP-01) is live
    "last_update":     0.0,
    "last_update_str": "—",
}

_command_queue: list[str] = []   # pending LED commands for ESP-01 (future)

_arduino: serial.Serial | None = None
_arduino_connected = False


def _ts():
    return datetime.now().strftime("%H:%M:%S")


# ── Socket.IO client (persistent connection to ui_server) ────────────────────

_sio = sio_client.Client(reconnection=True, reconnection_delay=2, logger=False, engineio_logger=False)


@_sio.event(namespace="/internal")
def connect():
    print(f"[SIO] Connected to ui_server")


@_sio.event(namespace="/internal")
def disconnect():
    print(f"[SIO] Disconnected from ui_server")


def _start_sio():
    while True:
        try:
            _sio.connect(UI_SERVER_URL, namespaces=["/internal"])
            _sio.wait()
        except Exception:
            time.sleep(3)


def _push_to_ui():
    """Emit current state to ui_server via Socket.IO."""
    if not _sio.connected:
        return
    with _lock:
        payload = dict(_state)
    try:
        _sio.emit("state_push", payload, namespace="/internal")
    except Exception:
        pass


def _set_connected(connected: bool):
    """Update connection state under lock."""
    global _arduino_connected
    with _lock:
        prev = _state["esp_connected"]
        _state["esp_connected"] = connected
        _arduino_connected = connected
        if not connected:
            _state["distance_cm"] = -1.0
        changed = connected != prev
    if changed:
        status = "connected" if connected else "disconnected"
        print(f"[{_ts()}] Arduino {status}")
        _push_to_ui()


# ── Serial background tasks ───────────────────────────────────────────────────

def _check_alive(ser: serial.Serial) -> bool:
    try:
        ser.write(b"")
        _ = ser.in_waiting
        return True
    except (serial.SerialException, OSError):
        return False


def serial_reader():
    """Read DIST: and LED state lines from Arduino and update _state."""
    global _arduino
    print("[READER] Serial reader started")
    while True:
        with _lock:
            ser = _arduino
        if ser is None or not _arduino_connected:
            time.sleep(0.5)
            continue
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode(errors="ignore").strip()
                if line.startswith("DIST:"):
                    try:
                        val = float(line.split(":")[1])
                        cm = round(val, 1) if 3.0 <= val <= 30.0 else -1.0
                        with _lock:
                            _state["distance_cm"]     = cm
                            _state["last_update"]     = time.time()
                            _state["last_update_str"] = _ts()
                        _push_to_ui()
                    except (ValueError, IndexError):
                        pass
                elif line in ("ON", "OFF", "LED ON", "LED OFF"):
                    state = "ON" if "ON" in line else "OFF"
                    with _lock:
                        _state["led_state"] = state
                    _push_to_ui()
            else:
                time.sleep(0.01)
        except (serial.SerialException, OSError):
            time.sleep(0.5)


def monitor_arduino():
    """Reconnect to Arduino every 3 s if disconnected."""
    global _arduino
    print("[MONITOR] Arduino monitor started")
    while True:
        time.sleep(3)
        with _lock:
            ser = _arduino
        if ser is None:
            try:
                new_ser = serial.Serial(SERIAL_PORT, BAUD_RATE)
                time.sleep(2)   # wait for Arduino reset
                new_ser.write(b"STATE?\n")
                new_ser.timeout = 2
                resp = new_ser.readline().decode(errors="ignore").strip().upper()
                with _lock:
                    _arduino = new_ser
                    if resp in ("ON", "OFF"):
                        _state["led_state"] = resp
                _set_connected(True)
            except Exception as e:
                print(f"[{_ts()}] Cannot open {SERIAL_PORT}: {e}")
                _set_connected(False)
        else:
            if _check_alive(ser):
                if not _arduino_connected:
                    _set_connected(True)
            else:
                try:
                    ser.close()
                except Exception:
                    pass
                with _lock:
                    _arduino = None
                _set_connected(False)


# ── Routes — ESP-01 side (future) ────────────────────────────────────────────

@app.route("/api/sensor", methods=["POST"])
def post_sensor():
    """Future: ESP-01 POSTs sensor readings. Overrides serial data when active."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "no JSON body"}), 400
    with _lock:
        if "distance_cm" in data:
            val = float(data["distance_cm"])
            _state["distance_cm"] = round(val, 1) if 3.0 <= val <= 30.0 else -1.0
        if "led_state" in data and data["led_state"] in ("ON", "OFF"):
            _state["led_state"] = data["led_state"]
        _state["esp_connected"]   = True
        _state["last_update"]     = time.time()
        _state["last_update_str"] = _ts()
    _push_to_ui()
    return jsonify({"ok": True})


@app.route("/api/command", methods=["GET"])
def get_command():
    """Future: ESP-01 polls for queued LED commands."""
    with _lock:
        cmd = _command_queue.pop(0) if _command_queue else None
    return jsonify({"command": cmd})


@app.route("/api/command/ack", methods=["POST"])
def ack_command():
    """Future: ESP-01 confirms command executed."""
    data = request.get_json(silent=True)
    if data:
        print(f"[{_ts()}] ESP-01 ack: {data.get('command')} -> {data.get('result')}")
    return jsonify({"ok": True})


# ── Routes — UI server side ───────────────────────────────────────────────────

@app.route("/api/sensor", methods=["GET"])
def get_sensor():
    """UI server polls this for the latest state."""
    with _lock:
        return jsonify(dict(_state))


@app.route("/api/command", methods=["POST"])
def post_command():
    """UI server sends a LED command — writes directly to serial (and queues for future ESP-01)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "no JSON body"}), 400
    cmd = data.get("command", "").upper()
    if cmd not in ("ON", "OFF"):
        return jsonify({"error": "command must be ON or OFF"}), 400

    # Write to serial immediately
    with _lock:
        ser = _arduino
    if ser is not None:
        try:
            ser.write(f"{cmd}\n".encode())
            with _lock:
                _state["led_state"] = cmd
            print(f"[{_ts()}] LED -> {cmd} (serial)")
            _push_to_ui()
        except (serial.SerialException, OSError) as e:
            return jsonify({"error": f"serial write failed: {e}"}), 500
    else:
        # Queue for ESP-01 (future)
        with _lock:
            _command_queue.clear()
            _command_queue.append(cmd)
        print(f"[{_ts()}] LED command queued (no serial): {cmd}")

    return jsonify({"ok": True, "cmd": cmd})


@app.route("/api/status", methods=["GET"])
def status():
    """Debug overview."""
    with _lock:
        return jsonify({
            "state":        dict(_state),
            "pending_cmds": list(_command_queue),
            "serial_port":  SERIAL_PORT,
        })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Data server starting on port 5001 (serial: {SERIAL_PORT} @ {BAUD_RATE})")
    print(f"  UI server socket target: {UI_SERVER_URL} /internal namespace")
    print("  GET  /api/sensor        <- direct state read")
    print("  POST /api/command       <- ui_server sends LED command")
    print("  POST /api/sensor        <- future ESP-01 pushes readings")
    print("  GET  /api/command       <- future ESP-01 polls commands")
    threading.Thread(target=monitor_arduino, daemon=True).start()
    threading.Thread(target=serial_reader,   daemon=True).start()
    threading.Thread(target=_start_sio,      daemon=True).start()
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
