"""Application factory and entrypoint.

``uvicorn app.main:app`` uses the module-level ``app``. Tests call
:func:`create_app` with an injected config and clock so nothing touches ``/data``.
An invalid configuration is reported as a readable message and a clean exit,
never a traceback deep in the framework (milestone M1 acceptance).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.api import admin, captive, gallery, routes, websocket
from app.api.admin import AdminAuth, LockedError, PinError
from app.broadcaster import Broadcaster
from app.clock import Clock, RealClock
from app.config import Config, ConfigError, default_config_path, load_config
from app.engine import Engine, NotFound
from app.hardware import CameraManager
from app.logging_setup import setup_logging
from app.state_machine import ActionRejected
from app.states import InvalidTransition

log = logging.getLogger("fotobox.main")

# The guest UI: vanilla JS/CSS served straight from disk, no build step.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


async def _timer_loop(engine: Engine, interval: float) -> None:
    """Poll the state machine on a fixed cadence: countdown ticks and timeouts."""
    while True:
        engine.tick()
        await engine.flush()
        await asyncio.sleep(interval)


async def _print_status_loop(engine: Engine, interval: float) -> None:
    """Ask CUPS what became of the open print jobs and persist the outcome.

    Runs off the event loop: pycups calls are blocking. Errors are logged and
    the loop keeps going — a print job outcome is never worth taking the box
    down for.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(engine.reconcile_print_jobs)
        except Exception:
            log.exception("Druckauftragsstatus konnte nicht abgeglichen werden")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    engine: Engine = app.state.engine
    interval = app.state.config.runtime.tick_interval_seconds
    task = asyncio.create_task(_timer_loop(engine, interval))
    prints = asyncio.create_task(
        _print_status_loop(engine, app.state.config.hardware.printer.status_poll_seconds)
    )
    # Catch up on any pipelines a crash/restart left pending, off the event loop.
    recovery = asyncio.create_task(asyncio.to_thread(engine.recover_pending_pipelines))
    log.info("Fotobox bereit (Hardware=%s).", app.state.config.hardware.mode)
    try:
        yield
    finally:
        task.cancel()
        prints.cancel()
        recovery.cancel()
        with suppress(asyncio.CancelledError):
            await task
        with suppress(asyncio.CancelledError):
            await prints
        with suppress(asyncio.CancelledError, Exception):
            await recovery


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ActionRejected)
    async def _action_rejected(request: Request, exc: ActionRejected) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(NotFound)
    async def _not_found(request: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(InvalidTransition)
    async def _invalid_transition(request: Request, exc: InvalidTransition) -> JSONResponse:
        # A programming error: log loudly, do not leak internals to the client.
        log.error("InvalidTransition: %s -> %s", exc.source, exc.target)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal", "message": "Interner Fehler"}},
        )

    @app.exception_handler(PinError)
    async def _pin_error(request: Request, exc: PinError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "unauthorized", "message": "Falsche PIN"}},
        )

    @app.exception_handler(LockedError)
    async def _locked_error(request: Request, exc: LockedError) -> JSONResponse:
        return JSONResponse(
            status_code=423,
            headers={"Retry-After": str(exc.retry_after)},
            content={
                "error": {"code": "locked", "message": "Zu viele Fehlversuche — kurz gesperrt"}
            },
        )


def create_app(
    config: Config | None = None,
    clock: Clock | None = None,
    config_path: Path | None = None,
) -> FastAPI:
    if config is None:
        config_path = config_path or default_config_path()
        config = load_config(config_path)
    clock = clock or RealClock()
    setup_logging(config)

    conn = db.connect(config.db_path)
    db.migrate(conn)

    manager = CameraManager(config)
    broadcaster = Broadcaster()
    engine = Engine(
        config,
        clock,
        conn,
        manager.backends,
        broadcaster,
        camera_manager=manager,
        config_path=config_path,
    )
    # Pending pipelines are recovered in the lifespan (off the event loop).

    app = FastAPI(title="Fotobox", lifespan=_lifespan)
    app.state.config = config
    app.state.engine = engine
    app.state.broadcaster = broadcaster
    app.state.admin_auth = AdminAuth()

    _register_error_handlers(app)
    app.include_router(routes.router)
    app.include_router(websocket.router)
    app.include_router(gallery.router)
    app.include_router(admin.router)
    app.include_router(captive.router)

    @app.exception_handler(404)
    async def _not_found(request: Request, exc) -> Response:
        """Send a guest on the guest WiFi to the gallery instead of a 404.

        With the DNS hijack every hostname a phone tries lands here, so this is
        what turns "connected to Fotobox" into an open gallery. Anywhere else a
        404 stays a 404 — see app.api.captive.
        """
        if captive.is_captured(request):
            return captive.redirect_to_gallery(request)
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Nicht gefunden"}},
        )

    @app.get("/gallery")
    async def gallery_page() -> Response:
        if not config.network.gallery_enabled:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {"code": "gallery_disabled", "message": "Die Galerie ist deaktiviert"}
                },
            )
        return FileResponse(FRONTEND_DIR / "gallery.html", media_type="text/html")

    @app.get("/admin")
    async def admin_page() -> Response:
        return FileResponse(FRONTEND_DIR / "admin.html", media_type="text/html")

    # Mounted last so API and WebSocket routes win; serves index.html at "/".
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


_module_app: FastAPI | None = None


def _build_module_app() -> FastAPI:
    try:
        return create_app()
    except ConfigError as exc:
        # Readable message on the console, clean exit — not a traceback.
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


def __getattr__(name: str):
    # Build the ASGI app lazily so that `uvicorn app.main:app` works, while a
    # plain `import app.main` (e.g. in tests) does not touch /data or the config.
    if name == "app":
        global _module_app
        if _module_app is None:
            _module_app = _build_module_app()
        return _module_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
