"""ASCII banner and visual signature for Claudock."""

from __future__ import annotations

from rich.align import Align
from rich.console import Group
from rich.text import Text

from claudock import __version__
from claudock.console.console import console

# ANSI Shadow style. Width ~70 cols.
_LOGO = r"""
 ██████╗██╗      █████╗ ██╗   ██╗██████╗  ██████╗  ██████╗██╗  ██╗
██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔═══██╗██╔════╝██║ ██╔╝
██║     ██║     ███████║██║   ██║██║  ██║██║   ██║██║     █████╔╝
██║     ██║     ██╔══██║██║   ██║██║  ██║██║   ██║██║     ██╔═██╗
╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝╚██████╔╝╚██████╗██║  ██╗
 ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝╚═╝  ╚═╝
""".strip("\n")

_TAGLINE = "Claude Code, contained."


def render_banner(*, compact: bool = False) -> Group:
    """Render banner + tagline + version as a rich Group."""
    if compact:
        title = Text("◆ claudock", style="brand")
        title.append(f"  v{__version__}", style="version")
        return Group(title)

    logo = Text(_LOGO, style="brand")
    tagline = Text(_TAGLINE, style="brand.dim")
    version = Text(f"v{__version__}", style="version")
    return Group(
        Align.center(logo),
        Align.center(tagline),
        Align.center(version),
    )


def print_banner(*, compact: bool = False) -> None:
    console.print(render_banner(compact=compact))
