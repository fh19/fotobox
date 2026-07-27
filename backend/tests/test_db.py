"""Migrations and schema — must match docs/datenmodell.md."""

from __future__ import annotations

from datetime import UTC

from app import db

EXPECTED_TABLES = {
    "schema_version",
    "events",
    "photos",
    "print_jobs",
    "events_log",
    "counters",
}

# Derived from the files on disk, so adding a migration does not break the test.
LATEST_VERSION = len(list(db.MIGRATIONS_DIR.glob("*.sql")))

EXPECTED_PHOTO_COLUMNS = {
    "id",
    "event_id",
    "filename",
    "captured_at",
    "background_id",
    "background_mode",
    "pipeline_status",
    "pipeline_error",
    "pipeline_ms",
    "camera_model",
    "width",
    "height",
    "deleted",
}


def test_migration_creates_schema(tmp_path):
    conn = db.connect(tmp_path / "fotobox.db")
    version = db.migrate(conn)
    assert version == LATEST_VERSION

    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert EXPECTED_TABLES <= tables


def test_photos_columns(tmp_path):
    conn = db.connect(tmp_path / "fotobox.db")
    db.migrate(conn)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(photos)").fetchall()}
    assert columns == EXPECTED_PHOTO_COLUMNS


def test_single_active_event_index_enforced(tmp_path):
    import sqlite3

    conn = db.connect(tmp_path / "fotobox.db")
    db.migrate(conn)
    conn.execute(
        "INSERT INTO events (name, directory, created_at, is_active) VALUES ('A', 'a', 't', 1)"
    )
    try:
        conn.execute(
            "INSERT INTO events (name, directory, created_at, is_active) VALUES ('B', 'b', 't', 1)"
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("two active events should violate the unique index")


def test_migration_is_idempotent(tmp_path):
    path = tmp_path / "fotobox.db"
    conn = db.connect(path)
    assert db.migrate(conn) == LATEST_VERSION
    # Running again applies nothing and keeps the schema intact.
    assert db.migrate(conn) == LATEST_VERSION
    assert db.count_photos(conn, event_id=1) == 0


def test_pragmas_are_set(tmp_path):
    conn = db.connect(tmp_path / "fotobox.db")
    journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal.lower() == "wal"


def test_insert_photo_names_file_from_id(tmp_path):
    from datetime import datetime

    conn = db.connect(tmp_path / "fotobox.db")
    db.migrate(conn)
    event = db.ensure_active_event(conn, "Test", datetime(2026, 8, 15, tzinfo=UTC))
    photo_id = db.insert_photo(
        conn,
        event_id=event["id"],
        captured_at=datetime(2026, 8, 15, tzinfo=UTC),
        background_id=None,
        background_mode="none",
        camera_model="Mock",
        width=6000,
        height=4000,
    )
    row = conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()
    assert row["filename"] == f"IMG_{photo_id:04d}.jpg"
    assert row["pipeline_status"] == "pending"
