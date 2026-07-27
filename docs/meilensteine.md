# Meilensteine

Reihenfolge ist verbindlich. Ein Meilenstein gilt als fertig, wenn **alle**
Abnahmekriterien erfüllt sind — nicht, wenn der Code „im Prinzip funktioniert".

Meilensteine 1–4 und 7a laufen vollständig mit `FOTOBOX_HARDWARE=mock` auf dem
Entwicklungsrechner.

---

## M1 — Grundgerüst und Zustandsautomat

**Umfang:** Projektstruktur, Config-Laden, Zustandsautomat, WebSocket, Mock-Hardware,
SQLite-Migrationen.

**Abnahme:**

- [ ] `make dev` startet ohne angeschlossene Hardware, `GET /api/status` liefert `IDLE`
- [ ] Alle in `api-contract.md` gelisteten Übergänge sind implementiert; jeder nicht
      gelistete Übergang wirft `InvalidTransition`
- [ ] Ein Test durchläuft `IDLE → BACKGROUND_SELECT → COUNTDOWN → CAPTURE → PROCESSING →
      PREVIEW → IDLE` ohne echte Hardware
- [ ] Timeouts werden getestet, mit gefälschter Uhr (`freezegun` o. ä.), nicht mit `sleep`
- [ ] Ein WebSocket-Client empfängt bei jedem Übergang `state_changed` mit vollständigem
      Status; in `COUNTDOWN` kommen genau `countdown.duration_seconds` × `countdown_tick`
- [ ] `sqlite3 /data/fotobox.db ".schema"` entspricht `datenmodell.md`
- [ ] Ein ungültiger Wert in `config.yaml` führt zu einer verständlichen Fehlermeldung
      beim Start, nicht zu einem Traceback tief in der Anwendung
- [ ] `make lint` und `make test` sind grün

---

## M2 — Gäste-UI

**Umfang:** Alle Screens aus `ui-screens.md`, MJPEG-Anzeige, WebSocket-Anbindung,
Kiosk-Verhalten im Browser.

**Abnahme:**

- [ ] Jeder Screen aus `ui-screens.md` existiert mit **wortgleichen** deutschen Texten
- [ ] Der komplette Ablauf ist mit der Maus im Desktop-Chromium durchspielbar
- [ ] Das Live-Bild ist gespiegelt, das Ergebnisfoto nicht
- [ ] Rechtsklick, Textselektion, Doppeltipp-Zoom und Pinch sind deaktiviert
- [ ] Bei getrenntem Backend erscheint das Reconnect-Overlay; nach Neustart des Backends
      ist die UI ohne Reload wieder im korrekten Zustand
- [ ] Ein Reload mitten in `PREVIEW` stellt genau `PREVIEW` wieder her, nicht `IDLE`
- [ ] Keine externe Ressource wird geladen — im Netzwerktab des Browsers erscheint keine
      Anfrage außerhalb von `localhost`
- [ ] Bedienung mit einem Finger auf 1280 × 800 vollständig möglich, alle Ziele ≥ 120 px

---

## M3 — Bildpipeline

**Umfang:** Overlay, Chroma-Key, KI-Segmentierung, Komposition, Rahmentext, QR-Code.
Reihenfolge einhalten: erst Overlay (trivial), dann Chroma, dann KI.

**Abnahme:**

- [ ] `tests/fixtures/` enthält mindestens 12 Testbilder: gute und schlechte
      Greenscreen-Ausleuchtung, Einzelperson, Gruppe, dunkle Kleidung, weißes Kleid,
      lange Haare, Brille, grünes Kleidungsstück (Negativfall)
- [ ] Overlay-Modus: Ausgabe pixelgenau 1248 × 1872, Overlay deckungsgleich
- [ ] Chroma-Modus: auf den gut ausgeleuchteten Fixtures kein sichtbarer grüner Saum an
      Haaren und Kleiderkanten (visuelle Abnahme, Referenzbilder in `tests/expected/`)
- [ ] Chroma-Modus: das Bild mit grünem Kleidungsstück erzeugt erwartungsgemäß Löcher —
      dokumentiert, kein Bug
- [ ] KI-Modus: läuft mit lokalem ONNX-Modell ohne Netzwerkzugriff
- [ ] Pipeline-Laufzeit auf dem Entwicklungsrechner protokolliert (`pipeline_ms`)
- [ ] Rahmentext ist im sicheren Bereich, mit Schatten lesbar auf hellem und dunklem Grund
- [ ] Ein Fehler in der Pipeline lässt das Original unangetastet und setzt
      `pipeline_status='failed'`
- [ ] Regressionstest: jede Pipeline-Variante erzeugt für ein festes Eingabebild ein
      Ergebnis, das dem Referenzbild bis auf eine Toleranz entspricht

---

## M4 — Storage, Galerie, Export

**Abnahme:**

- [ ] Verzeichnisstruktur wie in `datenmodell.md`, Dateinamen `IMG_{id:04d}.jpg`
- [ ] `GET /gallery` zeigt alle Bilder des Events, Umschalter Original/Bearbeitet
- [ ] ZIP-Download wird **gestreamt** — nachweisbar dadurch, dass der Speicherverbrauch
      des Prozesses bei 500 Bildern nicht messbar steigt
- [ ] Ein Neustart mit `pipeline_status='pending'` in der DB holt die Pipeline nach
- [ ] Speicherwarnung ab `storage.warn_threshold_percent`
- [ ] Ein Event mit 500 erzeugten Testbildern lädt die Galerie in unter 2 s (paginiert)

