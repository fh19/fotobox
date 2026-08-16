# Konzept: DIY-Fotobox für Hochzeiten

Version 1.0 — Grundlage für die Umsetzung mit Claude Code

---

## 1. Zielbild

Eine autarke Fotobox, die nach dem Einschalten ohne Bedienung hochfährt und direkt in
einem Vollbild-Kiosk landet. Gäste sehen ein permanentes Live-Bild von sich, tippen auf
„Foto starten", wählen optional einen Hintergrund, ein Countdown läuft, die DSLR löst aus,
das fertige Bild wird angezeigt und kann gedruckt werden. Alles offline. Nach der
Veranstaltung werden die Bilder per Netzwerk abgeholt.

**Leitprinzipien**

1. *Fehlertoleranz vor Features.* Eine Hochzeit lässt sich nicht wiederholen. Jede
   Komponente, die ausfallen kann (Drucker, Papier, USB), darf den Aufnahmebetrieb nicht
   blockieren.
2. *Original immer zuerst sichern.* Das unbearbeitete JPEG landet auf der Platte, bevor
   irgendeine Bildverarbeitung startet.
3. *Keine Sackgassen in der UI.* Jeder Screen hat einen Timeout, der zurück in den
   Idle-Zustand führt. Ein betrunkener Gast darf die Box nicht in einem Zustand hinterlassen.

---

## 2. Zwei Punkte vorweg, die das Konzept prägen

### 2.1 Die Kamera

Eine **Nikon D9000 gibt es nicht** — gemeint ist vermutlich die D90, D7000 oder D5000. Das
ist keine Wortklauberei, sondern relevant: die Modelle unterscheiden sich deutlich darin,
wie gut `libgphoto2` sie fernsteuern kann. Vor dem ersten Zeilencode Codes prüfen:

```bash
gphoto2 --auto-detect
gphoto2 --summary
gphoto2 --list-config          # welche Parameter sind fernsteuerbar?
gphoto2 --capture-image-and-download
```

Alle drei genannten Modelle können per PTP ausgelöst werden. Die D90 ist die kritischste
(ältestes PTP-Protokoll, Liveview nur eingeschränkt nutzbar).

### 2.2 Live-Bild NICHT über die DSLR

Das ist die wichtigste Architekturentscheidung des ganzen Projekts.

Der naheliegende Weg — Liveview per `gphoto2 --capture-movie` streamen — funktioniert
technisch, ist für einen 6-Stunden-Dauerbetrieb aber die falsche Wahl:

- Der Spiegel bleibt hochgeklappt, der Sensor heizt sich über Stunden auf.
- gphoto2 belegt das USB-Gerät exklusiv. Für jede Auslösung muss der Liveview-Stream
  gestoppt und danach neu gestartet werden → 1–2 Sekunden schwarzer Bildschirm bei jedem
  Foto, plus eine zusätzliche Fehlerquelle bei jedem einzelnen Auslösen.
- Die Bildrate liegt bei ca. 10–15 fps in niedriger Auflösung, mit spürbarer Latenz.
- Der Akku der DSLR ist nach 2–3 Stunden Liveview leer (Netzteil/Dummy-Akku ist ohnehin Pflicht).

**Empfehlung: Zwei Kameras.** Eine Raspberry Pi Camera Module 3 (oder eine gute USB-Webcam)
liefert das permanente Live-Bild. Die DSLR wird ausschließlich für die eigentliche
Aufnahme angesprochen und ist ansonsten im Ruhezustand.

Vorteile: Live-Bild bleibt auch dann stehen, wenn die DSLR gerade arbeitet oder einen
Fehler wirft. Die Entwicklung ist entkoppelt. Der USB-Bus wird nicht überlastet.

Nachteil: Live-Bild und finales Foto haben leicht unterschiedlichen Bildausschnitt. Das
löst ein einmaliger Kalibrierschritt im Admin-Menü — eine Crop/Offset-Maske, die dem
Live-Bild den DSLR-Ausschnitt als Rahmen überlagert. Für „stehe ich im Bild?" ist das
völlig ausreichend. Die Vorschaukamera montierst du direkt über oder unter dem
Objektiv der DSLR.

