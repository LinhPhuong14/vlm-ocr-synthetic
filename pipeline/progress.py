"""A progress bar for a run, and the two rules that keep it out of the way.

    from pipeline.progress import Bar
    with Bar(total=1200, label="ảnh") as bar:
        bar.advance(37, note="market_vat")

**Rule one: it draws to stderr, never to stdout.** Every tool in this
repository that reads another one reads stdout -- `tools/baseline.py` parses
`generate_dataset.py`, `pipeline/worker.py` answers with a single line of JSON.
A bar on stdout would be inside that JSON.

**Rule two: it draws only to a terminal.** Redirected to a file or a pipe, it
prints one ordinary line per update instead, at most every `QUIET_EVERY`
images. A carriage return in a CI log turns a run into one 400 000-character
line, and a log that cannot be read is a log that nobody reads after the third
time it happens.

The two rules together mean the bar is a *view* and never a record. Nothing
downstream may parse it; what a run actually did is in `manifest.json`,
`timings.json` and `report.json`, all of which are written whether anyone was
watching or not.

## What it shows, and why each part earns its place

    [████████░░░░░░░░]  312/1200 ảnh  26%  4m12s  còn ~11m50s  market_vat

* the count, because "how far in" is the question;
* the percentage, because the bar alone is hard to read at a glance;
* elapsed, because a run that has stopped moving looks exactly like a slow one
  until you have watched the number for a while;
* an estimate, computed from the rate so far and rounded coarsely -- a
  four-significant-figure ETA on a rate that changes with the layout mix is a
  number that lies about how well it knows;
* what is being drawn, because a run stuck on one layout for two minutes is
  the interesting case and the name is how anybody starts looking.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from typing import TextIO

# Redrawn no more often than this. A bar that repaints per image spends more
# time formatting than the renderer spends drawing, on a fast layout.
REDRAW_SECONDS = 0.2

# When there is no terminal: print a plain line every this many items instead
# of a bar. Coarse on purpose -- this is the log a person reads afterwards, not
# a live view.
QUIET_EVERY = 25

FULL, EMPTY = "█", "░"
MIN_WIDTH, MAX_WIDTH = 10, 40


def duration(seconds: float) -> str:
    """`4m12s`, `1h03m`, `9s`. Two units at most, and never more precise than
    the thing being measured deserves."""
    seconds = max(int(seconds), 0)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def _wide() -> int:
    return shutil.get_terminal_size((80, 24)).columns


class Bar:
    """One run's progress. Safe to use when nothing is watching."""

    def __init__(self, total: int, label: str = "ảnh", stream: TextIO | None = None,
                 enabled: bool | None = None):
        self.total = max(int(total), 0)
        self.label = label
        self.stream = stream if stream is not None else sys.stderr
        # `enabled` is resolved once and stored, so a caller can ask what it
        # decided -- a run that prints no bar should not also print nothing.
        self.tty = self._decide(enabled)
        self.done = 0
        self.note = ""
        self.started = time.monotonic()
        self._painted = 0.0
        self._last_quiet = 0
        self._dirty = False

    def _decide(self, enabled: bool | None) -> bool:
        if enabled is not None:
            return bool(enabled)
        if os.environ.get("NO_COLOR") or os.environ.get("CI"):
            return False
        return bool(getattr(self.stream, "isatty", lambda: False)())

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> "Bar":
        self.paint(force=True)
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        """Leave the line clean for whatever prints next.

        Without this the summary lands on top of the bar's own characters, and
        the last thing a person sees from a finished run is half a bar.
        """
        if self.tty and self._dirty:
            self.stream.write("\r" + " " * max(_wide() - 1, 0) + "\r")
            self.stream.flush()
            self._dirty = False

    # -- moving ------------------------------------------------------------

    def advance(self, count: int = 1, note: str = "") -> None:
        self.done += count
        if note:
            self.note = note
        self.paint()

    def set(self, done: int, note: str = "") -> None:
        self.done = done
        if note:
            self.note = note
        self.paint()

    # -- drawing -----------------------------------------------------------

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def eta(self) -> str:
        """Coarse on purpose. See the module docstring."""
        if self.done <= 0 or self.done >= self.total:
            return ""
        rate = self.done / max(self.elapsed, 1e-6)
        return f"còn ~{duration((self.total - self.done) / rate)}"

    def render(self, width: int | None = None) -> str:
        width = _wide() if width is None else width
        share = (self.done / self.total) if self.total else 1.0
        share = min(max(share, 0.0), 1.0)
        tail = (f"{self.done}/{self.total} {self.label}  {share:3.0%}  "
                f"{duration(self.elapsed)}")
        eta = self.eta()
        if eta:
            tail += f"  {eta}"
        if self.note:
            tail += f"  {self.note}"
        # The bar takes whatever the text leaves, between a floor and a
        # ceiling: a 200-column terminal does not want a 190-character bar, and
        # a 60-column one must still show the numbers.
        room = width - len(tail) - 4
        cells = max(min(room, MAX_WIDTH), MIN_WIDTH)
        filled = int(round(cells * share))
        return f"[{FULL * filled}{EMPTY * (cells - filled)}]  {tail}"

    def paint(self, force: bool = False) -> None:
        if not self.tty:
            self._quiet()
            return
        now = time.monotonic()
        if not force and now - self._painted < REDRAW_SECONDS:
            return
        self._painted = now
        line = self.render()
        self.stream.write("\r" + line[:max(_wide() - 1, 0)].ljust(_wide() - 1))
        self.stream.flush()
        self._dirty = True

    def _quiet(self) -> None:
        """No terminal: one plain line every `QUIET_EVERY`, and at the end."""
        if self.done - self._last_quiet < QUIET_EVERY and self.done < self.total:
            return
        if self.done == self._last_quiet:
            return
        self._last_quiet = self.done
        share = (self.done / self.total) if self.total else 1.0
        note = f"  {self.note}" if self.note else ""
        self.stream.write(f"  {self.done}/{self.total} {self.label} "
                          f"({share:.0%}, {duration(self.elapsed)}){note}\n")
        self.stream.flush()

    # -- saying something without breaking the bar --------------------------

    def say(self, message: str) -> None:
        """Print a line that must survive, above the bar.

        A run has things to report while it is running -- a shard failing, a
        warning worth seeing now. Writing them straight to the stream would
        interleave with the bar and leave fragments behind, so the bar is
        erased, the line is printed, and the bar is drawn again.
        """
        if self.tty and self._dirty:
            self.stream.write("\r" + " " * max(_wide() - 1, 0) + "\r")
        self.stream.write(message.rstrip("\n") + "\n")
        self.stream.flush()
        self._dirty = False
        if self.tty:
            self.paint(force=True)


__all__ = ["Bar", "MAX_WIDTH", "MIN_WIDTH", "QUIET_EVERY", "REDRAW_SECONDS",
           "duration"]
