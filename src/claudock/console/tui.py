"""Polished tables and recap panels.

Tables use a bold cyan header, rounded box, colored statuses, and a 2-column
container recap (label / value).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from claudock.console.console import console
from claudock.console.styles import TABLE_BOX, fmt_size, status_markup, truncate_path

if TYPE_CHECKING:
    from claudock.model import ClaudockContainer
    from claudock.model.container_config import ContainerConfig
    from claudock.model.profile import Profile


def _new_table(title: str | None = None) -> Table:
    return Table(
        title=title,
        title_style="brand",
        header_style="bold cyan",
        border_style="brand.dim",
        box=TABLE_BOX,
        show_lines=False,
        pad_edge=True,
    )


def container_table(containers: list[ClaudockContainer]) -> Table:
    table = _new_table("Claudock containers")
    table.add_column("Name", style="name")
    table.add_column("Status")
    table.add_column("Profile", style="accent")
    table.add_column("Image", style="value")
    table.add_column("Workspace", style="path", overflow="fold")
    for c in sorted(containers, key=lambda x: x.name):
        table.add_row(
            c.name,
            status_markup(c.status),
            c.profile,
            c.image_tag,
            truncate_path(c.workspace, 50),
        )
    return table


def profile_table(
    profiles: list[Profile],
    counts: dict[str, int],
) -> Table:
    table = _new_table("Claudock profiles")
    table.add_column("Name", style="name")
    table.add_column("Size", justify="right", style="value")
    table.add_column("Modified", style="muted")
    table.add_column("Containers", justify="right")
    table.add_column("Path", style="path", overflow="fold")
    for p in profiles:
        mod = p.last_modified.strftime("%Y-%m-%d %H:%M") if p.last_modified else "-"
        n = counts.get(p.name, 0)
        n_disp = f"[ok]{n}[/]" if n > 0 else f"[muted]{n}[/]"
        table.add_row(
            p.name,
            fmt_size(p.size_bytes),
            mod,
            n_disp,
            truncate_path(str(p.path), 50),
        )
    return table


def container_recap(spec: ContainerConfig) -> Table:
    """2-column label/value table summarizing a container before creation."""
    t = Table(
        title=f"Container recap [name]{spec.name}[/]",
        title_style="brand",
        show_header=False,
        border_style="panel.border.info",
        box=TABLE_BOX,
        pad_edge=True,
    )
    t.add_column("Label", style="key", no_wrap=True)
    t.add_column("Value", style="value", overflow="fold")

    def add(label: str, value: str) -> None:
        t.add_row(label, value)

    add("Name", f"[name]{spec.name}[/]")
    add("Image", f"[value]{spec.image}[/]")
    add("Profile", f"[accent]{spec.profile_name}[/]")
    add("Hostname", spec.hostname or spec.name)
    add("Workspace", f"[path]{spec.workspace_host}[/] → /workspace")
    add("Claude auth", f"[path]{spec.profile_claude_dir}[/] → /root/.claude")
    add("Network", spec.network_mode)
    if spec.extra_volumes:
        vols = "\n".join(f"[path]{v.host}[/] → {v.container} [muted]({v.mode})[/]" for v in spec.extra_volumes)
        add("Extra volumes", vols)
    if spec.extra_ports:
        ports = "\n".join(f"{p.host} → {p.container}/{p.proto}" for p in spec.extra_ports)
        add("Ports", ports)
    if spec.extra_env:
        envs = "\n".join(f"[key]{k}[/]=[value]{v}[/]" for k, v in spec.extra_env.items())
        add("Extra env", envs)
    if spec.extra_caps:
        add("Added caps", ", ".join(spec.extra_caps))
    if spec.disposable:
        add("Mode", "[warn]disposable (--tmp)[/]")
    return t


def print_container_recap(spec: ContainerConfig) -> None:
    console.print(container_recap(spec))


def container_detail(c: ClaudockContainer) -> Table:
    """Full detail for one existing container (future `claudock info <name>`)."""
    t = Table(
        title=f"Container [name]{c.name}[/]",
        title_style="brand",
        show_header=False,
        border_style="panel.border.info",
        box=TABLE_BOX,
    )
    t.add_column("Label", style="key", no_wrap=True)
    t.add_column("Value", style="value", overflow="fold")
    t.add_row("Status", status_markup(c.status))
    t.add_row("Profile", f"[accent]{c.profile}[/]")
    t.add_row("Image", c.image_tag)
    t.add_row("Workspace", f"[path]{c.workspace}[/]")
    return t
