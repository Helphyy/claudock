"""Spinners for short-lived operations.

Wraps `rich.status.Status` and degrades cleanly to a single info line when
stdout is not a TTY (CI, pipe).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager

from claudock.console import log
from claudock.console.console import console


@contextmanager
def step(text: str, *, spinner: str = "dots") -> Iterator[None]:
    """Spinner for a short operation. Logs a plain info line when non-TTY."""
    if not sys.stdout.isatty():
        log.info(text)
        yield
        return
    with console.status(f"[brand]{text}[/]", spinner=spinner, spinner_style="brand"):
        yield
