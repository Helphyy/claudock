"""Sortie console (rich)."""

from claudock.console import log, progress, prompt, selector, status
from claudock.console.banner import print_banner, render_banner
from claudock.console.console import console
from claudock.console.errors import (
    error_panel,
    info_panel,
    show_exception,
    success_panel,
    warn_panel,
)
from claudock.console.styles import TABLE_BOX, fmt_size, status_markup, truncate_path
from claudock.console.tui import (
    container_recap,
    container_table,
    print_container_recap,
    profile_table,
)

__all__ = [
    "TABLE_BOX",
    "console",
    "container_recap",
    "container_table",
    "error_panel",
    "fmt_size",
    "info_panel",
    "log",
    "print_banner",
    "print_container_recap",
    "profile_table",
    "progress",
    "prompt",
    "selector",
    "status",
    "render_banner",
    "show_exception",
    "status_markup",
    "success_panel",
    "truncate_path",
    "warn_panel",
]
