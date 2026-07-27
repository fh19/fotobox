"""Real printer backend via CUPS/pycups (milestone M6).

The Selphy CP1500 is driven driverless (IPP-Everywhere) as a normal CUPS queue —
no Gutenprint build needed (the queue already supports ``Postcard.Borderless``).
``pycups`` is imported lazily so the rest of the app runs without it.

Paper-out stops the CUPS queue; the central M6 behaviour is that the guest flow
keeps running and the admin ``Drucker fortsetzen`` button re-enables the queue.
"""

from __future__ import annotations

import logging

from app.config import Config
from app.hardware.base import PrinterState

log = logging.getLogger("fotobox.printer")

# CUPS printer-state values.
_IPP_IDLE = 3
_IPP_PROCESSING = 4
_IPP_STOPPED = 5

# IPP job-state values → the states the engine persists in print_jobs.
_JOB_STATE = {
    3: "pending",  # pending
    4: "pending",  # pending-held
    5: "pending",  # processing
    6: "pending",  # processing-stopped
    7: "cancelled",  # canceled
    8: "failed",  # aborted
    9: "done",  # completed
}

# printer-state-reasons substrings that mean "cannot print right now".
_BLOCKING_REASONS = ("media-empty", "media-needed", "marker-supply-empty", "offline", "shutdown")


def _is_blocking(reason: str) -> bool:
    return any(token in reason for token in _BLOCKING_REASONS)


# Postcard, RGB, true borderless. On the Gutenprint CP1500 queue borderless is a
# real option (StpBorderless, default off) plus StpiShrinkOutput=Expand to fill the
# oversized borderless media edge to edge — otherwise a ~2–3 mm white margin remains.
_PRINT_OPTIONS = {
    "PageSize": "Postcard",
    "ColorModel": "RGB",
    "StpBorderless": "True",
    "StpiShrinkOutput": "Expand",
}


class CupsPrinter:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._queue = config.hardware.printer.queue_name
        self._conn = None

    # --- protocol -----------------------------------------------------------

    def available(self) -> bool:
        attrs = self._attrs()
        if attrs is None:
            return False
        if attrs.get("printer-state") == _IPP_STOPPED:
            return False
        if any(_is_blocking(r) for r in attrs.get("printer-state-reasons", [])):
            return False
        return attrs.get("printer-state") in (_IPP_IDLE, _IPP_PROCESSING)

    def state(self) -> PrinterState:
        attrs = self._attrs()
        if attrs is None:
            return PrinterState.OFFLINE
        reasons = attrs.get("printer-state-reasons", [])
        if any("offline" in r or "shutdown" in r for r in reasons):
            return PrinterState.OFFLINE
        return {
            _IPP_IDLE: PrinterState.IDLE,
            _IPP_PROCESSING: PrinterState.PRINTING,
            _IPP_STOPPED: PrinterState.ERROR,
        }.get(attrs.get("printer-state"), PrinterState.OFFLINE)

    def paused(self) -> bool:
        attrs = self._attrs()
        if attrs is None:
            return False
        # A paper/band-out stops the CUPS queue → resume re-enables it (M6).
        return attrs.get("printer-state") == _IPP_STOPPED

    def submit(self, path: str) -> int:
        conn = self._connection()
        return conn.printFile(self._queue, path, "Fotobox", dict(_PRINT_OPTIONS))

    def job_state(self, job_id: int) -> str | None:
        """Read ``job-state`` for a submitted job.

        Relies on the CUPS job history (``PreserveJobHistory``, on by default);
        once a job is purged the attributes are gone and we report ``None``
        rather than guessing an outcome.
        """
        try:
            attrs = self._connection().getJobAttributes(job_id)
        except Exception as exc:
            log.debug("Job %s nicht abfragbar: %s", job_id, exc)
            return None
        return _JOB_STATE.get(attrs.get("job-state"))

    # --- admin operations ---------------------------------------------------

    def resume(self) -> None:
        """`cupsenable` + accept jobs — the answer to a paper-out (M6)."""
        conn = self._connection()
        conn.enablePrinter(self._queue)
        conn.acceptJobs(self._queue)

    def cancel_all(self) -> None:
        self._connection().cancelAllJobs(self._queue)

    def queue_length(self) -> int:
        try:
            jobs = self._connection().getJobs(which_jobs="not-completed")
        except Exception:
            return 0
        return len(jobs)

    # --- internals ----------------------------------------------------------

    def _connection(self):
        import cups

        if self._conn is None:
            self._conn = cups.Connection()
        return self._conn

    def _attrs(self) -> dict | None:
        try:
            printers = self._connection().getPrinters()
        except Exception as exc:
            log.debug("CUPS nicht erreichbar: %s", exc)
            return None
        return printers.get(self._queue)
