# API-Kontrakt

Verbindlich. Änderungen hier ziehen Änderungen in Frontend und Tests nach sich —
nichts still abweichen lassen.

## Grundregeln

- **Alle Aktionen des Clients laufen über REST (POST).** Der WebSocket ist einseitig:
  Server → Client. Damit gibt es genau einen Pfad, auf dem Zustand verändert wird.
- Alle Zeitstempel sind ISO 8601 mit Zeitzone (`2026-08-15T21:14:03+02:00`).
- Alle Antworten sind JSON, außer Bild- und Streamendpunkten.
- Fehler: HTTP-Statuscode plus `{"error": {"code": "...", "message": "..."}}`.
  `message` ist auf Deutsch und darf direkt angezeigt werden.

## Zustände

Genau diese Literale, `SCREAMING_SNAKE_CASE`:

```
IDLE  SCREENSAVER  BACKGROUND_SELECT  COUNTDOWN  CAPTURE  PROCESSING  PREVIEW
PRINTING  ERROR
```

Erlaubte Übergänge:

| von | nach | Auslöser |
|---|---|---|
| `IDLE` | `BACKGROUND_SELECT` | `POST /api/session/start` |
| `BACKGROUND_SELECT` | `COUNTDOWN` | `POST /api/session/background` |
| `BACKGROUND_SELECT` | `IDLE` | Abbruch oder Timeout |
| `COUNTDOWN` | `CAPTURE` | Countdown abgelaufen |
| `COUNTDOWN` | `IDLE` | Abbruch |
| `CAPTURE` | `PROCESSING` | Auslösung erfolgreich |
| `CAPTURE` | `ERROR` | Auslösung fehlgeschlagen |
| `PROCESSING` | `PREVIEW` | Pipeline fertig |
| `PROCESSING` | `ERROR` | Pipeline fehlgeschlagen |
| `PREVIEW` | `PRINTING` | `POST /api/session/print` |
| `PREVIEW` | `IDLE` | `POST /api/session/finish` oder Timeout |
| `PRINTING` | `PREVIEW` | Job an CUPS übergeben |
| `PRINTING` | `ERROR` | Übergabe fehlgeschlagen |
| `ERROR` | `IDLE` | nach `timeouts.error_seconds` |
| `IDLE` | `SCREENSAVER` | nach `screensaver.after_seconds` ohne Bedienung |
| `SCREENSAVER` | `IDLE` | `POST /api/session/wake` (Berührung) |

Jeder andere Übergang ist ein Programmfehler und wirft `InvalidTransition`.

`SCREENSAVER` hat als einziger Zustand neben `IDLE` und `ERROR` **keinen Timeout**
(Abweichung von CLAUDE.md Regel 4, bewusst): Er ist ein Ruhezustand, kein Schritt
in einer Sitzung. Nichts ist halb fertig, niemand wartet, und verlassen wird er
durch eine Berührung. Ein Timeout könnte ihn nur auf einen Bildschirm
zurückwerfen, von dem die Box gerade festgestellt hat, dass niemand hinsieht.

Der Statusblock enthält in `SCREENSAVER` zusätzlich
`screensaver: {photos: [...], interval_ms, fade_ms}` — die Reihenfolge ist
gemischt und wird im Backend gewürfelt (Regel 5).

`BACKGROUND_SELECT` ist standardmäßig deaktiviert (`ui.background_select_enabled: false`):
`IDLE` geht direkt nach `COUNTDOWN` mit dem Hintergrund aus `ui.default_background`.
Dessen Wert `auto` (Standard) heißt „der vorhandene Rahmen" — der erste aktive Eintrag,
der nicht `none` ist. Gibt es keinen, wird ohne Rahmen fotografiert.

---

## REST — Gästebetrieb

### `GET /api/status`

Vollständiger Zustand. Beim Laden der Seite einmal abrufen, danach reicht der WebSocket.

```json
{
  "state": "IDLE",
  "session": null,
  "printer": {
    "available": true,
    "state": "idle",
    "paused": false,
    "message": null
  },
  "camera": { "available": true, "model": "Nikon D7000", "fallback": false },
  "preview": { "available": true },
  "event": { "id": 1, "name": "Hochzeit Müller", "photo_count": 142 },
  "storage": { "free_bytes": 84327194624, "warning": false }
}
```

`session` ist im Zustand `IDLE` `null`, sonst:

```json
{
  "photo_id": 143,
  "background_id": "strand",
  "countdown_remaining": 3,
  "processed_url": "/api/photos/143/processed",
  "print_count": 0,
  "print_allowed": true,
  "print_hint": null
}
```

`printer.state`: `idle` | `printing` | `error` | `offline`

