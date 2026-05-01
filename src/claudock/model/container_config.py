"""Build `docker run` parameters for a Claudock container."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claudock import __version__
from claudock.constants import (
    CONTAINER_CLAUDE_DIR,
    CONTAINER_CLAUDE_JSON,
    CONTAINER_LOG_DIR,
    CONTAINER_PREFIX,
    CONTAINER_WORKSPACE,
    LABEL_MANAGED_BY,
    LABEL_NAME,
    LABEL_PROFILE,
    LABEL_VERSION,
)


@dataclass
class VolumeMount:
    host: str
    container: str
    mode: str = "rw"

    @classmethod
    def parse(cls, spec: str) -> VolumeMount:
        """Parse a 'host:container[:mode]' spec."""
        parts = spec.split(":")
        if len(parts) == 2:
            return cls(host=parts[0], container=parts[1])
        if len(parts) == 3:
            return cls(host=parts[0], container=parts[1], mode=parts[2])
        raise ValueError(f"Invalid volume '{spec}', expected host:container[:mode]")


@dataclass
class PortMapping:
    host: int
    container: int
    proto: str = "tcp"
    host_ip: str | None = None

    @classmethod
    def parse(cls, spec: str) -> PortMapping:
        """Parse '[host_ip:]host_port:container_port[/proto]'."""
        proto = "tcp"
        rest = spec
        if "/" in rest:
            rest, proto = rest.split("/", 1)
        parts = rest.split(":")
        try:
            if len(parts) == 2:
                return cls(host=int(parts[0]), container=int(parts[1]), proto=proto)
            if len(parts) == 3:
                return cls(host_ip=parts[0], host=int(parts[1]), container=int(parts[2]), proto=proto)
            raise ValueError
        except ValueError as exc:
            raise ValueError(f"Invalid port '{spec}', expected [ip:]host:container[/proto]") from exc


@dataclass
class ContainerConfig:
    """Spec of a Claudock container to be created."""

    name: str
    image: str
    workspace_host: Path
    profile_name: str
    profile_claude_dir: Path
    profile_claude_json: Path
    logs_host_dir: Path
    network_mode: str = "bridge"
    hostname: str | None = None
    extra_env: dict[str, str] = field(default_factory=dict)
    extra_volumes: list[VolumeMount] = field(default_factory=list)
    extra_ports: list[PortMapping] = field(default_factory=list)
    extra_caps: list[str] = field(default_factory=list)
    disposable: bool = False

    @property
    def container_name(self) -> str:
        return f"{CONTAINER_PREFIX}{self.name}"

    @property
    def labels(self) -> dict[str, str]:
        return {
            LABEL_MANAGED_BY: "claudock",
            LABEL_NAME: self.name,
            LABEL_VERSION: __version__,
            LABEL_PROFILE: self.profile_name,
        }

    def to_run_kwargs(self) -> dict[str, Any]:
        """Args passed to `docker.containers.run` (or `create`)."""
        volumes: dict[str, dict[str, str]] = {
            str(self.workspace_host): {"bind": CONTAINER_WORKSPACE, "mode": "rw"},
            str(self.profile_claude_dir): {"bind": CONTAINER_CLAUDE_DIR, "mode": "rw"},
            str(self.profile_claude_json): {"bind": CONTAINER_CLAUDE_JSON, "mode": "rw"},
            str(self.logs_host_dir): {"bind": CONTAINER_LOG_DIR, "mode": "rw"},
        }
        for v in self.extra_volumes:
            volumes[v.host] = {"bind": v.container, "mode": v.mode}

        ports: dict[str, int | tuple[str, int]] = {}
        for p in self.extra_ports:
            key = f"{p.container}/{p.proto}"
            ports[key] = (p.host_ip, p.host) if p.host_ip else p.host

        env = {
            "TERM": "xterm-256color",
            "LANG": "C.UTF-8",
            **self.extra_env,
        }

        kwargs: dict[str, Any] = {
            "image": self.image,
            "name": self.container_name,
            "hostname": self.hostname or self.name,
            "labels": self.labels,
            "volumes": volumes,
            "environment": env,
            "network_mode": self.network_mode,
            "working_dir": CONTAINER_WORKSPACE,
            "tty": True,
            "stdin_open": True,
            "detach": True,
            "security_opt": ["no-new-privileges:true"],
        }
        if ports:
            kwargs["ports"] = ports
        if self.extra_caps:
            kwargs["cap_add"] = self.extra_caps
        if self.disposable:
            kwargs["auto_remove"] = True
        return kwargs