---

## M5 — Kameraanbindung *(braucht Pi + DSLR + Vorschaukamera)*

**Vorbedingung:** Kameramodell geklärt, `gphoto2 --list-config` ausgewertet.

**Abnahme:**

- [ ] `gphoto2 --auto-detect` erkennt die Kamera; Modellname steht in `GET /api/status`
- [ ] 50 aufeinanderfolgende Auslösungen ohne manuellen Eingriff, Zeit pro Auslösung
      protokolliert (Erwartung: 2–4 s bis zum Download)
- [ ] USB-Kabel im Betrieb abziehen → UI zeigt „Kleine Pause", Wiederanstecken →
      Betrieb ohne Neustart wieder aufgenommen
- [ ] Vorschaukamera liefert ≥ 20 fps bei 1280 × 720; der Stream reißt während einer
      DSLR-Auslösung **nicht** ab
- [ ] Kalibrierung gespeichert und über einen Neustart hinweg wirksam
- [ ] DSLR läuft über Netzteil/Dummy-Akku, nicht über Akku

---

## M6 — Drucken *(braucht Pi + Selphy CP1500)*

Der Meilenstein mit der höchsten Unsicherheit. Zeitpuffer einplanen.

**Abnahme:**

- [ ] Gutenprint (≥ 5.3.4 bzw. Snapshot nach 2022-10-10) kompiliert; das Build-Skript in
      `deploy/cups/` ist idempotent und wiederholbar
- [ ] `ipp-usb` entfernt, Drucker in CUPS als USB-Gerät eingerichtet
- [ ] Randloser Testdruck im Postkartenformat, Motiv sitzt mittig, Rahmentext vollständig
      sichtbar — **am echten Ausdruck geprüft, nicht am Bildschirm**
- [ ] Papier während eines Jobs entnehmen → UI blendet Drucken aus, Aufnahme läuft weiter
- [ ] Papier nachlegen → Admin-Button `Drucker fortsetzen` entsperrt die Queue, der Job
      läuft durch. Das ist das zentrale Kriterium dieses Meilensteins.
- [ ] Bandende erkannt und im Admin gemeldet
- [ ] 20 Drucke hintereinander, Warteschlangenlänge korrekt angezeigt
- [ ] `PRINTING` blockiert die Session nicht — der nächste Gast kann starten, während
      gedruckt wird

---

## M7 — Admin, Netzwerk, Export

**7a (ohne Hardware):** Admin-UI, PIN, Konfigurationsänderung zur Laufzeit
**7b (Pi):** AP-Umschaltung, USB-Export, Shutdown

**Abnahme:**

- [ ] Long-Press in der Ecke + PIN öffnet den Admin; falsche PIN sperrt nach 5 Versuchen
- [ ] Ohne PIN ist kein `/api/admin/`-Endpunkt erreichbar (Test je Endpunkt)
- [ ] Geänderte Countdown-Dauer wirkt sofort, ohne Neustart
- [ ] AP-Modus einschalten → Verbindung von einem Handy → Galerie erreichbar
- [ ] AP-Modus ausschalten → Ethernet → Galerie über die LAN-IP erreichbar
- [ ] USB-Export kopiert ein vollständiges Event und meldet Fortschritt
- [ ] `Herunterfahren` fährt sauber herunter (Dateisystem intakt nach Wiedereinschalten)

---

## M8 — Deployment *(Pi)*

**Abnahme:**

- [ ] `deploy/setup.sh` bringt einen frischen Pi-OS-Stand vollständig in Betrieb und ist
      zweimal hintereinander ausführbar, ohne etwas kaputtzumachen
- [ ] Kaltstart → Kiosk-Oberfläche in `IDLE`, ohne Tastatur, ohne Eingriff, < 60 s
- [ ] `systemctl kill chromium` → Kiosk ist binnen 5 s zurück, Zustand erhalten
- [ ] `systemctl kill uvicorn` → Backend zurück, UI reconnected
- [ ] Root-Dateisystem read-only; `touch /etc/test` schlägt fehl, `touch /data/test` nicht
- [ ] Stecker ziehen im laufenden Betrieb, 10× → Dateisystem und DB jedes Mal intakt
- [ ] Watchdog aktiv (`RuntimeWatchdogSec`)
- [ ] Kein Bildschirmschoner, kein DPMS, kein Update-Dialog

---

## M9 — Dauertest

Kein optionaler Puffer. Findet die Fehler, die alle vorherigen Meilensteine nicht finden.

**Abnahme:**

- [ ] 4 Stunden Dauerbetrieb ohne Neustart
- [ ] ≥ 100 Auslösungen, davon ≥ 30 echte Drucke mit echtem Papier
- [ ] Speicherverbrauch des Backends am Ende nicht höher als nach 30 Minuten (kein Leck)
- [ ] CPU-Temperatur bleibt unter 75 °C
- [ ] Kein `gphoto2`-Fehler, der manuellen Eingriff erfordert
- [ ] Mindestens einmal währenddessen: Papier leer laufen lassen, nachlegen, weitermachen
- [ ] Mindestens fünf echte Testpersonen bedienen die Box ohne Erklärung erfolgreich
- [ ] Fehlerliste aus `events_log` durchgesehen und bewertet

Der letzte Punkt ist der wichtigste des ganzen Projekts. Was fünf nüchterne Testpersonen
missverstehen, missverstehen hundert Gäste um Mitternacht garantiert.
