"""Represents a Claudock container (creation, lifecycle, attach)."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass

from docker.errors import APIError, NotFound
from docker.models.containers import Container

from claudock.constants import CONTAINER_PREFIX, LABEL_MANAGED_BY, LABEL_PROFILE
from claudock.exceptions import (
    ContainerAlreadyExistsError,
    ContainerNotFoundError,
)
from claudock.model.container_config import ContainerConfig
from claudock.utils.docker_client import get_client


def _docker_io_flags() -> list[str]:
    """Pick -i / -t flags depending on whether stdin/stdout are TTYs."""
    flags = []
    if sys.stdin.isatty():
        flags.append("-i")
    if sys.stdin.isatty() and sys.stdout.isatty():
        flags.append("-t")
    return flags or ["-i"]


@dataclass
class ClaudockContainer:
    """Application-level view of a Docker container managed by Claudock."""

    raw: Container

    @property
    def name(self) -> str:
        n = self.raw.name or ""
        return n.removeprefix(CONTAINER_PREFIX)

    @property
    def status(self) -> str:
        return self.raw.status

    @property
    def image_tag(self) -> str:
        tags = self.raw.image.tags if self.raw.image else []
        return tags[0] if tags else (self.raw.image.short_id if self.raw.image else "<unknown>")

    @property
    def workspace(self) -> str:
        for m in self.raw.attrs.get("Mounts", []):
            if m.get("Destination") == "/workspace":
                return m.get("Source", "")
        return ""

    @property
    def profile(self) -> str:
        labels = self.raw.labels or {}
        return labels.get(LABEL_PROFILE, "?")

    def reload(self) -> None:
        self.raw.reload()

    def start_code_server(self, listen_port: int = 8080, workdir: str = "/workspace") -> None:
        """Start code-server in the background inside the container (auth=none, listens on 0.0.0.0)."""
        cmd = (
            "pkill -f 'code-server' 2>/dev/null; "
            f"nohup code-server --bind-addr 0.0.0.0:{listen_port} "
            f"--auth none {workdir} "
            "> /tmp/code-server.log 2>&1 &"
        )
        self.raw.exec_run(["sh", "-c", cmd], detach=True)

    def start(self) -> None:
        if self.raw.status != "running":
            self.raw.start()
            self.reload()

    def stop(self, timeout: int = 10) -> None:
        if self.raw.status == "running":
            self.raw.stop(timeout=timeout)
            self.reload()

    def remove(self, force: bool = False) -> None:
        self.raw.remove(force=force)

    def attach_interactive(self, command: list[str], *, log_to: str | None = None) -> int:
        """Attach an interactive command via `docker exec` for a real TTY.

        If `log_to` is provided (a path inside the container), the session is
        recorded with asciinema into that file.

        We force `umask 002` before the command so files created in /workspace
        are group-writable (combined with the setgid bit set on /workspace).
        """
        flags = _docker_io_flags()
        wrapped = " ".join(shlex.quote(a) for a in command)
        sh_cmd = f"umask 002; exec {wrapped}"
        if log_to:
            cmd = [
                "docker", "exec", *flags, self.raw.name or "",
                "asciinema", "rec", "--command", f"sh -c {shlex.quote(sh_cmd)}", "--quiet", log_to,
            ]
        else:
            cmd = ["docker", "exec", *flags, self.raw.name or "", "sh", "-c", sh_cmd]
        return subprocess.call(cmd, env=os.environ.copy())

    def exec_command(self, command: list[str]) -> int:
        flags = _docker_io_flags()
        cmd = ["docker", "exec", *flags, self.raw.name or "", *command]
        return subprocess.call(cmd, env=os.environ.copy())

    @classmethod
    def create(cls, spec: ContainerConfig) -> ClaudockContainer:
        client = get_client()
        try:
            client.containers.get(spec.container_name)
            raise ContainerAlreadyExistsError(
                f"A container named '{spec.name}' already exists."
            )
        except NotFound:
            pass

        spec.workspace_host.mkdir(parents=True, exist_ok=True)

        try:
            raw = client.containers.run(**spec.to_run_kwargs())
        except APIError as exc:
            raise ContainerAlreadyExistsError(str(exc)) from exc
        return cls(raw=raw)

    @classmethod
    def get(cls, name: str) -> ClaudockContainer:
        client = get_client()
        try:
            raw = client.containers.get(f"{CONTAINER_PREFIX}{name}")
        except NotFound as exc:
            raise ContainerNotFoundError(f"No Claudock container named '{name}'.") from exc
        return cls(raw=raw)

    @classmethod
    def list_all(cls) -> list[ClaudockContainer]:
        client = get_client()
        raws = client.containers.list(
            all=True,
            filters={"label": f"{LABEL_MANAGED_BY}=claudock"},
        )
        return [cls(raw=r) for r in raws]
