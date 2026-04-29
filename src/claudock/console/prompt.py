"""Minimal wrappers around `rich.prompt`.

- `ask(prompt)`: cyan `[?]` prefix
- `confirm(question, default)`: `[Y/n]` or `[y/N]`
- `acknowledge(message)`: `[>]` prefix, waits for ENTER
"""

from __future__ import annotations

import sys

from rich.prompt import Confirm, Prompt

from claudock.console.console import console


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def ask(
    question: str,
    *,
    default: str | None = None,
    choices: list[str] | None = None,
    show_choices: bool = True,
    password: bool = False,
) -> str:
    """Text prompt. Returns default if non-interactive, raises if no default."""
    if not _is_interactive():
        if default is not None:
            return default
        raise RuntimeError(f"Non-interactive prompt without default: {question}")
    return Prompt.ask(
        f"[info]\\[?][/] {question}",
        default=default,
        choices=choices,
        show_choices=show_choices,
        password=password,
        console=console,
    )


def confirm(question: str, *, default: bool = False) -> bool:
    """y/N confirmation. Returns the default if non-interactive."""
    if not _is_interactive():
        return default
    return Confirm.ask(
        f"[info]\\[?][/] {question}",
        default=default,
        console=console,
    )


def acknowledge(message: str) -> None:
    """Print a message and wait for ENTER. No-op if non-interactive.

    Ctrl+C re-raises so the top-level handler renders the discreet
    `Cancelled.` line, instead of silently moving on as if the user
    had confirmed."""
    if not _is_interactive():
        console.print(f"[accent]\\[>][/] {message}")
        return
    try:
        console.input(f"[accent]\\[>][/] {message} [muted](press ENTER to continue)[/] ")
    except EOFError:
        pass
