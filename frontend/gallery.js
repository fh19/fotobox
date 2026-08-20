"use strict";

/*
 * Fotobox gallery (post-event). Read-only: no delete, no edit (docs/ui-screens.md).
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

/* Tile shape follows the photos, not a hardcoded guess: portrait tiles cropped
 * every landscape photo down its middle. photo_aspect comes from the print
 * canvas, so it flips with printing.orientation. Landscape tiles also need to be
 * wider to stay legible at the same height. */
async function applyPhotoAspect() {
  try {
    const cfg = await getJson("/api/client-config");
    const aspect = Number(cfg.photo_aspect);
    if (!aspect || !isFinite(aspect) || aspect <= 0) return;
    const root = document.documentElement.style;
    root.setProperty("--photo-aspect", String(aspect));
    root.setProperty("--tile-min", aspect > 1 ? "230px" : "150px");
  } catch (e) {
    /* keep the stylesheet default */
  }
}

async function init() {
  wireEvents();
  await applyPhotoAspect();
  try {
    const data = await getJson("/api/events");
    const events = data.events || [];
    if (!events.length || events[0].photo_count === 0) {
      showEmpty(events[0]);
      return;
    }
    const event = events[0];
    state.eventId = event.id;
    dom.eventName.textContent = event.name;
    dom.eventCount.textContent = `${event.photo_count} Fotos`;
    state.total = event.photo_count;
    await loadNextPage();
    await refreshDownload();
  } catch (err) {
    showEmpty();
  }
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
  return state.variant === "processed" ? photo.thumb_url : photo.original_url;
}

function fullSrc(photo) {
  return state.variant === "processed" ? photo.processed_url : photo.original_url;
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

  tile.addEventListener("click", () => openLightbox(fullSrc(photo)));
  dom.grid.appendChild(tile);
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
  dom.grid.innerHTML = "";
  loadNextPage();
  refreshDownload();
}

function openLightbox(src) {
  dom.lightboxImg.src = src;
  dom.lightbox.classList.remove("hidden");
}

function closeLightbox() {
  dom.lightbox.classList.add("hidden");
  dom.lightboxImg.src = "";
}

function wireEvents() {
  dom.loadMore.addEventListener("click", loadNextPage);
  dom.lightboxClose.addEventListener("click", closeLightbox);
  dom.lightbox.addEventListener("click", (e) => {
    if (e.target === dom.lightbox) closeLightbox();
  });
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
