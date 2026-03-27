const socket = io();

const dot         = document.getElementById('ws-dot');
const wsLabel     = document.getElementById('ws-label');
const ardDot      = document.getElementById('ard-dot');
const ardLabel    = document.getElementById('ard-label');
const bulb        = document.getElementById('bulb');
const stateText   = document.getElementById('state-text');
const btnOn       = document.getElementById('btn-on');
const btnOff      = document.getElementById('btn-off');
const card        = document.getElementById('card');
const consoleBody = document.getElementById('console-body');
const clientsBody = document.getElementById('clients-body');
const clientCount = document.getElementById('client-count');
const drawer      = document.getElementById('detail-drawer');

let activeChipIp      = null;
let arduinoConnected  = false;
let currentLedState   = 'OFF';

// single delegated listener — works for both mouse and touch
function onChipActivate(e) {
  const chip = e.target.closest('.ip-chip');
  if (!chip) return;
  e.preventDefault();
  openDetail(chip.dataset.ip);
}
clientsBody.addEventListener('click',    onChipActivate);
clientsBody.addEventListener('touchend', onChipActivate, { passive: false });

// ── ip detail drawer ──────────────────────────────
function openDetail(ip) {
  if (activeChipIp === ip) { closeDetail(); return; }
  activeChipIp = ip;
  document.querySelectorAll('.ip-chip').forEach(c =>
    c.classList.toggle('active', c.dataset.ip === ip));
  document.getElementById('detail-ip').textContent    = ip;
  document.getElementById('detail-first').textContent = '…';
  document.getElementById('detail-tabs').textContent  = '…';
  document.getElementById('detail-total').textContent = '…';
  document.getElementById('detail-cmds').innerHTML    = '';
  drawer.classList.add('open');
  socket.emit('get_ip_detail', { ip });
}

function closeDetail() {
  activeChipIp = null;
  drawer.classList.remove('open');
  document.querySelectorAll('.ip-chip').forEach(c => c.classList.remove('active'));
}

socket.on('ip_detail', (d) => {
  if (d.ip !== activeChipIp) return;
  document.getElementById('detail-ip').textContent    = d.ip;
  document.getElementById('detail-first').textContent = d.first_seen;
  document.getElementById('detail-tabs').textContent  = d.tabs;
  document.getElementById('detail-total').textContent = d.commands.length;

  // sessions
  const sessionList = document.getElementById('detail-sessions');
  if (!d.sessions || d.sessions.length === 0) {
    sessionList.innerHTML = '<span class="no-cmds">No active sessions</span>';
  } else {
    sessionList.innerHTML = d.sessions.map(s =>
      `<div class="session-card">
         <div class="session-row"><span class="session-key">Browser</span><span class="session-val">${s.browser}</span></div>
         <div class="session-row"><span class="session-key">OS</span><span class="session-val">${s.os}</span></div>
         <div class="session-row"><span class="session-key">Device</span><span class="session-val">${s.device}</span></div>
         <div class="session-row"><span class="session-key">Since</span><span class="session-val">${s.connected_at}</span></div>
       </div>`
    ).join('');
  }

  // commands
  const list = document.getElementById('detail-cmds');
  if (d.commands.length === 0) {
    list.innerHTML = '<span class="no-cmds">No commands yet</span>';
  } else {
    list.innerHTML = [...d.commands].reverse().map(c =>
      `<div class="cmd-row">
         <span class="cmd-time">${c.time}</span>
         <span class="cmd-val ${c.cmd.toLowerCase()}">${c.cmd}</span>
       </div>`
    ).join('');
  }
});

// ── connected clients panel ──────────────────────
function updateClients(ips) {
  clientCount.textContent = ips.length;
  if (ips.length === 0) {
    clientsBody.innerHTML = '<span class="no-clients">No clients connected</span>';
    if (activeChipIp) closeDetail();
    return;
  }
  clientsBody.innerHTML = ips.map(ip =>
    `<div class="ip-chip${ip === activeChipIp ? ' active' : ''}" data-ip="${ip}">
       <span class="chip-dot"></span>${ip}
     </div>`
  ).join('');
  if (activeChipIp && !ips.includes(activeChipIp)) closeDetail();
  if (activeChipIp && ips.includes(activeChipIp)) {
    socket.emit('get_ip_detail', { ip: activeChipIp });
  }
}

// ── console log ──────────────────────────────────
function addLog(time, ip, msg, cls) {
  const line = document.createElement('div');
  line.className = 'log-line';
  line.innerHTML =
    `<span class="log-time">${time}</span>` +
    `<span class="log-ip">[${ip}]</span>` +
    `<span class="log-msg ${cls || ''}">${msg}</span>`;
  consoleBody.appendChild(line);
  consoleBody.scrollTop = consoleBody.scrollHeight;
}

