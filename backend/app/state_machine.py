"""The state machine — the single source of truth for the session state.

Lives entirely in the backend (CLAUDE.md rule 5). It is pure: no hardware, no
database, no sleeping. Time is read through an injected :class:`Clock`; side
effects (capturing, the pipeline, printing) are driven by the :mod:`engine`,
which calls the transition methods here.

Every state except ``IDLE``, ``SCREENSAVER`` and ``ERROR`` has a timeout that
leads back towards ``IDLE`` (CLAUDE.md rule 4); the timeout values come from the
config, never hard-coded (rule 6). ``SCREENSAVER`` is the one addition to that
rule and for the same reason ``IDLE`` is exempt: it is a resting state, not a
step in a session. Nothing is half-finished there, nobody is waiting, and it is
left by a touch — a timeout could only send it back to a screen the box already
decided nobody is looking at.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.clock import Clock
from app.config import Config
from app.states import ALLOWED_TRANSITIONS, InvalidTransition, State

Emit = Callable[[str, dict], None]


class ActionRejected(Exception):
    """A client action that is invalid in the current state (maps to HTTP 409)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Session:
    background_id: str | None = None
    background_mode: str | None = None
    photo_id: int | None = None
    print_count: int = 0
    countdown_started_at: datetime | None = None
    countdown_ticks_emitted: int = 0


@dataclass
class ErrorInfo:
    code: str
    message: str


# Fixed timeout target and error mapping per state, resolved against the config.
_ERROR_MESSAGES = {
    "camera_timeout": "Die Kamera hat nicht reagiert",
    "capture_failed": "Das Foto konnte nicht aufgenommen werden",
    "pipeline_failed": "Das Foto konnte nicht bearbeitet werden — es ist aber gespeichert",
    "printer_unavailable": "Der Drucker ist gerade nicht bereit",
}


