"""SQLite access: connection, migrations and the handful of queries M1 needs.

No ORM (CLAUDE.md stack). WAL plus ``synchronous=FULL`` because a power cut is a
realistic event and the few milliseconds per photo are irrelevant
(docs/datenmodell.md).
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
_MIGRATION_RE = re.compile(r"^(\d+)_.*\.sql$")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if row is None:
        return 0
    version_row = conn.execute("SELECT version FROM schema_version").fetchone()
    return version_row["version"] if version_row else 0


def _pending_migrations(current: int, migrations_dir: Path) -> list[tuple[int, Path]]:
    found: list[tuple[int, Path]] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        match = _MIGRATION_RE.match(path.name)
        if not match:
            continue
        number = int(match.group(1))
        if number > current:
            found.append((number, path))
    found.sort(key=lambda item: item[0])
    return found


def migrate(conn: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> int:
    """Apply missing migrations in order. Returns the new schema version.

    ``executescript`` runs each migration file as one unit (and commits it); the
    version marker is then bumped so a rerun applies nothing (idempotent).
    """
    version = _current_version(conn)
    for number, path in _pending_migrations(version, migrations_dir):
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (number,))
        version = number
    return version


# --- Events -----------------------------------------------------------------


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "event"


def get_active_event(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM events WHERE is_active = 1").fetchone()


def create_event(conn: sqlite3.Connection, name: str, now: datetime) -> sqlite3.Row:
    directory = f"{now.date().isoformat()}_{_slug(name)}"
    conn.execute("BEGIN")
    try:
        conn.execute("UPDATE events SET is_active = 0 WHERE is_active = 1")
        cursor = conn.execute(
            "INSERT INTO events (name, directory, created_at, is_active) VALUES (?, ?, ?, 1)",
            (name, directory, now.isoformat()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return conn.execute("SELECT * FROM events WHERE id = ?", (cursor.lastrowid,)).fetchone()


def ensure_active_event(conn: sqlite3.Connection, name: str, now: datetime) -> sqlite3.Row:
    """Guarantee there is an active event so capturing works from a fresh install."""
    active = get_active_event(conn)
    if active is not None:
        return active
    return create_event(conn, name, now)


# --- Photos -----------------------------------------------------------------


def photo_filename(photo_id: int) -> str:
    return f"IMG_{photo_id:04d}.jpg"


def insert_photo(
    conn: sqlite3.Connection,
    *,
    event_id: int,
    captured_at: datetime,
    background_id: str | None,
    background_mode: str | None,
    camera_model: str | None,
    width: int | None,
    height: int | None,
) -> int:
    """Insert a photo row with ``pipeline_status='pending'``. Returns the new id.

    The filename encodes the id (``IMG_{id:04d}.jpg``), so it is filled in once the
    id is known. Written and committed before the pipeline starts (CLAUDE.md rule 3).
    """
    conn.execute("BEGIN")
    try:
        cursor = conn.execute(
            """
            INSERT INTO photos
                (event_id, filename, captured_at, background_id, background_mode,
                 pipeline_status, camera_model, width, height)
            VALUES (?, '', ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                event_id,
                captured_at.isoformat(),
                background_id,
                background_mode,
                camera_model,
                width,
                height,
            ),
        )
        photo_id = cursor.lastrowid
        conn.execute(
            "UPDATE photos SET filename = ? WHERE id = ?",
            (photo_filename(photo_id), photo_id),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return photo_id


def set_pipeline_ok(conn: sqlite3.Connection, photo_id: int, pipeline_ms: int) -> None:
    conn.execute(
        "UPDATE photos SET pipeline_status = 'ok', pipeline_ms = ?, pipeline_error = NULL "
        "WHERE id = ?",
        (pipeline_ms, photo_id),
    )


def set_pipeline_failed(conn: sqlite3.Connection, photo_id: int, error: str) -> None:
    conn.execute(
        "UPDATE photos SET pipeline_status = 'failed', pipeline_error = ? WHERE id = ?",
        (error, photo_id),
    )


def count_photos(conn: sqlite3.Connection, event_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM photos WHERE event_id = ? AND deleted = 0",
        (event_id,),
    ).fetchone()
    return row["n"]


def pending_pipeline_photos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM photos WHERE pipeline_status = 'pending' AND deleted = 0"
    ).fetchall()


