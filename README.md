# Fotobox

Autarke Fotobox für Hochzeiten auf einem Raspberry Pi mit Touchscreen-Kiosk.
Löst eine Nikon-DSLR (über gphoto2) aus, zeigt ein Live-Bild von einer separaten
USB-Vorschaukamera, bearbeitet das Foto (Greenscreen/KI/Rahmen) und druckt es auf
einem Canon Selphy CP1500. **Läuft komplett offline.**

## Funktionen

- Touch-Bedienung: antippen → Countdown → Auslösen → Vorschau → Drucken
- Zwei Kameras: DSLR nur zum Auslösen, Pi-/USB-Kamera fürs Live-Bild
  (fällt bei fehlender DSLR automatisch auf die Vorschaukamera zurück)
- Bildpipeline: Chroma-Key (Greenscreen), KI-Freistellung (rembg), Overlay- und
  Rahmen-/Passepartout-Modus mit eigenen PNGs
- Randloser Postkartendruck (Gutenprint), Druck-Zähler und Warteschlange
- Galerie: am Bildschirm und im Gäste-WLAN, Einzelansicht mit Wischen, Nachdrucken,
  Mehrfachauswahl mit ZIP-Download
- Bildschirmschoner: zeigt nach einigen Minuten die Bilder des Abends; die erste
  Berührung weckt nur auf, sie löst kein Foto aus
- Admin-Bereich (PIN): Kamera-/Drucker-Status, Hintergründe hochladen, Gäste-WLAN
  (auch automatisch, wenn kein Netz da ist), Bildschirmtastatur für den Touchbetrieb,
  Verwaltung aller Veranstaltungen, USB-Export, Neustart/Herunterfahren
- Netzwerkdrucker: die Box gibt den Selphy im Heimnetz frei — AirPrint und Mopria
  ohne Treiberinstallation
- Zwei Betriebsarten: Fotobox oder **Druckermodus** (nur Netzwerkdrucker, kein
  Kiosk, kein Live-Bild). Umschalten im Admin; zurück geht es auch dadurch, dass
  man eine Kamera ansteckt
- Robust für den Dauerbetrieb: Zustandsautomat mit Timeouts im Backend,
  read-only Root gegen SD-Korruption, Hardware-RTC für korrekte Zeit ohne Netz

## Technik

Python 3.11+, FastAPI/uvicorn, Pydantic v2, SQLite (ohne ORM), OpenCV, Pillow,
python-gphoto2, pycups, rembg/onnxruntime. Frontend: Vanilla JS/CSS, kein Build.

## Installation

Ein Kommando auf einem frischen Raspberry Pi (4 oder 5, Raspberry Pi OS Trixie 64-bit):

```bash
git clone <REPO-URL> /home/pi/fotobox
cd /home/pi/fotobox
bash deploy/install.sh --with-printer --with-rtc --yes
```

Vollständige Anleitung (inkl. Pi-5-Hinweise, read-only Root, KI-Modell):
[`docs/installation.md`](docs/installation.md).
Bedienung: [`docs/bedienungsanleitung.md`](docs/bedienungsanleitung.md).

## Gehäuse (3D-Druck)

Ein zweiteiliges, parametrisches Pi‑4‑Gehäuse mit 50‑mm‑Lüfter (inkl. Aussparung
für das DS1307‑RTC‑Modul auf dem GPIO‑Stecker) liegt unter
[`hardware/pi4-fan-case/`](hardware/pi4-fan-case/) — OpenSCAD‑Quelle plus fertige
STL/3MF, Druck- und Montagehinweise in der dortigen README. Zwei Varianten:
Lüfter oben aufgeschraubt und verschraubter Deckel, oder Lüfter innen mit
Klipsdeckel. Beide mit Anschraublaschen und Füßen für die Montage auf einer
Platte.

Dazu eine **Schaltbox** (`hardware/schaltbox/`): Einbaugehäuse für das
Halbleiterrelais der Fotolampe, Feinsicherung, drei Euro-Steckdosen und die
Kabeleinführung — innen durch einen Steg in Netz- und Steuerseite geteilt.

## Entwicklung

```bash
make dev     # Backend mit Mock-Hardware auf :8000
make test    # pytest
make lint    # ruff
```

Weitere Referenzdokumente in [`docs/`](docs/) (API-Vertrag, Datenmodell, UI-Screens,
Druck-Layout, Konzept).

## Lizenz

[MIT](LICENSE).