---

## 3. Hardware

| Komponente | Empfehlung | Begründung |
|---|---|---|
| Rechner | Raspberry Pi 4, 8 GB | Bildverarbeitung + Video-Encoding + Browser gleichzeitig |
| Speicher | **NVMe via PCIe-HAT oder USB3-SSD, keine SD-Karte** | SD-Karten sterben bei Dauerschreiblast; du kennst das Problem bereits |
| Display | 10–15" HDMI-Touch, kapazitiv | Resistive Touchscreens sind für Gäste frustrierend |
| Hauptkamera | Nikon DSLR + **Netzteil/Dummy-Akku** | Akkuwechsel mitten in der Feier will niemand |
| Vorschaukamera | Pi Camera Module 3 oder Logitech C920 | siehe 2.2 |
| Drucker | Canon Selphy CP1500 (USB) | vorgegeben |
| Licht | Dauerlicht-LED-Panel oder Ringlicht, dimmbar, ~5000 K | Blitz macht das Live-Bild unbrauchbar und die Belichtung unvorhersehbar |
| USV | Pi-UPS-HAT (z. B. Waveshare/PiSugar) | Sauberes Herunterfahren bei Stromausfall — schützt das Dateisystem |
| Netzwerk | Ethernet-Buchse zugänglich lassen | Für den Download nach der Veranstaltung |

**Licht:** Nimm Dauerlicht. Ein Blitz zwingt dich zu Blendensteuerung, verändert das
Ergebnis gegenüber dem Live-Bild und macht Chroma-Keying instabil. Mit Dauerlicht stellst
du die DSLR einmal auf feste Werte (manueller Modus, z. B. f/5.6, 1/125 s, ISO 400, manueller
Weißabgleich) und alle Bilder des Abends sind konsistent — Grundvoraussetzung für
zuverlässiges Freistellen.

---

## 4. Hintergrund-Integration — realistische Optionen

Das ist der anspruchsvollste Teil. Drei Verfahren, in absteigender Zuverlässigkeit:

### Variante A — Greenscreen / Chroma-Key (empfohlen)
Ein grüner Stoffhintergrund, gleichmäßig ausgeleuchtet. Freistellung per OpenCV im
HSV-Farbraum, Nachbearbeitung mit Morphologie und Kantenglättung (Spill-Suppression gegen
grüne Farbsäume an Haaren und weißem Brautkleid).

- Verarbeitungszeit: kurz auf dem Pi
- Qualität: sehr gut, sofern die Ausleuchtung stimmt
- Aufwand vor Ort: Greenscreen aufbauen und separat ausleuchten
- **Falle:** grüne Kleidung, grüne Deko, Getränke mit grünem Etikett verschwinden mit

### Variante B — KI-Segmentierung ohne Greenscreen
`rembg` mit dem u2netp-Modell (ONNX Runtime, läuft komplett lokal, kein Netzwerk nötig).

- Verarbeitungszeit: länger als Chroma auf dem Pi — passt aber in die Verarbeitungsphase nach der Auslösung
- Qualität: bei Portraits gut, bei Haaren und mehreren Personen mit sichtbaren Artefakten
- Aufwand vor Ort: keiner
- Modell vorab herunterladen und im Image ablegen (offline!)

### Variante C — Overlay / Rahmen statt Freistellung
Kein Freistellen, sondern eine PNG-Ebene mit Transparenz über das Foto: Rahmen, Datum,
Namen des Brautpaars, dekorative Elemente. Trivial, absolut robust, sieht gut aus.

**Empfehlung:** A und C fest einbauen, B als schaltbare Option im Admin-Menü. In der UI
wählt der Gast aus einer Kachelgalerie — die Engine dahinter (Chroma/KI/Overlay) steckt
als Metadatum in einer JSON-Datei pro Hintergrund:

