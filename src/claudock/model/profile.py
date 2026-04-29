"""Claude authentication profile model.

A profile is a host-side store of Claude Code credentials, independent from
any container. The profile's `.claude/` directory is bind-mounted into
`/root/.claude` of every container that uses it. Several containers sharing
the same profile share their auth state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from claudock.constants import DEFAULT_PROFILE_NAME, PROFILES_DIR
from claudock.exceptions import ClaudockError

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


class InvalidProfileNameError(ClaudockError):
    pass


class ProfileNotFoundError(ClaudockError):
    pass


class ProfileAlreadyExistsError(ClaudockError):
    pass


def validate_name(name: str) -> str:
    if not _NAME_RE.match(name):
        raise InvalidProfileNameError(
            f"Invalid profile name '{name}'. "
            "Expected: lowercase, digits, '-' or '_', max 32 chars, "
            "alphanumeric first character."
        )
    return name


@dataclass
class Profile:
    name: str
    path: Path

    @property
    def claude_dir(self) -> Path:
        """Host path that gets bind-mounted at /root/.claude inside containers."""
        return self.path / ".claude"

    @property
    def exists(self) -> bool:
        return self.claude_dir.exists()

    @property
    def size_bytes(self) -> int:
        if not self.claude_dir.exists():
            return 0
        return sum(f.stat().st_size for f in self.claude_dir.rglob("*") if f.is_file())

    @property
    def last_modified(self) -> datetime | None:
        if not self.claude_dir.exists():
            return None
        try:
            mtime = max(
                (f.stat().st_mtime for f in self.claude_dir.rglob("*") if f.is_file()),
                default=self.claude_dir.stat().st_mtime,
            )
        except ValueError:
            mtime = self.claude_dir.stat().st_mtime
        return datetime.fromtimestamp(mtime)

    def ensure(self) -> None:
        """Create the profile directory if missing (Claude will prompt login on first use)."""
        self.claude_dir.mkdir(parents=True, exist_ok=True)

    def remove(self) -> None:
        if not self.path.exists():
            return
        from claudock.utils.fs import force_rmtree
        force_rmtree(self.path)


def get_profile(name: str) -> Profile:
    validate_name(name)
    return Profile(name=name, path=PROFILES_DIR / name)


def get_or_create_profile(name: str) -> Profile:
    p = get_profile(name)
    p.ensure()
    return p


def list_profiles() -> list[Profile]:
    if not PROFILES_DIR.exists():
        return []
    return sorted(
        (Profile(name=child.name, path=child) for child in PROFILES_DIR.iterdir() if child.is_dir()),
        key=lambda p: p.name,
    )


def create_profile(name: str) -> Profile:
    p = get_profile(name)
    if p.exists:
        raise ProfileAlreadyExistsError(f"Profile '{name}' already exists.")
    p.ensure()
    return p


def remove_profile(name: str) -> Profile:
    p = get_profile(name)
    if not p.path.exists():
        raise ProfileNotFoundError(f"No profile named '{name}'.")
    p.remove()
    return p


__all__ = [
    "DEFAULT_PROFILE_NAME",
    "InvalidProfileNameError",
    "Profile",
    "ProfileAlreadyExistsError",
    "ProfileNotFoundError",
    "create_profile",
    "get_or_create_profile",
    "get_profile",
    "list_profiles",
    "remove_profile",
    "validate_name",
]
