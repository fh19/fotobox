"""Gallery endpoints and streaming ZIP export (M4)."""

from __future__ import annotations

import io
import os
import time
import tracemalloc
import zipfile
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app import db
from app.clock import RealClock
from app.main import create_app
from app.zipstream import stream_zip
from tests.conftest import make_config


def _app(tmp_path, **overrides):
    return create_app(make_config(tmp_path, **overrides), RealClock())


def _populate(app, count, *, ok=True):
    engine = app.state.engine
    event = engine.active_event
    ids = []
    for _ in range(count):
        photo_id = db.insert_photo(
            engine.conn,
            event_id=event["id"],
            captured_at=datetime.now(UTC),
            background_id=None,
            background_mode="none",
            camera_model="Mock",
            width=1200,
            height=1800,
        )
        if ok:
            db.set_pipeline_ok(engine.conn, photo_id, 5)
        for variant in ("originals", "processed", "thumbs", "prints"):
            path = engine.photo_variant_path(variant, photo_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"{variant}-{photo_id}".encode() * 100)
        ids.append(photo_id)
    return ids


# --- events & photos --------------------------------------------------------


def test_events_lists_active_event_with_count(tmp_path):
    app = _app(tmp_path)
    _populate(app, 3)
    body = TestClient(app).get("/api/events").json()
    assert len(body["events"]) == 1
    assert body["events"][0]["photo_count"] == 3


def test_photos_are_paginated(tmp_path):
    app = _app(tmp_path)
    _populate(app, 5)
    event_id = app.state.engine.active_event["id"]
    client = TestClient(app)

    page1 = client.get(f"/api/events/{event_id}/photos?page=1&per_page=2").json()
    assert page1["total"] == 5
    assert len(page1["photos"]) == 2
    assert page1["photos"][0]["thumb_url"].startswith("/api/photos/")

    page3 = client.get(f"/api/events/{event_id}/photos?page=3&per_page=2").json()
    assert len(page3["photos"]) == 1


def test_unknown_event_is_404(tmp_path):
    app = _app(tmp_path)
    assert TestClient(app).get("/api/events/999/photos").status_code == 404


# --- gallery gate -----------------------------------------------------------


def test_gallery_disabled_returns_404(tmp_path):
    app = _app(tmp_path, network__gallery_enabled=False)
    client = TestClient(app)
    assert client.get("/api/events").status_code == 404
    assert client.get("/gallery").status_code == 404


def test_gallery_page_served_when_enabled(tmp_path):
    app = _app(tmp_path)
    res = TestClient(app).get("/gallery")
    assert res.status_code == 200
    assert "Galerie" in res.text


# --- download info & zip ----------------------------------------------------


def test_download_info_counts_files(tmp_path):
    app = _app(tmp_path)
    _populate(app, 3)
    event_id = app.state.engine.active_event["id"]
    info = TestClient(app).get(f"/api/events/{event_id}/download-info?variant=processed").json()
    assert info["file_count"] == 3
    assert info["size_bytes"] > 0


def test_zip_contains_all_photos(tmp_path):
    app = _app(tmp_path)
    _populate(app, 4)
    event_id = app.state.engine.active_event["id"]
    res = TestClient(app).get(f"/api/events/{event_id}/download.zip?variant=processed")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
        names = archive.namelist()
    assert len(names) == 4
    assert all(name.startswith("IMG_") for name in names)


def test_zip_both_variants_has_two_folders(tmp_path):
    app = _app(tmp_path)
    _populate(app, 2)
    event_id = app.state.engine.active_event["id"]
    res = TestClient(app).get(f"/api/events/{event_id}/download.zip?variant=both")
    with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
        names = archive.namelist()
    assert sum(n.startswith("original/") for n in names) == 2
    assert sum(n.startswith("bearbeitet/") for n in names) == 2


def test_invalid_variant_is_404(tmp_path):
    app = _app(tmp_path)
    event_id = app.state.engine.active_event["id"]
    assert (
        TestClient(app).get(f"/api/events/{event_id}/download.zip?variant=nope").status_code == 404
    )


# --- streaming memory (criterion: memory does not grow with photo count) ----


def test_zip_stream_memory_is_flat(tmp_path):
    payload = b"x" * 50_000
    files = []
    for i in range(300):
        path = tmp_path / f"f{i}.jpg"
        path.write_bytes(payload)
        files.append((f"IMG_{i:04d}.jpg", path))

    tracemalloc.start()
    total = 0
    for chunk in stream_zip(files):  # consume and discard, like the HTTP transport
        total += len(chunk)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert total > 300 * 50_000 * 0.9  # everything was actually streamed (~15 MB)
    assert peak < 2_000_000  # but peak memory stays near one file, not the whole archive


