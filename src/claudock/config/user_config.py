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
    DEFAULT_IMAGE_NAME,
    DEFAULT_IMAGE_REGISTRY,
    DEFAULT_IMAGE_TAG,
    DEFAULT_PROFILE_NAME,
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
  # Default Docker image (override: --image). Bare name resolves via the
  # `images:` section below to `<registry>/<name>:<default_tag>`.
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

  # Share the host clipboard (Wayland socket, X11 fallback) on every
  # `claudock start`. Same effect as passing --clipboard each time.
  # Image needs wl-clipboard (Wayland) or xclip/xsel (X11).
  default_clipboard: false

network:
  # Docker network mode (bridge, host, none) (override: --network).
  mode: bridge

ui:
  # Show the ASCII banner on `claudock` with no args.
  banner: true

images:
  # Where the official Claudock image lives. A bare image name (e.g.
  # `claudock`) resolves to `<registry>/<name>:<default_tag>`. Set
  # `registry: ""` to manage local images only (no remote pull).
  registry: {DEFAULT_IMAGE_REGISTRY}
  default_tag: {DEFAULT_IMAGE_TAG}

  # Official image name (single image since v1.7.0).
  name: {DEFAULT_IMAGE_NAME}
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
    default_clipboard: bool = False


@dataclass
class NetworkConfig:
    mode: str = "bridge"


@dataclass
class UiConfig:
    banner: bool = True


@dataclass
class ImagesConfig:
    """Where the official Claudock image lives."""

    registry: str = DEFAULT_IMAGE_REGISTRY
    default_tag: str = DEFAULT_IMAGE_TAG
    name: str = DEFAULT_IMAGE_NAME

    @property
    def official_ref(self) -> str:
        """Full reference of the official image."""
        if self.registry:
            return f"{self.registry}/{self.name}:{self.default_tag}"
        return f"{self.name}:{self.default_tag}"

    def expand(self, name: str, *, tag: str | None = None) -> str:
        """Resolve a name to a full image reference.

        Rules:
        - If `name` contains a registry (a `/` before any `:`), return as-is
          (apply `default_tag` only if no tag at all).
        - If `name` is the official name (`claudock`, with or without tag),
          prepend the registry (if any).
        - Otherwise, assume the user typed a custom local image and only add
          the default tag if missing.
        """
        target_tag = tag or self.default_tag

        # Already a full ref with registry
        if "/" in name:
            return name if ":" in name.split("/")[-1] else f"{name}:{target_tag}"

        # Official name (with or without tag)
        stem, sep, t = name.partition(":")
        if stem == self.name:
            t = t or target_tag
            if self.registry:
                return f"{self.registry}/{stem}:{t}"
            return f"{stem}:{t}"

        # Custom local image
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
        # Legacy v1.6.x keys silently ignored: images.variants, default_variant.
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
                default_clipboard=bool(c.get("default_clipboard", False)),
            ),
            network=NetworkConfig(mode=n.get("mode", "bridge")),
            ui=UiConfig(banner=bool(u.get("banner", True))),
            images=ImagesConfig(
                registry=str(i.get("registry", DEFAULT_IMAGE_REGISTRY)),
                default_tag=str(i.get("default_tag", DEFAULT_IMAGE_TAG)),
                name=str(i.get("name", DEFAULT_IMAGE_NAME)),
            ),
        )


def _ensure_default_layout(cfg: UserConfig) -> None:
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    cfg.volumes.workspaces_path.mkdir(parents=True, exist_ok=True)


def _tighten_perms() -> None:
    """Tighten permissions on the local Claudock data layout, best-effort:
    - 0700 on ~/.claudock, 0600 on config.yml
    - 0700 on every ~/.claudock/profiles/<name> and its .claude/ subdir
    Holds OAuth tokens and API keys, must not be world/group-readable."""
    import os
    try:
        if CONFIG_ROOT.exists():
            os.chmod(CONFIG_ROOT, 0o700)
        if CONFIG_FILE.exists():
            os.chmod(CONFIG_FILE, 0o600)
        profiles_dir = CONFIG_ROOT / "profiles"
        if profiles_dir.exists():
            os.chmod(profiles_dir, 0o700)
            for d in profiles_dir.iterdir():
                if not d.is_dir():
                    continue
                try:
                    os.chmod(d, 0o700)
                    claude = d / ".claude"
                    if claude.exists():
                        os.chmod(claude, 0o700)
                except OSError:
                    pass
    except OSError:
        pass


def load_config() -> UserConfig:
    """Load the user config; create the default file if missing."""
    if not CONFIG_FILE.exists():
        CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
        _tighten_perms()
        cfg = UserConfig()
        _ensure_default_layout(cfg)
        return cfg

    raw = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    cfg = UserConfig.from_dict(raw)
    _ensure_default_layout(cfg)
    _tighten_perms()
    return cfg
