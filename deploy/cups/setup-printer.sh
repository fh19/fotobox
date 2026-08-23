#!/usr/bin/env bash
# Idempotent Selphy CP1500 printing setup (M6).
#
# The CP1500's IPP-over-USB is non-functional (ipp-usb: "doesn't implement print
# or scan service"), and Debian/Trixie's Gutenprint (5.3.4, 2022-06 snapshot)
# predates the CP1500. So we build Gutenprint 5.3.6 from source (has the CP1500 +
# Solomon Peachy's dyesub USB backend) and drive the printer over USB.
#
# Borderless = StpBorderless=True + StpiShrinkOutput=Expand (default is a ~2–3 mm
# margin). Safe to run repeatedly: the Gutenprint build is skipped once installed.
set -euo pipefail

GUTENPRINT_VERSION="5.3.6"
QUEUE="${QUEUE:-Selphy_CP1500}"
# Netz, das drucken darf, z.B. 192.168.0.0/24. Leer = keine Freigabe.
SHARE_SUBNET="${SHARE_SUBNET:-}"
SRC_DIR="${SRC_DIR:-/home/pi/gutenprint-src}"
DRIVER="canon-cp1500"

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

installed_gutenprint() {
  strings /usr/lib/libgutenprint.so.9 2>/dev/null | grep -m1 -oE '^5\.3\.[0-9]+' || true
}

apt_deps() {
  log "APT: CUPS, Build-Tools, USB"
  sudo apt-get install -y --no-install-recommends \
    cups cups-client cups-ipp-utils libusb-1.0-0-dev \
    build-essential autoconf automake libtool gettext autopoint pkg-config \
    libcups2-dev libcupsimage2-dev flex bison git
  sudo systemctl enable --now cups
  sudo usermod -aG lpadmin pi 2>/dev/null || true
}

free_usb() {
  # ipp-usb and usblp both grab the USB printer, blocking the Gutenprint backend.
  log "ipp-usb maskieren, usblp blacklisten"
  sudo systemctl mask ipp-usb 2>/dev/null || true
  sudo systemctl stop ipp-usb 2>/dev/null || true
  echo "blacklist usblp" | sudo tee /etc/modprobe.d/blacklist-usblp.conf >/dev/null
  sudo modprobe -r usblp 2>/dev/null || true
}

build_gutenprint() {
  if [ "$(installed_gutenprint)" = "$GUTENPRINT_VERSION" ]; then
    log "Gutenprint $GUTENPRINT_VERSION bereits installiert — Build übersprungen"
    return
  fi
  log "Altes apt-Gutenprint entfernen (Multiarch-Konflikt 5.3.4 vs 5.3.6)"
  sudo apt-get remove -y printer-driver-gutenprint libgutenprint9 libgutenprint-common 2>/dev/null || true
  log "Gutenprint-Quelle (SourceForge)"
  [ -d "$SRC_DIR/.git" ] || git clone --depth 1 https://git.code.sf.net/p/gimp-print/source "$SRC_DIR"
  cd "$SRC_DIR"
  [ -x ./configure ] || ./autogen.sh || true  # autogen 'fails' only on the Docbook doc warning
  ./configure --prefix=/usr --disable-static --without-doc
  # The testpattern tool needs flex/ylwrap and we don't use it — neutralise it.
  printf '.DEFAULT:\n\t@true\nall install install-am install-data install-exec clean distclean mostlyclean maintainer-clean check installcheck installdirs:\n\t@true\n' \
    > src/testpattern/Makefile
  log "make (das dauert ~20-30 Min auf dem Pi 4)"
  make -j"$(nproc)"
  sudo make install
  sudo ldconfig
}

setup_queue() {
  log "CP1500 per USB erkennen"
  local uri
  uri=$(sudo /usr/lib/cups/backend/gutenprint53+usb 2>/dev/null \
        | awk '/gutenprint53\+usb:\/\/canon-cp1500/{print $2; exit}')
  if [ -z "$uri" ]; then
    echo "WARNUNG: Kein CP1500 per USB gefunden — Drucker anschließen + einschalten, dann erneut ausführen." >&2
    return 0
  fi
  log "PPD generieren ($DRIVER)"
  sudo mkdir -p /usr/share/cups/model/gutenprint/5.3
  sudo /usr/sbin/cups-genppd.5.3 "$DRIVER" >/dev/null 2>&1 || true
  local ppd="/usr/share/cups/model/gutenprint/5.3/stp-${DRIVER}.5.3.ppd.gz"
  log "CUPS-Queue '$QUEUE' (randlos)"
  sudo lpadmin -p "$QUEUE" -E -v "$uri" -P "$ppd" \
    -o PageSize=Postcard -o ColorModel=RGB -o StpBorderless=True -o StpiShrinkOutput=Expand
  sudo cupsenable "$QUEUE" 2>/dev/null || true
  sudo cupsaccept "$QUEUE" 2>/dev/null || true
  sudo cups-genppdupdate >/dev/null 2>&1 || true
  sudo systemctl restart cups
}

share_on_lan() {
  # Druckservice fuer das Heimnetz. CUPS ist bereits ein vollstaendiger
  # Druckserver — er hoert nur ab Werk allein auf localhost.
  #
  # Bewusst NICHT "Allow @LOCAL": das schloesse den Gaeste-AP (192.168.4.x) ein,
  # und dann druckt jeder Hochzeitsgast auf deinem Farbband.
  local conf=/etc/cups/cupsd.conf
  if [ "${SHARE_SUBNET:-}" = "" ]; then
    log "Freigabe uebersprungen (SHARE_SUBNET nicht gesetzt)"
    return 0
  fi
  log "CUPS im Netz freigeben fuer $SHARE_SUBNET"
  sudo cp -a "$conf" "$conf.vor-freigabe.$(date +%Y%m%d)"
  # 0.0.0.0 schliesst localhost ein — beide Listen-Zeilen zugleich kollidieren
  # ("Address already in use") und CUPS bleibt still auf localhost.
  sudo sed -i 's/^Listen localhost:631$/Listen 0.0.0.0:631/' "$conf"
  sudo sed -i 's/^Browsing No$/Browsing On/' "$conf"
  if ! grep -q "Allow $SHARE_SUBNET" "$conf"; then
    sudo perl -0pi -e "s{<Location />\n  Order allow,deny\n</Location>}"\
"{<Location />\n  Order allow,deny\n  Allow $SHARE_SUBNET\n</Location>}" "$conf"
  fi
  sudo lpadmin -p "$QUEUE" -o printer-is-shared=true
  sudo systemctl restart cups
  sudo systemctl restart avahi-daemon
  log "Angekuendigt als: $(avahi-browse -t _ipp._tcp 2>/dev/null | grep -c "$QUEUE") Eintraege"
}

main() {
  apt_deps
  free_usb
  build_gutenprint
  setup_queue
  share_on_lan
  log "Fertig: $(lpstat -p "$QUEUE" 2>&1 | head -1)"
}

main "$@"
