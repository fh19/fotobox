"use strict";

/* Fotobox admin. Plain and functional. Holds the PIN in memory for the session
 * and sends it as X-Fotobox-Pin on every /api/admin/ call. */

let pin = null;
// Config and backgrounds load in parallel, either order — whichever arrives
// second fills the background dropdown with the configured value.
let configuredBackground = "auto";
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
    // The gallery page opens in this same tab and needs the PIN to delete.
    // sessionStorage, not a URL parameter: it dies with the tab and never ends
    // up in a link somebody shares.
    try {
      sessionStorage.setItem("fotobox_pin", pin);
    } catch (err) {
      /* private mode — deleting from the gallery then asks again */
    }
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
    loadDeleted(),
    loadEventsForRerender(),
  ]);
  // Erst danach: die Modus-Zeile nennt die Adresse der Box, und die kommt aus
  // loadNetwork().
  await loadMode();
}

// --- on-screen keyboard -----------------------------------------------------
//
// "in der Konfiguration kann man ohne Tastatur nur sehr wenig ändern" — the box
// has a touchscreen and no keyboard, so text and number fields were read-only in
// practice. The PIN pad already proved the idea; this generalises it to every
// field and appears when one is focused.

const OSK_LETTERS = [
  "1234567890",
  "qwertzuiopü",
  "asdfghjklöä",
  "yxcvbnmß-.",
];
const OSK_DIGITS = ["123", "456", "789", "0.-"];

let oskTarget = null;
let oskShift = false;

function oskInsert(text) {
  if (!oskTarget) return;
  // Number inputs report an empty selection API in some browsers; append is enough
  // for the short values here and keeps the caret handling simple.
  oskTarget.value += text;
  oskTarget.dispatchEvent(new Event("input", { bubbles: true }));
}

function oskAction(action) {
  if (!oskTarget) return;
  if (action === "back") oskTarget.value = oskTarget.value.slice(0, -1);
  else if (action === "clear") oskTarget.value = "";
  else if (action === "shift") {
    oskShift = !oskShift;
    buildOsk();
    return;
  } else if (action === "done") {
    hideOsk();
    return;
  }
  oskTarget.dispatchEvent(new Event("input", { bubbles: true }));
}

function oskKey(label, opts = {}) {
  const key = document.createElement("button");
  key.type = "button";
  key.className = "osk__key" + (opts.aux ? " osk__key--aux" : "");
  key.textContent = label;
  if (opts.wide) key.classList.add("osk__key--wide");
  // pointerdown + preventDefault: the field must keep focus, otherwise the next
  // key press has nowhere to write.
  key.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    if (opts.action) oskAction(opts.action);
    else oskInsert(opts.insert ?? label);
    if (oskShift && !opts.action) {
      oskShift = false;
      buildOsk();
    }
  });
  return key;
}

function buildOsk() {
  const numeric = oskTarget && oskTarget.type === "number";
  const rows = numeric ? OSK_DIGITS : OSK_LETTERS;
  $("osk").innerHTML = "";
  for (const row of rows) {
    const line = document.createElement("div");
    line.className = "osk__row";
    for (const char of row) {
      const label = oskShift ? char.toUpperCase() : char;
      line.appendChild(oskKey(label));
    }
    $("osk").appendChild(line);
  }
  const last = document.createElement("div");
  last.className = "osk__row";
  if (!numeric) {
    last.appendChild(oskKey(oskShift ? "abc" : "ABC", { action: "shift", aux: true }));
    last.appendChild(oskKey("Leer", { insert: " ", wide: true }));
  }
  last.appendChild(oskKey("←", { action: "back", aux: true }));
  last.appendChild(oskKey("✕", { action: "clear", aux: true }));
  last.appendChild(oskKey("Fertig", { action: "done", aux: true, wide: true }));
  $("osk").appendChild(last);
}

function showOsk(input) {
  oskTarget = input;
  oskShift = false;
  buildOsk();
  $("osk").classList.remove("hidden");
  $("osk").setAttribute("aria-hidden", "false");
}

