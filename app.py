"""
Arduino Mega LED Control — WebSocket edition
Requires: pip install flask flask-socketio eventlet pyserial
Run:      python app.py
"""

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from werkzeug.middleware.proxy_fix import ProxyFix
import serial
import time
import re
import os
import sys
import subprocess
import threading
from datetime import datetime

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=2, x_proto=2, x_host=1)
app.config["SECRET_KEY"] = "arduino-secret"
# socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
socketio = SocketIO(app, cors_allowed_origins="https://iot.fikrow.com", async_mode="eventlet")


arduino           = None
arduino_connected = False
led_state         = "OFF"

# sid -> ip
connected_clients = {}

# ip -> { first_seen, tabs, commands, sessions }
ip_details = {}


# ── UA parser ─────────────────────────────────────────────────────────────────

def get_client_ip():
    """
    Resolve the real client IP through Cloudflare + Nginx proxies.
    Priority:
      1. CF-Connecting-IP  — set by Cloudflare, always the true client IP
      2. X-Forwarded-For   — first entry in the chain
      3. remote_addr       — fallback for direct / LAN connections
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_client_ip()


def parse_ua(ua):
    browser = "Unknown"
    os_name = "Unknown"
    device  = "Desktop"

    if "iPhone" in ua:
        device, os_name = "Mobile", "iOS"
    elif "iPad" in ua:
        device, os_name = "Tablet", "iPadOS"
    elif "Android" in ua:
        device  = "Mobile"
        os_name = "Android"
    elif "Windows NT" in ua:
        m  = re.search(r"Windows NT ([\d.]+)", ua)
        nt = {"10.0": "10/11", "6.3": "8.1", "6.2": "8", "6.1": "7"}.get(m.group(1) if m else "", "")
        os_name = f"Windows {nt}" if nt else "Windows"
    elif "Mac OS X" in ua:
        os_name = "macOS"
    elif "Linux" in ua:
        os_name = "Linux"

    if re.search(r"Edg[e]?/", ua):
        m = re.search(r"Edg[e]?/([\d]+)", ua)
        browser = f"Edge {m.group(1)}" if m else "Edge"
    elif "OPR/" in ua:
        m = re.search(r"OPR/([\d]+)", ua)
        browser = f"Opera {m.group(1)}" if m else "Opera"
    elif "Chrome/" in ua:
        m = re.search(r"Chrome/([\d]+)", ua)
        browser = f"Chrome {m.group(1)}" if m else "Chrome"
    elif "Firefox/" in ua:
        m = re.search(r"Firefox/([\d]+)", ua)
        browser = f"Firefox {m.group(1)}" if m else "Firefox"
    elif "Safari/" in ua:
        m = re.search(r"Version/([\d]+)", ua)
        browser = f"Safari {m.group(1)}" if m else "Safari"

    return {"browser": browser, "os": os_name, "device": device}


# ── Serial ────────────────────────────────────────────────────────────────────

def get_serial():
    global arduino
    if arduino is None:
        arduino = serial.Serial("COM6", 9600)
        time.sleep(2)
    return arduino


def query_initial_state():
    """Ask the Arduino for its current LED state on server startup."""
    global led_state, arduino_connected
    try:
        ser = get_serial()
        ser.write(b"STATE?\n")
        ser.timeout = 2
        response = ser.readline().decode().strip().upper()
        if response in ("ON", "OFF"):
            led_state = response
            print(f"[INIT] Arduino LED state: {led_state}")
        else:
            print(f"[INIT] No valid state received (got: {repr(response)}), defaulting to {led_state}")
        arduino_connected = True
    except Exception as e:
        print(f"[INIT] Could not query Arduino state: {e}, defaulting to {led_state}")
        arduino_connected = False


def _check_serial_alive(ser):
    """Return True if the serial port is still alive. Write is more reliable than
    in_waiting on Windows when a USB device is physically unplugged."""
    try:
        ser.write(b"")      # zero-byte write flushes the driver state check
        _ = ser.in_waiting  # ClearCommError — raises on Windows if port is gone
        return True
    except (serial.SerialException, OSError):
        return False


def monitor_arduino():
    """Background task: poll serial every 3 s and emit arduino_status on changes."""
    global arduino, arduino_connected, led_state
    print("[MONITOR] Arduino monitor started")
    while True:
        socketio.sleep(3)
        prev = arduino_connected
        if arduino is None:
            try:
                new_ser = serial.Serial("COM6", 9600)
                socketio.sleep(2)
                arduino = new_ser
                arduino_connected = True
            except Exception:
                arduino_connected = False
        else:
            if _check_serial_alive(arduino):
                arduino_connected = True
            else:
                try:
                    arduino.close()
                except Exception:
                    pass
                arduino = None
                arduino_connected = False

        if arduino_connected != prev:
            ts = datetime.now().strftime("%H:%M:%S")
            status = "connected" if arduino_connected else "disconnected"
            print(f"[{ts}] Arduino {status}")
            socketio.emit("arduino_status", {"connected": arduino_connected})
            if arduino_connected:
                # Arduino always resets to OFF on power cycle — sync server state
                led_state = "OFF"
                socketio.emit("state_update", {"state": led_state})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log(ip, msg, cls=""):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{ip}] {msg}")
    socketio.emit("log", {"time": ts, "ip": ip, "msg": msg, "cls": cls})


def _broadcast_clients():
    unique_ips = sorted(set(connected_clients.values()))
    print(f"  Connected IPs ({len(unique_ips)}): {', '.join(unique_ips) or 'none'}")
    socketio.emit("clients_update", {"ips": unique_ips})


def _exit_after(delay=0.4):
    """Wait briefly so the HTTP response is sent, then force-exit."""
    def _do():
        time.sleep(delay)
        os._exit(0)
    threading.Thread(target=_do, daemon=True).start()


# ── HTTP routes ───────────────────────────────────────────────────────────────

@app.route("/")
def gallery():
    return render_template("index.html")


@app.route("/lcd-control/")
@app.route("/lcd-control")
def led_control():
    return render_template("led_control.html")


@app.route("/shutdown", methods=["POST"])
def shutdown():
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Server shutdown requested via web UI")
    _exit_after()
    return "ok", 200


@app.route("/restart", methods=["POST"])
def restart():
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Server restart requested via web UI")
    subprocess.Popen([sys.executable] + sys.argv)
    _exit_after()
    return "ok", 200


# ── Socket events ─────────────────────────────────────────────────────────────

@socketio.on("connect")
def handle_connect():
    ip  = get_client_ip()
    sid = request.sid  # type: ignore[attr-defined]
    connected_clients[sid] = ip

    ua_info = parse_ua(request.headers.get("User-Agent", ""))
    if ip not in ip_details:
        ip_details[ip] = {
            "first_seen": datetime.now().strftime("%H:%M:%S"),
            "tabs":       0,
            "commands":   [],
            "sessions":   {},
        }
    ip_details[ip]["tabs"] += 1
    ip_details[ip]["sessions"][sid] = {
        "browser":      ua_info["browser"],
        "os":           ua_info["os"],
        "device":       ua_info["device"],
        "connected_at": datetime.now().strftime("%H:%M:%S"),
    }

    _log(ip, "Client connected", "ok")
    _broadcast_clients()
    emit("state_update",   {"state": led_state})
    emit("arduino_status", {"connected": arduino_connected})


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid  # type: ignore[attr-defined]
    ip  = connected_clients.pop(sid, get_client_ip())
    if ip in ip_details:
        ip_details[ip]["tabs"] = max(0, ip_details[ip]["tabs"] - 1)
        ip_details[ip]["sessions"].pop(sid, None)
    _log(ip, "Client disconnected", "err")
    _broadcast_clients()


@socketio.on("get_state")
def handle_get_state():
    emit("state_update", {"state": led_state})


@socketio.on("get_ip_detail")
def handle_get_ip_detail(data):
    ip     = data.get("ip", "")
    detail = ip_details.get(ip)
    if not detail:
        emit("ip_detail", {"ip": ip, "first_seen": "—", "tabs": 0, "commands": [], "sessions": []})
        return
    emit("ip_detail", {
        "ip":         ip,
        "first_seen": detail["first_seen"],
        "tabs":       detail["tabs"],
        "commands":   detail["commands"],
        "sessions":   list(detail.get("sessions", {}).values()),
    })


@socketio.on("led_command")
def handle_led_command(data):
    global led_state, arduino, arduino_connected
    ip  = get_client_ip()
    cmd = data.get("state", "").upper()
    if cmd not in ("ON", "OFF"):
        return

    try:
        get_serial().write(f"{cmd}\n".encode())
    except (serial.SerialException, OSError) as e:
        try:
            if arduino is not None:
                arduino.close()
        except Exception:
            pass
        arduino = None
        arduino_connected = False
        socketio.emit("arduino_status", {"connected": False})
        _log(ip, f"Arduino disconnected: {e}", "err")
        return

    led_state = cmd

    ts = datetime.now().strftime("%H:%M:%S")
    if ip in ip_details:
        ip_details[ip]["commands"].append({"time": ts, "cmd": cmd})

    _log(ip, f"LED → {cmd}", "ok" if cmd == "ON" else "err")
    socketio.emit("state_update", {"state": led_state})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    query_initial_state()
    socketio.start_background_task(monitor_arduino)
    socketio.run(app, host="0.0.0.0", port=8000, debug=False)
