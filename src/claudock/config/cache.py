"""Light cache at ~/.claudock/.cache/ (recently seen images, useful for shell autocomplete).

Reads do NOT call Docker, which makes the cache the right source for
shell autocomplete. Writes happen passively from `claudock info` and
`claudock install`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from claudock.constants import CACHE_DIR, IMAGES_CACHE_FILE


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _read() -> dict[str, Any]:
    if not IMAGES_CACHE_FILE.exists():
        return {"images": {}, "updated_at": None}
    try:
        return json.loads(IMAGES_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"images": {}, "updated_at": None}


def _write(data: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_image(repo_tag: str, size: int = 0) -> None:
    """Record/refresh one image in the cache."""
    data = _read()
    data["images"][repo_tag] = {"size": int(size), "last_seen": _now_iso()}
    data["updated_at"] = _now_iso()
    _write(data)


def known_images() -> list[str]:
    """Sorted list of known tags (for autocomplete)."""
    data = _read()
    return sorted(data.get("images", {}).keys())


def reset() -> None:
    if IMAGES_CACHE_FILE.exists():
        IMAGES_CACHE_FILE.unlink()
