"""Project configuration (.claudock.yml inside a workdir).

When the user runs `claudock start --cwd` (or with an explicit path), if a
`.claudock.yml` file exists at the root of that workdir, its values fill in
gaps left by the global config. CLI flags still win.

Accepted schema (all keys optional):

    defaults:
      image: ghcr.io/helphyy/claudock-dev:latest
      profile: pro
      network: bridge        # bridge | host | none | <docker-net>
      shell: zsh             # empty = launch claude directly
      hostname: my-box
      log: false
      x11: false
      vscode: false
      git: git@github.com:user/repo.git
      ssh: true              # or "/path/to/.ssh-acme"
      caps: [SYS_PTRACE]
      effort: max            # low | medium | high | max
      env:
        HTTP_PROXY: http://proxy:3128
      volumes:
        - /shared:/cache:ro
      ports:
        - "3000:3000"

Final resolution: CLI flag > .claudock.yml > ~/.claudock/config.yml > built-in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_CONFIG_FILENAME = ".claudock.yml"


@dataclass
class ProjectConfig:
    image: str | None = None
    profile: str | None = None
    network: str | None = None
    shell: str | None = None
    hostname: str | None = None
    log: bool | None = None
    x11: bool | None = None
    vscode: bool | None = None
    git: str | None = None
    ssh: bool | str | None = None
    caps: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    volumes: list[str] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)
    effort: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ProjectConfig:
        defaults = raw.get("defaults") or raw or {}
        return cls(
            image=defaults.get("image"),
            profile=defaults.get("profile"),
            network=defaults.get("network"),
            shell=defaults.get("shell"),
            hostname=defaults.get("hostname"),
            log=defaults.get("log"),
            x11=defaults.get("x11"),
            vscode=defaults.get("vscode"),
            git=defaults.get("git"),
            ssh=defaults.get("ssh"),
            caps=list(defaults.get("caps") or []),
            env=dict(defaults.get("env") or {}),
            volumes=[str(v) for v in (defaults.get("volumes") or [])],
            ports=[str(p) for p in (defaults.get("ports") or [])],
            effort=defaults.get("effort"),
        )


def find_project_config(workspace_path: Path) -> Path | None:
    """Look for .claudock.yml in the given workspace (no parent walk)."""
    candidate = workspace_path / PROJECT_CONFIG_FILENAME
    return candidate if candidate.is_file() else None


def load_project_config(path: Path) -> ProjectConfig | None:
    """Load a .claudock.yml or return None if missing/unreadable."""
    if not path.is_file():
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(raw, dict):
        return None
    return ProjectConfig.from_dict(raw)