def test_zip_entries_keep_the_file_date(tmp_path):
    """From the first real event: every extracted photo was dated 1980-01-01, so
    the guests' downloads looked like the box had no clock. It had one — the ZIP
    was written with a bare arcname, which is zipfile's epoch default."""
    photo = tmp_path / "IMG_0402.jpg"
    photo.write_bytes(b"\xff\xd8\xff" + b"jpeg" * 100)
    taken = datetime(2026, 8, 22, 5, 6, 31)
    os.utime(photo, (taken.timestamp(), taken.timestamp()))

    data = b"".join(stream_zip([("Fotos/IMG_0402.jpg", photo)]))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo("Fotos/IMG_0402.jpg")
        assert info.date_time[:5] == (2026, 8, 22, 5, 6)
        # ...and readable by more than just the owner after extraction.
        assert (info.external_attr >> 16) & 0o044
        assert archive.read("Fotos/IMG_0402.jpg") == photo.read_bytes()


# --- reprint from the gallery ------------------------------------------------
#
# From the first real event: "Bilder lassen sich nachträglich nicht mehr
# ausdrucken". A guest asking for a copy an hour later was out of luck.


def _event_with_photo(tmp_path, **overrides):
    """An app whose active event holds one printable photo on disk."""
    config = make_config(tmp_path, **overrides)
    app = create_app(config, RealClock())
    engine = app.state.engine
    photo_id = db.insert_photo(
        engine.conn,
        event_id=engine.active_event["id"],
        captured_at=datetime.now(UTC).astimezone(),
        background_id=None,
        background_mode="none",
        camera_model="Nikon DSC D7200",
        width=1872,
        height=1248,
    )
    printable = engine.photo_variant_path("prints", photo_id)
    printable.parent.mkdir(parents=True, exist_ok=True)
    printable.write_bytes(b"\xff\xd8\xff" + b"print" * 50)
    return app, engine, photo_id


def test_a_stored_photo_can_be_printed_again(tmp_path):
    app, engine, photo_id = _event_with_photo(tmp_path)
    client = TestClient(app)

    body = client.post(f"/api/photos/{photo_id}/print").json()
    assert body["queued"] is True
    assert body["photo_id"] == photo_id
    assert engine.conn.execute("SELECT COUNT(*) FROM print_jobs").fetchone()[0] == 1


def test_a_reprint_counts_against_the_event_quota(tmp_path):
    app, engine, photo_id = _event_with_photo(tmp_path, printing__max_per_event=1)
    client = TestClient(app)

    assert client.post(f"/api/photos/{photo_id}/print").status_code == 200
    res = client.post(f"/api/photos/{photo_id}/print")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "daily_limit_reached"


def test_a_reprint_says_why_the_printer_will_not(tmp_path):
    app, engine, photo_id = _event_with_photo(tmp_path)
    engine.backends.printer.set_reason("media_empty")

    res = TestClient(app).post(f"/api/photos/{photo_id}/print")
    assert res.status_code == 409
    assert res.json()["error"]["message"] == "Kein Papier"


def test_an_unknown_photo_is_404(tmp_path):
    app, _, _ = _event_with_photo(tmp_path)
    assert TestClient(app).post("/api/photos/9999/print").status_code == 404


def test_a_photo_without_a_print_file_is_404(tmp_path):
    app, engine, photo_id = _event_with_photo(tmp_path)
    engine.photo_variant_path("prints", photo_id).unlink()
    res = TestClient(app).post(f"/api/photos/{photo_id}/print")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "no_printable"


def test_reprint_is_off_with_the_gallery(tmp_path):
    app, _, photo_id = _event_with_photo(tmp_path, network__gallery_enabled=False)
    assert TestClient(app).post(f"/api/photos/{photo_id}/print").status_code == 404


def test_client_config_carries_the_gallery_settings(tmp_path):
    client = TestClient(create_app(make_config(tmp_path), RealClock()))
    cfg = client.get("/api/client-config").json()
    assert cfg["gallery_enabled"] is True
    assert cfg["gallery_return_seconds"] > 0


