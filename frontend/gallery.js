"use strict";

/*
 * Fotobox gallery (post-event). Read-only for guests: no delete, no edit
 * (docs/ui-screens.md). Opened from the admin with ?admin=1 it gains an event
 * picker across all events and a delete for the selection — "Anschauen und
 * Löschen aller Veranstaltungsbilder aus dem Konfig-Menü heraus".
 * Loads the most recent event, paginates its photos, toggles between the
 * processed ("Mit Hintergrund") and original variants, and offers a streamed ZIP.
 */

const PER_PAGE = 60;
const el = (id) => document.getElementById(id);

const state = {
  eventId: null,
  variant: "processed", // processed | original
  page: 0,
  total: 0,
  loaded: 0,
  // Every photo loaded so far, in grid order, plus which one the lightbox shows.
  // Without this the single view was a dead end: open, look, close, open the
  // next — the most tiresome part of the evening according to the notes.
  photos: [],
  index: -1,
  // Selecting: after the first event the only choices were "all 252 photos" or
  // "one at a time". Tapping a tile selects instead of opening while this is on.
  selecting: false,
  selected: new Set(),
  kiosk: new URLSearchParams(location.search).has("kiosk"),
  admin: new URLSearchParams(location.search).has("admin"),
  events: [],
};

const dom = {
  eventName: el("event-name"),
  eventCount: el("event-count"),
  grid: el("grid"),
  empty: el("empty"),
  loadMore: el("load-more"),
  download: el("download-all"),
  toggle: el("variant-toggle"),
  lightbox: el("lightbox"),
  lightboxImg: el("lightbox-img"),
  lightboxClose: el("lightbox-close"),
  lightboxPrev: el("lightbox-prev"),
  lightboxNext: el("lightbox-next"),
  lightboxPrint: el("lightbox-print"),
  lightboxCount: el("lightbox-count"),
  lightboxNote: el("lightbox-note"),
  backToBox: el("back-to-box"),
  selectMode: el("select-mode"),
  selectionBar: el("selection-bar"),
  selectionCount: el("selection-count"),
  selectionClear: el("selection-clear"),
  selectionDelete: el("selection-delete"),
  eventPick: el("event-pick"),
  downloadSelection: el("download-selection"),
};

function humanSize(bytes) {
  if (!bytes) return "0 MB";
  const mb = bytes / (1024 * 1024);
  if (mb >= 1000) return `${(mb / 1024).toFixed(1)} GB`;
  if (mb >= 10) return `${Math.round(mb)} MB`;
  return `${mb.toFixed(1)} MB`;
}

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function applyClientConfig() {
  let cfg = {};
  try {
    cfg = await getJson("/api/client-config");
  } catch (e) {
    /* keep the stylesheet defaults and, at the box, the plain back button */
  }
  // Tile shape follows the photos instead of a hardcoded guess: portrait tiles
  // cropped every landscape photo down its middle. photo_aspect comes from the
  // print canvas, so it flips with printing.orientation. Landscape tiles need
  // more width to stay legible at the same height.
  const aspect = Number(cfg.photo_aspect);
  if (aspect && isFinite(aspect) && aspect > 0) {
    const root = document.documentElement.style;
    root.setProperty("--photo-aspect", String(aspect));
    root.setProperty("--tile-min", aspect > 1 ? "230px" : "150px");
  }
  if (state.kiosk) wireKioskReturn(Number(cfg.gallery_return_seconds) || 0);
}

/* At the box the browser has no address bar and nobody is watching: an open
 * gallery would keep the Fotobox out of its photo flow indefinitely. A back
 * button plus an idle timeout return to the kiosk. */
function wireKioskReturn(seconds) {
  dom.backToBox.classList.remove("hidden");
  if (!seconds) return;
  let timer = null;
  const back = () => location.assign("/");
  const restart = () => {
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(back, seconds * 1000);
  };
  ["click", "touchstart", "keydown", "scroll"].forEach((event) =>
    document.addEventListener(event, restart, { passive: true })
  );
  restart();
}

async function init() {
  wireEvents();
  await applyClientConfig();
  try {
    const data = await getJson("/api/events");
    state.events = data.events || [];
    if (state.admin) setUpAdmin();
    const events = state.events;
    if (!events.length || events[0].photo_count === 0) {
      showEmpty(events[0]);
      return;
    }
    await showEvent(events[0]);
  } catch (err) {
    showEmpty();
  }
}

async function showEvent(event) {
  state.eventId = event.id;
  state.total = event.photo_count;
  state.page = 0;
  state.loaded = 0;
  state.photos = [];
  state.selected.clear();
  dom.grid.innerHTML = "";
  dom.empty.classList.toggle("hidden", event.photo_count > 0);
  dom.eventName.textContent = event.name;
  dom.eventCount.textContent = `${event.photo_count} Fotos`;
  if (dom.eventPick) dom.eventPick.value = String(event.id);
  if (event.photo_count > 0) await loadNextPage();
  await refreshDownload();
  await refreshSelection();
}

