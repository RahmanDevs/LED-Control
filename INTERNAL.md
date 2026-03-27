# Internal Documentation — Arduino Mega LED Control

> Developer reference. Not for public distribution.

---

## Architecture Overview

```
Browser (Socket.IO client)
        │  WebSocket (ws://)
        ▼
Flask-SocketIO server  (app.py)
        │  Serial (pyserial)
        ▼
Arduino Mega 2560  (main/main.ino)
        │
        ▼
     Pin 13 LED
```

- **Transport:** Socket.IO over WebSocket, async via `eventlet`
- **Serial:** `pyserial` at 9600 baud on `COM6`
- **Frontend:** Vanilla JS + Socket.IO CDN — no build step, no framework

---

## File Reference

| File | Purpose |
|---|---|
| `app.py` | Flask app, all socket event handlers, serial logic, HTTP routes |
| `templates/index.html` | HTML structure only — no inline CSS or JS |
| `static/css/style.css` | All styles |
| `static/js/main.js` | All client-side JavaScript |
| `main/main.ino` | Arduino sketch |
| `Scaffold_File/` | Earlier prototype versions — kept for reference, not used |

---

## Server-Side Data Structures

### `connected_clients`
```python
connected_clients: dict[str, str]
# sid -> ip
# Populated on connect, removed on disconnect.
```

### `ip_details`
```python
ip_details: dict[str, dict]
# ip -> {
#   "first_seen":  str,          # HH:MM:SS of first connect this session
#   "tabs":        int,          # count of active SIDs from this IP
#   "commands":    list[dict],   # [{"time": str, "cmd": "ON"|"OFF"}, ...]
#   "sessions":    dict[str, dict]  # sid -> {browser, os, device, connected_at}
# }
#
# Not cleared on disconnect — persists across reconnects for the same IP
# within the same server session.
```

---

## Socket Events

### Server → Client

| Event | Payload | When sent |
|---|---|---|
| `state_update` | `{state: "ON"\|"OFF"}` | On connect, after every LED command |
| `clients_update` | `{ips: string[]}` | On every connect/disconnect |
| `log` | `{time, ip, msg, cls}` | On every connect, disconnect, LED command |
| `ip_detail` | See below | In response to `get_ip_detail` |

**`ip_detail` payload:**
```json
{
  "ip": "192.168.1.42",
  "first_seen": "14:32:05",
  "tabs": 2,
  "commands": [{"time": "14:33:01", "cmd": "ON"}, ...],
  "sessions": [
    {"browser": "Chrome 124", "os": "Windows 10/11", "device": "Desktop", "connected_at": "14:32:05"},
    ...
  ]
}
```

### Client → Server

| Event | Payload | Purpose |
|---|---|---|
| `led_command` | `{state: "ON"\|"OFF"}` | Toggle LED |
| `get_state` | _(none)_ | Request current LED state on page load |
| `get_ip_detail` | `{ip: string}` | Fetch detail data for a specific IP |

---

## HTTP Routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Serves `index.html` via `render_template` |
| POST | `/shutdown` | Force-exits the process after 0.4s delay |
| POST | `/restart` | Spawns a new process then force-exits |

### Shutdown / Restart mechanism

`os._exit(0)` is used instead of `signal.SIGTERM` because SIGTERM is a no-op on Windows. A 0.4s delay via a daemon thread ensures the HTTP `200` response is delivered before the process dies.

```python
def _exit_after(delay=0.4):
    def _do():
        time.sleep(delay)
        os._exit(0)
    threading.Thread(target=_do, daemon=True).start()
```

Restart spawns a fresh copy first:
```python
subprocess.Popen([sys.executable] + sys.argv)
_exit_after()
```

---

## UA Parsing

`parse_ua(ua: str)` is a dependency-free User-Agent parser in `app.py`. It returns:
```python
{"browser": str, "os": str, "device": str}
# device: "Desktop" | "Mobile" | "Tablet"
```

Detection order matters — Edge and Opera are checked before Chrome since their UA strings also contain `Chrome/`.

---

## Initial State Query

On startup, `query_initial_state()` sends `STATE?\n` to the Arduino and reads back the response (2s timeout).

```
Server  →  "STATE?\n"
Arduino →  "ON\n" or "OFF\n"
```

**The current Arduino sketch (`main/main.ino`) does NOT handle `STATE?`.** Until it is updated, the server will always default to `OFF` at startup. The sketch fix is documented in `README.md`.

---

## Client-Side Architecture (`static/js/main.js`)

All logic is in a single flat script — no modules, no bundler.

### Real-time command history refresh

The `log` socket event carries the sender's IP. When the IP detail drawer is open, any `log` event from that IP triggers a fresh `get_ip_detail` request:

```js
socket.on('log', (d) => {
  addLog(d.time, d.ip, d.msg, d.cls);
  if (activeChipIp && d.ip === activeChipIp) {
    socket.emit('get_ip_detail', { ip: activeChipIp });
  }
});
```

### Mobile touch handling

IP chips use event delegation on the container with both `click` and `touchend` to avoid the 300ms delay on mobile. `e.preventDefault()` on `touchend` stops the subsequent synthetic `click`:

```js
clientsBody.addEventListener('click',    onChipActivate);
clientsBody.addEventListener('touchend', onChipActivate, { passive: false });
```

---

## Known Issues / Pending Work

| # | Issue | Notes |
|---|---|---|
| 1 | Arduino sketch missing `STATE?` handler | Server defaults to `OFF` on startup until fixed |
| 2 | `ip_details` grows unbounded | No eviction — restarting server clears it |
| 3 | COM port hardcoded to `COM6` | Move to config or env var if deploying on another machine |

---

## Development Notes

- `request.sid` is injected by Flask-SocketIO at runtime but unknown to pyright — suppressed with `# type: ignore[attr-defined]`
- `async_mode="eventlet"` is required; do not switch to `threading` mode without testing Socket.IO broadcast behaviour
- The `Scaffold_File/` directory contains `app_v1.py`, `app_v2.py`, and `main.py` — kept as historical reference only
