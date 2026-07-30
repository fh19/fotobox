#!/usr/bin/env bash
#
# One-shot Fotobox installer. Orchestrates the individual, idempotent scripts so a
# fresh machine is set up in a single command. Safe to re-run.
#
# Base target: a Raspberry Pi (4 or 5) with Raspberry Pi OS Trixie (64-bit, Desktop).
# Also runs on any other Debian/Ubuntu Linux (dev/backup box) — there it installs the
# backend HEADLESS (no kiosk, no Pi-only OS tweaks) and keeps hardware on mock.
#
# What it does NOT do (on purpose — destructive / environment-specific, must be last):
#   * repartitioning for a separate /data
#   * enabling read-only root (overlayroot)
# See docs/installation.md, section 8, for those.
#
# Usage:
#   bash deploy/install.sh [options]
#
# Options:
#   --with-printer        Set up the Selphy CP1500 (Gutenprint/USB). Printer must be
#                         attached + on. Adds ~20-30 min (compiles Gutenprint).
#   --with-rtc            Hardware clock. Pi 4: install the DS1307 I2C overlay.
#                         Pi 5: use the built-in RTC (nothing to install).
#   --set-time "Y-M-D H:M:S"   Set system + RTC time now (local time). Offline-friendly.
#   --with-ai             Install the AI backend (rembg/onnxruntime) in addition to core.
#                         You still must place the model at pipeline.ai.model_path.
#   --mock                Keep preview + printer on mock (don't switch to real hardware).
#   --headless            Force headless (no kiosk/desktop tweaks). Auto on non-Pi.
#   --app-dir DIR         Install location (default: this checkout).
#   --data-dir DIR        Data dir (default: /data).
#   --yes                 Non-interactive (assume yes for prompts).
#   -h, --help            This help.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="/data"
WITH_PRINTER=0
WITH_RTC=0
WITH_AI=0
FORCE_MOCK=0
FORCE_HEADLESS=0
SET_TIME=""
ASSUME_YES=0

while [ $# -gt 0 ]; do
  case "$1" in
    --with-printer) WITH_PRINTER=1 ;;
    --with-rtc) WITH_RTC=1 ;;
    --with-ai) WITH_AI=1 ;;
    --mock) FORCE_MOCK=1 ;;
    --headless) FORCE_HEADLESS=1 ;;
    --set-time) SET_TIME="${2:?--set-time braucht \"JJJJ-MM-TT HH:MM:SS\"}"; shift ;;
    --app-dir) APP_DIR="${2:?}"; shift ;;
    --data-dir) DATA_DIR="${2:?}"; shift ;;
    --yes|-y) ASSUME_YES=1 ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
  esac
  shift
done

PY="$APP_DIR/.venv/bin/python"
log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!  %s\033[0m\n' "$*"; }

# --- platform detection -----------------------------------------------------
PI_MODEL="$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || true)"
IS_PI=0; PI5=0
case "$PI_MODEL" in
  *"Raspberry Pi 5"*) IS_PI=1; PI5=1 ;;
  *Raspberry*) IS_PI=1 ;;
esac
HEADLESS=0
{ [ "$IS_PI" != "1" ] || [ "$FORCE_HEADLESS" = "1" ]; } && HEADLESS=1

if ! command -v apt-get >/dev/null; then
  echo "Dieser Installer setzt ein Debian/Ubuntu-System (apt) voraus." >&2
  exit 1
fi

# Real hardware by default on a Pi; mock on a headless/dev box or with --mock.
ENABLE_REAL=0
{ [ "$HEADLESS" != "1" ] && [ "$FORCE_MOCK" != "1" ]; } && ENABLE_REAL=1

confirm() {
  [ "$ASSUME_YES" = "1" ] && return 0
  read -r -p "$1 [j/N] " a; [ "$a" = "j" ] || [ "$a" = "J" ] || [ "$a" = "y" ]
}

# --- plan -------------------------------------------------------------------
cat <<PLAN

