-- Initial schema. Mirrors docs/datenmodell.md exactly.
-- Applied in a single transaction by app/db.py on startup.

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
