"""Compare local image digests with what's currently published on the
registry, so `claudock image list` and the install picker can flag
"update available" without forcing a `docker pull`.

A short-lived JSON cache (`~/.claudock/.cache/image_updates.json`)
keeps the result for 1h to avoid re-querying the registry on every
table render."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

from claudock.constants import CACHE_DIR

_UPDATES_CACHE_FILE = CACHE_DIR / "image_updates.json"
_TTL_SECONDS = 3600  # 1 hour

# Status values
LOCAL_ABSENT = "absent"          # not pulled locally
UP_TO_DATE = "up-to-date"        # local digest == remote digest
UPDATE_AVAILABLE = "available"   # local digest != remote digest
UNKNOWN = "unknown"              # registry unreachable / no creds


def _read_cache() -> dict[str, Any]:
    if not _UPDATES_CACHE_FILE.exists():
        return {}
    try:
        data: dict[str, Any] = json.loads(_UPDATES_CACHE_FILE.read_text(encoding="utf-8"))
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def _write_cache(data: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _UPDATES_CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def _local_digest(client: Any, ref: str) -> str | None:
    try:
        img = client.images.get(ref)
    except Exception:
        return None
    repo = ref.rsplit(":", 1)[0]
    for d in img.attrs.get("RepoDigests") or []:
        d_str = str(d)
        if d_str.startswith(repo + "@"):
            return d_str.split("@", 1)[1]
    # No RepoDigest matches the ref (image was loaded locally without a pull)
    return None


def _remote_digest(client: Any, ref: str) -> str | None:
    try:
        digest = client.images.get_registry_data(ref).id
    except Exception:
        return None
    if not digest:
        return None
    return cast(str, digest)


def _resolve_one(client: Any, ref: str) -> str:
    local = _local_digest(client, ref)
    if local is None:
        # No local image with a registry-anchored digest: maybe present
        # via local build, maybe just absent. We treat absence as "absent"
        # so the picker keeps showing "not local" without an update flag.
        try:
            client.images.get(ref)
            return UNKNOWN  # local-only build, can't tell
        except Exception:
            return LOCAL_ABSENT
    remote = _remote_digest(client, ref)
    if remote is None:
        return UNKNOWN
    return UP_TO_DATE if local == remote else UPDATE_AVAILABLE


def check_updates(client: Any, refs: list[str], *, force: bool = False) -> dict[str, str]:
    """Return {ref: status} for each ref. Uses a 1h disk cache so successive
    calls inside the same hour skip the registry roundtrip. Set `force=True`
    to bypass the cache."""
    cache = _read_cache() if not force else {}
    now = time.time()
    fresh: dict[str, str] = {}
    stale: list[str] = []

    for ref in refs:
        entry = cache.get(ref)
        if entry and now - entry.get("ts", 0) < _TTL_SECONDS:
            fresh[ref] = entry["status"]
        else:
            stale.append(ref)

    if stale:
        with ThreadPoolExecutor(max_workers=4) as ex:
            for ref, status in zip(stale, ex.map(lambda r: _resolve_one(client, r), stale)):
                fresh[ref] = status
                cache[ref] = {"ts": now, "status": status}
        _write_cache(cache)

    return fresh


def status_markup(status: str) -> str:
    """Rich markup for a status string (used by tables)."""
    return {
        UP_TO_DATE: "[ok]✓ up-to-date[/]",
        UPDATE_AVAILABLE: "[warn]↑ update[/]",
        LOCAL_ABSENT: "[muted]-[/]",
        UNKNOWN: "[muted]?[/]",
    }.get(status, "[muted]?[/]")
