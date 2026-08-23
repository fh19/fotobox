"use strict";

/*
 * Fotobox guest UI.
 *
 * The frontend holds no application state and makes no decisions (CLAUDE.md
 * rule 5). It renders whatever the backend reports: on load it fetches
 * GET /api/status once, then follows the WebSocket. A reload in any state
 * therefore restores exactly that state (e.g. PREVIEW stays PREVIEW).
 */

const RING_COUNTDOWN_CIRC = 2 * Math.PI * 140; // matches r=140 in the SVG
const RECONNECT_BACKOFF = [1000, 2000, 4000, 8000, 10000];

const el = (id) => document.getElementById(id);

const body = document.body;
const dom = {
  resultPhoto: el("result-photo"),
  idleReady: el("idle-ready"),
  idlePause: el("idle-pause"),
  idleHeading: el("idle-heading"),
  idlePrintNote: el("idle-print-note"),
  idlePrintReason: el("idle-print-reason"),
  idleGallery: el("idle-gallery"),
  previewPrintReason: el("preview-print-reason"),
  bgTiles: el("bg-tiles"),
  countdownNumber: el("countdown-number"),
  countdownRing: el("countdown-ring"),
  processingWarn: el("processing-warn"),
  previewActions: el("preview-actions"),
  btnPrint: el("btn-print"),
  btnFinish: el("btn-finish"),
  previewRing: el("preview-ring"),
  screenPreview: el("screen-preview"),
  errorMessage: el("error-message"),
  flash: el("flash"),
  reconnect: el("reconnect-overlay"),
};

// The only cached values are presentational config and the last status the
// server sent — a mirror of server state, not independent state.
let uiConfig = {
  mirror_preview: true,
  idle_hint_pulse: true,
  flash_enabled: true,
  gallery_enabled: true,
  processing_warn_seconds: 8,
  preview_seconds: 30,
  preview_fps: 15,
  admin_corner: "top_left",
  admin_longpress_seconds: 5,
};
let lastStatus = null;
let previousState = null;
let countdownMax = null;
let processingWarnTimer = null;
let printingLabelTimer = null;
let socket = null;
let reconnectAttempt = 0;

// --- input hardening (kiosk) ------------------------------------------------

function hardenInput() {
  document.addEventListener("contextmenu", (e) => e.preventDefault());
  document.addEventListener("selectstart", (e) => e.preventDefault());
  document.addEventListener("dragstart", (e) => e.preventDefault());
  document.addEventListener("dblclick", (e) => e.preventDefault());
  // Safari pinch gestures.
  document.addEventListener("gesturestart", (e) => e.preventDefault());
  // Multi-touch pinch on touchscreens.
  document.addEventListener(
    "touchmove",
    (e) => {
      if (e.touches.length > 1) e.preventDefault();
    },
    { passive: false }
  );
}

// --- server actions (POST only; the WebSocket delivers the result) ----------

async function postAction(path) {
  try {
    return await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" } });
  } catch (err) {
    return null;
  }
}

async function postBackground(backgroundId) {
  try {
    return await fetch("/api/session/background", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ background_id: backgroundId }),
    });
  } catch (err) {
    return null;
  }
}

// --- rendering --------------------------------------------------------------

function render(status) {
  if (!status) return;
  lastStatus = status;
  const state = status.state;
  const entering = state !== previousState;

  body.dataset.state = state;

  // Fill-light flash: hold the screen white through CAPTURE. The engine turns
  // CAPTURE on before the shutter fires, so the subject is lit during exposure.
  dom.flash.classList.toggle("on", uiConfig.flash_enabled && state === "CAPTURE");

  if (state === "IDLE") renderIdle(status);
  else if (state === "BACKGROUND_SELECT") {
    if (entering) loadBackgrounds();
  } else if (state === "COUNTDOWN") {
    if (entering) enterCountdown(status);
  } else if (state === "CAPTURE" || state === "PROCESSING") {
    if (entering && previousState !== "CAPTURE" && previousState !== "PROCESSING") {
      enterProcessing();
    }
  } else if (state === "PREVIEW" || state === "PRINTING") {
    renderPreview(status, entering);
  } else if (state === "SCREENSAVER") {
    if (entering) startScreensaver(status.screensaver);
  } else if (state === "ERROR") {
    dom.errorMessage.textContent = (status.error && status.error.message) || "";
  }

  if (state !== "SCREENSAVER") stopScreensaver();

  if (state !== "PREVIEW" && state !== "PRINTING") clearPrintingLabel();
  if (state !== "CAPTURE" && state !== "PROCESSING") clearProcessingWarn();

  previousState = state;
}

