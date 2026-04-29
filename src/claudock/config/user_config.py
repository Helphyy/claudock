"""User configuration (~/.claudock/config.yml).

Resolution order: CLI flag > user config > built-in defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from claudock.constants import (
    CONFIG_FILE,
    CONFIG_ROOT,
    DEFAULT_IMAGE,
    DEFAULT_IMAGE_REGISTRY,
    DEFAULT_IMAGE_TAG,
    DEFAULT_PROFILE_NAME,
    KNOWN_VARIANTS,
    WORKSPACES_DIR,
)

DEFAULT_CONFIG_YAML = f"""\
# Claudock configuration file, generated automatically.
# Edit by hand; claudock will reload it on the next run.
# Resolution order: CLI flag > this file > built-in defaults.

volumes:
  # Host directory mounted at /workspace inside the container when no cwd is
  # passed to `claudock start` and `--cwd` is not used.
  workspaces_path: {WORKSPACES_DIR}

config:
  # Default Docker image (override: --image).
  default_image: {DEFAULT_IMAGE}

  # Default Claude auth profile (override: --profile).
  default_profile: {DEFAULT_PROFILE_NAME}

  # Default shell on attach when --shell is set explicitly (bash, zsh).
  default_shell: zsh

  # Linux capabilities always added at creation (override: --cap, additive).
  # E.g.: [SYS_PTRACE] for gdb/strace.
  default_caps: []

  # Environment variables always injected (override: -e, additive).
  # E.g.: {{ HTTP_PROXY: http://proxy.local:3128 }}
  default_env: {{}}

  # Auto-check for image updates at startup (not implemented in v0).
  auto_check_update: false

  # Default reasoning effort passed to Claude Code (low/medium/high/max).
  # Override per-run with --effort.
  default_effort: max

network:
  # Docker network mode (bridge, host, none) (override: --network).
  mode: bridge

ui:
  # Show the ASCII banner on `claudock` with no args.
  banner: true

images:
  # Where the official Claudock images live. The image manager (`claudock
  # image install`) expands a variant name (e.g. `dev`) into
  # `<registry>/claudock-<variant>:<default_tag>`. Set `registry: ""` if you
  # only want to manage local images (no remote pull).
  registry: {DEFAULT_IMAGE_REGISTRY}
  default_tag: {DEFAULT_IMAGE_TAG}

  # Official variants shipped under the registry above. Used by
  # `claudock image list` and `claudock image install-all`.
  variants:
{chr(10).join(f"    - {v}" for v in KNOWN_VARIANTS)}
"""


@dataclass
class VolumesConfig:
    workspaces_path: Path = field(default_factory=lambda: WORKSPACES_DIR)


@dataclass
class GeneralConfig:
    default_image: str = DEFAULT_IMAGE
    default_profile: str = DEFAULT_PROFILE_NAME
    default_shell: str = "zsh"
    default_caps: list[str] = field(default_factory=list)
    default_env: dict[str, str] = field(default_factory=dict)
    auto_check_update: bool = False
    default_effort: str = "max"


@dataclass
class NetworkConfig:
    mode: str = "bridge"


@dataclass
class UiConfig:
    banner: bool = True


@dataclass
class ImagesConfig:
    """Where official Claudock images live + which variants are known."""

    registry: str = DEFAULT_IMAGE_REGISTRY
    default_tag: str = DEFAULT_IMAGE_TAG
    variants: list[str] = field(default_factory=lambda: list(KNOWN_VARIANTS))

    def expand(self, name: str, *, tag: str | None = None) -> str:
        """Resolve a variant name or partial spec to a full image reference.

        Rules:
        - If `name` already contains a registry (`/` before any `:`) or is a
          local-only ref (no `/` at all but with explicit tag, e.g.
          `myimage:dev`), return as-is.
        - If `name` is a known variant (`minimal`, `dev`, ...), expand to
          `<registry>/claudock-<name>:<tag>` (registry omitted if empty).
        - If `name` is `claudock-<variant>` (with or without tag), prepend
          the registry (if any) and apply default tag if missing.
        """
        target_tag = tag or self.default_tag

        # Already a full ref with registry
        if "/" in name:
            return name if ":" in name.split("/")[-1] else f"{name}:{target_tag}"

        # `claudock-<variant>[:<tag>]` form
        if name.startswith("claudock-"):
            stem, sep, t = name.partition(":")
            t = t or target_tag
            if self.registry:
                return f"{self.registry}/{stem}:{t}"
            return f"{stem}:{t}"

        # Bare variant name
        if name in self.variants:
            if self.registry:
                return f"{self.registry}/claudock-{name}:{target_tag}"
            return f"claudock-{name}:{target_tag}"

        # Otherwise: assume the user knows what they typed (custom image)
        return name if ":" in name else f"{name}:{target_tag}"


@dataclass
class UserConfig:
    volumes: VolumesConfig = field(default_factory=VolumesConfig)
    config: GeneralConfig = field(default_factory=GeneralConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    images: ImagesConfig = field(default_factory=ImagesConfig)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> UserConfig:
        v = raw.get("volumes") or {}
        c = raw.get("config") or {}
        n = raw.get("network") or {}
        u = raw.get("ui") or {}
        i = raw.get("images") or {}
        return cls(
            volumes=VolumesConfig(
                workspaces_path=Path(v.get("workspaces_path", WORKSPACES_DIR)).expanduser(),
            ),
            config=GeneralConfig(
                default_image=c.get("default_image", DEFAULT_IMAGE),
                default_profile=c.get("default_profile", DEFAULT_PROFILE_NAME),
                default_shell=c.get("default_shell", "zsh"),
                default_caps=list(c.get("default_caps") or []),
                default_env=dict(c.get("default_env") or {}),
                auto_check_update=bool(c.get("auto_check_update", False)),
                default_effort=str(c.get("default_effort", "max")),
            ),
            network=NetworkConfig(mode=n.get("mode", "bridge")),
            ui=UiConfig(banner=bool(u.get("banner", True))),
            images=ImagesConfig(
                registry=str(i.get("registry", DEFAULT_IMAGE_REGISTRY)),
                default_tag=str(i.get("default_tag", DEFAULT_IMAGE_TAG)),
                variants=list(i.get("variants") or KNOWN_VARIANTS),
            ),
        )


def _ensure_default_layout(cfg: UserConfig) -> None:
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    cfg.volumes.workspaces_path.mkdir(parents=True, exist_ok=True)


def load_config() -> UserConfig:
    """Load the user config; create the default file if missing."""
    if not CONFIG_FILE.exists():
        CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
        cfg = UserConfig()
        _ensure_default_layout(cfg)
        return cfg

    raw = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    cfg = UserConfig.from_dict(raw)
    _ensure_default_layout(cfg)
    return cfg