/* Admin mode: the "Hauptgalerie" — every event in one picker, plus delete. */
function setUpAdmin() {
  dom.eventPick.classList.remove("hidden");
  fillEventPicker();
  dom.eventPick.addEventListener("change", () => {
    const event = state.events.find((e) => String(e.id) === dom.eventPick.value);
    if (event) showEvent(event);
  });
  dom.selectionDelete.classList.remove("hidden");
  dom.selectionDelete.addEventListener("click", deleteSelection);
  dom.backToBox.textContent = "Zurück zum Admin";
  dom.backToBox.href = "/admin";
  dom.backToBox.classList.remove("hidden");
}

async function deleteSelection() {
  const ids = [...state.selected];
  if (!ids.length) return;
  const what = ids.length === 1 ? "1 Foto" : `${ids.length} Fotos`;
  if (!window.confirm(`${what} löschen? Sie verschwinden aus der Galerie.`)) return;
  const pin = sessionStorage.getItem("fotobox_pin") || "";
  try {
    const res = await fetch("/api/admin/photos/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Fotobox-Pin": pin },
      body: JSON.stringify({ ids }),
    });
    if (!res.ok) throw new Error(res.status === 401 ? "PIN abgelaufen" : `HTTP ${res.status}`);
    // Reload the event: counts, pages and the grid all shift.
    const data = await getJson("/api/events");
    state.events = data.events || [];
    const event = state.events.find((e) => e.id === state.eventId);
    fillEventPicker();
    if (event) await showEvent(event);
  } catch (err) {
    window.alert("Löschen fehlgeschlagen: " + err.message);
  }
}

function fillEventPicker() {
  const current = dom.eventPick.value;
  dom.eventPick.innerHTML = "";
  for (const event of state.events) {
    const option = document.createElement("option");
    option.value = String(event.id);
    option.textContent = `${event.name} (${event.photo_count})`;
    dom.eventPick.appendChild(option);
  }
  if (current) dom.eventPick.value = current;
}

function showEmpty(event) {
  if (event) {
    dom.eventName.textContent = event.name;
  }
  dom.empty.classList.remove("hidden");
  dom.download.classList.add("is-disabled");
}

async function loadNextPage() {
  state.page += 1;
  const data = await getJson(
    `/api/events/${state.eventId}/photos?page=${state.page}&per_page=${PER_PAGE}`
  );
  state.total = data.total;
  for (const photo of data.photos) appendTile(photo);
  state.loaded += data.photos.length;
  dom.loadMore.classList.toggle("hidden", state.loaded >= state.total);
}

function tileSrc(photo) {
  // Always the thumbnail: a grid of 60 full-size originals (8 MB each off the
  // DSLR) brought the box's browser to its knees.
  return photo.thumb_url || photo.original_url;
}

function fullSrc(photo) {
  // Screen-sized, not the download master: processed/ is composed above print
  // resolution and its decode made stepping through the photos — and the back
  // button — feel stuck. prints/ is the same image at the print raster.
  if (state.variant !== "processed") return photo.original_url;
  return photo.print_url || photo.processed_url;
}

function appendTile(photo) {
  const tile = document.createElement("button");
  tile.type = "button";
  tile.className = "tile";

  const img = document.createElement("img");
  img.loading = "lazy";
  img.src = tileSrc(photo);
  // If a processed thumb is missing (pipeline failed/pending), fall back.
  img.addEventListener("error", () => {
    if (img.src.indexOf(photo.original_url) === -1) img.src = photo.original_url;
  });
  tile.appendChild(img);

  if (photo.pipeline_status !== "ok") {
    const badge = document.createElement("span");
    badge.className = "tile__badge";
    badge.textContent = photo.pipeline_status === "pending" ? "in Arbeit" : "nur Original";
    tile.appendChild(badge);
  }

  const index = state.photos.length;
  state.photos.push(photo);
  tile.dataset.photoId = String(photo.id);
  tile.addEventListener("click", () => {
    if (state.selecting) toggleSelected(photo.id, tile);
    else openLightbox(index);
  });
  if (state.selected.has(photo.id)) tile.classList.add("is-selected");
  dom.grid.appendChild(tile);
}

function toggleSelected(photoId, tile) {
  if (state.selected.has(photoId)) state.selected.delete(photoId);
  else state.selected.add(photoId);
  tile.classList.toggle("is-selected", state.selected.has(photoId));
  refreshSelection();
}

function setSelecting(on) {
  state.selecting = on;
  dom.selectMode.classList.toggle("is-active", on);
  dom.selectMode.textContent = on ? "Auswahl beenden" : "Auswählen";
  if (!on) clearSelection();
  refreshSelection();
}

function clearSelection() {
  state.selected.clear();
  dom.grid.querySelectorAll(".tile.is-selected").forEach((t) => t.classList.remove("is-selected"));
  refreshSelection();
}

