#!/usr/bin/env bash
# Launch Chromium as a full-screen kiosk pointing at the local Fotobox UI.
# Started from the desktop session's autostart (Wayland/labwc or Wayfire).
set -u

URL="${1:-http://localhost/}"
MODE_FILE="${2:-/data/mode}"

# Betriebsart: "fotobox" (Standard) oder "printserver". Die Datei liegt auf der
# Datenpartition, überlebt also den schreibgeschützten Root, und wird im Admin
# umgeschaltet. Ohne Datei ist es die Fotobox.
MODE="fotobox"
[ -r "$MODE_FILE" ] && MODE="$(tr -d "[:space:]" < "$MODE_FILE")"

if [ "$MODE" = "printserver" ]; then
  # NICHT beenden: lwrespawn startet dieses Skript sonst im Sekundentakt neu
  # (while-Schleife mit "sleep 1", siehe /usr/bin/lwrespawn). Warten lässt den
  # Bildschirm dunkel und kostet nichts.
  #
  # Gewartet wird auf die Datei, nicht auf ein Signal: Erkennt das Backend eine
  # Kamera, schreibt es "fotobox" hinein, und der Kiosk startet von hier aus
  # weiter — ohne Neustart, der beim Druckserver die Warteschlange kosten würde.
  echo "Druckserver-Modus — kein Kiosk. Warte auf einen Moduswechsel."
  # Ein schwarzer Bildschirm sieht aus wie ein Defekt. Also eine feste Seite,
  # die sagt, was los ist und wie man zurückkommt. Statisch: kein Live-Bild,
  # keine Abfragen — nach dem Zeichnen kostet sie praktisch nichts.
  until curl -fs "$URL" >/dev/null 2>&1; do sleep 1; done
  chromium --kiosk --ozone-platform=wayland --password-store=basic --incognito \
    --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
    --app="${URL%/}/printserver.html" &
  NOTICE=$!

  while [ "$MODE" = "printserver" ]; do
    sleep 5
    MODE="fotobox"
    [ -r "$MODE_FILE" ] && MODE="$(tr -d "[:space:]" < "$MODE_FILE")"
  done

  echo "Betriebsart ist jetzt '$MODE' — Kiosk startet."
  kill "$NOTICE" 2>/dev/null
  wait "$NOTICE" 2>/dev/null
  sleep 1  # Chromium den Bildschirm freigeben lassen, bevor der Kiosk startet
fi

# Wait until the backend answers, so the kiosk never shows a connection error.
until curl -fs "$URL" >/dev/null 2>&1; do sleep 1; done

exec chromium \
  --kiosk \
  --ozone-platform=wayland \
  --password-store=basic \
  --incognito \
  --noerrdialogs \
  --disable-infobars \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --disable-session-crashed-bubble \
  --disable-features=Translate,TranslateUI \
  --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  --app="$URL"
