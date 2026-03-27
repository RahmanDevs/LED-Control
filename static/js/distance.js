"use strict";

const socket = io();

// DOM
const wsDot      = document.getElementById("ws-dot");
const wsLabel    = document.getElementById("ws-label");
const ardDot     = document.getElementById("ard-dot");
const ardLabel   = document.getElementById("ard-label");
const distValue  = document.getElementById("dist-value");
const unitToggle = document.getElementById("unit-toggle");
const rangeFill  = document.getElementById("range-fill");
const rangeMarker= document.getElementById("range-marker");
const statMin    = document.getElementById("stat-min");
const statMax    = document.getElementById("stat-max");
const statCount  = document.getElementById("stat-count");
const consoleBody= document.getElementById("console-body");
const clientsBody= document.getElementById("clients-body");
const clientCount= document.getElementById("client-count");

// State
let currentUnit = "cm";   // "cm" | "in"
let minCm = null;
let maxCm = null;
let readingCount = 0;

// ── Unit toggle ────────────────────────────────────────────────────────────

function toggleUnit() {
  currentUnit = currentUnit === "cm" ? "in" : "cm";
  unitToggle.textContent = currentUnit;

  // Re-render stats with new unit
  if (minCm !== null) statMin.textContent = fmt(minCm);
  if (maxCm !== null) statMax.textContent = fmt(maxCm);
}

function fmt(cm) {
  if (cm < 0) return "—";
  if (currentUnit === "in") return (cm / 2.54).toFixed(1) + " in";
  return cm.toFixed(1) + " cm";
}

// ── Range bar (0–400 cm) ───────────────────────────────────────────────────

function updateBar(cm) {
  if (cm < 0) {
    rangeFill.style.width   = "0%";
    rangeMarker.style.left  = "0%";
    return;
  }
  const pct = Math.min(100, (cm / 400) * 100).toFixed(1) + "%";
  rangeFill.style.width  = pct;
  rangeMarker.style.left = pct;
}

// ── Log ───────────────────────────────────────────────────────────────────

function addLog(cm) {
  const ts = new Date().toLocaleTimeString("en-GB");
  const line = document.createElement("div");
  line.className = "log-line";
  if (cm < 0) {
    line.innerHTML = `<span class="ts">${ts}</span><span class="oor">Out of range</span>`;
  } else {
    const display = currentUnit === "in"
      ? (cm / 2.54).toFixed(1) + " in"
      : cm.toFixed(1) + " cm";
    line.innerHTML = `<span class="ts">${ts}</span><span class="val">${display}</span>`;
  }
  consoleBody.appendChild(line);
  consoleBody.scrollTop = consoleBody.scrollHeight;

  // Keep log from growing unboundedly
  while (consoleBody.children.length > 200) {
    consoleBody.removeChild(consoleBody.firstChild);
  }
}

function clearLog() {
  consoleBody.innerHTML = "";
}

// ── Apply incoming reading ─────────────────────────────────────────────────

function applyReading(cm) {
  readingCount++;
  statCount.textContent = readingCount;

  if (cm < 0) {
    distValue.textContent = "OOR";
    distValue.classList.add("oor");
    updateBar(-1);
    addLog(-1);
    return;
  }

  distValue.classList.remove("oor");
  distValue.textContent = currentUnit === "in"
    ? (cm / 2.54).toFixed(1)
    : cm.toFixed(1);
  unitToggle.textContent = currentUnit;

  updateBar(cm);
  addLog(cm);

  // Min / Max
  if (minCm === null || cm < minCm) { minCm = cm; statMin.textContent = fmt(cm); }
  if (maxCm === null || cm > maxCm) { maxCm = cm; statMax.textContent = fmt(cm); }
}

// ── Socket events ──────────────────────────────────────────────────────────

socket.on("connect", () => {
  wsDot.classList.add("dot-ok");
  wsLabel.textContent = "Live";
  socket.emit("get_distance");
});

socket.on("disconnect", () => {
  wsDot.classList.remove("dot-ok");
  wsLabel.textContent = "Disconnected";
});

socket.on("arduino_status", (data) => {
  if (data.connected) {
    ardDot.classList.add("dot-ok");
    ardDot.classList.remove("dot-err");
    ardLabel.textContent = "Arduino — Connected";
  } else {
    ardDot.classList.remove("dot-ok");
    ardDot.classList.add("dot-err");
    ardLabel.textContent = "Arduino — Disconnected";
    distValue.textContent = "—";
    distValue.classList.remove("oor");
    updateBar(-1);
  }
});

socket.on("clients_update", (data) => {
  const ips = data.ips || [];
  clientCount.textContent = ips.length;
  clientsBody.innerHTML = "";
  if (ips.length === 0) {
    clientsBody.innerHTML = '<span class="no-clients">No clients connected</span>';
    return;
  }
  ips.forEach(ip => {
    const chip = document.createElement("div");
    chip.className = "ip-chip";
    chip.innerHTML = `<span class="chip-dot"></span>${ip}`;
    clientsBody.appendChild(chip);
  });
});

socket.on("distance_update", (data) => {
  applyReading(data.cm);
});