async function refreshSelection() {
  const count = state.selected.size;
  dom.selectionBar.classList.toggle("hidden", !state.selecting);
  dom.selectionCount.textContent = count === 1 ? "1 Foto ausgewählt" : `${count} Fotos ausgewählt`;
  dom.downloadSelection.classList.toggle("is-disabled", count === 0);
  if (!count) return;
  const ids = [...state.selected].join(",");
  dom.downloadSelection.href =
    `/api/events/${state.eventId}/download.zip?variant=${state.variant}&ids=${ids}`;
  try {
    const info = await getJson(
      `/api/events/${state.eventId}/download-info?variant=${state.variant}&ids=${ids}`
    );
    dom.downloadSelection.textContent = `Auswahl herunterladen (ZIP, ${humanSize(info.size_bytes)})`;
  } catch (err) {
    dom.downloadSelection.textContent = "Auswahl herunterladen (ZIP)";
  }
}

async function refreshDownload() {
  try {
    const info = await getJson(
      `/api/events/${state.eventId}/download-info?variant=${state.variant}`
    );
    dom.download.textContent = `Alle Fotos herunterladen (ZIP, ${humanSize(info.size_bytes)})`;
    dom.download.href = `/api/events/${state.eventId}/download.zip?variant=${state.variant}`;
    dom.download.classList.toggle("is-disabled", info.file_count === 0);
  } catch (err) {
    dom.download.classList.add("is-disabled");
  }
}

function reload() {
  state.page = 0;
  state.loaded = 0;
  state.photos = [];
  dom.grid.innerHTML = "";
  loadNextPage();
  refreshDownload();
}

function openLightbox(index) {
  // A photo whose pipeline failed has no print/processed file — fall back once.
  dom.lightboxImg.onerror = () => {
    const photo = state.photos[state.index];
    if (photo && dom.lightboxImg.src.indexOf(photo.original_url) === -1) {
      dom.lightboxImg.src = photo.original_url;
    }
  };
  showPhoto(index);
  dom.lightbox.classList.remove("hidden");
}

function showPhoto(index) {
  if (index < 0 || index >= state.photos.length) return;
  state.index = index;
  const photo = state.photos[index];
  dom.lightboxImg.src = fullSrc(photo);
  dom.lightboxImg.decoding = "async";
  dom.lightboxCount.textContent = `${index + 1} von ${state.total || state.photos.length}`;
  dom.lightboxPrev.disabled = index === 0;
  // Only what is loaded can be shown; "Mehr laden" extends the range.
  dom.lightboxNext.disabled = index >= state.photos.length - 1;
  dom.lightboxNote.textContent = "";
  setPrintBusy(false);
}

function setPrintBusy(busy, note = "") {
  // The button carries an icon — never overwrite its content with text.
  dom.lightboxPrint.disabled = busy;
  dom.lightboxPrint.classList.toggle("is-busy", busy);
  dom.lightboxNote.textContent = note;
}

function step(delta) {
  showPhoto(state.index + delta);
}

function closeLightbox() {
  dom.lightbox.classList.add("hidden");
  dom.lightboxImg.src = "";
  state.index = -1;
}

async function printCurrent() {
  const photo = state.photos[state.index];
  if (!photo) return;
  setPrintBusy(true, "Wird gedruckt …");
  try {
    // Print what is on screen: framed or original, whichever the toggle shows.
    const res = await fetch(`/api/photos/${photo.id}/print?variant=${state.variant}`, {
      method: "POST",
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error((data && data.error && data.error.message) || `HTTP ${res.status}`);
    setPrintBusy(true, "Der Druck läuft.");
  } catch (err) {
    setPrintBusy(false, err.message);
  }
}

/* Swipe on the photo itself: on a phone reaching for a small arrow is fiddly. */
function wireSwipe() {
  let startX = null;
  dom.lightboxImg.addEventListener("touchstart", (e) => {
    startX = e.touches[0].clientX;
  }, { passive: true });
  dom.lightboxImg.addEventListener("touchend", (e) => {
    if (startX === null) return;
    const dx = e.changedTouches[0].clientX - startX;
    startX = null;
    if (Math.abs(dx) > 40) step(dx < 0 ? 1 : -1);
  }, { passive: true });
}

function wireEvents() {
  dom.loadMore.addEventListener("click", loadNextPage);
  dom.lightboxClose.addEventListener("click", closeLightbox);
  dom.lightboxPrev.addEventListener("click", () => step(-1));
  dom.lightboxNext.addEventListener("click", () => step(1));
  dom.lightboxPrint.addEventListener("click", printCurrent);
  wireSwipe();
  document.addEventListener("keydown", (e) => {
    if (dom.lightbox.classList.contains("hidden")) return;
    if (e.key === "ArrowRight") step(1);
    else if (e.key === "ArrowLeft") step(-1);
    else if (e.key === "Escape") closeLightbox();
  });
  dom.lightbox.addEventListener("click", (e) => {
    if (e.target === dom.lightbox) closeLightbox();
  });
  dom.selectMode.addEventListener("click", () => setSelecting(!state.selecting));
  dom.selectionClear.addEventListener("click", clearSelection);
  dom.toggle.querySelectorAll(".toggle__btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.variant === state.variant) return;
      state.variant = btn.dataset.variant;
      dom.toggle
        .querySelectorAll(".toggle__btn")
        .forEach((b) => b.classList.toggle("is-active", b === btn));
      if (state.eventId) reload();
    });
  });
}

window.addEventListener("DOMContentLoaded", init);
