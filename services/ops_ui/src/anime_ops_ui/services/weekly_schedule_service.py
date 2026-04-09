from __future__ import annotations

import json
import re
import sqlite3
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
_JELLYFIN_SERIES_TYPE = "MediaBrowser.Controller.Entities.TV.Series"


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


def _jellyfin_db_path(anime_data_root: Path) -> Path:
    return anime_data_root / "appdata" / "jellyfin" / "config" / "data" / "jellyfin.db"


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


def _load_title_resolver():
    try:
        return load_title_map()
    except Exception:
        return None


def _expanded_title_candidates(values: list[Any], *, resolver=None) -> set[str]:
    candidates: set[str] = set()
    normalized_titles: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        normalized_titles.append(text)
        candidates.update(_normalize_title_candidates(text))

    if resolver is None:
        return candidates

    for title in normalized_titles:
        normalized = normalize_title(title)
        if not normalized:
            continue
        mapping = resolver.alias_index.get(normalized)
        if mapping is None:
            continue
        for candidate in [mapping.folder_name, mapping.series_title, mapping.original_title, *mapping.aliases]:
            candidates.update(_normalize_title_candidates(candidate))

    return {item for item in candidates if item}


def _build_bangumi_title_index(bangumi_items: list[dict[str, Any]]) -> dict[str, set[int]]:
    resolver = _load_title_resolver()
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
        for candidate in _expanded_title_candidates(primary_titles, resolver=resolver):
            index.setdefault(candidate, set()).add(bangumi_id)

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


def _read_jellyfin_series_rows(anime_data_root: Path | None) -> list[dict[str, str | None]]:
    if anime_data_root is None:
        return []

    db_path = _jellyfin_db_path(anime_data_root)
    if not db_path.exists():
        return []

    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT Id, Name, OriginalTitle, Path
                FROM BaseItems
                WHERE Type = ?
                """,
                (_JELLYFIN_SERIES_TYPE,),
            ).fetchall()
    except sqlite3.Error:
        return []

    return [
        {
            "id": str(item_id) if item_id is not None else None,
            "name": str(name) if name is not None else None,
            "original_title": str(original_title) if original_title is not None else None,
            "path": str(path) if path is not None else None,
        }
        for item_id, name, original_title, path in rows
    ]


def _build_jellyfin_title_index(anime_data_root: Path | None, *, resolver=None) -> dict[str, set[str]]:
    if resolver is None:
        resolver = _load_title_resolver()
    index: dict[str, set[str]] = {}

    for row in _read_jellyfin_series_rows(anime_data_root):
        item_id = str(row.get("id") or "").strip()
        if not item_id:
            continue
        path_value = str(row.get("path") or "").strip()
        path_name = Path(path_value.replace("\\", "/")).name if path_value else None
        titles = [row.get("name"), row.get("original_title"), path_name]
        for candidate in _expanded_title_candidates(titles, resolver=resolver):
            index.setdefault(candidate, set()).add(item_id)

    return index


def _jellyfin_details_url(base_host: str, jellyfin_port: int, item_id: str) -> str:
    return f"http://{base_host}:{jellyfin_port}/web/#/details?id={item_id}"


def _resolve_jellyfin_url(
    item: dict[str, Any],
    *,
    jellyfin_title_index: dict[str, set[str]],
    base_host: str,
    jellyfin_port: int,
    resolver=None,
) -> str | None:
    if not jellyfin_title_index:
        return None

    matched_ids: set[str] = set()
    titles = [item.get("official_title"), item.get("title_raw"), item.get("title")]
    for candidate in _expanded_title_candidates(titles, resolver=resolver):
        matched_ids.update(jellyfin_title_index.get(candidate, set()))
        if len(matched_ids) > 1:
            return None

    if len(matched_ids) != 1:
        return None
    return _jellyfin_details_url(base_host, jellyfin_port, next(iter(matched_ids)))


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
    anime_data_root: Path | None = None,
    base_host: str,
    autobangumi_port: int,
    jellyfin_port: int = 8096,
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
    title_resolver = _load_title_resolver()
    jellyfin_title_index = _build_jellyfin_title_index(anime_data_root, resolver=title_resolver)

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
            "jellyfin_url": _resolve_jellyfin_url(
                item,
                jellyfin_title_index=jellyfin_title_index,
                base_host=base_host,
                jellyfin_port=jellyfin_port,
                resolver=title_resolver,
            ),
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
    jellyfin_port: int = 8096,
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
        anime_data_root=anime_data_root,
        base_host=base_host,
        autobangumi_port=autobangumi_port,
        jellyfin_port=jellyfin_port,
        library_ids=library_ids,
        now=now,
        state_root=state_root,
        visible_limit=visible_limit,
        locale=locale,
    )
    return {
        "weekly_schedule": schedule,
    }
