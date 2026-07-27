"""States and the transition table.

The literals and allowed transitions are taken verbatim from
docs/api-contract.md. Any transition not listed here is a programming error and
raises :class:`InvalidTransition` (milestone M1 acceptance).
"""

from __future__ import annotations

from enum import Enum


class State(str, Enum):
    IDLE = "IDLE"
    BACKGROUND_SELECT = "BACKGROUND_SELECT"
    COUNTDOWN = "COUNTDOWN"
    CAPTURE = "CAPTURE"
    PROCESSING = "PROCESSING"
    PREVIEW = "PREVIEW"
    PRINTING = "PRINTING"
    ERROR = "ERROR"

    def __str__(self) -> str:  # so f-strings render "IDLE", not "State.IDLE"
        return self.value


# Exactly the edges from the api-contract transition table, plus the documented
# conditional edge IDLE -> COUNTDOWN (used when background selection is disabled).
ALLOWED_TRANSITIONS: frozenset[tuple[State, State]] = frozenset(
    {
        (State.IDLE, State.BACKGROUND_SELECT),
        (State.IDLE, State.COUNTDOWN),
        (State.BACKGROUND_SELECT, State.COUNTDOWN),
        (State.BACKGROUND_SELECT, State.IDLE),
        (State.COUNTDOWN, State.CAPTURE),
        (State.COUNTDOWN, State.IDLE),
        (State.CAPTURE, State.PROCESSING),
        (State.CAPTURE, State.ERROR),
        (State.PROCESSING, State.PREVIEW),
        (State.PROCESSING, State.ERROR),
        (State.PREVIEW, State.PRINTING),
        (State.PREVIEW, State.IDLE),
        (State.PRINTING, State.PREVIEW),
        (State.PRINTING, State.ERROR),
        (State.ERROR, State.IDLE),
    }
)


class InvalidTransition(Exception):
    """Raised when a transition outside ALLOWED_TRANSITIONS is attempted."""

    def __init__(self, source: State, target: State) -> None:
        super().__init__(f"Ungültiger Zustandsübergang: {source} -> {target}")
        self.source = source
        self.target = target
