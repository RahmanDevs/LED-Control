"""
UI Server — Web dashboard (ESP-01 edition)
Replaces serial communication with HTTP polling against data_server.py.

Requires: pip install flask flask-socketio requests
Run:      python ui_server.py   (data_server.py must already be running)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
import time
import re
import os
import subprocess
import threading
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────

DATA_SERVER_URL  = "http://127.0.0.1:5001"
POLL_INTERVAL    = 0.5   # seconds between data-server polls

# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=2, x_proto=2, x_host=1)
app.config["SECRET_KEY"] = "arduino-secret"
socketio = SocketIO(app, cors_allowed_origins=["https://iot.fikrow.com", "http://localhost:8000", "http://127.0.0.1:8000"], async_mode="threading")

esp_connected = False
led_state     = "OFF"
distance_cm   = -1.0

connected_clients: dict[str, str] = {}   # sid -> ip
ip_details:        dict           = {}   # ip -> analytics


# ── UA parser ─────────────────────────────────────────────────────────────────

def get_client_ip():
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr


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


# ── Data server polling ───────────────────────────────────────────────────────

def data_poller():
    """
    Background task: poll data_server every POLL_INTERVAL seconds.
    Emits distance_update and arduino_status events on changes.
    Replaces serial_reader() + monitor_arduino() from app.py.
    """
    global esp_connected, led_state, distance_cm
    prev_connected = False
    prev_led       = None
    print("[POLLER] Data poller started")

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            r    = requests.get(f"{DATA_SERVER_URL}/api/sensor", timeout=2)
            data = r.json()

            new_connected = data.get("esp_connected", False)
            new_distance  = data.get("distance_cm", -1.0)
            new_led       = data.get("led_state", "OFF")

            # Emit distance every poll (UI expects continuous updates)
            distance_cm = new_distance
            socketio.emit("distance_update", {"cm": distance_cm})

            # Emit LED state only on change
            if new_led != prev_led:
                led_state = new_led
                socketio.emit("state_update", {"state": led_state})
                prev_led = new_led

            # Emit connection status only on change
            if new_connected != prev_connected:
                esp_connected = new_connected
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"[{ts}] Arduino {'connected' if esp_connected else 'disconnected'}")
                socketio.emit("arduino_status", {"connected": esp_connected})

            prev_connected = new_connected

        except requests.RequestException:
            if prev_connected:
                esp_connected  = False
                prev_connected = False
                socketio.emit("arduino_status", {"connected": False})
                print("[POLLER] data_server unreachable")
        except Exception as e:
            print(f"[POLLER] unexpected error: {e}")


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


@app.route("/distance-measurement/")
@app.route("/distance-measurement")
def distance_measurement():
    return render_template("distance_measurement.html")


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
    ip  = get_client_ip() or "unknown"
    sid = request.sid  # type: ignore[attr-defined]
    if not sid:
        return
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
    emit("arduino_status", {"connected": esp_connected})


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid  # type: ignore[attr-defined]
    if not sid:
        return
    ip  = connected_clients.pop(sid, "unknown")
    if ip in ip_details:
        ip_details[ip]["tabs"] = max(0, ip_details[ip]["tabs"] - 1)
        ip_details[ip]["sessions"].pop(sid, None)
    _log(ip, "Client disconnected", "err")
    _broadcast_clients()


@socketio.on("get_state")
def handle_get_state():
    emit("state_update", {"state": led_state})


@socketio.on("get_distance")
def handle_get_distance():
    emit("distance_update", {"cm": distance_cm})


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
    global led_state
    ip  = get_client_ip()
    cmd = data.get("state", "").upper()
    if cmd not in ("ON", "OFF"):
        return

    try:
        r = requests.post(
            f"{DATA_SERVER_URL}/api/command",
            json={"command": cmd},
            timeout=2,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        _log(ip, f"data_server unreachable: {e}", "err")
        socketio.emit("arduino_status", {"connected": False})
        return

    led_state = cmd

    ts = datetime.now().strftime("%H:%M:%S")
    if ip in ip_details:
        ip_details[ip]["commands"].append({"time": ts, "cmd": cmd})

    _log(ip, f"LED -> {cmd}", "ok" if cmd == "ON" else "err")
    socketio.emit("state_update", {"state": led_state})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"UI server starting on port 8000")
    print(f"  Data server: {DATA_SERVER_URL}")
    socketio.start_background_task(data_poller)
    socketio.run(app, host="0.0.0.0", port=8000, debug=False)
