"use strict";

/* Fotobox admin. Plain and functional. Holds the PIN in memory for the session
 * and sends it as X-Fotobox-Pin on every /api/admin/ call. */

let pin = null;
const $ = (id) => document.getElementById(id);

async function api(method, path, body) {
  const opts = { method, headers: { "X-Fotobox-Pin": pin || "" } };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    /* no body */
  }
  if (!res.ok) {
    const msg = data && data.error ? data.error.message : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function note(id, text, ok = true) {
  const el = $(id);
  el.textContent = text;
  el.style.color = ok ? "" : "#ff8a80";
}

// --- auth -------------------------------------------------------------------

/* Keypad input. The kiosk has no keyboard, so digits arrive through the pad;
 * the field itself stays editable for development on a desktop. */
function pinKey(key) {
  const el = $("pin");
  if (key === "back") {
    el.value = el.value.slice(0, -1);
  } else if (key === "clear") {
    el.value = "";
  } else {
    el.value += key;
  }
  $("pin-error").textContent = "";
}

async function login() {
  pin = $("pin").value;
  if (!pin) return;
  try {
    await api("POST", "/api/admin/auth");
    $("gate").classList.add("hidden");
    $("admin").classList.remove("hidden");
    await loadAll();
  } catch (e) {
    pin = null;
    // Clear the field so the next attempt starts empty — without a keyboard
    // there is no comfortable way to correct a half-typed PIN.
    $("pin").value = "";
    $("pin-error").textContent = "Anmeldung fehlgeschlagen: " + e.message;
  }
}

async function loadAll() {
  startAdminPreview(); // only after login — no polling while the PIN gate is up
  await Promise.all([
    loadPrinter(),
    loadCameras(),
    loadBackgrounds(),
    loadConfig(),
    loadStatus(),
    loadNetwork(),
  ]);
}

// --- printer ----------------------------------------------------------------

async function loadPrinter() {
  const p = await api("GET", "/api/admin/printer");
  $("printer-status").textContent =
    `Status: ${PRINTER_STATE[p.state] || p.state} · pausiert: ${p.paused ? "ja" : "nein"} · ` +
    `Warteschlange: ${p.queue_length} · ` +
    `gedruckt: ${p.prints_done_event ?? "?"} (Event), ${p.prints_total ?? "?"} (gesamt)`;
}

async function printerAction(path, confirmMsg) {
  if (confirmMsg && !window.confirm(confirmMsg)) return;
  try {
    await api("POST", path);
    await loadPrinter();
  } catch (e) {
    note("printer-status", "Fehler: " + e.message, false);
  }
}

// --- cameras ----------------------------------------------------------------

function fillSelect(sel, options, value) {
  sel.innerHTML = "";
  for (const opt of options) {
    const o = document.createElement("option");
    o.value = opt.value;
    o.textContent = opt.label;
    sel.appendChild(o);
  }
  sel.value = value;
}

async function loadCameras() {
  const c = await api("GET", "/api/admin/cameras");
  fillSelect(
    $("cam-select"),
    [{ value: "auto", label: "Automatisch" }].concat(
      c.capture.detected.map((cam) => ({
        value: cam.model,
        label: `${cam.model} (${cam.port || cam.id})`,
      }))
    ),
    c.capture.select
  );
  fillSelect(
    $("prev-backend"),
    ["auto", "mock", "picamera2", "v4l2"].map((b) => ({ value: b, label: b })),
    c.preview.backend
  );
  fillSelect(
    $("prev-device"),
    [{ value: "auto", label: "Automatisch" }].concat(
      c.preview.detected.map((p) => ({ value: p.device, label: `${p.name} (${p.device})` }))
    ),
    c.preview.device
  );
  $("cam-status").textContent = c.capture.selected
    ? `Aktiv: ${c.capture.selected.model}`
    : "Keine Kamera erkannt";
  $("cam-fallback").classList.toggle("hidden", !c.capture.fallback);
}

async function applyCamera() {
  try {
    await api("POST", "/api/admin/cameras", {
      camera_select: $("cam-select").value,
      preview_backend: $("prev-backend").value,
      preview_device: $("prev-device").value,
    });
    await loadCameras();
    note("cam-status", "Kamera übernommen.");
  } catch (e) {
    note("cam-status", "Fehler: " + e.message, false);
  }
}

async function rescanCameras() {
  note("cam-status", "Suche läuft …");
  try {
    const c = await api("POST", "/api/admin/camera/rescan");
    await loadCameras();
    note(
      "cam-status",
      c.capture.selected ? `Gefunden: ${c.capture.selected.model}` : "Keine Kamera gefunden",
      Boolean(c.capture.selected)
    );
  } catch (e) {
    note("cam-status", "Fehler: " + e.message, false);
  }
}

async function resetCameras() {
  // Takes the camera off the USB bus for a moment — ask before doing that.
  if (!window.confirm("Kamera zurücksetzen? Sie wird kurz vom USB getrennt.")) return;
  note("cam-status", "Zurücksetzen läuft …");
  try {
    const c = await api("POST", "/api/admin/camera/reset");
    await loadCameras();
    note(
      "cam-status",
      c.capture.selected
        ? `Zurückgesetzt, gefunden: ${c.capture.selected.model}`
        : "Zurückgesetzt, aber keine Kamera gefunden",
      Boolean(c.capture.selected)
    );
  } catch (e) {
    note("cam-status", "Fehler: " + e.message, false);
  }
}

async function testShot() {
  note("cam-status", "Probefoto läuft …");
  try {
    const r = await api("POST", "/api/admin/camera/testshot");
    note("cam-status", "Probefoto aufgenommen.");
    $("cam-shot-info").textContent = `${r.model || "unbekannt"} · ${r.width}×${r.height}`;
    const img = $("cam-shot");
    // The endpoint needs the PIN header, so the image is fetched and shown as a blob.
    const url = await apiBlobUrl(`/api/admin/camera/testshot.jpg?ts=${Date.now()}`);
    if (img.dataset.url) URL.revokeObjectURL(img.dataset.url);
    img.dataset.url = url;
    img.src = url;
    img.classList.remove("hidden");
    await loadCameras();
  } catch (e) {
    note("cam-status", "Fehler: " + e.message, false);
  }
}

async function apiBlobUrl(path) {
  const res = await fetch(path, { headers: { "X-Fotobox-Pin": pin || "" }, cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return URL.createObjectURL(await res.blob());
}

/* Live view of the preview camera, same self-healing polling as the kiosk
 * (frontend/app.js startPreview): single frames instead of one long-lived MJPEG
 * connection, because Chromium can silently freeze a multipart <img> without ever
 * firing "error". Deliberately duplicated — there is no build pipeline, and the
 * kiosk and the admin page load different scripts. */
function startAdminPreview() {
  const img = $("cam-live");
  let currentUrl = null;

  const tick = async () => {
    let delay = 200; // 5 fps is plenty to check the framing
    try {
      const res = await fetch(`/preview/frame?ts=${Date.now()}`, { cache: "no-store" });
      if (res.ok) {
        const url = URL.createObjectURL(await res.blob());
        img.src = url;
        if (currentUrl) URL.revokeObjectURL(currentUrl);
        currentUrl = url;
      } else {
        delay = 1000;
      }
    } catch (e) {
      delay = 1000;
    }
    window.setTimeout(tick, delay);
  };
  tick();
}

async function calibrate() {
  note("cam-status", "Probefoto läuft …");
  try {
    const r = await api("POST", "/api/admin/calibration");
    note("cam-status", `Ausrichtung erkannt: ${r.orientation} (${r.width}×${r.height})`);
  } catch (e) {
    note("cam-status", "Fehler: " + e.message, false);
  }
}

// --- backgrounds / frames ---------------------------------------------------

const BG_MODE_LABEL = {
  frame: "Rahmen",
  overlay: "Overlay",
  chroma: "Greenscreen",
  ai: "KI-Freisteller",
  none: "—",
};

async function loadBackgrounds() {
  const r = await api("GET", "/api/admin/backgrounds");
  const ul = $("bg-list");
  ul.innerHTML = "";
  if (r.backgrounds.length === 0) {
    ul.innerHTML = "<li class='muted'>Noch keine Hintergründe hochgeladen.</li>";
    return;
  }
  for (const bg of r.backgrounds) {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = `${bg.name} · ${BG_MODE_LABEL[bg.mode] || bg.mode}`;
    const del = document.createElement("button");
    del.className = "btn btn--small";
    del.textContent = "Löschen";
    del.addEventListener("click", () => deleteBackground(bg.id, bg.name));
    li.appendChild(span);
    li.appendChild(del);
    ul.appendChild(li);
  }
}

async function uploadBackground() {
  const name = $("bg-name").value.trim();
  const file = $("bg-file").files[0];
  if (!name || !file) {
    note("bg-status", "Name und Datei sind nötig.", false);
    return;
  }
  const fd = new FormData();
  fd.append("name", name);
  fd.append("mode", $("bg-mode").value);
  fd.append("file", file);
  note("bg-status", "Lade hoch …");
  try {
    // Multipart, so no JSON Content-Type (the browser sets the boundary).
    const res = await fetch("/api/admin/backgrounds", {
      method: "POST",
      headers: { "X-Fotobox-Pin": pin || "" },
      body: fd,
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data && data.error ? data.error.message : `HTTP ${res.status}`);
    $("bg-name").value = "";
    $("bg-file").value = "";
    await loadBackgrounds();
    note("bg-status", "Hochgeladen.");
  } catch (e) {
    note("bg-status", "Fehler: " + e.message, false);
  }
}

async function deleteBackground(id, name) {
  if (!window.confirm(`Hintergrund „${name}" löschen?`)) return;
  try {
    await api("DELETE", "/api/admin/backgrounds/" + encodeURIComponent(id));
    await loadBackgrounds();
  } catch (e) {
    note("bg-status", "Fehler: " + e.message, false);
  }
}

// --- config -----------------------------------------------------------------

async function loadConfig() {
  const cfg = await api("GET", "/api/admin/config");
  $("cfg-countdown").value = cfg.countdown.duration_seconds;
  $("cfg-lead").value = cfg.countdown.shutter_lead_ms;
  $("cfg-preview").value = cfg.timeouts.preview_seconds;
  $("cfg-error").value = cfg.timeouts.error_seconds;
  $("cfg-perphoto").value = cfg.printing.max_per_photo;
  $("cfg-perevent").value = cfg.printing.max_per_event;
  $("cfg-bgselect").checked = cfg.ui.background_select_enabled;
}

async function saveConfig() {
  const updates = {
    countdown: {
      duration_seconds: Number($("cfg-countdown").value),
      shutter_lead_ms: Number($("cfg-lead").value),
    },
    timeouts: {
      preview_seconds: Number($("cfg-preview").value),
      error_seconds: Number($("cfg-error").value),
    },
    printing: {
      max_per_photo: Number($("cfg-perphoto").value),
      max_per_event: Number($("cfg-perevent").value),
    },
    ui: { background_select_enabled: $("cfg-bgselect").checked },
  };
  try {
    await api("PUT", "/api/admin/config", updates);
    note("cfg-status", "Gespeichert — wirkt sofort.");
  } catch (e) {
    note("cfg-status", "Fehler: " + e.message, false);
  }
}

// --- event / status / system ------------------------------------------------

async function createEvent() {
  const name = $("event-name").value.trim();
  if (!name) return;
  try {
    await api("POST", "/api/admin/event", { name });
    $("event-name").value = "";
    await loadStatus();
  } catch (e) {
    note("event-current", "Fehler: " + e.message, false);
  }
}

/* --- status formatting ------------------------------------------------------
 * The tile shows the fields listed in ui-screens.md. Anything the backend
 * cannot determine (cpu_temp and uptime return null off the Pi) is shown as
 * "unbekannt" rather than as an empty row. */

const UNKNOWN = "unbekannt";

function fmtUptime(seconds) {
  if (seconds === null || seconds === undefined) return UNKNOWN;
  const total = Math.floor(seconds);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const parts = [];
  if (days) parts.push(`${days} ${days === 1 ? "Tag" : "Tage"}`);
  if (hours) parts.push(`${hours} Std.`);
  parts.push(`${minutes} Min.`);
  return parts.join(", ");
}

function fmtBytes(bytes) {
  if (bytes === null || bytes === undefined) return UNKNOWN;
  const gb = bytes / 1e9;
  if (gb >= 1) return `${gb.toLocaleString("de-DE", { maximumFractionDigits: 1 })} GB`;
  return `${Math.round(bytes / 1e6).toLocaleString("de-DE")} MB`;
}

function fmtCamera(cam) {
  if (!cam) return UNKNOWN;
  return cam.available ? cam.model || "verfügbar" : "nicht verfügbar";
}

/* PrinterState arrives as the raw backend value; the UI is German throughout. */
const PRINTER_STATE = {
  idle: "bereit",
  printing: "druckt",
  error: "Fehler",
  offline: "nicht erreichbar",
};

function fmtPrinter(p) {
  if (!p) return UNKNOWN;
  if (!p.available) return "nicht verfügbar";
  const state = PRINTER_STATE[p.state] || p.state || UNKNOWN;
  const parts = [p.paused ? "angehalten" : state];
  if (p.queue_length) parts.push(`Warteschlange ${p.queue_length}`);
  return parts.join(" · ");
}

function fmtStorage(st) {
  if (!st) return UNKNOWN;
  let text = `${fmtBytes(st.free_bytes)} frei`;
  if (st.blocked) text += " — Speicher voll";
  else if (st.warning) text += " — wird knapp";
  return text;
}

/* Renders label/value pairs into the <dl>. `warn` marks a row visually. */
function renderStatus(rows) {
  const box = $("status-box");
  box.textContent = "";
  for (const [label, value, warn] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    if (warn) dd.classList.add("status__warn");
    box.append(dt, dd);
  }
}

async function loadStatus() {
  const s = await api("GET", "/api/admin/system");
  $("event-current").textContent = `Aktuell: ${s.event.name} (${s.event.photo_count} Fotos)`;
  const storage = s.storage || {};
  const p = s.printer || {};
  renderStatus([
    ["Kamera", fmtCamera(s.camera), s.camera && !s.camera.available],
    ["Drucker", fmtPrinter(s.printer), s.printer && (!s.printer.available || s.printer.paused)],
    ["Gedruckt (Event)", p.prints_done_event ?? UNKNOWN],
    ["Gedruckt (gesamt)", p.prints_total ?? UNKNOWN],
    ["Speicher", fmtStorage(storage), storage.warning || storage.blocked],
    ["CPU-Temperatur", s.cpu_temp === null || s.cpu_temp === undefined ? UNKNOWN : `${s.cpu_temp} °C`],
    ["Uptime", fmtUptime(s.uptime_seconds)],
    ["Version", s.versions && s.versions.python ? `Python ${s.versions.python}` : UNKNOWN],
  ]);
}

async function shutdown() {
  if (!window.confirm("Fotobox wirklich herunterfahren?")) return;
  try {
    await api("POST", "/api/admin/shutdown");
    document.body.innerHTML = "<p style='padding:40px'>Fotobox fährt herunter …</p>";
  } catch (e) {
    window.alert("Fehler: " + e.message);
  }
}

async function reboot() {
  if (!window.confirm("Fotobox wirklich neu starten?")) return;
  try {
    await api("POST", "/api/admin/reboot");
    document.body.innerHTML = "<p style='padding:40px'>Fotobox startet neu …</p>";
  } catch (e) {
    window.alert("Fehler: " + e.message);
  }
}

// --- network / export -------------------------------------------------------

let apEnabled = false;

function galleryUrl(ip) {
  if (!ip) return "";
  const port = location.port || (location.protocol === "https:" ? "443" : "80");
  return `${location.protocol}//${ip}:${port}/gallery`;
}

async function loadNetwork() {
  const n = await api("GET", "/api/admin/network");
  apEnabled = n.ap_enabled;
  $("net-ap").textContent = apEnabled ? "Access-Point ausschalten" : "Access-Point einschalten";
  $("net-status").textContent = apEnabled
    ? `Access-Point „${n.ssid}" aktiv · IP ${n.ip ?? "?"}`
    : `Access-Point aus · IP ${n.ip ?? "?"}`;
  const url = galleryUrl(n.ip);
  const link = $("net-gallery");
  link.textContent = url || "—";
  link.href = url || "#";
}

async function toggleAP() {
  const target = !apEnabled;
  const msg = target
    ? "Access-Point einschalten? Die WLAN-Verbindung zum Heimnetz wird dabei getrennt."
    : "Access-Point ausschalten?";
  if (!window.confirm(msg)) return;
  note("net-status", target ? "Schalte Access-Point ein …" : "Schalte Access-Point aus …");
  try {
    await api("POST", "/api/admin/network/ap", { enabled: target });
    await loadNetwork();
  } catch (e) {
    note("net-status", "Fehler: " + e.message, false);
  }
}

async function exportUSB() {
  $("export-usb").disabled = true;
  note("export-status", "Starte Export …");
  try {
    const start = await api("POST", "/api/admin/export/usb");
    note("export-status", `0 / ${start.total} Dateien`);
    await pollExport();
  } catch (e) {
    note("export-status", "Fehler: " + e.message, false);
  } finally {
    $("export-usb").disabled = false;
  }
}

async function pollExport() {
  for (;;) {
    const s = await api("GET", "/api/admin/export/usb");
    const mb = (s.bytes / 1e6).toFixed(1);
    if (s.finished) {
      if (s.error) {
        note("export-status", "Fehler: " + s.error, false);
      } else {
        note("export-status", `Fertig: ${s.done} Dateien (${mb} MB) auf USB-Stick kopiert.`);
      }
      return;
    }
    note("export-status", `${s.done} / ${s.total} Dateien (${mb} MB)`);
    await new Promise((r) => setTimeout(r, 800));
  }
}

// --- wiring -----------------------------------------------------------------

window.addEventListener("DOMContentLoaded", () => {
  $("pin-submit").addEventListener("click", login);
  $("pin").addEventListener("keydown", (e) => {
    if (e.key === "Enter") login();
  });
  $("pin-pad").addEventListener("click", (e) => {
    const key = e.target.closest(".pad__key");
    if (!key) return;
    pinKey(key.dataset.digit ?? key.dataset.action);
  });
  $("printer-resume").addEventListener("click", () => printerAction("/api/admin/printer/resume"));
  $("printer-cancel").addEventListener("click", () =>
    printerAction("/api/admin/printer/cancel-all", "Warteschlange wirklich leeren?")
  );
  $("printer-test").addEventListener("click", () =>
    printerAction("/api/admin/printer/test-page", "Testdruck starten? (verbraucht ein Blatt)")
  );
  $("printer-reset").addEventListener("click", () => printerAction("/api/admin/printer/counter-reset", "Druckzähler wirklich auf 0 setzen?"));
  $("cam-apply").addEventListener("click", applyCamera);
  $("cam-rescan").addEventListener("click", rescanCameras);
  $("cam-reset").addEventListener("click", resetCameras);
  $("cam-testshot").addEventListener("click", testShot);
  $("cam-calibrate").addEventListener("click", calibrate);
  $("bg-upload").addEventListener("click", uploadBackground);
  $("cfg-save").addEventListener("click", saveConfig);
  $("event-create").addEventListener("click", createEvent);
  $("status-refresh").addEventListener("click", loadStatus);
  $("net-ap").addEventListener("click", toggleAP);
  $("export-usb").addEventListener("click", exportUSB);
  $("sys-reboot").addEventListener("click", reboot);
  $("sys-shutdown").addEventListener("click", shutdown);
});
