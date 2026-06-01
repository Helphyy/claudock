"""Render errors as rich panels with contextual hints."""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from claudock.console.console import console
from claudock.console.styles import TABLE_BOX
from claudock.exceptions import (
    ClaudockError,
    ConfigError,
    ContainerAlreadyExistsError,
    ContainerNotFoundError,
    DockerUnavailableError,
    ImageNotFoundError,
)
from claudock.model.profile import (
    InvalidProfileNameError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
)


def error_panel(title: str, message: str, hint: str | None = None) -> None:
    body = Text.from_markup(message)
    if hint:
        body.append("\n\n")
        body.append("Hint  ", style="bold cyan")
        body.append(hint, style="hint")
    console.print(
        Panel(
            body,
            title=f"[panel.title.err]✖ {title}[/]",
            border_style="panel.border.err",
            box=TABLE_BOX,
            padding=(0, 1),
        )
    )


def warn_panel(title: str, message: str) -> None:
    console.print(
        Panel(
            Text.from_markup(message),
            title=f"[panel.title.warn]⚠ {title}[/]",
            border_style="panel.border.warn",
            box=TABLE_BOX,
            padding=(0, 1),
        )
    )


def success_panel(title: str, message: str) -> None:
    console.print(
        Panel(
            Text.from_markup(message),
            title=f"[panel.title.ok]✔ {title}[/]",
            border_style="panel.border.ok",
            box=TABLE_BOX,
            padding=(0, 1),
        )
    )


def info_panel(title: str, message: str) -> None:
    console.print(
        Panel(
            Text.from_markup(message),
            title=f"[panel.title.info]◆ {title}[/]",
            border_style="panel.border.info",
            box=TABLE_BOX,
            padding=(0, 1),
        )
    )


# --- Mapping exception → title + hint ---------------------------------------

_HINTS: dict[type[Exception], tuple[str, str | None]] = {
    DockerUnavailableError: (
        "Docker unreachable",
        "Make sure the daemon is running. On Linux: `systemctl status docker`. On macOS/Windows: open Docker Desktop.",
    ),
    ContainerNotFoundError: (
        "Container not found",
        "List existing containers with `claudock info`.",
    ),
    ContainerAlreadyExistsError: (
        "Container already exists",
        "Use `claudock start <name>` to restart it, or `claudock remove <name>` then recreate.",
    ),
    ImageNotFoundError: (
        "Image not found",
        "Pull it: `claudock image install`. Or build locally: `cd claudock-images && make build`.",
    ),
    InvalidProfileNameError: (
        "Invalid profile name",
        "Expected: lowercase + digits + `-` or `_`, max 32 chars. Examples: `perso`, `client-acme`.",
    ),
    ProfileNotFoundError: (
        "Profile not found",
        "List profiles with `claudock profile list`. Create one with `claudock profile create <name>`.",
    ),
    ProfileAlreadyExistsError: (
        "Profile already exists",
        "Pick another name or remove the existing one: `claudock profile remove <name>`.",
    ),
    ConfigError: (
        "Invalid configuration",
        "Check `~/.claudock/config.yml`, or remove it to regenerate the defaults at next run.",
    ),
}


def show_exception(exc: BaseException) -> None:
    """Render an error panel matching the exception type."""
    if isinstance(exc, ValueError):
        error_panel("Invalid argument", str(exc))
        return

    for cls, (title, hint) in _HINTS.items():
        if isinstance(exc, cls):
            error_panel(title, str(exc) or cls.__name__, hint=hint)
            return

    if isinstance(exc, ClaudockError):
        error_panel("Claudock error", str(exc) or exc.__class__.__name__)
        return

    error_panel(
        "Unexpected error",
        f"{exc.__class__.__name__}: {exc}",
        hint="If the issue persists, please open an issue with the trace above.",
    )
