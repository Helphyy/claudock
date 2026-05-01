"""Discovery of Claude Code sessions stored per profile.

Claude Code stores sessions under `~/.claude/projects/<encoded-cwd>/<id>.jsonl`,
where `<encoded-cwd>` is the working directory with `/` replaced by `-`
(e.g. `/workspace` → `-workspace`). Since we bind-mount the profile into the
container, those files are reachable host-side at
`~/.claudock/profiles/<profile>/.claude/projects/-workspace/<id>.jsonl`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ClaudeSession:
    id: str
    title: str
    mtime: float

    @property
    def mtime_dt(self) -> datetime:
        return datetime.fromtimestamp(self.mtime)


def encode_workspace_path(path: str) -> str:
    s = str(path)
    if not s.startswith("/"):
        s = "/" + s
    return s.replace("/", "-")


def _clip(text: str, max_len: int = 70) -> str:
    text = text.strip().replace("\n", " ").replace("\r", " ")
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


def _extract_title(file_path: Path) -> str:
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    d = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if d.get("type") == "summary" and d.get("summary"):
                    return _clip(d["summary"])
                if d.get("type") == "user":
                    msg = d.get("message", {}) or {}
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "text":
                                content = c.get("text", "")
                                break
                        else:
                            content = ""
                    if content:
                        return _clip(str(content))
    except OSError:
        pass
    return file_path.stem


def list_sessions(
    profile_claude_dir: Path,
    container_workspace: str,
    *,
    sessions_root: Path | None = None,
    min_mtime: float | None = None,
) -> list[ClaudeSession]:
    """List Claude Code sessions for a container.

    `sessions_root`: if set (per-container projects/ dir bind-mounted at
    /root/.claude/projects), look there. Otherwise fall back to the profile's
    projects/ dir (legacy: shared across all containers of the profile).

    `min_mtime`: drop sessions older than this epoch (used as a heuristic to
    hide pre-existing profile sessions when there is no per-container mount).
    """
    encoded = encode_workspace_path(container_workspace)
    if sessions_root is not None:
        project_dir = sessions_root / encoded
    else:
        project_dir = profile_claude_dir / "projects" / encoded
    if not project_dir.exists():
        return []
    sessions: list[ClaudeSession] = []
    for f in project_dir.glob("*.jsonl"):
        if not f.is_file():
            continue
        st = f.stat()
        if min_mtime is not None and st.st_mtime < min_mtime:
            continue
        sessions.append(
            ClaudeSession(
                id=f.stem,
                title=_extract_title(f),
                mtime=st.st_mtime,
            )
        )
    sessions.sort(key=lambda s: s.mtime, reverse=True)
    return sessions


def fmt_relative(dt: datetime) -> str:
    """Format a datetime as 'X ago' (s/min/h/d/absolute)."""
    delta = datetime.now() - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}min ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 86400 * 30:
        return f"{seconds // 86400}d ago"
    return dt.strftime("%Y-%m-%d")
