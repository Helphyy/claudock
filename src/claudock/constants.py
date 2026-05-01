"""Constants and default paths."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "claudock"
CONTAINER_PREFIX = "claudock-"

DEFAULT_IMAGE = "full"

# Official image catalog (used by `claudock image` for install/update/list).
DEFAULT_IMAGE_REGISTRY = "ghcr.io/helphyy"
DEFAULT_IMAGE_TAG = "latest"
KNOWN_VARIANTS = ("minimal", "dev", "cloud", "security", "data", "doc", "full")

HOME = Path.home()
CONFIG_ROOT = HOME / ".claudock"
CONFIG_FILE = CONFIG_ROOT / "config.yml"
WORKSPACES_DIR = CONFIG_ROOT / "workspaces"
PROFILES_DIR = CONFIG_ROOT / "profiles"
CACHE_DIR = CONFIG_ROOT / ".cache"
IMAGES_CACHE_FILE = CACHE_DIR / "images.json"
LOGS_DIR = CONFIG_ROOT / "logs"

DEFAULT_PROFILE_NAME = "default"

CONTAINER_WORKSPACE = "/workspace"
CONTAINER_CLAUDE_DIR = "/root/.claude"
CONTAINER_CLAUDE_JSON = "/root/.claude.json"
CONTAINER_LOG_DIR = "/var/log/claudock-sessions"

LABEL_MANAGED_BY = "claudock.managed-by"
LABEL_NAME = "claudock.name"
LABEL_VERSION = "claudock.version"
LABEL_PROFILE = "claudock.profile"