Fotobox-Installer
  Verzeichnis : $APP_DIR
  Daten       : $DATA_DIR
  Plattform   : ${PI_MODEL:-Nicht-Pi (generisches Linux)}$( [ "$HEADLESS" = "1" ] && echo "  [headless]" )
  Schritte    : Basis$( [ "$ENABLE_REAL" = 1 ] && echo ", Echt-Hardware" )$( [ "$WITH_PRINTER" = 1 ] && echo ", Drucker" )$( [ "$WITH_RTC" = 1 ] && echo ", RTC" )$( [ "$WITH_AI" = 1 ] && echo ", KI" )$( [ -n "$SET_TIME" ] && echo ", Zeit setzen" )
PLAN
confirm "Fortfahren?" || { echo "Abgebrochen."; exit 0; }

# --- 1) base ----------------------------------------------------------------
log "Basis-Provisionierung (deploy/setup.sh)"
HEADLESS="$HEADLESS" APP_DIR="$APP_DIR" DATA_DIR="$DATA_DIR" bash "$APP_DIR/deploy/setup.sh"

# --- 2) printer -------------------------------------------------------------
if [ "$WITH_PRINTER" = "1" ]; then
  log "Drucker (Gutenprint/CP1500) — Drucker muss angeschlossen + an sein"
  bash "$APP_DIR/deploy/cups/setup-printer.sh"
fi

# --- 3) RTC -----------------------------------------------------------------
if [ "$WITH_RTC" = "1" ]; then
  if [ "$PI5" = "1" ]; then
    log "RTC: Pi 5 hat eine eingebaute Uhr — kein Overlay nötig"
    [ -e /dev/rtc0 ] && echo "/dev/rtc0 vorhanden." || warn "Kein /dev/rtc0 — Knopfzelle am RTC-Header prüfen."
  elif [ "$IS_PI" = "1" ]; then
    log "RTC: DS1307-Overlay (deploy/rtc/setup-rtc.sh)"
    sudo bash "$APP_DIR/deploy/rtc/setup-rtc.sh"
  else
    warn "RTC nur auf dem Raspberry Pi sinnvoll — übersprungen."
  fi
fi

if [ -n "$SET_TIME" ]; then
  log "Zeit setzen (System + RTC): $SET_TIME"
  sudo timedatectl set-ntp false
  sudo timedatectl set-time "$SET_TIME"
  sudo timedatectl set-ntp true
  timedatectl | grep -E "Local time|RTC time" || true
fi

# --- 4) AI ------------------------------------------------------------------
if [ "$WITH_AI" = "1" ]; then
  log "KI-Backend (rembg/onnxruntime)"
  "$PY" -m pip install --quiet -r "$APP_DIR/requirements.txt"
  warn "Modell noch lokal ablegen: pipeline.ai.model_path (Standard: $DATA_DIR/assets/models/u2netp.onnx)"
fi

# --- 5) enable real hardware in config --------------------------------------
if [ "$ENABLE_REAL" = "1" ]; then
  log "Echt-Hardware in config.yaml aktivieren (Vorschau=auto$( [ "$WITH_PRINTER" = 1 ] && echo ", Drucker=cups" ))"
  WITH_PRINTER="$WITH_PRINTER" "$PY" - "$DATA_DIR/config.yaml" <<'PYEOF'
import os, sys, yaml
p = sys.argv[1]
d = yaml.safe_load(open(p))
d["hardware"]["preview"]["backend"] = "auto"
if os.environ.get("WITH_PRINTER") == "1":
    d["hardware"]["printer"]["backend"] = "cups"
yaml.safe_dump(d, open(p, "w"), sort_keys=False, allow_unicode=True)
print("config.yaml aktualisiert:", d["hardware"]["preview"]["backend"], d["hardware"]["printer"]["backend"])
PYEOF
  sudo systemctl restart fotobox-backend
fi

# --- done -------------------------------------------------------------------
log "Installation fertig."
echo "Guest-UI: http://$(hostname -I | awk '{print $1}'):8000/"
if [ "$IS_PI" = "1" ]; then
  cat <<'NEXT'

Noch offen (manuell, siehe docs/installation.md):
  * read-only Root (overlayroot=tmpfs:recurse=0) als LETZTES scharf schalten
    (braucht eine eigene /data-Partition). Danach brauchen Code-Deploys den
    Overlay-Aus/Ein-Zyklus.
NEXT
fi
