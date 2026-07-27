"""Pipeline error type.

Separate module so pipeline sub-modules can import it without a cycle through
the runner.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Raised when processing fails. The original is always left untouched."""
