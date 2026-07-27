"""Injectable clock.

Every time-based decision in the state machine reads the current time through a
:class:`Clock`. Production uses :class:`RealClock`; tests inject
:class:`FakeClock` so timeouts and the countdown can be exercised deterministically
with a fake clock instead of ``sleep`` (milestone M1 acceptance).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Timezone-aware current time (ISO 8601 with offset)."""
        ...


class RealClock:
    """Wall-clock time in the local timezone."""

    def now(self) -> datetime:
        return datetime.now().astimezone()


class FakeClock:
    """Manually advanced clock for tests."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 8, 15, 21, 0, 0, tzinfo=UTC).astimezone()

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)

    def set(self, moment: datetime) -> None:
        self._now = moment