function clearLog() { consoleBody.innerHTML = ''; }

// ── confirmation modal ────────────────────────────
const overlay         = document.getElementById('modal-overlay');
const modalCard       = document.getElementById('modal-card');
const modalIcon       = document.getElementById('modal-icon');
const modalTitle      = document.getElementById('modal-title');
const modalMsg        = document.getElementById('modal-msg');
const modalConfirmBtn = document.getElementById('modal-confirm-btn');

function showConfirm({ icon, title, msg, confirmText, color, onConfirm }) {
  modalCard.style.setProperty('--modal-color', color);
  modalConfirmBtn.style.setProperty('--modal-color', color);
  modalIcon.textContent       = icon;
  modalTitle.textContent      = title;
  modalMsg.textContent        = msg;
  modalConfirmBtn.textContent = confirmText;
  modalConfirmBtn.onclick     = () => { closeModal(); onConfirm(); };
  overlay.classList.add('open');
}

function closeModal() { overlay.classList.remove('open'); }

overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

// ── server controls ───────────────────────────────
function shutdownServer() {
  showConfirm({
    icon: '⏹',
    title: 'Stop Server?',
    msg: 'This will shut down the Flask server. You will need to restart it manually from the terminal.',
    confirmText: 'Stop',
    color: '#ff3b3b',
    onConfirm: () => {
      fetch('/shutdown', { method: 'POST' }).catch(() => {});
      document.body.innerHTML =
        '<div style="font-family:monospace;color:#c8d0d6;display:flex;flex-direction:column;' +
        'align-items:center;justify-content:center;height:100vh;gap:12px;">' +
        '<span style="font-size:2rem">⏹</span>' +
        '<span style="letter-spacing:.15em">Server stopped.</span></div>';
    }
  });
}

function restartServer() {
  showConfirm({
    icon: '↺',
    title: 'Restart Server?',
    msg: 'The server will restart. The page will automatically reconnect via WebSocket when it comes back online.',
    confirmText: 'Restart',
    color: '#f5a623',
    onConfirm: () => {
      fetch('/restart', { method: 'POST' }).catch(() => {});
    }
  });
}

// ── apply LED state to all UI elements ───────────
function applyState(state) {
  currentLedState = state;
  const isOn = state === 'ON';
  bulb.classList.toggle('on',  isOn);
  bulb.classList.toggle('off', !isOn);
  stateText.textContent = state;
  stateText.style.color = isOn ? 'var(--accent-on)' : 'var(--accent-off)';
  card.style.setProperty('--stripe', isOn
    ? 'linear-gradient(90deg, var(--accent-on), #00bfff, transparent)'
    : 'linear-gradient(90deg, var(--accent-off), #ff8800, transparent)');
  // only apply active-button dimming when Arduino is connected
  if (arduinoConnected) {
    btnOn.classList.toggle('dimmed',  isOn);
    btnOff.classList.toggle('dimmed', !isOn);
  }
}

// ── send command to server ───────────────────────
function sendCommand(cmd) {
  if (!arduinoConnected) return;
  socket.emit('led_command', { state: cmd });
}

// ── socket events ────────────────────────────────
socket.on('connect', () => {
  dot.classList.add('connected');
  wsLabel.textContent = 'Live';
  wsLabel.style.color = 'var(--accent-on)';
  socket.emit('get_state');
});

socket.on('disconnect', () => {
  dot.classList.remove('connected');
  wsLabel.textContent = 'Disconnected';
  wsLabel.style.color = 'var(--accent-off)';
});

socket.on('state_update',   (d) => applyState(d.state));

socket.on('arduino_status', (d) => {
  arduinoConnected = d.connected;
  if (d.connected) {
    ardDot.classList.remove('arduino-off');
    ardDot.classList.add('connected');
    ardLabel.textContent = 'Arduino';
    ardLabel.style.color = 'var(--accent-on)';
    // restore button state based on current LED state
    applyState(currentLedState);
  } else {
    ardDot.classList.remove('connected');
    ardDot.classList.add('arduino-off');
    ardLabel.textContent = 'Arduino Disconnected';
    ardLabel.style.color = 'var(--accent-off)';
    // dim both buttons — controls are unavailable
    btnOn.classList.add('dimmed');
    btnOff.classList.add('dimmed');
    // grey out the bulb indicator
    bulb.classList.remove('on');
    bulb.classList.add('off');
    stateText.textContent = '—';
    stateText.style.color = 'var(--muted)';
  }
});
socket.on('clients_update', (d) => updateClients(d.ips));
socket.on('log', (d) => {
  addLog(d.time, d.ip, d.msg, d.cls);
  if (activeChipIp && d.ip === activeChipIp) {
    socket.emit('get_ip_detail', { ip: activeChipIp });
  }
});