`print_hint` nennt auf Deutsch den Grund, warum `print_allowed` false ist
(aufgebrauchtes Kontingent, Foto schon gedruckt, Drucken abgeschaltet, oder der
Druckergrund) — sonst `null`. `GET /api/admin/printer` liefert zusätzlich
`quota_used`/`quota_total`.

`printer.message` nennt auf Deutsch den Grund, warum nicht gedruckt werden kann
(`Kein Papier`, `Farbband verbraucht`, `Papierstau`, `Klappe offen`,
`Drucker nicht erreichbar`, `Warteschlange angehalten`) — sonst `null`.

`camera.fallback` ist `true`, wenn die DSLR fehlt und die Vorschaukamera als Ersatz
auslöst (`camera.fallback_to_preview`). Die Box fotografiert dann weiter, sagt es aber —
eine stille Umschaltung hat schon einmal einen ganzen Testlauf gekostet.

Die Druckzähler stehen nicht im Gäste-Status, sondern nur unter
`GET /api/admin/printer` und `GET /api/admin/system`:

- `prints_done_event` — erfolgreich gedruckte Aufträge des aktiven Events, gezählt
  aus `print_jobs` mit `status = 'done'`
- `prints_total` — laufende Gesamtzahl seit dem letzten Zurücksetzen, persistent in
  der Tabelle `counters`

Beides zählt nur tatsächlich fertiggestellte Drucke. Den Status pflegt eine
Abgleichschleife nach, die im Takt von `hardware.printer.status_poll_seconds` die
offenen Aufträge bei CUPS abfragt. Ist ein Auftrag aus der CUPS-Historie verschwunden,
bleibt er offen statt geraten zu werden.

### `GET /api/backgrounds`

```json
{
  "backgrounds": [
    {
      "id": "strand",
      "name": "Strand",
      "mode": "chroma",
      "thumbnail_url": "/api/backgrounds/strand/thumbnail",
      "enabled": true,
      "sort_order": 10
    }
  ]
}
```

`mode`: `chroma` | `ai` | `overlay` | `frame` | `none`

`frame`: das Foto wird in den transparenten Fensterbereich eines `overlay.png`
eingepasst (Passepartout) und der Rahmen darübergelegt. Das Fenster wird aus der
Transparenz des PNG erkannt (oder per `window: [x, y, w, h]` in der `config.json`
gesetzt); `fit` (`cover` | `contain`) und `background_color` sind optional.

### `GET /api/backgrounds/{id}/thumbnail`

JPEG, 400×267 px.

### `POST /api/session/start`

Kein Body. `IDLE` → `BACKGROUND_SELECT`.
`409` mit Code `invalid_state`, wenn nicht in `IDLE`.

### `POST /api/session/background`

```json
{ "background_id": "strand" }
```

`BACKGROUND_SELECT` → `COUNTDOWN`. `404` bei unbekannter oder deaktivierter ID.

### `POST /api/session/cancel`

Kein Body. Aus `BACKGROUND_SELECT` oder `COUNTDOWN` zurück nach `IDLE`.
In allen anderen Zuständen `409`.

### `POST /api/session/print`

Kein Body. `PREVIEW` → `PRINTING` → `PREVIEW`.

- `409 print_limit_reached`, wenn `print_count >= printing.max_per_photo`
- `409 printer_unavailable`, wenn `printer.available` false ist
- `409 daily_limit_reached`, wenn `printing.max_per_event` erreicht ist

### `POST /api/session/finish`

Kein Body. `PREVIEW` → `IDLE`.

### `POST /api/session/wake`

Kein Body. `SCREENSAVER` → `IDLE`. Beendet nur die Diaschau und startet
**keine** Sitzung: Der erste Tipp holt den Startbildschirm zurück, erst der
zweite löst ein Foto aus. Außerhalb von `SCREENSAVER` → `409 invalid_state`.

### `GET /preview/stream`

MJPEG, `multipart/x-mixed-replace; boundary=frame`. Läuft dauerhaft, unabhängig vom
Zustand. Auflösung und Bildrate aus `preview.*`. **Nicht** gespiegelt — das Spiegeln
macht das Frontend per CSS (`transform: scaleX(-1)`).

Ist die Vorschaukamera nicht verfügbar, liefert der Endpoint ein Standbild
(`assets/preview-unavailable.jpg`) statt eines Fehlers, damit die UI nicht bricht.

Die Bildquelle bestimmt `hardware.preview.backend`: `v4l2` (USB-Webcam), `picamera2`
(noch nicht gebaut) oder `gphoto2` — Live-Bild aus der DSLR für den Fall, dass gar keine
zweite Kamera angeschlossen ist. `auto` bevorzugt weiterhin eine echte Vorschaukamera
und greift erst zur DSLR, wenn keine da ist.

