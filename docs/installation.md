# Installation auf einem neuen Raspberry Pi

Schritt-für-Schritt-Anleitung, um die Fotobox auf einem frischen Pi in Betrieb zu
nehmen. Läuft im Betrieb **offline** (CLAUDE-Regel 7) — die Installation selbst
braucht aber einmal **Netz** (apt, pip, ggf. KI-Modell). Danach kann das Netz weg.

Zielsystem: **Raspberry Pi OS „Trixie" (Debian 13), 64-bit, mit Desktop** (der Kiosk
braucht den Wayland-Compositor **labwc**). Benutzer **`pi`**. Pi 4 **oder Pi 5** — die
wenigen Pi-5-Unterschiede stehen unten in einem eigenen Abschnitt.

Hardware: Pi + Touchscreen, Nikon-DSLR (via gphoto2), Canon Selphy CP1500,
USB-Vorschaukamera (Webcam), optional Hardware-RTC. Am Pi 5 ist eine RTC bereits
eingebaut.

---

## Schnellster Weg: der Ein-Kommando-Installer

Nach Schritt 1 (OS) und Schritt 2 (Code nach `/home/pi/fotobox`) erledigt **ein**
Skript die komplette Software-Installation — idempotent, mehrfach ausführbar:

```bash
cd /home/pi/fotobox
# Voller Pi-Aufbau inkl. Drucker + RTC, Zeit setzen, nichts nachfragen:
bash deploy/install.sh --with-printer --with-rtc --set-time "2026-07-30 20:00:00" --yes
```

Ohne Flags macht es nur die Basis (fragt vorher nach). Nützliche Optionen:

| Option | Wirkung |
|---|---|
| `--with-printer` | Selphy CP1500 (Gutenprint/USB); Drucker muss an sein; ~20–30 min |
| `--with-rtc` | Hardware-Uhr — Pi 4: DS1307-Overlay; Pi 5: eingebaute RTC |
| `--set-time "…"` | System- **und** RTC-Zeit setzen (offline-tauglich) |
| `--with-ai` | KI-Backend (rembg/onnxruntime) zusätzlich installieren |
| `--mock` | Vorschau/Drucker auf Mock lassen (nicht auf echt umstellen) |
| `--headless` | ohne Kiosk/Desktop (automatisch auf Nicht-Pi) |
| `--yes` | keine Rückfragen |

Der Installer erkennt selbst, ob er auf einem **Pi 4/5** oder auf **anderem
Debian/Ubuntu-Linux** läuft (dort headless, Hardware auf Mock, kein Kiosk). Er
templatet den systemd-Dienst auf den tatsächlichen Pfad/Benutzer, aktiviert auf
dem Pi standardmäßig die echte Vorschaukamera und (mit `--with-printer`) den Drucker.

**Nicht** automatisiert (bewusst, destruktiv/umgebungsspezifisch, als Letztes von
Hand): das Anlegen der `/data`-Partition und das Scharfschalten des read-only Roots
(overlayroot) — siehe Schritt 8. Die folgenden Abschnitte beschreiben alles einzeln,
falls man es Schritt für Schritt statt per Installer machen will.

## 0. Reihenfolge im Überblick

1. Betriebssystem flashen und Grundeinstellungen
2. Code nach `/home/pi/fotobox` bringen
3. `deploy/setup.sh` (apt/venv/Dienst/Kiosk)
4. Drucker: `deploy/cups/setup-printer.sh` (Drucker angeschlossen, dauert ~20–30 min)
5. RTC einbinden — **Pi 4:** `deploy/rtc/setup-rtc.sh`; **Pi 5:** eingebaute RTC nutzen
6. Optional: KI-Freistellung (rembg-Modell)
7. Echte Hardware in `/data/config.yaml` aktivieren
8. **Zuletzt:** read-only Root (overlayroot) scharf schalten
9. Optional: Gäste-WLAN (Access Point)

> Read-only Root **als Letztes**. Ist es aktiv, brauchen spätere System-/Code-Änderungen
> den Overlay-Aus/Ein-Zyklus (siehe Schritt 8). Config und Fotos auf `/data` sind davon
> nicht betroffen.