class StateMachine:
    def __init__(self, config: Config, clock: Clock, emit: Emit) -> None:
        self._config = config
        self._clock = clock
        self._emit = emit
        self._state = State.IDLE
        self._session: Session | None = None
        self._deadline: datetime | None = None
        self._error: ErrorInfo | None = None
        self._arm(State.IDLE)  # a box that boots and is left alone dims too

    # --- read-only accessors ------------------------------------------------

    @property
    def state(self) -> State:
        return self._state

    @property
    def session(self) -> Session | None:
        return self._session

    @property
    def error(self) -> ErrorInfo | None:
        return self._error

    @property
    def deadline(self) -> datetime | None:
        return self._deadline

    def countdown_remaining(self) -> int | None:
        if self._state != State.COUNTDOWN or self._session is None:
            return None
        started = self._session.countdown_started_at
        if started is None:
            return self._config.countdown.duration_seconds
        elapsed = (self._clock.now() - started).total_seconds()
        remaining = self._config.countdown.duration_seconds - int(elapsed)
        return max(0, min(self._config.countdown.duration_seconds, remaining))

    # --- transition primitive ----------------------------------------------

    def _set_state(self, target: State) -> None:
        source = self._state
        if (source, target) not in ALLOWED_TRANSITIONS:
            raise InvalidTransition(source, target)
        self._state = target
        self._arm(target)
        if target == State.IDLE:
            self._session = None
            self._error = None
        self._emit("state_changed", {"old": str(source), "new": str(target)})

    def _arm(self, target: State) -> None:
        now = self._clock.now()
        timeouts = self._config.timeouts
        self._deadline = None
        if target == State.IDLE:
            screensaver = self._config.screensaver
            if screensaver.enabled:
                self._deadline = _plus(now, screensaver.after_seconds)
        elif target == State.BACKGROUND_SELECT:
            self._deadline = _plus(now, timeouts.background_select_seconds)
        elif target == State.COUNTDOWN:
            assert self._session is not None
            self._session.countdown_started_at = now
            self._session.countdown_ticks_emitted = 0
        elif target == State.CAPTURE:
            self._deadline = _plus(now, timeouts.capture_seconds)
        elif target == State.PROCESSING:
            self._deadline = _plus(now, timeouts.processing_seconds)
        elif target == State.PREVIEW:
            self._deadline = _plus(now, timeouts.preview_seconds)
        elif target == State.ERROR:
            self._deadline = _plus(now, timeouts.error_seconds)

    def _to_error(self, code: str) -> None:
        self._error = ErrorInfo(code=code, message=_ERROR_MESSAGES.get(code, "Unbekannter Fehler"))
        self._set_state(State.ERROR)

    # --- client-initiated transitions --------------------------------------

    def start(self, background_id: str | None = None, background_mode: str | None = None) -> None:
        """Begin a session. Without the selection screen the caller says what to use.

        The engine resolves the default against the uploaded backgrounds (it owns
        the registry), so the state machine only stores the answer.
        """
        if self._state != State.IDLE:
            raise ActionRejected("invalid_state", "Es läuft bereits eine Sitzung")
        self._session = Session()
        if self._config.ui.background_select_enabled:
            self._set_state(State.BACKGROUND_SELECT)
            return
        self._session.background_id = None if background_id == "none" else background_id
        self._session.background_mode = background_mode or "none"
        self._set_state(State.COUNTDOWN)

    def select_background(self, background_id: str, background_mode: str) -> None:
        if self._state != State.BACKGROUND_SELECT:
            raise ActionRejected("invalid_state", "Kein Hintergrund erwartet")
        assert self._session is not None
        self._session.background_id = None if background_id == "none" else background_id
        self._session.background_mode = background_mode
        self._set_state(State.COUNTDOWN)

    def wake(self) -> None:
        """Leave the slideshow. Deliberately does *not* start a session: the first
        touch brings the start screen back, only the next one takes a photo."""
        if self._state != State.SCREENSAVER:
            raise ActionRejected("invalid_state", "Kein Bildschirmschoner aktiv")
        self._set_state(State.IDLE)

    def cancel(self) -> None:
        if self._state == State.BACKGROUND_SELECT:
            self._set_state(State.IDLE)
            return
        if self._state == State.COUNTDOWN:
            remaining = self.countdown_remaining() or 0
            if remaining <= self._config.timeouts.countdown_cancel_grace_seconds:
                raise ActionRejected("countdown_locked", "Der Countdown läuft schon")
            self._set_state(State.IDLE)
            return
        raise ActionRejected("invalid_state", "Hier ist kein Abbruch möglich")

    def finish(self) -> None:
        if self._state != State.PREVIEW:
            raise ActionRejected("invalid_state", "Keine Vorschau aktiv")
        self._set_state(State.IDLE)

    def begin_print(self) -> None:
        if self._state != State.PREVIEW:
            raise ActionRejected("invalid_state", "Keine Vorschau aktiv")
        self._set_state(State.PRINTING)

    # --- engine-driven transitions (side effects live in the engine) --------

    def capture_succeeded(self, photo_id: int) -> None:
        assert self._session is not None
        self._session.photo_id = photo_id
        self._set_state(State.PROCESSING)

    def capture_failed(self, code: str = "capture_failed") -> None:
        self._to_error(code)

    def processing_succeeded(self) -> None:
        self._set_state(State.PREVIEW)

    def processing_failed(self, code: str = "pipeline_failed") -> None:
        self._to_error(code)

    def print_submitted(self) -> None:
        assert self._session is not None
        self._session.print_count += 1
        self._set_state(State.PREVIEW)

    def print_failed(self, code: str = "printer_unavailable") -> None:
        self._to_error(code)

    # --- time-driven progression -------------------------------------------

    def poll(self) -> None:
        """Advance anything driven by the clock: countdown ticks and timeouts."""
        now = self._clock.now()
        if self._state == State.COUNTDOWN:
            self._advance_countdown(now)
            return
        if self._deadline is not None and now >= self._deadline:
            self._fire_timeout()

    def _advance_countdown(self, now: datetime) -> None:
        assert self._session is not None
        duration = self._config.countdown.duration_seconds
        started = self._session.countdown_started_at
        assert started is not None
        elapsed = (now - started).total_seconds()
        target_ticks = min(duration, int(elapsed) + 1)
        while self._session.countdown_ticks_emitted < target_ticks:
            self._session.countdown_ticks_emitted += 1
            remaining = duration - (self._session.countdown_ticks_emitted - 1)
            self._emit("countdown_tick", {"remaining": remaining})
        # Fire early by the configured lead so the exposure lands on "0" instead of
        # a second later — the shutter release is not instant (flash duration plus
        # camera latency). The last second of the countdown always survives: a
        # generous lead must never rob the guests of the count itself.
        lead = min(self._config.countdown.shutter_lead_ms / 1000, max(0.0, duration - 1))
        if elapsed >= duration - lead:
            self._set_state(State.CAPTURE)

    def _fire_timeout(self) -> None:
        if self._state == State.IDLE:
            self._set_state(State.SCREENSAVER)
        elif self._state == State.BACKGROUND_SELECT:
            self._set_state(State.IDLE)
        elif self._state == State.PREVIEW:
            self._set_state(State.IDLE)
        elif self._state == State.CAPTURE:
            self._to_error("camera_timeout")
        elif self._state == State.PROCESSING:
            self._to_error("pipeline_failed")
        elif self._state == State.ERROR:
            self._set_state(State.IDLE)


def _plus(moment: datetime, seconds: float) -> datetime:
    return moment + timedelta(seconds=seconds)
