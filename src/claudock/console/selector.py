"""Generic interactive selector.

Pattern: print a numbered table (`#` column 1..N), then prompt the user to
type a number. No curses, no alt-screen; just a polished table plus
`prompt.ask(choices=[...], show_choices=False)`.

If the list has a single item, it is auto-selected. If empty, returns None.
If stdin is not a TTY (CI, pipe), returns the default or None.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from rich.table import Table

from claudock.console import prompt
from claudock.console.console import console
from claudock.console.styles import TABLE_BOX

T = TypeVar("T")


def select_from_table(
    items: list[T],
    *,
    title: str,
    columns: list[str],
    render_row: Callable[[T], list[str]],
    object_label: str = "item",
    auto_single: bool = True,
) -> T | None:
    """Print an indexed table and ask the user for a number.

    - `columns`: column names besides the auto-prepended `#`.
    - `render_row(item)`: returns one string per `columns` entry.
    - `auto_single`: if True and only one item, return it without asking.
    """
    if not items:
        return None
    if auto_single and len(items) == 1:
        return items[0]

    keys = [str(i) for i in range(1, len(items) + 1)]

    table = Table(
        title=title,
        title_style="brand",
        header_style="bold cyan",
        border_style="brand.dim",
        box=TABLE_BOX,
        pad_edge=True,
    )
    table.add_column("#", style="kbd", justify="right")
    for col in columns:
        table.add_column(col)
    for key, item in zip(keys, items, strict=True):
        table.add_row(key, *render_row(item))
    console.print(table)

    try:
        choice = prompt.ask(
            f"Pick a {object_label} (number)",
            default=keys[0],
            choices=keys,
            show_choices=False,
        )
    except (RuntimeError, EOFError, KeyboardInterrupt):
        return None

    try:
        idx = int(choice) - 1
    except ValueError:
        return None
    if 0 <= idx < len(items):
        return items[idx]
    return None


def select_from_list(
    items: list[str],
    *,
    object_label: str = "item",
    auto_single: bool = True,
) -> str | None:
    """Pick one entry from a list of strings via a single-column table."""
    return select_from_table(
        items,
        title=f"Pick a {object_label}",
        columns=["Name"],
        render_row=lambda s: [s],
        object_label=object_label,
        auto_single=auto_single,
    )