---

## 1. Betriebssystem

Mit dem **Raspberry Pi Imager**: „Raspberry Pi OS (64-bit)" (Trixie, mit Desktop).
Im Imager unter „Einstellungen" (Zahnrad) setzen:

- Hostname `fotobox`, Benutzer **`pi`** + Passwort
- SSH aktivieren (Schlüssel empfohlen — dann funktionieren die Deploy-Befehle per SSH)
- WLAN + Land `DE`, Zeitzone `Europe/Berlin`, Tastatur `de`

Erststart, dann per SSH verbinden. System aktuell ziehen:

```bash
sudo apt update && sudo apt full-upgrade -y
```

## 2. Code auf den Pi

Mit Netz am einfachsten per Git (oder per `rsync` vom Entwicklungsrechner):

```bash
git clone <REPO-URL> /home/pi/fotobox
# oder vom Dev-Rechner:  rsync -a ./ pi@fotobox:/home/pi/fotobox/
```

Erwarteter Pfad ist **`/home/pi/fotobox`** (die Skripte und der systemd-Dienst gehen
davon aus).

## 3. Basis-Provisionierung: `deploy/setup.sh`

Idempotent, mehrfach ausführbar:

```bash
cd /home/pi/fotobox
bash deploy/setup.sh
```

Das erledigt:

- **apt-Pakete** (python3-venv, libgl/glib, DejaVu-Font, chromium, unclutter, rsync, curl)
- **Python-venv** unter `.venv` + `requirements-core.txt` (FastAPI, uvicorn, OpenCV,
  Pillow, numpy, qrcode) — **ohne** KI (siehe Schritt 6)
- **Kamera:** `libgphoto2-dev`, `gphoto2`, `python-gphoto2`
- **Drucker-Basis:** `cups`, `pycups`, `pi` in Gruppe `lpadmin` (die *echte*
  Druckereinrichtung folgt in Schritt 4)
- **`/data`** anlegen (`events/`, `backgrounds/`, `logs/`, `assets/fonts/`) und
  `config.yaml` aus `config.example.yaml` kopieren — dabei **preview + printer
  zunächst auf `mock`** gesetzt (in Schritt 7 auf echt umstellen)
- **systemd-Dienst** `fotobox-backend` (real-Modus, Autostart, `Restart=always`)
- **Kiosk-Autostart** (labwc): Chromium im Kiosk via `lwrespawn` (Neustart < 5 s),
  Desktop-Autologin (B4)
