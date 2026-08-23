# Fotobox

Autarke Fotobox für Hochzeiten. Raspberry Pi 4, Touchscreen-Kiosk, Nikon-DSLR per gphoto2,
Canon Selphy CP1500. Läuft offline.

## Sprache

- Code, Kommentare, Commits: Englisch
- Alle Texte in der Benutzeroberfläche: **Deutsch**. Wortlaut ausschließlich aus
  `docs/ui-screens.md` übernehmen, nie neu formulieren.
- Dokumentation in `docs/`: Deutsch

## Referenzdokumente — vor der Implementierung lesen

| Datei | Inhalt |
|---|---|
| `docs/api-contract.md` | REST-Endpunkte, WebSocket-Nachrichten, Zustandsnamen |
| `docs/datenmodell.md` | SQLite-Schema, Verzeichnislayout |
| `docs/ui-screens.md` | Screens, exakte deutsche Texte, Verhalten |
| `docs/druck-layout.md` | Pixelmaße, Beschnitt, Rahmenpositionen |
| `docs/meilensteine.md` | Reihenfolge und Abnahmekriterien |
| `docs/konzept.md` | Hintergrund und Begründungen (nicht bei jeder Aufgabe nötig) |

## Harte Regeln

1. **Zwei Kameras.** Das Live-Bild kommt von einer separaten Vorschaukamera
   (Pi Camera Module 3), *nicht* aus der DSLR. Die DSLR wird ausschließlich zum Auslösen
   angesprochen. Das ist Absicht — nicht „korrigieren".
   *Ausnahme seit 2026-08-02:* Läuft die Box ohne zweite Kamera, liefert
   `preview.backend: gphoto2` das Live-Bild aus der Kamera (`app/hardware/gphoto2_preview.py`,
   teilt sich den Kamera-Handle mit dem Auslöser). Das muss **bewusst** eingestellt
   werden — `auto` wählt es nie: bei einer Spiegelreflex (D7200) klappt der Spiegel
   für Live View hoch und leert den Akku in unter einer Stunde. Sinnvoll nur bei
   spiegellosen Kameras (a7 IV). Der Standard bleibt die eigene Vorschaukamera.
2. **Kein Hardwarezugriff außerhalb von `backend/app/hardware/`.** Businesslogik spricht
   nur mit den Protokollen `CameraBackend`, `PrinterBackend`, `PreviewBackend`.
   Kein `subprocess`, kein `gphoto2`, kein `pycups` in `state_machine.py` oder `pipeline/`.
3. **Original zuerst.** In `CAPTURE` wird das unveränderte JPEG nach `originals/`
   geschrieben und der DB-Eintrag angelegt, *bevor* die Pipeline startet. Ein Fehler in der
   Pipeline darf nie zum Verlust des Bildes führen.
4. **Jeder Zustand außer `IDLE` und `ERROR` braucht einen Timeout**, der nach `IDLE`
   zurückführt. Timeout-Werte kommen aus der Config, nie hartkodiert.
   *Ausnahme seit 2026-08-23:* `SCREENSAVER` hat keinen Timeout. Er ist ein
   Ruhezustand wie `IDLE` — nichts ist halb fertig, niemand wartet, verlassen wird
   er durch eine Berührung (`POST /api/session/wake`). Ein Timeout könnte ihn nur
   auf einen Bildschirm zurückwerfen, von dem die Box gerade festgestellt hat,
   dass niemand hinsieht.
5. **Der Zustandsautomat lebt im Backend.** Das Frontend hält keinen eigenen Zustand und
   trifft keine Entscheidungen; es rendert, was per WebSocket kommt.
6. **Keine Konstanten im Code.** Alle Zahlen (Countdown, Timeouts, Limits, Pfade, Pixelmaße)
   stammen aus `config.yaml`, validiert über ein Pydantic-Modell in `app/config.py`.
7. **Kein Netzwerkzugriff zur Laufzeit.** Keine CDNs, keine Google Fonts, keine
   Modell-Downloads. Alles wird beim Deployment lokal abgelegt.
8. **Fehler beenden nie die Session.** Jeder erwartbare Fehler (Kamera weg, Drucker
   pausiert, Pipeline fehlgeschlagen) führt zu einer Meldung und dann nach `IDLE`.

## Stack

Python 3.11, FastAPI, uvicorn, Pydantic v2, SQLite (stdlib `sqlite3`, kein ORM),
OpenCV, Pillow, `python-gphoto2`, `picamera2`, `pycups`, `rembg` (onnxruntime).
Frontend: Vanilla JS + CSS, keine Build-Pipeline, keine npm-Abhängigkeiten.

## Kommandos

```bash
make dev            # Backend mit Mock-Hardware auf :8000
make test           # pytest
make lint           # ruff check + ruff format --check
make fixtures       # Testbilder nach tests/fixtures/ generieren
FOTOBOX_HARDWARE=mock uvicorn app.main:app --reload   # Alternative zu make dev
```

Die Entwicklung findet auf dem Entwicklungsrechner mit `FOTOBOX_HARDWARE=mock` statt.
Nur die Meilensteine 5, 6 und 8 brauchen den Pi.

## Tests

- Zustandsautomat und Pipeline: vollständig testbar, hier keine Lücken lassen
- Hardware-Backends: nur die Mocks werden getestet, die echten nicht
- Jeder Bugfix bekommt vorher einen Test, der ihn reproduziert

## Was nicht gebaut wird

Kein Login, keine Mandanten, keine Cloud-Anbindung, kein Upload zu sozialen Netzwerken,
kein Videomodus, kein GIF/Boomerang. Nicht spekulativ erweitern.