def pending_pipeline_photos_with_event(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Pending photos joined with their event directory, for restart recovery."""
    return conn.execute(
        """
        SELECT p.*, e.directory AS event_directory
        FROM photos p
        JOIN events e ON e.id = p.event_id
        WHERE p.pipeline_status = 'pending' AND p.deleted = 0
        ORDER BY p.id ASC
        """
    ).fetchall()


def get_photo_with_event(conn: sqlite3.Connection, photo_id: int) -> sqlite3.Row | None:
    """One photo plus its event's directory — a photo may not be in the active event."""
    return conn.execute(
        """
        SELECT p.*, e.directory AS event_directory
        FROM photos p
        JOIN events e ON e.id = p.event_id
        WHERE p.id = ? AND p.deleted = 0
        """,
        (photo_id,),
    ).fetchone()


# --- Gallery ----------------------------------------------------------------


def list_events(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT e.*,
               (SELECT COUNT(*) FROM photos p WHERE p.event_id = e.id AND p.deleted = 0)
                   AS photo_count
        FROM events e
        ORDER BY e.created_at DESC, e.id DESC
        """
    ).fetchall()


def get_event(conn: sqlite3.Connection, event_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()


def list_photos(
    conn: sqlite3.Connection, event_id: int, *, limit: int, offset: int
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM photos
        WHERE event_id = ? AND deleted = 0
        ORDER BY captured_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (event_id, limit, offset),
    ).fetchall()


def iter_event_photos(conn: sqlite3.Connection, event_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM photos WHERE event_id = ? AND deleted = 0 ORDER BY id ASC",
        (event_id,),
    ).fetchall()


# --- Print jobs -------------------------------------------------------------


def insert_print_job(
    conn: sqlite3.Connection,
    *,
    photo_id: int,
    cups_job_id: int | None,
    requested_at: datetime,
    status: str,
    is_reprint: bool = False,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO print_jobs (photo_id, cups_job_id, requested_at, status, is_reprint)
        VALUES (?, ?, ?, ?, ?)
        """,
        (photo_id, cups_job_id, requested_at.isoformat(), status, int(is_reprint)),
    )
    return cursor.lastrowid


def count_event_prints(conn: sqlite3.Connection, event_id: int) -> int:
    """Count print jobs that were handed to the printer for this event's photos.

    Deliberately counts submitted jobs, not finished ones — this backs the
    ``printing.max_per_event`` limit, which must apply the moment a job is
    queued. For the "how many were actually printed" display use
    :func:`count_event_prints_done`.
    """
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM print_jobs pj
        JOIN photos p ON p.id = pj.photo_id
        WHERE p.event_id = ? AND pj.status != 'cancelled'
        """,
        (event_id,),
    ).fetchone()
    return row["n"]


def count_event_prints_done(conn: sqlite3.Connection, event_id: int) -> int:
    """Successfully printed jobs for this event's photos."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM print_jobs pj
        JOIN photos p ON p.id = pj.photo_id
        WHERE p.event_id = ? AND pj.status = 'done'
        """,
        (event_id,),
    ).fetchone()
    return row["n"]


def pending_print_jobs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Jobs that still have an open outcome and carry a CUPS job id."""
    return conn.execute(
        """
        SELECT id, cups_job_id, status
        FROM print_jobs
        WHERE status IN ('queued', 'printing') AND cups_job_id IS NOT NULL
        """
    ).fetchall()


def update_print_job_status(
    conn: sqlite3.Connection, *, job_id: int, status: str, finished_at: datetime | None
) -> None:
    conn.execute(
        "UPDATE print_jobs SET status = ?, finished_at = ? WHERE id = ?",
        (status, finished_at.isoformat() if finished_at else None, job_id),
    )


# --- Counters ---------------------------------------------------------------


def get_counter(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT value FROM counters WHERE name = ?", (name,)).fetchone()
    return row["value"] if row else 0


def increment_counter(conn: sqlite3.Connection, name: str, by: int = 1) -> None:
    conn.execute(
        """
        INSERT INTO counters (name, value) VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET value = value + excluded.value
        """,
        (name, by),
    )


def reset_counter(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        """
        INSERT INTO counters (name, value) VALUES (?, 0)
        ON CONFLICT(name) DO UPDATE SET value = 0
        """,
        (name,),
    )


# --- Log --------------------------------------------------------------------


def log_event(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    level: str,
    component: str,
    code: str,
    message: str,
    photo_id: int | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO events_log (ts, level, component, code, message, photo_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (now.isoformat(), level, component, code, message, photo_id),
    )
