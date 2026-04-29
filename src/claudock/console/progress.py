"""Multi-bar progress for Docker pulls (one bar per layer)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from claudock.console import log
from claudock.console.console import console

if TYPE_CHECKING:
    from docker import DockerClient

# Docker statuses that mark a layer as finished.
_DONE_STATUSES = {"Pull complete", "Already exists", "Download complete"}
# Statuses to ignore (global, no layer id).
_GLOBAL_STATUSES = {
    "Pulling from",
    "Status: Image is up to date for",
    "Status: Downloaded newer image for",
    "Digest:",
}


def pull_image(
    client: DockerClient,
    repository: str,
    tag: str = "latest",
    *,
    platform: str | None = None,
) -> bool:
    """Pull an image with a streamed layer-by-layer progress display.

    Returns True on success, False on failure.
    """
    full = f"{repository}:{tag}"

    if not sys.stdout.isatty():
        log.info(f"Pulling {full}...")
        try:
            client.images.pull(repository, tag=tag, platform=platform)
        except Exception as exc:
            log.err(f"Pull failed: {exc}")
            return False
        return True

    progress = Progress(
        TextColumn("[brand.dim]{task.fields[layer_id]:<14.14}"),
        TextColumn("[muted]{task.fields[state]:<22}"),
        BarColumn(bar_width=None, complete_style="ok", finished_style="ok"),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )

    tasks: dict[str, int] = {}
    success = True

    with progress:
        try:
            for event in client.api.pull(
                repository,
                tag=tag,
                stream=True,
                decode=True,
                platform=platform,
            ):
                layer_id = event.get("id")
                status = event.get("status", "")
                detail = event.get("progressDetail") or {}
                current = detail.get("current", 0)
                total = detail.get("total", 0)

                if "error" in event:
                    log.err(f"Pull: {event['error']}")
                    success = False
                    continue

                if not layer_id or any(status.startswith(g) for g in _GLOBAL_STATUSES):
                    continue

                if layer_id not in tasks:
                    tasks[layer_id] = progress.add_task(
                        layer_id,
                        total=total or 1,
                        layer_id=layer_id,
                        state=status or "...",
                    )

                tid = tasks[layer_id]
                if total:
                    progress.update(tid, total=total)
                if status in _DONE_STATUSES:
                    progress.update(
                        tid,
                        completed=total or 1,
                        total=total or 1,
                        state=status,
                    )
                else:
                    progress.update(tid, completed=current, state=status)
        except Exception as exc:
            log.err(f"Pull failed: {exc}")
            success = False

    return success
