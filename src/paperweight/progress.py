"""Lightweight progress reporting to stderr for pipeline phases."""

import sys
import time


class ProgressReporter:
    """Write ``paperweight: phase... detail`` lines to stderr.

    Suppressed entirely when *quiet* is ``True``.
    """

    def __init__(self, *, quiet: bool = False):
        self._quiet = quiet
        self._phase_start: float | None = None

    def phase(self, label: str, detail: str = "") -> None:
        """Begin a new phase, printing its status line immediately."""
        self._phase_start = time.monotonic()
        self._emit(label, detail)

    def phase_end(self, label: str, detail: str = "") -> None:
        """End the current phase, appending elapsed time."""
        elapsed = ""
        if self._phase_start is not None:
            secs = time.monotonic() - self._phase_start
            elapsed = f" ({secs:.0f}s)"
        self._emit(label, f"{detail}{elapsed}")
        self._phase_start = None

    def _emit(self, label: str, detail: str) -> None:
        if self._quiet:
            return
        suffix = f" {detail}" if detail else ""
        print(f"paperweight: {label}{suffix}", file=sys.stderr, flush=True)
