"""Filesystem helpers that need to escalate past the host user (e.g. removing
files created by root inside a container)."""

from __future__ import annotations

import shutil
from pathlib import Path

from claudock.console import log
from claudock.utils.docker_client import get_client

_HELPER_IMAGE_CANDIDATES = ("alpine:latest", "busybox:latest")


def force_rmtree(path: Path) -> None:
    """Recursively delete `path`. If `shutil.rmtree` hits a PermissionError
    because some files were created by container root, fall back to running
    `rm -rf` inside a throwaway Docker container running as root."""
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
        return
    except PermissionError:
        log.info(
            "Some files are owned by container root; "
            "removing through a throwaway Docker container."
        )

    _docker_rmtree(path)
    if path.exists():
        raise RuntimeError(
            f"Docker-assisted removal failed: {path} still exists. "
            "Try `sudo rm -rf {path}` manually."
        )


def _docker_rmtree(path: Path) -> None:
    client = get_client()
    image = _resolve_helper_image(client)
    parent = path.parent.resolve()
    name = path.name
    client.containers.run(
        image,
        command=["rm", "-rf", f"/target/{name}"],
        volumes={str(parent): {"bind": "/target", "mode": "rw"}},
        remove=True,
        network_disabled=True,
    )


def _resolve_helper_image(client: object) -> str:
    """Pick a small image already present locally; fall back to pulling alpine."""
    for ref in _HELPER_IMAGE_CANDIDATES:
        try:
            client.images.get(ref)  # type: ignore[attr-defined]
            return ref
        except Exception:
            continue
    log.info("Pulling alpine:latest (small helper for privileged file ops)...")
    client.images.pull("alpine:latest")  # type: ignore[attr-defined]
    return "alpine:latest"