```
/data/backgrounds/
  strand/
    background.jpg
    thumbnail.jpg
    config.json      → {"mode": "chroma", "overlay": "frame.png", "name": "Strand"}
```

Neue Hintergründe = Ordner reinkopieren. Kein Code-Deploy nötig.

---

## 5. Softwarearchitektur

### 5.1 Gesamtbild

```
┌─────────────────────────────────────────────────┐
│  Chromium im Kiosk-Modus (localhost)             │
│  Frontend: Vanilla JS oder Svelte, kein Framework-Overkill │
└───────────────┬─────────────────────────────────┘
                │ HTTP + WebSocket
┌───────────────▼─────────────────────────────────┐
│  FastAPI / Python 3.11                          │
│  ├── StateMachine   (Zustandslogik)             │
│  ├── CameraService  (gphoto2 via python-gphoto2) │
│  ├── PreviewService (MJPEG-Stream, picamera2)   │
│  ├── ImagePipeline  (OpenCV / Pillow / rembg)   │
│  ├── PrintService   (CUPS via pycups)           │
│  └── StorageService (Dateisystem + SQLite)      │
└─────────────────────────────────────────────────┘
```

**Warum Browser und nicht native App:** Chromium im Kiosk-Modus ist auf dem Pi Standard und
gut abzudichten, das UI lässt sich am Entwicklungsrechner ohne Hardware bauen, und du
bekommst die Download-Galerie nach der Veranstaltung geschenkt — dasselbe Backend, andere
Route.

**Warum Python:** `python-gphoto2`, `picamera2`, `pycups`, OpenCV und `rembg` sind alle
nativ verfügbar. Keine Sprachgrenze im Projekt.

### 5.2 Zustandsautomat

```
IDLE ──[Touch: Start]──> BACKGROUND_SELECT ──[Auswahl]──> COUNTDOWN (5,4,3,2,1)
                                                              │
                                                    CAPTURE (DSLR auslösen)
                                                              │
                                              PROCESSING ("Einen Moment...")
                                                              │
                                                          PREVIEW
                                                       ┌──────┴──────┐
                                                  [Drucken]      [Fertig]
                                                       │              │
                                                   PRINTING ──────────┘
                                                                      │
                                                                    IDLE
```

Regeln:
- Jeder Zustand außer IDLE hat einen Timeout (PREVIEW z. B. 30 s), der nach IDLE zurückführt.
- Das Live-Bild läuft in **allen** Zuständen weiter, auch im Hintergrund von PREVIEW.
- Fehler in CAPTURE, PROCESSING oder PRINTING führen nie in eine Sackgasse: Fehlermeldung
  auf dem Screen, 5 s, zurück nach IDLE.
- Der Zustandsautomat lebt im Backend, nicht im Frontend. Das Frontend ist reine Darstellung
  und bekommt Zustandswechsel per WebSocket gepusht. Bei einem Browser-Reload ist der
  Zustand sofort wiederhergestellt.

### 5.3 Live-Bild-Übertragung

MJPEG über einen HTTP-Endpoint (`multipart/x-mixed-replace`), im Frontend schlicht als
`<img src="/preview/stream">`. Kein WebRTC, kein HLS — die Latenz ist niedriger und die
Komplexität um Größenordnungen geringer. Bei 1280×720 und 25 fps reicht das locker.

Der Stream muss **spiegelverkehrt** dargestellt werden. Menschen erwarten ihr Spiegelbild.
Das gedruckte Foto natürlich nicht spiegeln.

### 5.4 Speicherstruktur

```
/data/events/2026-08-15_hochzeit-mueller/
  originals/   IMG_0001.jpg          ← unverändert von der DSLR, sofort geschrieben
  processed/   IMG_0001_strand.jpg   ← mit Hintergrund/Overlay
  prints/      IMG_0001_print.jpg    ← druckfertig, 4:3 auf 10×15 zugeschnitten
  thumbs/      IMG_0001.jpg
  event.db     ← SQLite: Zeitstempel, Hintergrund, Druckstatus, Fehler
```

