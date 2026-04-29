"""rich.Console singleton and global palette."""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

# Single palette reused everywhere. Any color in code should reference one of
# these names instead of using a literal, so the look stays consistent.
THEME = Theme(
    {
        # Semantic states
        "info": "bold cyan",
        "ok": "bold green3",
        "warn": "bold yellow",
        "err": "bold red",
        "muted": "grey50",
        # Identity
        "brand": "bold bright_cyan",
        "brand.dim": "cyan3",
        "accent": "bold magenta",
        "name": "bold magenta",
        "version": "grey62",
        # Content
        "key": "bold white",
        "value": "bright_white",
        "kbd": "reverse bold cyan",
        "hint": "italic grey62",
        "path": "blue",
        # Container statuses
        "status.running": "bold green3",
        "status.exited": "grey50",
        "status.created": "bright_yellow",
        "status.paused": "yellow",
        "status.restarting": "bright_cyan",
        "status.dead": "bold red",
        "status.removing": "bright_red",
        # Panels
        "panel.title.info": "bold cyan",
        "panel.title.ok": "bold green3",
        "panel.title.warn": "bold yellow",
        "panel.title.err": "bold red",
        "panel.border.info": "cyan",
        "panel.border.ok": "green3",
        "panel.border.warn": "yellow",
        "panel.border.err": "red",
    }
)

console = Console(theme=THEME, highlight=False)