- **gvfs** vom automatischen Kamerazugriff abhalten (sonst „Could not claim" bei gphoto2)
- Datei-Manager-Autostart für Wechselmedien aus, Bildschirmschoner aus, Hostname `fotobox`

Danach läuft die Guest-UI schon: `http://<pi-ip>/` (mit Mock-Vorschau/-Drucker).

## 4. Drucker (Canon Selphy CP1500)

Der CP1500 kann **nicht** treiberlos über USB. Das eigene, idempotente Skript baut
Gutenprint 5.3.6 aus der Quelle und richtet eine randlose USB-Queue (Postcard) ein.
**Drucker anschließen und einschalten**, dann:

```bash
bash deploy/cups/setup-printer.sh
```

Erster Lauf dauert **~20–30 min** (Kompilieren). Details/Queue-Name in
`deploy/cups/` und in der Memory-Notiz zum Drucker.

### Optional: die Box als Netzwerkdrucker

CUPS ist bereits ein vollständiger Druckserver — er hört ab Werk nur auf
`localhost`. Mit einem gesetzten Netz gibt das Skript ihn frei:

```bash
SHARE_SUBNET=192.168.0.0/24 bash deploy/cups/setup-printer.sh
```

Danach erscheint die Box im Netz als **Canon SELPHY CP1500** — unter Windows,
macOS, iOS (AirPrint) und Android (Mopria), ohne Treiberinstallation. Puffern,
Warteschlange, Abbrechen durch den Client und Fehlermeldungen wie „kein Papier"
macht CUPS von sich aus.

Bewusst **kein** `Allow @LOCAL`: das schlösse den Gäste-AP (`192.168.4.x`) ein,
und dann druckt jeder Gast auf deinem Farbband. Nur das angegebene Heimnetz darf.

Zwei Stolpersteine, die Zeit kosten, wenn man sie nicht kennt:

- `Listen localhost:631` und `Listen 0.0.0.0:631` **zugleich** kollidieren
  (`Address already in use`) — CUPS bleibt dann still auf localhost. Die
  localhost-Zeile muss ersetzt, nicht ergänzt werden.
- `/etc/cups` und `/var/spool/cups` liegen auf dem Overlay. Die Freigabe muss also
  bei **abgeschaltetem overlayroot** eingerichtet werden (Abschnitt 8), sonst ist
  sie nach dem Neustart weg. Umgekehrt bedeutet das: die Warteschlange ist nach
  jedem Neustart automatisch leer — Aufträge, die auf einen ausgeschalteten
  Drucker warten, überleben einen Stromausfall nicht.

## 5. Hardware-Uhr (RTC)

Offline gibt es kein NTP — ohne RTC ist die Uhr nach jedem Stromausfall falsch (und
damit Zeitstempel/Verzeichnisnamen).

- **Pi 4:** externe RTC einbinden — siehe `deploy/rtc/README.md`. Kurz:
  ```bash
  sudo bash deploy/rtc/setup-rtc.sh
  sudo bash deploy/rtc/setup-rtc.sh --set-time "JJJJ-MM-TT HH:MM:SS"
  ```
  (Unsere Platine ist trotz Aufdruck „DS1302" ein **DS1307**, I²C 0x68.)
- **Pi 5:** RTC ist **eingebaut** — meist genügt eine Knopfzelle am RTC-Batterie-Header,
  dann existiert `/dev/rtc0` von selbst. Siehe Pi-5-Abschnitt unten.

Kontrolle: `timedatectl` → Zeile „RTC time" muss stimmen.

## 6. Optional: KI-Freistellung (rembg)

Standard ist **Chroma-Key** (Greenscreen) — der braucht **kein** Modell. Nur wenn der
KI-Modus („ai") genutzt werden soll:

```bash
# statt requirements-core.txt die volle Liste (rembg + onnxruntime):
.venv/bin/pip install -r requirements.txt
```

Und das Modell **lokal** ablegen (kein Laufzeit-Download, CLAUDE-Regel 7). Erwarteter
Pfad aus `config.yaml` (`pipeline.ai.model_path`): **`/data/assets/models/u2netp.onnx`**.
Mit Netz einmalig holen und dorthin kopieren, z. B.:

```bash
mkdir -p /data/assets/models
# u2netp.onnx von einem Rechner mit Netz besorgen (rembg lädt es sonst nach ~/.u2net)
# und nach /data/assets/models/u2netp.onnx legen.
```

## 7. Echte Hardware in `config.yaml` aktivieren

`setup.sh` hat `preview` und `printer` bewusst auf `mock` gesetzt. In
`/data/config.yaml` umstellen:

```yaml
hardware:
  preview:
    backend: auto        # findet die USB-Webcam (v4l2); "mock" -> "auto"
  printer:
    backend: cups        # "mock" -> "cups"
```

Die DSLR (`hardware.camera.backend: gphoto2`, `select: auto`) ist bereits real. Bei
fehlender DSLR springt automatisch die Vorschaukamera als Auslöse-Ersatz ein
(`camera.fallback_to_preview: true`). Danach:

```bash
sudo systemctl restart fotobox-backend
```

Verkabelung/Fokus: die DSLR sollte auf **manuellen Fokus** stehen (Fotobox löst sofort
aus). Details in der Memory-Notiz zur Kamera.

### Sony a7 IV (und andere Sony Alpha)

Am Kameramenü nötig:

- **USB → USB-Verbindungsmodus: PC-Fernbedienung** (sonst kein Auslösen über gphoto2)
- **USB → USB-Stromversorgung: Aus.** Sonst lädt die Kamera aus dem Pi und der Pi geht in
  Unterspannung (`vcgencmd get_throttled` ≠ 0x0) — das lässt auch die USB-Webcam der
  Vorschau aussetzen.
- **Bildqualität/Dateiformat**: Die Fotobox setzt vor jeder Auslösung
  `camera.image_quality` (Default `JPEG`). Ohne das liefert die Kamera im Modus RAW+JPEG
  zuerst die `.ARW` — 35 MB, die als Foto unbrauchbar sind. Bleibt die Kamera bei RAW+JPEG,
  holt sich das Backend das JPEG aus dem Folge-Event.
- **JPEG-Bildgröße M oder S** verkürzt die Übertragung spürbar (L ≈ 17 MB ≈ 4 s über USB —
  das muss unter `camera.capture_timeout_seconds` bleiben).

**Ohne separate Vorschaukamera:** `hardware.preview.backend: gphoto2` (oder im Admin
unter Vorschau-Backend) holt das Live-Bild aus der Kamera selbst — 1024×768, ~30 Bilder/s,
über denselben offenen Kamera-Handle wie der Auslöser.

⚠️ **Nur bei spiegellosen Kameras.** Eine Spiegelreflex (D7200) klappt für Live View den
Spiegel hoch und ist damit in unter einer Stunde leer. `auto` wählt die Kamera deshalb
**nie** von selbst als Vorschau — ohne Webcam gibt es dann lieber gar kein Live-Bild als
einen leeren Akku mitten in der Feier. Fotografieren geht in diesem Zustand normal weiter.

**Akkuwechsel:** Die Kamera darf im Betrieb aus- und wieder eingeschaltet werden. Sie
kommt unter einer neuen USB-Gerätenummer zurück; die Box merkt das von selbst und nimmt
sie wieder als Hauptkamera — nichts im Admin anzuklicken. Wie schnell, bestimmen
`camera.reconnect_backoff_seconds` (wachsende Abstände) und
`camera.reconnect_max_seconds` (Deckel von 10 s, sobald einmal eine Kamera da war).
Dazwischen fotografiert die Vorschaukamera als Ersatz, sichtbar im Admin.

**Auslöseverzögerung:** Die a7 IV braucht ab Auslösebefehl ~650 ms bis zur Belichtung
(die Fotobox hält die Kamera dafür dauerhaft geöffnet; ohne das wären es 4,2 s, weil
libgphoto2 nach jedem `init()` 3 s Sony-Startzeit abwartet). Wer den Rest ausgleichen
will, stellt im Admin unter `Auslöser-Vorlauf (ms)` z. B. 650 ein — dann fällt die
Belichtung auf das Ende des Countdowns statt kurz danach.

Steht `[-53] Could not claim the USB device` im Log, hängt die Kamera am Bus, lässt sich
aber nicht mehr ansprechen. Dafür gibt es im Admin-Bereich `Kamera zurücksetzen`
(USB-Reset, kein Neustart nötig); nach `camera.usbreset_after_failures` Fehlversuchen
in Folge macht die Box das von allein.

Das CLI-`gphoto2` von Debian (libgphoto2 2.5.31) kann die a7 IV **nicht** auslösen
(„Konnte Bild nicht aufnehmen"; alle PTP-Properties melden 0x2002). Das ist kein
Fotobox-Fehler: das `python-gphoto2`-Rad im venv bringt libgphoto2 2.5.34 mit, und die
funktioniert. Zum Testen also immer den venv-Python nehmen, nicht `gphoto2` aus der Shell.

## 8. Read-only Root (overlayroot) — als Letztes

Schützt die SD gegen Korruption bei Stromausfall. Auf diesem System bereits eingerichtet;
für eine **neue** SD:

1. Eigene Datenpartition `/data` anlegen (auf unserer SD p3), fstab-Eintrag mit
   `PARTUUID … /data ext4 defaults,noatime 0 2`.
2. overlayroot installieren und in `/boot/firmware/cmdline.txt` **`overlayroot=tmpfs:recurse=0`**
   voranstellen. **`recurse=0` ist essenziell** — sonst wird auch `/data` überlagert und
   Fotos landen im RAM.

Kontrolle: `findmnt -no FSTYPE /` → `overlay`, `findmnt /data` → echtes `ext4`.

**Danach gilt für Code-Deploys:** Overlay per `cmdline.txt` **aus** (Token entfernen →
Reboot, root=ext4) → `rsync` nach `/home/pi/fotobox` → Token wieder **rein** → Reboot
(root=overlay). Nicht den `/media/root-ro`-Remount-Trick nutzen — der wirft laufende
Prozesse (Chromium) raus. `config.txt`/`cmdline.txt` (auf der Boot-Partition) und
`/data` bleiben ohne diesen Zyklus änderbar.

## 9. Optional: Gäste-WLAN (Access Point)

Für die Galerie am Handy der Gäste bringt das Backend einen nmcli-basierten AP mit
(Admin-Bereich → Netzwerk). Konfiguration unter `network.access_point` in `config.yaml`.
Achtung: AP-Betrieb kappt die WLAN-Verbindung ins Heimnetz (dann kein SSH über WLAN).

## 10. Abschluss

```bash
sudo reboot
```

Nach dem Boot sollte der Kiosk automatisch im Vollbild starten (`http://localhost/`),
Backend `active`, RTC-Zeit korrekt. Admin-Bereich: lange in die konfigurierte
Bildschirmecke drücken (PIN aus `ui.admin_pin`) oder `…/admin`.

---

## Raspberry Pi 5 — Besonderheiten

Der Stack läuft auf dem Pi 5 identisch (gleiche Architektur aarch64, Trixie, labwc,
gphoto2, CUPS/Gutenprint, OpenCV, overlayroot). Zu beachten:

- **Eingebaute RTC:** Der Pi 5 hat eine **onboard-RTC** mit eigenem Batterie-Header.
  Knopfzelle einstecken → `/dev/rtc0` ist von selbst da, kein Overlay/DS1307 nötig.
  Zeit einmal setzen (offline, ohne `hwclock`, das auf Trixie fehlt):
  ```bash
  sudo timedatectl set-ntp false
  sudo timedatectl set-time "JJJJ-MM-TT HH:MM:SS"   # setzt System + RTC
  sudo timedatectl set-ntp true
  ```
  Optional Trickle-Charge für ladbare Zellen: `dtparam=rtc_bbat_vchg=…` in `config.txt`
  (nur mit passender Zelle!). Die externe DS1307 kann man weglassen — **Schritt 5 entfällt**.
- **GPIO-Bibliotheken:** Auf dem Pi 5 funktioniert `RPi.GPIO` nicht mehr (lgpio/gpiozero
  nötig). **Für die Fotobox irrelevant** — die Anwendung nutzt keine GPIOs; die RTC läuft
  über I²C bzw. onboard, nicht über Bit-Banging.
- **Schneller:** KI-Freistellung (rembg) ist auf dem Pi 5 deutlich flotter — Schritt 6
  wird damit praktikabler als auf dem Pi 4 (wo Chroma der Default ist).
- **Boot/Config:** `/boot/firmware/config.txt` und `cmdline.txt` funktionieren wie beim
  Pi 4; overlayroot ebenso. Dual-HDMI stört nicht (Touchscreen an einem Ausgang).
- **Wichtig:** wirklich das **64-bit-OS mit Desktop** nehmen (labwc), sonst fehlt der
  Kiosk-Compositor.

---

## Schnell-Checkliste (Kurzform)

```text
[ ] Pi OS Trixie 64-bit Desktop, User pi, SSH, TZ Europe/Berlin
[ ] Code nach /home/pi/fotobox
[ ] bash deploy/setup.sh
[ ] bash deploy/cups/setup-printer.sh          (Drucker an)
[ ] RTC: Pi4 -> deploy/rtc/setup-rtc.sh ; Pi5 -> Knopfzelle + timedatectl set-time
[ ] (optional) requirements.txt + u2netp.onnx nach /data/assets/models/
[ ] config.yaml: preview backend=auto, printer backend=cups ; restart backend
[ ] read-only Root (overlayroot=tmpfs:recurse=0) als Letztes
[ ] reboot -> Kiosk startet, RTC-Zeit stimmt
```
