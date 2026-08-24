#!/usr/bin/env bash
# Fotobox deployment (M8). Idempotent: safe to run repeatedly.
# Run on the Raspberry Pi as user 'pi' after the code has been synced to
# /home/pi/fotobox. Currently provisions the backend as a mock-mode service;
# real camera/printer (M5/M6) and read-only root come later.
#
# Hardening notes:
# - Watchdog: Raspberry Pi OS already runs the BCM2835 hardware watchdog
#   (RuntimeWatchdogSec=1min) by default — no drop-in needed. (Setting a custom
#   RuntimeWatchdogSec drop-in triggered a reboot loop on this Pi; do not re-add.)
# - Screen blanking: on labwc, blanking only happens if a `swayidle ... wlopm`
#   line is in the autostart. Our kiosk autostart omits it, so the screen stays on.
# - Kiosk crash recovery: launched via `lwrespawn` (restarts it in a loop, 1 s apart,
#   for as long as labwc runs — so the script must never exit quickly).
# - Backend crash recovery: systemd `Restart=always` (see the .service file).
set -euo pipefail

APP_DIR="${APP_DIR:-/home/pi/fotobox}"
DATA_DIR="${DATA_DIR:-/data}"
VENV="$APP_DIR/.venv"
PY="$VENV/bin/python"
USER_NAME="${SUDO_USER:-$(id -un)}"

# Platform: the kiosk/desktop tweaks only apply on the Raspberry Pi OS desktop.
# On any other Linux (a dev/backup box) we install the backend headless and skip
# hostname/gvfs/pcmanfm/kiosk. Force with HEADLESS=1.
is_pi() { grep -qi raspberry /proc/device-tree/model 2>/dev/null; }
HEADLESS="${HEADLESS:-0}"
is_pi || HEADLESS=1

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

apt_packages() {
  log "APT-Pakete installieren"
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends \
    python3-venv python3-dev \
    libgl1 libglib2.0-0t64 \
    fonts-dejavu-core \
    rsync curl
  # Kiosk-Browser nur auf dem Pi-Desktop.
  if [ "$HEADLESS" != "1" ]; then
    sudo apt-get install -y --no-install-recommends chromium unclutter
  fi
}

python_env() {
  log "Python-venv + Core-Abhängigkeiten"
  [ -d "$VENV" ] || python3 -m venv "$VENV"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r "$APP_DIR/requirements-core.txt"
  "$PY" -c "import fastapi, uvicorn, cv2, PIL, numpy, qrcode; print('Core-Import OK')"
}

camera_deps() {
  # Echter DSLR-Zugriff via python-gphoto2 (braucht libgphoto2-dev zum Bauen).
  log "Kamera-Abhängigkeiten (gphoto2)"
  sudo apt-get install -y --no-install-recommends libgphoto2-dev gphoto2
  "$PY" -m pip install --quiet gphoto2
}

lamp_deps() {
  # Die Fotolampe hängt an einem GPIO. lgpio spricht /dev/gpiochip0 über das
  # Character-Device und braucht dafür kein root — die Gruppe "gpio" genügt.
  # Es wird aus der Quelle gebaut, deshalb swig.
  log "GPIO-Bibliothek für die Fotolampe"
  # liblgpio-dev liefert die Kopfdateien, ohne die der Bau an "-llgpio" scheitert.
  sudo apt-get install -y --no-install-recommends swig python3-dev liblgpio-dev
  "$APP_DIR/.venv/bin/pip" install --quiet lgpio
  id -nG "$USER" | tr " " "\n" | grep -qx gpio || sudo usermod -aG gpio "$USER"
}

printer_deps() {
  # Drucken via CUPS/pycups. Der CP1500 kann NICHT driverless über USB (IPP-over-USB
  # ist am Gerät funktionslos) — die vollständige Einrichtung (Gutenprint 5.3.6 aus
  # der Quelle + USB-Queue randlos) macht das eigene, idempotente Skript
  # deploy/cups/setup-printer.sh (dauert beim ersten Lauf ~20-30 Min, braucht den
  # angeschlossenen, eingeschalteten Drucker). Hier nur die Basis.
  log "Drucker-Abhängigkeiten (CUPS/pycups)"
  sudo apt-get install -y --no-install-recommends cups cups-client libcups2-dev
  sudo usermod -aG lpadmin "$USER_NAME" 2>/dev/null || true
  "$PY" -m pip install --quiet pycups
}

data_dir() {
  log "Datenverzeichnis $DATA_DIR"
  sudo mkdir -p "$DATA_DIR"/{events,backgrounds,logs,assets/fonts}
  sudo chown -R "$USER_NAME":"$USER_NAME" "$DATA_DIR"
  if [ ! -f "$DATA_DIR/config.yaml" ]; then
    cp "$APP_DIR/config.example.yaml" "$DATA_DIR/config.yaml"
    # The service runs in real mode (see the unit); preview + printer stay mocked
    # until that hardware is attached (M5b/M6). The camera (gphoto2) is real.
    "$PY" - "$DATA_DIR/config.yaml" <<'PYEOF'
import sys, yaml
p = sys.argv[1]
d = yaml.safe_load(open(p))
d["hardware"]["preview"]["backend"] = "mock"
d["hardware"]["printer"]["backend"] = "mock"
yaml.safe_dump(d, open(p, "w"), sort_keys=False, allow_unicode=True)
PYEOF
  fi
  # A usable caption font on the device (the pipeline also has a bundled fallback).
  cp -n "$APP_DIR/backend/assets/fonts/DejaVuSerif.ttf" "$DATA_DIR/assets/fonts/" 2>/dev/null || true
}

