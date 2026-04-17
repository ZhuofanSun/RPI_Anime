from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

SHARED_FILE_MODE = 0o666


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def event_log_path() -> Path:
    explicit = os.environ.get("OPS_EVENT_LOG_PATH")
    if explicit:
        return Path(explicit)
    anime_data_root = Path(_env("ANIME_DATA_ROOT", "/srv/anime-data"))
    return anime_data_root / "appdata" / "ops-ui" / "events.json"


def event_log_cap() -> int:
    return max(100, _env_int("OPS_UI_LOG_CAP", 1500))


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _ensure_shared_writable_file(path: Path) -> None:
    if not path.exists():
        path.touch(mode=SHARED_FILE_MODE, exist_ok=True)
    path.chmod(SHARED_FILE_MODE)


def _read_events_unlocked(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _write_events_unlocked(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")


def _locked_edit(callback, *, ensure_parent: bool = True) -> Any:
    path = event_log_path()
    lock_path = _lock_path(path)
    if ensure_parent:
        _ensure_parent(path)
        _ensure_parent(lock_path)
        _ensure_shared_writable_file(path)
        _ensure_shared_writable_file(lock_path)
    else:
        if not path.parent.exists() or not lock_path.parent.exists():
            return callback(path)
        if lock_path.exists():
            try:
                lock_path.chmod(SHARED_FILE_MODE)
            except OSError:
                pass
        else:
            return callback(path)
    with lock_path.open("r+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        return callback(path)


def append_event(
    *,
    source: str,
    level: str,
    action: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _edit(path: Path) -> dict[str, Any]:
        events = _read_events_unlocked(path)
        event = {
            "id": uuid.uuid4().hex,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "ts_unix": int(time.time()),
            "source": source,
            "level": level,
            "action": action,
            "message": message,
            "details": details or {},
        }
        events.append(event)
        cap = event_log_cap()
        if len(events) > cap:
            events = events[-cap:]
        _write_events_unlocked(path, events)
        return event

    return _locked_edit(_edit)


def read_events(*, limit: int | None = None) -> list[dict[str, Any]]:
    def _read(path: Path) -> list[dict[str, Any]]:
        events = _read_events_unlocked(path)
        events.sort(key=lambda item: int(item.get("ts_unix", 0)), reverse=True)
        if limit is not None:
            return events[:limit]
        return events

    return _locked_edit(_read, ensure_parent=False)


def clear_events() -> dict[str, Any]:
    def _clear(path: Path) -> dict[str, Any]:
        existing = _read_events_unlocked(path)
        _write_events_unlocked(path, [])
        return {
            "cleared": len(existing),
        }

    return _locked_edit(_clear)
