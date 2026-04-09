from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from anime_ops_ui.copy import payload_copy
from anime_postprocessor.parser import normalize_title
from anime_postprocessor.title_map import load_title_map

from .autobangumi_client import AutoBangumiClient

_SEASON_FOLDER_PATTERN = re.compile(r"^season\s*\d+$", re.IGNORECASE)
_EPISODE_CODE_PATTERN = re.compile(r"\bs\d{1,2}e\d{1,3}\b", re.IGNORECASE)
_IGNORED_PATH_TOKENS = {"library", "seasonal"}


def _week_key(now: datetime) -> str:
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def _state_path(state_root: Path) -> Path:
    return state_root / "weekly_schedule_state.json"


def _poster_url(base_host: str, autobangumi_port: int, poster_link: str | None) -> str | None:
    if not poster_link:
        return None
    poster_path = str(poster_link).strip()
    if not poster_path:
        return None
    if poster_path.startswith("http://") or poster_path.startswith("https://"):
        return poster_path
    return f"http://{base_host}:{autobangumi_port}/{poster_path.lstrip('/')}"


def _autobangumi_db_path(anime_data_root: Path) -> Path:
    return anime_data_root / "appdata" / "autobangumi" / "data" / "data.db"


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_datetime(event: dict[str, Any], *, tzinfo) -> datetime | None:
    ts_unix = event.get("ts_unix")
    unix_value = _safe_int(ts_unix)
    if unix_value is not None:
        return datetime.fromtimestamp(unix_value, tz=tzinfo)

    raw_ts = str(event.get("ts") or "").strip()
    if not raw_ts:
        return None
    try:
        parsed = datetime.fromisoformat(raw_ts)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tzinfo)
    return parsed.astimezone(tzinfo)


def _normalize_title_candidates(value: str | None) -> set[str]:
    if not value:
        return set()
    normalized = normalize_title(value)
    if not normalized:
        return set()
    candidates = {normalized}
    cleaned_episode = normalize_title(_EPISODE_CODE_PATTERN.sub(" ", value))
    if cleaned_episode:
        candidates.add(cleaned_episode)
    return {item for item in candidates if item}


def _build_bangumi_title_index(bangumi_items: list[dict[str, Any]]) -> dict[str, set[int]]:
    try:
        resolver = load_title_map()
    except Exception:
        resolver = None

    index: dict[str, set[int]] = {}

    def add_candidate(candidate: str | None, bangumi_id: int) -> None:
        for normalized in _normalize_title_candidates(candidate):
            index.setdefault(normalized, set()).add(bangumi_id)

    for item in bangumi_items:
        bangumi_id = _safe_int(item.get("id"))
        if bangumi_id is None:
            continue

        primary_titles = [
            item.get("official_title"),
            item.get("title_raw"),
            item.get("title"),
        ]
        for title in primary_titles:
            add_candidate(str(title) if title is not None else None, bangumi_id)

        if resolver is None:
            continue

        for title in primary_titles:
            if not title:
                continue
            normalized = normalize_title(str(title))
            if not normalized:
                continue
            mapping = resolver.alias_index.get(normalized)
            if mapping is None:
                continue
            add_candidate(mapping.folder_name, bangumi_id)
            add_candidate(mapping.series_title, bangumi_id)
            add_candidate(mapping.original_title, bangumi_id)
            for alias in mapping.aliases:
                add_candidate(alias, bangumi_id)

    return index


def _target_title_candidates(target: str) -> set[str]:
    normalized_path = str(target).replace("\\", "/")
    candidates: set[str] = set()
    for part in normalized_path.split("/"):
        cleaned = part.strip()
        if not cleaned:
            continue
        stem = Path(cleaned).stem
        for candidate in _normalize_title_candidates(cleaned) | _normalize_title_candidates(stem):
            if candidate in _IGNORED_PATH_TOKENS:
                continue
            if _SEASON_FOLDER_PATTERN.fullmatch(candidate):
                continue
            candidates.add(candidate)
    return candidates


def _resolve_target_ids(target: str, title_index: dict[str, set[int]]) -> set[int]:
    matched: set[int] = set()
    for candidate in _target_title_candidates(target):
        candidate_ids = title_index.get(candidate, set())
        matched.update(candidate_ids)
        if len(matched) > 1:
            return set()
    return matched


def _season_label(item: dict[str, Any]) -> str | None:
    raw = str(item.get("season_raw") or "").strip()
    if raw:
        return raw
    season = _safe_int(item.get("season"))
    if season is None:
        return None
    return f"S{season:02d}"


def _card_detail(item: dict[str, Any], *, title: str) -> dict[str, str | None]:
    title_raw = str(item.get("title_raw") or "").strip() or None
    if title_raw == title:
        title_raw = None

    return {
        "title_raw": title_raw,
        "group_name": str(item.get("group_name") or "").strip() or None,
        "source": str(item.get("source") or "").strip() or None,
        "subtitle": str(item.get("subtitle") or "").strip() or None,
        "dpi": str(item.get("dpi") or "").strip() or None,
        "season_label": _season_label(item),
        "review_reason": str(item.get("needs_review_reason") or "").strip() or None,
    }


