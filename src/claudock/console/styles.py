"""Centralized display mappings: container statuses, formatters."""

from __future__ import annotations

from rich.box import ROUNDED

# Standard box style for every Claudock table and panel.
TABLE_BOX = ROUNDED

# Status glyphs (ascii-fallback safe).
STATUS_GLYPH: dict[str, str] = {
    "running": "●",
    "created": "○",
    "exited": "■",
    "paused": "‖",
    "restarting": "↻",
    "dead": "✖",
    "removing": "…",
}


def status_markup(status: str) -> str:
    """Render a container status as rich markup: glyph + themed color."""
    style = f"status.{status}" if f"status.{status}" in {
        "status.running",
        "status.created",
        "status.exited",
        "status.paused",
        "status.restarting",
        "status.dead",
        "status.removing",
    } else "muted"
    glyph = STATUS_GLYPH.get(status, "·")
    return f"[{style}]{glyph} {status}[/]"


def fmt_size(n: int) -> str:
    """Human-readable size for a byte count."""
    f = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024 or unit == "GB":
            return f"{f:.0f} {unit}" if unit == "B" else f"{f:.1f} {unit}"
        f /= 1024
    return f"{f:.1f} TB"


def truncate_path(path: str, max_len: int = 50) -> str:
    """Truncate an overly long path while keeping the readable suffix."""
    if len(path) <= max_len:
        return path
    keep = max_len - 1
    return "…" + path[-keep:]