function hideOsk() {
  oskTarget = null;
  $("osk").classList.add("hidden");
  $("osk").setAttribute("aria-hidden", "true");
}

/* "auto" = only where there is no real keyboard (a touchscreen has no hover). */
let oskWired = false;
let oskMode = "auto";
let oskTouchSeen = false;

/* "auto" must not ask the hover media query: the box's touchscreen registers a
   mouse device as well (usb-wch.cn_TouchScreen...-if02-event-mouse), so the
   browser reports a hovering pointer and the keyboard never appeared. A real
   touch device, or an actual touch, is the honest signal. */
function oskAllowed() {
  if (oskMode === "off") return false;
  if (oskMode === "on") return true;
  return oskTouchSeen || navigator.maxTouchPoints > 0;
}

function wireOnscreenKeyboard(mode) {
  oskMode = mode;
  if (oskWired || mode === "off") return;
  document.querySelectorAll('#admin input[type="text"], #admin input[type="number"]').forEach(
    (input) => {
      input.addEventListener("focus", () => {
        if (oskAllowed()) showOsk(input);
      });
    }
  );
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (event.pointerType === "touch") oskTouchSeen = true;
    },
    true
  );
  document.addEventListener("pointerdown", (event) => {
    if (!oskTarget) return;
    if (event.target.closest("#osk") || event.target === oskTarget) return;
    hideOsk();
  });
  oskWired = true;
}

// --- printer ----------------------------------------------------------------