### Captive Portal (nur im Access-Point-Modus)

Die Prüf-URLs, mit denen Handys eine neue WLAN-Verbindung testen
(`/generate_204`, `/hotspot-detect.html`, `/connecttest.txt` u. a.), antworten
Clients **aus dem AP-Subnetz** mit `302` auf `/gallery`; jeder unbekannte Pfad
ebenso. Damit öffnet sich die Galerie beim Verbinden von selbst. Außerhalb des
AP-Subnetzes bleibt ein `404` ein `404` und die Prüf-URLs liefern `204`.
Schalter: `network.access_point.captive_portal` (Standard an). Voraussetzung ist
der DNS-Umbieger, den der AP-Start schreibt, und Port **80**.

### `POST /api/photos/{id}/print`

Druckt ein gespeichertes Foto erneut (Galerie-Nachdruck), unabhängig von einer
laufenden Sitzung — der Zustandsautomat bleibt unberührt. `?variant=processed`
(Standard) druckt die Fassung mit Rahmen, `?variant=original` das unbearbeitete
Bild — was die Galerie gerade zeigt, kommt auch aus dem Drucker. Antwort:
`{"queued": true, "photo_id": 143, "job_id": 17, "quota_used": 111, "quota_total": 219}`.

- `404 unknown_photo` — Foto gibt es nicht (oder gelöscht)
- `404 no_printable` — keine Druckfassung vorhanden
- `409 printer_unavailable` — `message` nennt den Grund (`Kein Papier`, …)
- `409 daily_limit_reached` — `printing.max_per_event` erreicht
- `404`, wenn `network.gallery_enabled` false ist

Geprüft wird das Event-Kontingent, **nicht** `max_per_photo`: das begrenzt nur
mehrfaches Tippen auf derselben Vorschau.

### `GET /api/photos/{id}/{variant}`

`variant`: `original` | `processed` | `print` | `thumb`. Liefert JPEG.
`404`, wenn die Variante noch nicht existiert.

---

## WebSocket `/ws`

Server → Client. Jede Nachricht: `{"type": "...", "payload": {...}, "ts": "..."}`.
Der Client sendet nichts außer Ping-Frames.