backend_service() {
  log "systemd-Dienst fotobox-backend"
  # Template the unit so it works for any install path / user / data dir, not just
  # the Pi's /home/pi/fotobox + user pi + /data.
  local tmp
  tmp="$(mktemp)"
  sed -e "s#/home/pi/fotobox#$APP_DIR#g" \
      -e "s#^User=pi\$#User=$USER_NAME#" \
      -e "s#FOTOBOX_DATA_DIR=/data#FOTOBOX_DATA_DIR=$DATA_DIR#" \
      "$APP_DIR/deploy/fotobox-backend.service" > "$tmp"
  sudo cp "$tmp" /etc/systemd/system/fotobox-backend.service
  rm -f "$tmp"
  sudo systemctl daemon-reload
  sudo systemctl enable fotobox-backend.service
  sudo systemctl restart fotobox-backend.service
}

kiosk_autostart() {
  log "Kiosk-Autostart (labwc)"
  chmod +x "$APP_DIR/deploy/kiosk.sh"
  mkdir -p "$HOME/.config/labwc"
  cat > "$HOME/.config/labwc/autostart" <<EOF
# Fotobox-Kiosk. Ersetzt den Standard-Desktop-Autostart bewusst (kein Panel).
/usr/bin/kanshi &
# lwrespawn startet den Kiosk neu, falls Chromium abstürzt/gekillt wird — in einer
# Schleife im Sekundentakt, solange labwc läuft.
/usr/bin/lwrespawn $APP_DIR/deploy/kiosk.sh http://localhost/ $DATA_DIR/mode >/tmp/fotobox-kiosk.log 2>&1 &
EOF
  # Desktop-Autologin, damit der Kiosk ohne Anmeldung hochkommt (B4 = Desktop Autologin).
  sudo raspi-config nonint do_boot_behaviour B4 || true
}

set_hostname() {
  if [ "$(hostname)" != "fotobox" ]; then
    log "Hostname auf 'fotobox' setzen"
    sudo hostnamectl set-hostname fotobox
  fi
}

free_camera_from_gvfs() {
  # Der Desktop-gvfs-Stack schnappt sich USB-Kameras (gphoto2/mtp) automatisch und
  # blockiert damit gphoto2/python-gphoto2 im Backend ("Could not claim").
  # Zuverlässig: die gvfs-Monitor-Definitionen neutralisieren + User-Units maskieren.
  log "gvfs vom automatischen Kamerazugriff abhalten"
  for m in gphoto2 mtp; do
    f="/usr/share/gvfs/remote-volume-monitors/$m.monitor"
    [ -f "$f" ] && sudo mv "$f" "$f.disabled"
  done
  XDG_RUNTIME_DIR="/run/user/$(id -u)" systemctl --user mask \
    gvfs-gphoto2-volume-monitor.service gvfs-mtp-volume-monitor.service 2>/dev/null || true
  killall gvfsd-gphoto2 gvfs-gphoto2-volume-monitor 2>/dev/null || true
}

disable_removable_media() {
  # Kein Auto-Mount/Popup des Dateimanagers, wenn Kamera/USB angesteckt werden
  # (sonst legt sich ein Fenster über den Kiosk). gphoto2-Konflikt (gvfs) folgt in M5.
  log "Wechselmedien-Autostart des Dateimanagers abschalten"
  for prof in LXDE-pi default; do
    d="$HOME/.config/pcmanfm/$prof"
    f="$d/pcmanfm.conf"
    mkdir -p "$d"
    if [ -f "$f" ] && grep -q '\[volume\]' "$f"; then
      sed -i '/\[volume\]/,/^\[/ {s/^mount_on_startup=.*/mount_on_startup=0/; s/^mount_removable=.*/mount_removable=0/; s/^autorun=.*/autorun=0/}' "$f"
    else
      printf '\n[volume]\nmount_on_startup=0\nmount_removable=0\nautorun=0\n' >>"$f"
    fi
  done
}

verify() {
  log "Warten, bis das Backend antwortet"
  for _ in $(seq 1 30); do
    if curl -fs http://localhost/api/status >/dev/null; then
      echo "Backend OK:"
      curl -s http://localhost/api/status
      echo
      return 0
    fi
    sleep 1
  done
  echo "Backend antwortet nicht — Logs:" >&2
  sudo journalctl -u fotobox-backend.service --no-pager -n 40 >&2
  return 1
}

main() {
  apt_packages
  python_env
  camera_deps
  printer_deps
  lamp_deps
  data_dir
  if [ "$HEADLESS" != "1" ]; then
    set_hostname
    disable_removable_media
    free_camera_from_gvfs
  else
    log "Headless/Nicht-Pi: Hostname, gvfs, Datei-Manager und Kiosk werden übersprungen"
  fi
  backend_service
  [ "$HEADLESS" != "1" ] && kiosk_autostart
  verify
  log "Fertig. Guest-UI: http://$(hostname -I | awk '{print $1}')/"
}

main "$@"