async function loadPrinter() {
  const p = await api("GET", "/api/admin/printer");
  const used = p.quota_used ?? 0;
  const total = p.quota_total ?? 0;
  $("printer-status").textContent =
    `Status: ${PRINTER_STATE[p.state] || p.state} · pausiert: ${p.paused ? "ja" : "nein"} · ` +
    `Warteschlange: ${p.queue_length} · ` +
    `gedruckt: ${p.prints_done_event ?? "?"} (Event), ${p.prints_total ?? "?"} (gesamt)` +
    (total ? ` · Kontingent: ${used}/${total}` : "");
  // The reason, prominently: "nicht verfügbar" alone made everyone guess, and a
  // used-up quota withdrew the print button without a word.
  const problem = $("printer-problem");
  const exhausted = total > 0 && used >= total;
  problem.textContent =
    p.message || (exhausted ? "Druckkontingent aufgebraucht — Drucken wird nicht angeboten" : "");
  problem.classList.toggle("hidden", !problem.textContent);
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
  fillBackgroundChoice(r.backgrounds);
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

/* Which background every photo gets when the guests are not asked. Filled from
 * the uploaded ones, so a freshly uploaded frame can be picked right away. The
 * value is kept across the refill — loadBackgrounds() also runs after an upload. */
function fillBackgroundChoice(backgrounds) {
  const sel = $("cfg-bgdefault");
  const previous = sel.value || configuredBackground;
  fillSelect(
    sel,
    [
      { value: "auto", label: "Automatisch (vorhandener Rahmen)" },
      { value: "none", label: "Ohne Hintergrund" },
    ].concat(
      backgrounds.map((bg) => ({
        value: bg.id,
        label: `${bg.name} · ${BG_MODE_LABEL[bg.mode] || bg.mode}${bg.enabled ? "" : " (aus)"}`,
      }))
    ),
    previous
  );
  if (!sel.value) sel.value = "auto"; // configured id no longer exists
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
  $("cfg-flash").checked = cfg.ui.flash_enabled;
  $("cfg-flashms").value = cfg.ui.flash_duration_ms;
  $("cfg-preview").value = cfg.timeouts.preview_seconds;
  $("cfg-error").value = cfg.timeouts.error_seconds;
  $("cfg-perphoto").value = cfg.printing.max_per_photo;
  $("cfg-perevent").value = cfg.printing.max_per_event;
  $("cfg-bgselect").checked = cfg.ui.background_select_enabled;
  configuredBackground = cfg.ui.default_background;
  $("cfg-bgdefault").value = configuredBackground;
  $("cfg-saver").checked = cfg.screensaver.enabled;
  $("cfg-saverafter").value = cfg.screensaver.after_seconds;
  wireOnscreenKeyboard(cfg.ui.onscreen_keyboard || "auto");
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
    ui: {
      background_select_enabled: $("cfg-bgselect").checked,
      default_background: $("cfg-bgdefault").value || "auto",
      flash_enabled: $("cfg-flash").checked,
      flash_duration_ms: Number($("cfg-flashms").value),
    },
    screensaver: {
      enabled: $("cfg-saver").checked,
      after_seconds: Number($("cfg-saverafter").value),
    },
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
let boxAddress = null; // IP der Box, für den Rückweg aus dem Druckserver-Modus

function galleryUrl(ip) {
  if (!ip) return "";
  const port = location.port || (location.protocol === "https:" ? "443" : "80");
  return `${location.protocol}//${ip}:${port}/gallery`;
}

async function loadNetwork() {
  const n = await api("GET", "/api/admin/network");
  apEnabled = n.ap_enabled;
  boxAddress = n.ip || null;
  $("net-ap").textContent = apEnabled ? "Access-Point ausschalten" : "Access-Point einschalten";
  $("net-status").textContent = apEnabled
    ? `Access-Point „${n.ssid}" aktiv · IP ${n.ip ?? "?"}`
    : `Access-Point aus · IP ${n.ip ?? "?"}`;
  $("net-ap-auto").checked = !!n.ap_auto;
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

async function toggleAPAuto() {
  const enabled = $("net-ap-auto").checked;
  try {
    await api("POST", "/api/admin/network/ap-auto", { enabled });
    note(
      "net-status",
      enabled
        ? "Access-Point geht bei fehlendem Netzwerk von selbst an"
        : "Access-Point nur noch von Hand"
    );
  } catch (e) {
    note("net-status", "Fehler: " + e.message, false);
    await loadNetwork();
  }
}

/* Deleting only flags a photo (datenmodell.md); this is the separate, explicit
   step that actually frees the card. */
async function loadDeleted() {
  try {
    const stats = await api("GET", "/api/admin/photos/deleted");
    const has = stats.count > 0;
    $("gal-purge").classList.toggle("hidden", !has);
    $("gal-deleted").textContent = has
      ? `${stats.count} gelöschte Bilder belegen noch ${fmtBytes(stats.bytes)}`
      : "Keine gelöschten Bilder auf der Karte";
  } catch (e) {
    $("gal-deleted").textContent = "";
  }
}

async function purgeDeleted() {
  if (
    !window.confirm("Die Dateien der gelöschten Bilder endgültig entfernen? Nicht umkehrbar.")
  )
    return;
  $("gal-purge").disabled = true;
  try {
    const res = await api("POST", "/api/admin/photos/purge");
    note("gal-deleted", `${res.purged} Dateien entfernt, ${fmtBytes(res.freed_bytes)} frei`);
  } catch (e) {
    note("gal-deleted", "Fehler: " + e.message, false);
  } finally {
    $("gal-purge").disabled = false;
    await loadDeleted();
  }
}

/* Die bearbeiteten Bilder sind nur so gut wie die Pipeline, die sie gemacht hat.
   Nach einer Verbesserung lassen sie sich aus den Originalen neu erzeugen. */
async function loadEventsForRerender() {
  try {
    const data = await api("GET", "/api/events");
    const select = $("gal-event");
    select.innerHTML = "";
    for (const event of data.events || []) {
      const option = document.createElement("option");
      option.value = String(event.id);
      option.textContent = `${event.name} (${event.photo_count})`;
      select.appendChild(option);
    }
  } catch (e) {
    /* Galerie deaktiviert — dann gibt es hier nichts zu wählen */
  }
}

async function startRerender() {
  const select = $("gal-event");
  const label = select.options[select.selectedIndex]?.textContent || "";
  if (!window.confirm(`${label} neu berechnen? Das dauert einige Minuten.`)) return;
  $("gal-rerender").disabled = true;
  try {
    const res = await api("POST", `/api/admin/events/${select.value}/rerender`);
    note("gal-rerender-status", `Neuberechnung läuft: 0 / ${res.total}`);
    pollRerender();
  } catch (e) {
    note("gal-rerender-status", "Fehler: " + e.message, false);
    $("gal-rerender").disabled = false;
  }
}

async function pollRerender() {
  let status;
  try {
    status = await api("GET", "/api/admin/rerender");
  } catch (e) {
    $("gal-rerender").disabled = false;
    return;
  }
  const failed = status.failed ? `, ${status.failed} fehlgeschlagen` : "";
  if (status.running) {
    note("gal-rerender-status", `Neuberechnung läuft: ${status.done} / ${status.total}${failed}`);
    window.setTimeout(pollRerender, 2000);
    return;
  }
  $("gal-rerender").disabled = false;
  if (status.error) {
    note("gal-rerender-status", "Fehler: " + status.error, false);
  } else if (status.finished) {
    note("gal-rerender-status", `Fertig: ${status.done} Bilder neu berechnet${failed}`);
  }
}

/* Betriebsart: bewusst eine Entscheidung des Betreibers, nicht geraten aus den
   Geräten, die beim Booten zufällig da sind. */
async function loadMode() {
  try {
    const res = await api("GET", "/api/admin/mode");
    $("sys-mode").value = res.mode;
    const label = res.mode === "printserver" ? "Druckserver" : "Fotobox";
    $("sys-mode-status").textContent = res.reboot_required
      ? `${label} ab dem nächsten Neustart — läuft gerade als ${
          res.running === "printserver" ? "Druckserver" : "Fotobox"
        }.`
      : res.mode === "printserver"
        ? `Läuft als Druckserver — kein Kiosk, kein Live-Bild. Umschalten über ${adminUrls()}`
        : "Läuft als Fotobox.";
  } catch (e) {
    $("sys-mode-status").textContent = "";
  }
}

function adminUrls() {
  const hosts = ["fotobox.local"];
  if (boxAddress) hosts.push(boxAddress);
  return hosts.map((h) => `http://${h}/admin`).join("  oder  ");
}

async function switchMode() {
  const mode = $("sys-mode").value;
  const label = mode === "printserver" ? "Druckserver" : "Fotobox";
  // Im Druckserver-Modus gibt es keinen Kiosk mehr — der Rückweg gehört genau
  // hierhin, nicht in eine Dokumentation, die man dann nicht mehr aufrufen kann.
  const warning =
    mode === "printserver"
      ? `\n\nDanach bleibt der Bildschirm dunkel. Zurückschalten von einem anderen ` +
        `Gerät im Netz:\n${adminUrls()}`
      : "";
  if (!window.confirm(`Als ${label} starten? Die Box startet dazu neu.${warning}`)) {
    await loadMode();
    return;
  }
  try {
    const res = await api("POST", "/api/admin/mode", { mode });
    if (!res.reboot_required) {
      // Zurück zur Fotobox geht live — der Kiosk merkt es an der Datei.
      note("sys-mode-status", `Betriebsart ${label} — der Kiosk startet gleich.`);
      return;
    }
    note("sys-mode-status", `Betriebsart ${label} — Box startet neu …`);
    await api("POST", "/api/admin/reboot");
  } catch (e) {
    note("sys-mode-status", "Fehler: " + e.message, false);
    await loadMode();
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
  $("net-ap-auto").addEventListener("change", toggleAPAuto);
  $("gal-purge").addEventListener("click", purgeDeleted);
  $("gal-rerender").addEventListener("click", startRerender);
  $("sys-mode").addEventListener("change", switchMode);
  $("export-usb").addEventListener("click", exportUSB);
  $("sys-reboot").addEventListener("click", reboot);
  $("sys-shutdown").addEventListener("click", shutdown);
});