function renderIdle(status) {
  const cameraReady = status.camera && status.camera.available;
  dom.idleReady.classList.toggle("hidden", !cameraReady);
  dom.idlePause.classList.toggle("hidden", cameraReady);
  dom.idleHeading.classList.toggle("pulse", uiConfig.idle_hint_pulse);

  const printerReady = status.printer && status.printer.available;
  dom.idlePrintNote.classList.toggle("hidden", printerReady);
  // Say *what* is wrong, in large type. On the first event paper and ribbon ran
  // out unnoticed — the only symptom was that prints stopped coming.
  // Looking at the photos was only possible over the guest WiFi; at the box
  // itself there was no way in (Optimierungen.md).
  dom.idleGallery.classList.toggle("hidden", !uiConfig.gallery_enabled);
  const problem = (status.printer && status.printer.message) || "";
  dom.idlePrintReason.textContent = problem;
  dom.idlePrintReason.classList.toggle("hidden", printerReady || !problem);
}

async function loadBackgrounds() {
  let items = [{ id: "none", name: "Ohne Hintergrund", thumbnail_url: null }];
  try {
    const res = await fetch("/api/backgrounds");
    if (res.ok) {
      const data = await res.json();
      if (data.backgrounds && data.backgrounds.length) items = data.backgrounds;
    }
  } catch (err) {
    /* keep the fallback "Ohne Hintergrund" tile */
  }
  dom.bgTiles.innerHTML = "";
  for (const bg of items) {
    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = "tile";
    if (bg.thumbnail_url && bg.id !== "none") {
      tile.style.backgroundImage = `url("${bg.thumbnail_url}")`;
    }
    const label = document.createElement("span");
    label.className = "tile__label";
    label.textContent = bg.name;
    tile.appendChild(label);
    // Antippen wählt aus und startet sofort den Countdown.
    tile.addEventListener("click", () => postBackground(bg.id));
    dom.bgTiles.appendChild(tile);
  }
}

function enterCountdown(status) {
  const remaining =
    status.session && status.session.countdown_remaining != null
      ? status.session.countdown_remaining
      : null;
  countdownMax = remaining;
  if (remaining != null) setCountdown(remaining);
  dom.countdownRing.style.strokeDashoffset = "0";
}

function setCountdown(remaining) {
  if (countdownMax == null || remaining > countdownMax) countdownMax = remaining;
  const num = dom.countdownNumber;
  if (remaining <= 1) {
    num.textContent = "Lächeln!";
    num.classList.add("smile");
  } else {
    num.textContent = String(remaining);
    num.classList.remove("smile");
  }
  // Kurzes Skalieren bei jedem Wechsel.
  num.classList.remove("tick");
  void num.offsetWidth;
  num.classList.add("tick");

  if (countdownMax) {
    const fraction = Math.max(0, Math.min(1, remaining / countdownMax));
    dom.countdownRing.style.strokeDashoffset = String(RING_COUNTDOWN_CIRC * (1 - fraction));
  }
}

function enterProcessing() {
  clearProcessingWarn();
  dom.processingWarn.classList.add("hidden");
  processingWarnTimer = window.setTimeout(() => {
    dom.processingWarn.classList.remove("hidden");
  }, uiConfig.processing_warn_seconds * 1000);
}

function clearProcessingWarn() {
  if (processingWarnTimer) {
    window.clearTimeout(processingWarnTimer);
    processingWarnTimer = null;
  }
}

function renderPreview(status, entering) {
  const session = status.session || {};
  if (session.processed_url) dom.resultPhoto.src = session.processed_url;

  const printAllowed = !!session.print_allowed;
  dom.previewActions.classList.toggle("no-print", !printAllowed);
  // A button that simply vanished looked like a fault; the reason comes along.
  const hint = printAllowed ? "" : session.print_hint || "";
  dom.previewPrintReason.textContent = hint;
  dom.previewPrintReason.classList.toggle("hidden", !hint);

  if (printingLabelTimer) {
    dom.btnPrint.textContent = "Wird gedruckt …";
    dom.btnPrint.disabled = true;
  } else {
    dom.btnPrint.textContent = "Drucken";
    dom.btnPrint.disabled = false;
  }

  if (entering && status.state === "PREVIEW") startPreviewRing();
}