def _read_postprocessor_publish_events(
    events: list[dict[str, Any]],
    bangumi_items: list[dict[str, Any]],
    week_key: str,
    *,
    now: datetime,
) -> set[int]:
    title_index = _build_bangumi_title_index(bangumi_items)
    timezone = now.tzinfo or datetime.now().astimezone().tzinfo
    if timezone is None:
        return set()

    published_ids: set[int] = set()
    for item in events:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "")
        action = str(item.get("action") or "")
        if source == "postprocessor" and action == "watch-process-group":
            pass
        elif source == "ops-review" and action in {"retry-parse", "manual-publish"}:
            pass
        else:
            continue

        event_ts = _event_datetime(item, tzinfo=timezone)
        if event_ts is None or _week_key(event_ts) != week_key:
            continue

        details = item.get("details")
        if not isinstance(details, dict):
            continue

        targets: list[str] = []
        if source == "postprocessor":
            published = _safe_int(details.get("published"))
            if published is None:
                published = 1 if details.get("published") else 0
            if published <= 0:
                continue
            winner_targets = details.get("winner_targets")
            if not isinstance(winner_targets, list):
                continue
            targets = [str(target) for target in winner_targets if target]
        else:
            target = details.get("target")
            if not target:
                continue
            targets = [str(target)]

        for target in targets:
            published_ids.update(_resolve_target_ids(target, title_index))

    return published_ids


def build_weekly_schedule_payload(
    *,
    bangumi_items: list[dict[str, Any]],
    base_host: str,
    autobangumi_port: int,
    library_ids: set[int],
    now: datetime,
    state_root: Path,
    visible_limit: int = 4,
    locale: str | None = None,
) -> dict[str, Any]:
    copy = payload_copy("weekly_schedule", locale)
    state_root.mkdir(parents=True, exist_ok=True)
    week_key = _week_key(now)
    try:
        _state_path(state_root).write_text(
            json.dumps({"week_key": week_key}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass

    today_weekday = now.weekday()
    safe_limit = max(int(visible_limit), 0)

    grouped: dict[int, list[dict[str, Any]]] = {index: [] for index in range(7)}
    unknown_items: list[dict[str, Any]] = []

    for item in bangumi_items:
        bangumi_id = _safe_int(item.get("id"))
        if bangumi_id is None:
            continue

        title = item.get("official_title") or item.get("title_raw") or item.get("title") or copy["title_fallback"]

        card = {
            "id": bangumi_id,
            "title": title,
            "poster_url": _poster_url(base_host, autobangumi_port, item.get("poster_link")),
            "is_library_ready": bangumi_id in library_ids,
            "detail": _card_detail(item, title=title),
        }

        weekday = _safe_int(item.get("air_weekday"))
        if weekday is None or not 0 <= weekday <= 6:
            unknown_items.append(card)
        else:
            grouped[weekday].append(card)

    days: list[dict[str, Any]] = []
    for weekday in range(7):
        items = grouped[weekday]
        days.append(
            {
                "weekday": weekday,
                "label": copy["day_labels"][weekday],
                "is_today": weekday == today_weekday,
                "items": items[:safe_limit] if safe_limit else [],
                "hidden_items": items[safe_limit:] if safe_limit else items[:],
                "has_hidden_items": len(items) > safe_limit if safe_limit else bool(items),
            }
        )

    return {
        "week_key": week_key,
        "today_weekday": today_weekday,
        "days": days,
        "unknown": {
            "label": copy["unknown_label"],
            "hint": copy["unknown_hint"],
            "items": unknown_items,
            "hidden_items": [],
            "has_hidden_items": False,
        },
    }


def build_phase4_schedule_snapshot(
    *,
    anime_data_root: Path,
    base_host: str,
    autobangumi_port: int,
    autobangumi_base_url: str,
    autobangumi_username: str,
    autobangumi_password: str,
    state_root: Path,
    now: datetime,
    events: list[dict[str, Any]],
    visible_limit: int = 4,
    locale: str | None = None,
) -> dict[str, Any]:
    client = AutoBangumiClient(
        base_url=autobangumi_base_url,
        username=autobangumi_username,
        password=autobangumi_password,
    )
    bangumi_items = [
        item
        for item in client.fetch_bangumi()
        if not bool(item.get("deleted")) and not bool(item.get("archived"))
    ]

    library_ids = _read_postprocessor_publish_events(
        events,
        bangumi_items,
        _week_key(now),
        now=now,
    )

    schedule = build_weekly_schedule_payload(
        bangumi_items=bangumi_items,
        base_host=base_host,
        autobangumi_port=autobangumi_port,
        library_ids=library_ids,
        now=now,
        state_root=state_root,
        visible_limit=visible_limit,
        locale=locale,
    )
    return {
        "weekly_schedule": schedule,
    }
