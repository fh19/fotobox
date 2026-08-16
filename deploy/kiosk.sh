#!/usr/bin/env bash
# Launch Chromium as a full-screen kiosk pointing at the local Fotobox UI.
# Started from the desktop session's autostart (Wayland/labwc or Wayfire).
set -u

URL="${1:-http://localhost/}"

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
