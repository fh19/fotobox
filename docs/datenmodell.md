# Datenmodell

## Verzeichnislayout

```
/data/
├── fotobox.db                     ← eine DB über alle Events
├── config.yaml                    ← Laufzeitkonfiguration
├── backgrounds/
│   └── strand/
│       ├── background.jpg         ← 1872×1248 oder größer
│       ├── overlay.png            ← optional, mit Alphakanal
│       ├── thumbnail.jpg          ← 400×267, wird bei Bedarf generiert
│       └── config.json
├── events/
│   └── 2026-08-15_hochzeit-mueller/
│       ├── originals/  IMG_0143.jpg
│       ├── processed/  IMG_0143.jpg
│       ├── prints/     IMG_0143.jpg
│       └── thumbs/     IMG_0143.jpg
└── logs/
    └── fotobox.log                ← rotierend, max. 50 MB
```

Der Ordnername eines Events ist `{ISO-Datum}_{slug}` und wird beim Anlegen aus dem Namen
abgeleitet. Der Dateiname `IMG_{photo_id:04d}.jpg` ist über alle Varianten identisch —
damit ist jede Datei ohne DB-Zugriff zuordenbar.

`/data` liegt auf der beschreibbaren Partition. Das Root-Dateisystem ist read-only
(Overlay); nichts außerhalb von `/data` darf zur Laufzeit geschrieben werden.

## `backgrounds/*/config.json`

```json
{
  "name": "Strand",
  "mode": "chroma",
  "enabled": true,
  "sort_order": 10,
  "overlay": "overlay.png",
  "chroma": {
    "hue_center": 60,
    "hue_tolerance": 25,
    "saturation_min": 60,
    "value_min": 40,
    "spill_suppression": 0.7,
    "edge_feather_px": 2
  }
}
```

Alle Schlüssel außer `name` und `mode` sind optional; fehlende Werte kommen aus
`pipeline.chroma_defaults` in der Config. Bei `mode: "ai"` wird der `chroma`-Block
ignoriert, bei `mode: "overlay"` zusätzlich `background.jpg`.

Der Ordner wird beim Start eingelesen und per Watchdog auf Änderungen überwacht — neue
Hintergründe erscheinen ohne Neustart. Ein fehlerhaftes `config.json` deaktiviert nur
diesen einen Hintergrund und schreibt eine Warnung ins Log; es darf den Start nicht
verhindern.

## SQLite-Schema

`PRAGMA journal_mode=WAL` und `PRAGMA synchronous=FULL`. WAL wegen paralleler Lesezugriffe
der Galerie, `synchronous=FULL` weil ein Stromausfall realistisch ist und die paar
Millisekunden pro Foto irrelevant sind.

```sql
CREATE TABLE schema_version (
    version     INTEGER NOT NULL
);

CREATE TABLE events (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    directory   TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL,
    closed_at   TEXT,
    is_active   INTEGER NOT NULL DEFAULT 0
);

-- Genau ein aktives Event
CREATE UNIQUE INDEX idx_events_active ON events(is_active) WHERE is_active = 1;

CREATE TABLE photos (
    id              INTEGER PRIMARY KEY,
    event_id        INTEGER NOT NULL REFERENCES events(id),
    filename        TEXT    NOT NULL,          -- IMG_0143.jpg
    captured_at     TEXT    NOT NULL,
    background_id   TEXT,                      -- NULL = ohne Hintergrund
    background_mode TEXT,                      -- chroma | ai | overlay | none
    pipeline_status TEXT    NOT NULL,          -- pending | ok | failed
    pipeline_error  TEXT,
    pipeline_ms     INTEGER,
    camera_model    TEXT,
    width           INTEGER,
    height          INTEGER,
    deleted         INTEGER NOT NULL DEFAULT 0,
    UNIQUE (event_id, filename)
);

CREATE INDEX idx_photos_event ON photos(event_id, captured_at);

CREATE TABLE print_jobs (
    id            INTEGER PRIMARY KEY,
    photo_id      INTEGER NOT NULL REFERENCES photos(id),
    cups_job_id   INTEGER,
    requested_at  TEXT    NOT NULL,
    finished_at   TEXT,
    status        TEXT    NOT NULL,            -- queued | printing | done | failed | cancelled
    error         TEXT,
    is_reprint    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_print_jobs_photo ON print_jobs(photo_id);

CREATE TABLE counters (
    name  TEXT    PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE events_log (
    id         INTEGER PRIMARY KEY,
    ts         TEXT NOT NULL,
    level      TEXT NOT NULL,                  -- info | warning | error
    component  TEXT NOT NULL,                  -- camera | printer | pipeline | system
    code       TEXT NOT NULL,
    message    TEXT NOT NULL,
    photo_id   INTEGER REFERENCES photos(id)
);

CREATE INDEX idx_events_log_ts ON events_log(ts);
```

`photos.id` ist zugleich die Nummer im Dateinamen und läuft über alle Events durch. Das
macht Kollisionen unmöglich, wenn Ordner später zusammengeführt werden.

`deleted` ist ein Flag, kein `DELETE`. Löscht der Admin ein misslungenes Bild, verschwindet
es aus Galerie und Zählern, die Datei bleibt aber liegen. Endgültiges Löschen ist ein
separater, expliziter Schritt.

`events_log` ist bewusst in der DB und nicht nur im Logfile: die Fehlerhistorie eines
Abends will man hinterher zusammen mit den Fotos auswerten können, ohne durch
`fotobox.log` zu greifen.

## Schreibreihenfolge beim Auslösen

Verbindlich, siehe Regel 3 in `CLAUDE.md`:

1. DSLR auslösen, Datei nach `originals/` herunterladen
2. `INSERT INTO photos (..., pipeline_status='pending')`, Commit
3. Zustandswechsel nach `PROCESSING`
4. Pipeline läuft, schreibt `processed/`, `prints/`, `thumbs/`
5. `UPDATE photos SET pipeline_status='ok', pipeline_ms=...`

Bricht Schritt 4 ab, bleibt `pipeline_status='pending'` bzw. `'failed'`. Beim nächsten
Start werden solche Einträge erkannt und die Pipeline im Hintergrund nachgeholt — das
Original ist ja da.

## Migrationen

`schema_version` plus nummerierte SQL-Dateien in `backend/migrations/`. Beim
Start werden fehlende Migrationen in einer Transaktion angewendet. Kein Alembic — bei
diesem Umfang ist das Overhead.

## Druckzähler

`print_jobs.status` ist die Quelle für „wie viele Fotos wurden gedruckt". Eine
Abgleichschleife fragt im Takt von `hardware.printer.status_poll_seconds` die offenen
Aufträge bei CUPS ab und schreibt `done`, `failed` oder `cancelled` samt `finished_at`
fort. Ist ein Auftrag aus der CUPS-Historie verschwunden, bleibt er offen — geraten wird
nicht.

Daraus ergeben sich zwei Werte im Admin-Bereich:

- **Gedruckt (Event)** — Aufträge mit `status = 'done'` zu Fotos des aktiven Events.
  Reine Historie, wird beim Anlegen eines neuen Events automatisch wieder 0.
- **Gedruckt (gesamt)** — `counters.prints_total`, läuft über Events hinweg weiter und
  wird nur durch `Druckzähler zurücksetzen` genullt.

Beide zählen ausschließlich fertiggestellte Drucke. Der Grenzwert
`printing.max_per_event` greift dagegen bewusst schon beim Einreihen und benutzt deshalb
weiterhin `count_event_prints`, das alle nicht stornierten Aufträge zählt.
