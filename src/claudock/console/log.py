"""Minimal CLI logger with colored prefixes.

Prefixes:
- `[*]` info, cyan
- `[!]` warning, yellow
- `[-]` error, red
- `[+]` success, green
- `[D]` debug, yellow
- `[V]` verbose, blue

All modules should route their non-table/non-panel user-facing output through
this module. Panels go through `console.errors`.
"""

from __future__ import annotations

from claudock.console.console import console

_state = {"verbose": False, "debug": False, "quiet": False}


def set_verbosity(*, verbose: bool = False, debug: bool = False, quiet: bool = False) -> None:
    _state["verbose"] = verbose or debug
    _state["debug"] = debug
    _state["quiet"] = quiet


def info(msg: str) -> None:
    if _state["quiet"]:
        return
    console.print(f"[info]\\[*][/] {msg}")


def warn(msg: str) -> None:
    if _state["quiet"]:
        return
    console.print(f"[warn]\\[!][/] {msg}")


def err(msg: str) -> None:
    console.print(f"[err]\\[-][/] {msg}")


def success(msg: str) -> None:
    if _state["quiet"]:
        return
    console.print(f"[ok]\\[+][/] {msg}")


def debug(msg: str) -> None:
    if not _state["debug"] or _state["quiet"]:
        return
    console.print(f"[warn]\\[D][/] [muted]{msg}[/]")


def verbose(msg: str) -> None:
    if not _state["verbose"] or _state["quiet"]:
        return
    console.print(f"[info]\\[V][/] [muted]{msg}[/]")


def raw(msg: str) -> None:
    """Raw output (rich markup allowed); honors quiet."""
    if _state["quiet"]:
        return
    console.print(msg)


def cancelled(msg: str = "Cancelled.") -> None:
    """Discrete yellow line shown after a Ctrl+C / explicit cancel.
    No `[!]` prefix, no panel — same UX as pvecli's `print_cancelled`."""
    console.print(f"[warn]{msg}[/]")