def test_the_reprint_follows_the_shown_variant(tmp_path):
    """Reported from the box: printing while looking at the original produced the
    framed copy. Whatever is on screen is what should come out."""
    app, engine, photo_id = _event_with_photo(tmp_path)
    original = engine.photo_variant_path("originals", photo_id)
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"\xff\xd8\xff" + b"original" * 50)

    submitted: list[str] = []
    engine.backends.printer.submit = lambda path: submitted.append(path) or 1
    client = TestClient(app)

    client.post(f"/api/photos/{photo_id}/print?variant=original")
    assert submitted[-1].endswith(f"originals/{db.photo_filename(photo_id)}")

    client.post(f"/api/photos/{photo_id}/print?variant=processed")
    assert submitted[-1].endswith(f"prints/{db.photo_filename(photo_id)}")

    # Without a variant the framed copy stays the default.
    client.post(f"/api/photos/{photo_id}/print")
    assert submitted[-1].endswith(f"prints/{db.photo_filename(photo_id)}")


# --- downloading a selection -------------------------------------------------
#
# After the first event the only choices were all 252 photos or one at a time.


def _event_with_photos(tmp_path, count=3):
    config = make_config(tmp_path)
    app = create_app(config, RealClock())
    engine = app.state.engine
    ids = []
    for _ in range(count):
        photo_id = db.insert_photo(
            engine.conn,
            event_id=engine.active_event["id"],
            captured_at=datetime.now(UTC).astimezone(),
            background_id=None,
            background_mode="none",
            camera_model="Nikon",
            width=1872,
            height=1248,
        )
        for variant in ("processed", "originals"):
            path = engine.photo_variant_path(variant, photo_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\xff\xd8\xff" + bytes([photo_id]) * 400)
        ids.append(photo_id)
    return app, engine, ids


def test_only_the_selected_photos_are_zipped(tmp_path):
    app, engine, ids = _event_with_photos(tmp_path, count=3)
    event_id = engine.active_event["id"]
    client = TestClient(app)
    wanted = f"{ids[0]},{ids[2]}"

    res = client.get(f"/api/events/{event_id}/download.zip?ids={wanted}")
    assert res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
        names = archive.namelist()
    assert names == [db.photo_filename(ids[0]), db.photo_filename(ids[2])]
    assert "auswahl-2" in res.headers["content-disposition"]


def test_the_whole_event_is_still_the_default(tmp_path):
    app, engine, ids = _event_with_photos(tmp_path, count=3)
    res = TestClient(app).get(f"/api/events/{engine.active_event['id']}/download.zip")
    with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
        assert len(archive.namelist()) == 3
    assert "auswahl" not in res.headers["content-disposition"]


def test_the_size_of_a_selection_is_reported(tmp_path):
    app, engine, ids = _event_with_photos(tmp_path, count=3)
    event_id = engine.active_event["id"]
    client = TestClient(app)

    whole = client.get(f"/api/events/{event_id}/download-info").json()
    part = client.get(f"/api/events/{event_id}/download-info?ids={ids[0]}").json()
    assert whole["file_count"] == 3
    assert part["file_count"] == 1
    assert part["size_bytes"] < whole["size_bytes"]


def test_nonsense_ids_fall_back_to_the_whole_event(tmp_path):
    app, engine, _ = _event_with_photos(tmp_path, count=2)
    res = TestClient(app).get(f"/api/events/{engine.active_event['id']}/download-info?ids=abc,")
    assert res.json()["file_count"] == 2


# --- admin gallery management ------------------------------------------------
#
# "Anschauen und Löschen aller Veranstaltungsbilder aus dem Konfig-Menü heraus."

PIN = {"X-Fotobox-Pin": "2606"}


def test_deleting_hides_photos_but_keeps_the_files(tmp_path):
    """datenmodell.md: `deleted` is a flag, not a DELETE."""
    app, engine, ids = _event_with_photos(tmp_path, count=3)
    client = TestClient(app)
    on_disk = engine.photo_variant_path("originals", ids[0])

    res = client.post("/api/admin/photos/delete", json={"ids": [ids[0]]}, headers=PIN)
    assert res.status_code == 200
    assert res.json()["deleted"] == 1
    assert on_disk.exists()

    listed = client.get(f"/api/events/{engine.active_event['id']}/photos").json()
    assert [p["id"] for p in listed["photos"]] == [ids[2], ids[1]]


def test_a_deleted_photo_leaves_the_zip_and_the_count(tmp_path):
    app, engine, ids = _event_with_photos(tmp_path, count=3)
    event_id = engine.active_event["id"]
    client = TestClient(app)
    client.post("/api/admin/photos/delete", json={"ids": [ids[1]]}, headers=PIN)

    with zipfile.ZipFile(
        io.BytesIO(client.get(f"/api/events/{event_id}/download.zip").content)
    ) as z:
        assert db.photo_filename(ids[1]) not in z.namelist()
    assert client.get("/api/events").json()["events"][0]["photo_count"] == 2


def test_the_purge_is_a_separate_step_that_frees_the_card(tmp_path):
    app, engine, ids = _event_with_photos(tmp_path, count=2)
    client = TestClient(app)
    client.post("/api/admin/photos/delete", json={"ids": [ids[0]]}, headers=PIN)

    stats = client.get("/api/admin/photos/deleted", headers=PIN).json()
    assert stats["count"] == 1 and stats["bytes"] > 0

    res = client.post("/api/admin/photos/purge", headers=PIN).json()
    assert res["purged"] == 2  # originals + processed of that one photo
    assert res["freed_bytes"] == stats["bytes"]
    assert not engine.photo_variant_path("originals", ids[0]).exists()
    assert engine.photo_variant_path("originals", ids[1]).exists()  # the kept one


def test_the_purge_leaves_photos_that_are_only_shown_alone(tmp_path):
    """Nothing is removed until something was explicitly marked deleted."""
    app, engine, ids = _event_with_photos(tmp_path, count=2)
    client = TestClient(app)
    assert client.post("/api/admin/photos/purge", headers=PIN).json()["purged"] == 0
    assert engine.photo_variant_path("originals", ids[0]).exists()


def test_deleting_needs_the_pin(tmp_path):
    """The gallery is reachable from the guest WiFi; deleting must not be."""
    app, engine, ids = _event_with_photos(tmp_path, count=1)
    client = TestClient(app)
    res = client.post("/api/admin/photos/delete", json={"ids": ids})
    assert res.status_code == 401
    assert client.post("/api/admin/photos/purge").status_code == 401
    assert engine.photo_variant_path("originals", ids[0]).exists()


def test_deleting_nothing_is_rejected(tmp_path):
    app, _, _ = _event_with_photos(tmp_path, count=1)
    res = TestClient(app).post("/api/admin/photos/delete", json={"ids": []}, headers=PIN)
    assert res.status_code == 409  # ActionRejected, like every other refused action


# --- re-rendering an old event ----------------------------------------------
#
# The processed files are only as good as the pipeline that made them. After an
# improvement they can be made again from the untouched originals.


def test_a_rerender_reports_progress_and_finishes(tmp_path, monkeypatch):
    app, engine, ids = _event_with_photos(tmp_path, count=3)
    seen = []
    monkeypatch.setattr(engine, "_reprocess", lambda conn, photo: seen.append(photo["id"]) or True)
    client = TestClient(app)

    res = client.post(f"/api/admin/events/{engine.active_event['id']}/rerender", headers=PIN)
    assert res.status_code == 200
    assert res.json()["total"] == 3

    for _ in range(200):
        status = client.get("/api/admin/rerender", headers=PIN).json()
        if status["finished"]:
            break
        time.sleep(0.02)
    assert status["done"] == 3 and status["failed"] == 0
    assert sorted(seen) == sorted(ids)


def test_a_photo_that_cannot_be_redone_is_counted_not_fatal(tmp_path, monkeypatch):
    """A missing original must not stop the other 250 photos."""
    app, engine, ids = _event_with_photos(tmp_path, count=3)
    monkeypatch.setattr(engine, "_reprocess", lambda conn, photo: photo["id"] != ids[1])
    client = TestClient(app)
    client.post(f"/api/admin/events/{engine.active_event['id']}/rerender", headers=PIN)

    for _ in range(200):
        status = client.get("/api/admin/rerender", headers=PIN).json()
        if status["finished"]:
            break
        time.sleep(0.02)
    assert status["done"] == 2 and status["failed"] == 1


def test_two_rerenders_at_once_are_refused(tmp_path, monkeypatch):
    app, engine, ids = _event_with_photos(tmp_path, count=2)
    monkeypatch.setattr(engine, "_reprocess", lambda conn, photo: time.sleep(0.3) or True)
    client = TestClient(app)
    event_id = engine.active_event["id"]

    assert client.post(f"/api/admin/events/{event_id}/rerender", headers=PIN).status_code == 200
    assert client.post(f"/api/admin/events/{event_id}/rerender", headers=PIN).status_code == 409


def test_rerendering_an_unknown_event_is_refused(tmp_path):
    app, _, _ = _event_with_photos(tmp_path, count=1)
    assert TestClient(app).post("/api/admin/events/999/rerender", headers=PIN).status_code == 409


def test_rerendering_needs_the_pin(tmp_path):
    app, engine, _ = _event_with_photos(tmp_path, count=1)
    res = TestClient(app).post(f"/api/admin/events/{engine.active_event['id']}/rerender")
    assert res.status_code == 401


# --- the grid must show what the toggle says --------------------------------


def test_the_grid_has_its_own_thumbnail_for_originals(tmp_path):
    """The stored thumbnail is made from the framed copy, so "Original" showed
    the frame anyway — the one thing that view is for."""
    from PIL import Image

    app, engine, ids = _event_with_photos(tmp_path, count=1)
    photo_id = ids[0]
    original = engine.photo_variant_path("originals", photo_id)
    Image.new("RGB", (4496, 3000), "red").save(original, "JPEG")
    client = TestClient(app)

    res = client.get(f"/api/photos/{photo_id}/thumb-original")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    made = engine.photo_variant_path("thumbs_original", photo_id)
    assert made.exists()
    with Image.open(made) as thumb:
        assert thumb.width == engine.config.pipeline.thumbnail_width

    listed = client.get(f"/api/events/{engine.active_event['id']}/photos").json()
    assert listed["photos"][0]["thumb_original_url"].endswith("/thumb-original")


def test_the_original_thumbnail_is_kept_once_made(tmp_path):
    from PIL import Image

    app, engine, ids = _event_with_photos(tmp_path, count=1)
    Image.new("RGB", (800, 600), "blue").save(engine.photo_variant_path("originals", ids[0]))
    client = TestClient(app)

    client.get(f"/api/photos/{ids[0]}/thumb-original")
    made = engine.photo_variant_path("thumbs_original", ids[0])
    stamp = made.stat().st_mtime_ns
    client.get(f"/api/photos/{ids[0]}/thumb-original")
    assert made.stat().st_mtime_ns == stamp  # not rebuilt on every request


def test_a_missing_original_gives_404_not_a_crash(tmp_path):
    app, engine, ids = _event_with_photos(tmp_path, count=1)
    engine.photo_variant_path("originals", ids[0]).unlink()
    assert TestClient(app).get(f"/api/photos/{ids[0]}/thumb-original").status_code == 404


def test_deleting_removes_the_photo_from_both_views(tmp_path):
    """One flag per photo, not per variant — deleting in one gallery must not
    leave it standing in the other."""
    app, engine, ids = _event_with_photos(tmp_path, count=2)
    client = TestClient(app)
    client.post("/api/admin/photos/delete", json={"ids": [ids[0]]}, headers=PIN)

    listed = client.get(f"/api/events/{engine.active_event['id']}/photos").json()
    assert [p["id"] for p in listed["photos"]] == [ids[1]]
    for variant in ("processed", "original", "both"):
        with zipfile.ZipFile(
            io.BytesIO(
                client.get(
                    f"/api/events/{engine.active_event['id']}/download.zip?variant={variant}"
                ).content
            )
        ) as archive:
            assert not any(db.photo_filename(ids[0]) in n for n in archive.namelist()), variant


def test_the_purge_also_clears_the_original_thumbnail(tmp_path):
    from PIL import Image

    app, engine, ids = _event_with_photos(tmp_path, count=1)
    Image.new("RGB", (800, 600), "green").save(engine.photo_variant_path("originals", ids[0]))
    client = TestClient(app)
    client.get(f"/api/photos/{ids[0]}/thumb-original")
    assert engine.photo_variant_path("thumbs_original", ids[0]).exists()

    client.post("/api/admin/photos/delete", json={"ids": ids}, headers=PIN)
    client.post("/api/admin/photos/purge", headers=PIN)
    assert not engine.photo_variant_path("thumbs_original", ids[0]).exists()


def test_the_original_thumbnail_keeps_the_photo_date(tmp_path):
    import os

    from PIL import Image

    app, engine, ids = _event_with_photos(tmp_path, count=1)
    original = engine.photo_variant_path("originals", ids[0])
    Image.new("RGB", (800, 600), "blue").save(original)
    long_ago = 1_500_000_000
    os.utime(original, (long_ago, long_ago))

    TestClient(app).get(f"/api/photos/{ids[0]}/thumb-original")
    made = engine.photo_variant_path("thumbs_original", ids[0])
    assert int(made.stat().st_mtime) == long_ago