Die SQLite-Datei ist die Wahrheit für die Galerie und macht Statistiken hinterher trivial
(„wie viele Bilder, wie viele Drucke, welcher Hintergrund war beliebt").

---

## 6. Drucken — mit den bekannten Fallstricken

Der CP1500 läuft unter Linux über **Gutenprint**, aber nicht mit der Version aus dem
Repository:

- Der CP1500 wurde erst mit einem Gutenprint-Snapshot **nach Oktober 2022** unterstützt
  (5.3.4+). In der Regel musst du Gutenprint selbst kompilieren.
- **`ipp-usb` muss deinstalliert werden**, sonst lässt sich der Drucker in CUPS nicht
  korrekt einrichten (er meldet sich als IPP-Gerät und blockiert den USB-Backend).
- Die CP1300-PPD funktioniert als Notlösung, ist aber nicht die saubere Variante.

**Der wichtigste Punkt für den Live-Betrieb:** Wenn Papier oder Farbband leer sind, geht
die CUPS-Warteschlange in den Zustand *paused*. Der Drucker selbst nimmt den Job nach dem
Nachlegen automatisch wieder auf, **CUPS bleibt aber pausiert** und muss manuell entsperrt
werden. Das darfst du nicht dem Trauzeugen überlassen.

Konsequenz für die Software:

1. Eine eigene Druck-Queue im Backend, nicht direkt in CUPS feuern.
2. Poll des CUPS-Status alle paar Sekunden.
3. Erkennt das Backend „paused", zeigt es im Admin-Bereich groß **„Papier/Farbband prüfen"**
   und bietet einen Button „Drucker fortsetzen" (`cupsenable`), der die Queue entsperrt.
4. In der Gäste-UI wird der Druck-Button in diesem Fall ausgeblendet, mit dem Hinweis
   „Drucken gerade nicht verfügbar — dein Foto ist gespeichert."
5. Nicht gedruckte Jobs bleiben in der Queue und lassen sich später nachdrucken.

Ein Limit für Drucke pro Foto (Default: 1) und ein Tageslimit sind sinnvoll — ein Farbband
reicht für 108 Bilder, ein Gast mit Spaß am Button ist schneller als du denkst.

---

## 7. Boot, Kiosk und Lockdown

### 7.1 Autostart

Zwei systemd-Units:

```ini
# fotobox-backend.service
[Unit]
Description=Fotobox Backend
After=network.target
[Service]
ExecStart=/opt/fotobox/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
```

```ini
# fotobox-kiosk.service
[Unit]
After=fotobox-backend.service
[Service]
ExecStartPre=/opt/fotobox/scripts/wait-for-backend.sh
ExecStart=/usr/bin/cage -- chromium --kiosk --noerrdialogs \
  --disable-infobars --disable-session-crashed-bubble \
  --disable-pinch --overscroll-history-navigation=0 \
  --check-for-update-interval=31536000 http://127.0.0.1:8000
Restart=always
```

`Restart=always` ist hier kein Nice-to-have: Wenn der Browser um 23 Uhr abstürzt, startet er
in drei Sekunden neu und der Zustand kommt vom Backend zurück. Niemand merkt es.

`cage` (Wayland-Kiosk-Compositor) ist deutlich dichter als ein normaler Desktop mit
Chromium darüber — es gibt schlicht keine Fensterverwaltung, aus der man ausbrechen könnte.

### 7.2 Lockdown

- Kein Desktop, kein Taskbar, kein Dateimanager (siehe `cage`)
- Tastatur physisch nicht anschließen; zusätzlich `keyd` oder ähnliches, das die üblichen
  Kombinationen abfängt
- Im Frontend: `contextmenu`, Textselektion, Drag&Drop und Pinch-Zoom per CSS/JS deaktivieren
- Cursor ausblenden (`unclutter` bzw. CSS `cursor: none`)
- Bildschirmschoner und DPMS aus
- **Admin-Zugang:** 5 Sekunden Long-Press in einer festgelegten Bildschirmecke → PIN-Eingabe.
  Keine sichtbare Schaltfläche.

### 7.3 Dateisystem-Robustheit

Nach deinen Erfahrungen mit SD-Karten: Root-Dateisystem als **Overlay (read-only)**
konfigurieren, `/data` als separate, beschreibbare Partition auf der SSD einhängen. Damit
überlebt das System auch einen harten Stromausfall — was auf einer Hochzeit realistisch ist,
wenn jemand über das Kabel stolpert. Zusammen mit der USV ist das Thema erledigt.

Hardware-Watchdog des Pi aktivieren (`/etc/systemd/system.conf`: `RuntimeWatchdogSec=15`).

---

## 8. Netzwerkbetrieb

**Während der Veranstaltung:** kein Netzwerk nötig. Backend lauscht auf `127.0.0.1`, WLAN
kann aus bleiben (spart Strom und Wärme).

**Für den Download danach:** zwei Wege, beide sinnvoll parallel vorzusehen.

1. **Ethernet anstecken.** Der Pi holt sich per DHCP eine Adresse, die Galerie ist unter
   `http://<ip>:8000/gallery` erreichbar — Bilder einzeln oder als ZIP je Event. Das ist der
   Standardweg und braucht keinerlei Extra-Konfiguration.
2. **Access-Point-Modus** (`hostapd` + `dnsmasq`), umschaltbar im Admin-Menü. Nützlich,
   wenn kein Netzwerk verfügbar ist: Gäste oder das Brautpaar verbinden sich direkt mit der
   Box. Bewusst *nicht* automatisch aktiv — ein offener AP während der Feier ist eine
   Einladung für gelangweilte Gäste.

Optional, aber beliebt: QR-Code auf dem Ausdruck, der auf die Einzelbild-URL zeigt. Nur
sinnvoll, wenn der AP läuft oder du die Bilder hinterher hochlädst.

Zusätzlich ein **Export-Button** im Admin-Menü: „Event auf USB-Stick kopieren". Der
verlässlichste Weg, wenn der Fotograf um 2 Uhr nachts die Bilder mitnehmen will.

---

## 9. Umsetzung mit Claude Code

### 9.1 Die entscheidende Weichenstellung: Hardware-Abstraktion

Wenn du auf dem Pi mit angeschlossener Hardware entwickelst, wird das zäh — jeder
Testdurchlauf braucht echte Kamera, echten Drucker, echtes Papier. Baue deshalb von Anfang
an eine Abstraktionsschicht mit austauschbaren Implementierungen:

```python
class CameraBackend(Protocol):
    def capture(self, target_path: Path) -> CaptureResult: ...
    def is_available(self) -> bool: ...

class GPhoto2Camera(CameraBackend): ...   # echte DSLR
class MockCamera(CameraBackend): ...      # liefert Bilder aus einem Testordner
```

Dasselbe für Drucker (Mock schreibt PDF in einen Ordner) und Vorschaukamera (Mock spielt
eine Videodatei in Schleife ab). Umschaltbar per Umgebungsvariable `FOTOBOX_HARDWARE=mock`.

Damit lassen sich **80 % des Projekts am Entwicklungsrechner bauen und testen** — inklusive
kompletter UI, Zustandsautomat und Bildpipeline. Nur die Backend-Implementierungen und die
Systemintegration brauchen den Pi. Für Claude Code ist das der Unterschied zwischen
flüssigem Arbeiten und ständigem Warten auf Hardware.

### 9.2 Repository-Struktur

```
fotobox/
├── CLAUDE.md                    ← Projektkontext für Claude Code
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── state_machine.py
│   │   ├── hardware/            ← camera.py, printer.py, preview.py + Mocks
│   │   ├── pipeline/            ← chroma.py, ai_segment.py, overlay.py, layout.py
│   │   ├── storage.py
│   │   └── config.py
│   └── tests/
├── frontend/                    ← Gäste-UI, Admin-UI, Galerie
├── deploy/
│   ├── systemd/
│   ├── cups/                    ← Gutenprint-Build-Skript, PPD
│   └── setup.sh                 ← idempotentes Provisioning des Pi
├── data/                        ← backgrounds/, events/ (gitignored)
└── docs/
```

### 9.3 CLAUDE.md — was reingehört

- Hardware-Inventar mit exakten Modellbezeichnungen
- Der Hinweis, dass Live-Bild und Aufnahme aus **zwei verschiedenen Kameras** kommen (das
  ist unintuitiv und Claude wird es sonst wiederholt „korrigieren")
- Regel: „Hardwarezugriff nur über `hardware/`-Protokolle, nie direkt aus der Businesslogik"
- Regel: „Jeder neue Zustand im StateMachine braucht einen Timeout"
- Regel: „Das Original wird gespeichert, bevor die Pipeline startet"
- Kommandos für Tests, Lint, lokalen Start mit Mock-Hardware
- Sprache der UI-Texte: Deutsch

### 9.4 Meilensteine

| # | Inhalt | Testbar ohne Hardware |
|---|---|---|
| 1 | Backend-Grundgerüst, StateMachine, WebSocket, Mock-Hardware | ✅ |
| 2 | Gäste-UI: Idle, Countdown, Preview, Kiosk-Verhalten | ✅ |
| 3 | Bildpipeline: Overlay → Chroma-Key → KI-Segmentierung | ✅ |
| 4 | Storage, SQLite, Galerie-Route, ZIP-Export | ✅ |
| 5 | gphoto2-Anbindung, Vorschaukamera, Kalibrierung | ❌ Pi + DSLR |
| 6 | CUPS/Gutenprint, Druck-Queue, Fehlerbehandlung | ❌ Pi + Drucker |
| 7 | Admin-UI, PIN, AP-Umschaltung, USB-Export | teilweise |
| 8 | Deployment: systemd, cage, Overlay-FS, Watchdog | ❌ Pi |
| 9 | Dauertest: 4 h Laufzeit, 100+ Auslösungen, Stecker ziehen | ❌ Pi |

Meilenstein 9 ist kein optionaler Puffer. Ein 4-Stunden-Dauertest mit echtem Papier findet
Speicherlecks, USB-Resets und Temperaturprobleme, die bei zehn Testauslösungen unsichtbar
bleiben.

---

## 10. Risiken und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| gphoto2 verliert die DSLR (USB-Reset) | Reconnect-Logik mit Backoff; `usbreset` als letzte Stufe; UI zeigt „Kamera startet neu" statt Absturz |
| Farbband/Papier leer | Statusüberwachung + Admin-Hinweis; Drucken wird deaktiviert, Aufnahme läuft weiter |
| CUPS-Queue bleibt pausiert | Automatische Erkennung + „Fortsetzen"-Button (siehe Abschnitt 6) |
| Stromausfall | USV + read-only Root-FS |
| Pi überhitzt | Aktivkühler; Gehäuse mit Belüftung; Temperatur im Admin-Screen |
| DSLR-Akku leer | Netzteil/Dummy-Akku, kein Akkubetrieb |
| Speicher voll | Freien Platz überwachen, Warnung ab 90 %; 128 GB reichen für tausende Bilder |
| Gast blockiert die Box | Timeouts in jedem Zustand |
| Chroma-Key versagt bei grüner Kleidung | Overlay-Hintergründe als Alternative immer verfügbar |

---

## 11. Nächste Schritte

1. Kameramodell klären und mit `gphoto2 --list-config` verifizieren, was fernsteuerbar ist
2. Selphy CP1500 unter Raspberry Pi OS zum Laufen bringen (Gutenprint kompilieren,
   `ipp-usb` entfernen) — das ist die Aufgabe mit der höchsten Unsicherheit, deshalb zuerst
3. Repository anlegen, `CLAUDE.md` schreiben, Meilenstein 1–4 mit Mock-Hardware bauen
4. Hardware-Integration auf dem Pi
5. Dauertest mit echtem Verbrauchsmaterial