function startPreviewRing() {
  const ring = dom.previewRing;
  dom.screenPreview.classList.remove("counting");
  ring.style.animationDuration = `${uiConfig.preview_seconds}s`;
  void ring.offsetWidth;
  dom.screenPreview.classList.add("counting");
}

function showPrintingLabel() {
  clearPrintingLabelTimer();
  dom.btnPrint.textContent = "Wird gedruckt …";
  dom.btnPrint.disabled = true;
  printingLabelTimer = window.setTimeout(() => {
    printingLabelTimer = null;
    render(lastStatus);
  }, 3000);
}

function clearPrintingLabelTimer() {
  if (printingLabelTimer) {
    window.clearTimeout(printingLabelTimer);
    printingLabelTimer = null;
  }
}

function clearPrintingLabel() {
  clearPrintingLabelTimer();
}

// --- WebSocket messages -----------------------------------------------------

function handleMessage(msg) {
  switch (msg.type) {
    case "state_changed":
      render(msg.payload);
      break;
    case "countdown_tick":
      setCountdown(msg.payload.remaining);
      break;
    case "photo_ready":
      if (msg.payload.processed_url) dom.resultPhoto.src = msg.payload.processed_url;
      break;
    case "printer_status":
      if (lastStatus) {
        lastStatus.printer = msg.payload;
        if (body.dataset.state === "IDLE") renderIdle(lastStatus);
      }
      break;
    case "print_started":
      showPrintingLabel();
      break;
    case "error":
      dom.errorMessage.textContent = msg.payload.message || "";
      break;
    default:
      break; // system_status, print_finished: nothing to do for the guest UI
  }
}

// --- WebSocket lifecycle & reconnect ----------------------------------------

function connect() {
  const url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
  socket = new WebSocket(url);

  socket.addEventListener("open", () => {
    reconnectAttempt = 0;
    dom.reconnect.classList.add("hidden");
    // After (re)connecting, resync once with the authoritative status.
    fetchStatus();
  });

  socket.addEventListener("message", (event) => {
    try {
      handleMessage(JSON.parse(event.data));
    } catch (err) {
      /* ignore malformed frames */
    }
  });

  socket.addEventListener("close", scheduleReconnect);
  socket.addEventListener("error", () => socket && socket.close());
}

function scheduleReconnect() {
  // Live-Bild bleibt sichtbar, nur ein dezentes Overlay.
  dom.reconnect.classList.remove("hidden");
  const delay = RECONNECT_BACKOFF[Math.min(reconnectAttempt, RECONNECT_BACKOFF.length - 1)];
  reconnectAttempt += 1;
  window.setTimeout(connect, delay);
}

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (res.ok) render(await res.json());
  } catch (err) {
    /* the WebSocket will catch up */
  }
}

async function loadUiConfig() {
  try {
    const res = await fetch("/api/client-config");
    if (res.ok) uiConfig = Object.assign(uiConfig, await res.json());
  } catch (err) {
    /* defaults are fine */
  }
}

// --- screensaver ------------------------------------------------------------
//
// "wenn die Box für zB 5min nicht benutzt wurde, sollen die bisherigen Bilder in
// zufälliger Reihenfolge auf dem Schirm angezeigt werden". The order and the
// list come from the backend (rule 5); this only cross-fades through them.

let saverTimer = null;
let saverIndex = 0;
let saverFront = null;

function startScreensaver(settings) {
  stopScreensaver();
  const photos = (settings && settings.photos) || [];
  if (!photos.length) return; // nothing shot yet — a black screen is fine
  document.documentElement.style.setProperty("--saver-fade", `${settings.fade_ms}ms`);
  saverIndex = 0;
  saverFront = el("saver-b");
  showSaverPhoto(photos);
  saverTimer = window.setInterval(() => showSaverPhoto(photos), settings.interval_ms);
}

function showSaverPhoto(photos) {
  const back = saverFront === el("saver-a") ? el("saver-b") : el("saver-a");
  const url = photos[saverIndex % photos.length];
  saverIndex += 1;
  // Decode before swapping, otherwise the fade starts on an empty element and
  // the picture pops in halfway through.
  const image = new Image();
  image.onload = () => {
    back.src = url;
    back.classList.add("is-visible");
    if (saverFront) saverFront.classList.remove("is-visible");
    saverFront = back;
  };
  image.src = url;
}