| `type` | `payload` | wann |
|---|---|---|
| `state_changed` | vollständiges Objekt aus `GET /api/status` | bei jedem Zustandswechsel **und** wenn sich die Verfügbarkeit von Kamera/Drucker/Vorschau ändert (damit der Kiosk „Kleine Pause" von selbst verlässt) |
| `countdown_tick` | `{"remaining": 3}` | jede Sekunde in `COUNTDOWN` |
| `photo_ready` | `{"photo_id": 143, "processed_url": "..."}` | Pipeline fertig |
| `print_started` | `{"photo_id": 143, "job_id": 17}` | Job an CUPS übergeben |
| `print_finished` | `{"photo_id": 143, "job_id": 17, "success": true}` | Job durch |
| `printer_status` | Objekt wie `status.printer` | bei Änderung, max. 1×/s |
| `system_status` | `{"cpu_temp": 61.2, "free_bytes": 8432719, "warnings": []}` | alle 30 s |
| `error` | `{"code": "camera_timeout", "message": "Kamera antwortet nicht"}` | bei Fehler |

Bei Verbindungsabbruch reconnected der Client mit Backoff (1 s, 2 s, 4 s, max. 10 s) und
holt danach einmal `GET /api/status`.

`state_changed` schickt bewusst den kompletten Status statt eines Diffs. Der Zustandsraum
ist klein, und Teilaktualisierungen sind eine verlässliche Quelle für Inkonsistenzen.

---

## REST — Admin

Alle Endpunkte unter `/api/admin/` brauchen den Header `X-Fotobox-Pin`.
Falsche PIN: `401`. Nach 5 Fehlversuchen 60 s Sperre.

| Methode | Pfad | Zweck |
|---|---|---|
| `POST` | `/api/admin/auth` | PIN prüfen, Session-Token setzen |
| `GET` | `/api/admin/system` | CPU-Temperatur, Speicher, Uptime, Versionen |
| `POST` | `/api/admin/printer/resume` | `cupsenable` — Queue nach Papierfehler entsperren |
| `POST` | `/api/admin/printer/cancel-all` | Warteschlange leeren |
| `POST` | `/api/admin/printer/counter-reset` | Laufenden Druckzähler auf 0 setzen |
| `POST` | `/api/admin/printer/test-page` | Testdruck |
| `GET`/`PUT` | `/api/admin/config` | Laufzeitkonfiguration lesen/schreiben |
| `GET`/`POST` | `/api/admin/cameras` | Erkannte Geräte + Auswahl lesen / Auswahl ändern |
| `POST` | `/api/admin/camera/rescan` | Erneut suchen — für eine nach dem Start angeschlossene Kamera |
| `POST` | `/api/admin/camera/reset` | USB-Reset der DSLR + Vorschaugerät neu öffnen, danach suchen |
| `POST` | `/api/admin/camera/testshot` | Probefoto (nicht im Event): `{model, width, height, fallback}` |
| `GET` | `/api/admin/camera/testshot.jpg` | Das zuletzt aufgenommene Probefoto |
| `POST` | `/api/admin/calibration` | Crop/Offset Vorschau ↔ DSLR speichern |
| `POST` | `/api/admin/event` | Neues Event anlegen und aktiv setzen |
| `GET` | `/api/admin/backgrounds` | Alle hochgeladenen Hintergründe/Rahmen (inkl. deaktivierte) |
| `POST` | `/api/admin/backgrounds` | Hintergrund/Rahmen hochladen (multipart: `name`, `mode`, `file`) |
| `DELETE` | `/api/admin/backgrounds/{id}` | Hintergrund/Rahmen löschen |
| `GET` | `/api/admin/network` | Aktueller Netzwerkzustand (AP ein/aus, IP, SSID) |
| `POST` | `/api/admin/network/ap` | Access-Point-Modus ein/aus (`{"enabled": true}`) |
| `POST` | `/api/admin/network/ap-auto` | `{enabled}` — Gäste-AP bei fehlendem Netz von selbst einschalten; nur die Regel, kein Funkwechsel |
| `POST` | `/api/admin/photos/delete` | `{ids: [12,13]}` — als gelöscht markieren; Dateien bleiben |
| `GET` | `/api/admin/photos/deleted` | `{count, bytes}` — was ein endgültiges Entfernen freigäbe |
| `POST` | `/api/admin/photos/purge` | Dateien der markierten Bilder endgültig entfernen |
| `POST` | `/api/admin/events/{id}/rerender` | Pipeline erneut über alle Bilder eines Events; 409 `rerender_busy` |
| `GET` | `/api/admin/rerender` | Fortschritt `{running, finished, done, failed, total, event, error}` |
| `POST` | `/api/admin/export/usb` | Aktives Event auf USB-Stick kopieren (startet Hintergrund-Kopie) |
| `GET` | `/api/admin/export/usb` | Fortschritt des laufenden/letzten Exports |
| `POST` | `/api/admin/shutdown` | Sauberes Herunterfahren |
| `POST` | `/api/admin/reboot` | Sauberer Neustart |
| `POST` | `/api/admin/reprint/{photo_id}` | Nachdruck außerhalb einer Session |

`GET /api/admin/network` → `{"ap_enabled": false, "ssid": "Fotobox", "ip": "192.168.0.134"}`.
Die Galerie-URL baut der Client aus `ip` und dem eigenen Port.

`POST /api/admin/network/ap` schaltet den Gäste-Access-Point auf `wlan0`. Beim
Einschalten bricht die normale WLAN-Verbindung ab — bedienbar nur am Touchscreen
(ein Neustart kehrt immer ins Heimnetz zurück, das AP-Profil hat `autoconnect=no`).

`POST /api/admin/export/usb` startet die Kopie im Hintergrund und antwortet sofort
mit `{"started": true, "total": 340, "device": "/dev/sda1"}`. `409 no_usb`, wenn
kein Stick gefunden wird; `409 export_busy`, wenn bereits ein Export läuft.
`GET /api/admin/export/usb` liefert den Fortschritt:

```json
{
  "running": true, "finished": false, "done": 42, "total": 340,
  "bytes": 128934912, "event": "Hochzeit Müller",
  "target": "/media/fotobox-export/Fotobox_2026-08-15_hochzeit-mueller", "error": null
}
```

`PUT /api/admin/config` schreibt nur Schlüssel unter `ui`, `countdown`, `timeouts` und
`printing` zurück. Hardware- und Pfadeinstellungen sind zur Laufzeit nicht änderbar.

---

## REST — Galerie (nach der Veranstaltung)

Erreichbar unter `/gallery`, ohne PIN, nur wenn `network.gallery_enabled` true ist.

| Methode | Pfad | Zweck |
|---|---|---|
| `GET` | `/api/events` | Liste aller Events mit Bildzahl |
| `GET` | `/api/events/{id}/photos` | Paginiert, `?page=1&per_page=60` |
| `GET` | `/api/events/{id}/download.zip` | Streaming-ZIP, `?variant=processed\|original\|both`, optional `?ids=12,13` für eine Auswahl |

Das ZIP wird gestreamt, nicht zwischengespeichert — bei 1000 Bildern ist die
Zwischendatei sonst größer als der freie Platz.