function stopScreensaver() {
  if (saverTimer !== null) {
    window.clearInterval(saverTimer);
    saverTimer = null;
  }
  ["saver-a", "saver-b"].forEach((id) => {
    const image = el(id);
    image.classList.remove("is-visible");
    image.removeAttribute("src");
  });
  saverFront = null;
}

// --- wiring -----------------------------------------------------------------

function wireButtons() {
  // Der gesamte IDLE-Bildschirm ist die Schaltfläche — außer dort, wo ein echtes
  // Bedienelement liegt. Der Galerie-Button löste sonst zugleich ein Foto aus,
  // das dann unbemerkt im Hintergrund weiterlief.
  el("screen-idle").addEventListener("click", (event) => {
    if (event.target.closest("a, button")) return;
    if (lastStatus && lastStatus.camera && lastStatus.camera.available) {
      postAction("/api/session/start");
    }
  });
  // Der erste Tipp holt nur den Startbildschirm zurück — er löst bewusst noch
  // kein Foto aus, sonst fotografiert die Box jeden, der bloß aufwecken wollte.
  el("screen-screensaver").addEventListener("click", () => postAction("/api/session/wake"));
  el("btn-cancel-bg").addEventListener("click", () => postAction("/api/session/cancel"));
  el("btn-cancel-countdown").addEventListener("click", () => postAction("/api/session/cancel"));
  dom.btnFinish.addEventListener("click", () => postAction("/api/session/finish"));
  dom.btnPrint.addEventListener("click", async (e) => {
    e.stopPropagation();
    const res = await postAction("/api/session/print");
    if (res && res.ok) showPrintingLabel();
  });
}

function startPreview() {
  // Self-healing live preview: poll independent single frames instead of holding
  // one long-lived MJPEG connection. Chromium can silently freeze or blank a
  // multipart <img> stream — the connection stalls without firing "error", so the
  // old reconnect-on-error never triggered and the picture went black while the
  // text (WebSocket) and capture kept working. One request per frame recovers on
  // its own every tick, so a stall can never leave the preview stuck.
  //
  // Each frame is fetched as a blob and shown via an in-memory object URL. The
  // <img> is NEVER pointed at a network URL (the frame is served no-store, so a
  // direct img.src would force a re-download and blank the picture for a moment) —
  // the browser keeps showing the previous frame until the new blob is decoded and
  // then swaps with no gap.
  const img = el("preview");
  const interval = Math.max(40, Math.round(1000 / (uiConfig.preview_fps || 15)));
  let currentUrl = null;

  const tick = async () => {
    let delay = interval;
    // No live picture behind the slideshow: nobody sees it, and the JPEG encoding
    // is the box's biggest constant CPU load.
    if (body.dataset.state === "SCREENSAVER") {
      window.setTimeout(tick, 1000);
      return;
    }
    try {
      const res = await fetch(`/preview/frame?ts=${Date.now()}`, { cache: "no-store" });
      if (res.ok) {
        const url = URL.createObjectURL(await res.blob());
        img.src = url;
        if (currentUrl) URL.revokeObjectURL(currentUrl); // free the previous frame
        currentUrl = url;
      } else {
        delay = 1000; // backend up but no frame yet → back off a little
      }
    } catch (err) {
      delay = 1000; // backend momentarily unreachable → retry, keep last frame visible
    }
    window.setTimeout(tick, delay);
  };
  tick();
}

function setupAdminCorner() {
  const corner = el("admin-corner");
  corner.classList.add(uiConfig.admin_corner === "top_right" ? "right" : "left");
  let timer = null;
  const start = (e) => {
    e.preventDefault();
    timer = window.setTimeout(() => {
      window.location.href = "/admin";
    }, (uiConfig.admin_longpress_seconds || 5) * 1000);
  };
  const cancel = () => {
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
  };
  corner.addEventListener("pointerdown", start);
  corner.addEventListener("pointerup", cancel);
  corner.addEventListener("pointerleave", cancel);
  corner.addEventListener("pointercancel", cancel);
}

async function init() {
  hardenInput();
  wireButtons();
  await loadUiConfig();
  if (!uiConfig.mirror_preview) body.classList.add("no-mirror");
  startPreview();
  setupAdminCorner();
  connect();
}

window.addEventListener("DOMContentLoaded", init);
