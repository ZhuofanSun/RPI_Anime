from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anime_postprocessor.parser import normalize_title
from anime_postprocessor.title_map import load_title_map

_JELLYFIN_SERIES_TYPE = "MediaBrowser.Controller.Entities.TV.Series"
_JELLYFIN_EPISODE_TYPE = "MediaBrowser.Controller.Entities.TV.Episode"


def _state_path(state_root: Path) -> Path:
    return state_root / "mobile_series_mappings.json"


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return normalize_title(text)


def _load_title_resolver():
    try:
        return load_title_map()
    except Exception:
        return None


def _mapping_for_titles(values: list[Any], *, resolver) -> Any | None:
    if resolver is None:
        return None
    for value in values:
        normalized = _normalize(value)
        if not normalized:
            continue
        mapping = resolver.alias_index.get(normalized)
        if mapping is not None:
            return mapping
    return None


def _jellyfin_db_path(anime_data_root: Path | None) -> Path | None:
    if anime_data_root is None:
        return None
    return anime_data_root / "appdata" / "jellyfin" / "config" / "data" / "jellyfin.db"


def _read_jellyfin_inventory(anime_data_root: Path | None) -> dict[str, Any]:
    db_path = _jellyfin_db_path(anime_data_root)
    if db_path is None or not db_path.exists():
        return {
            "byID": {},
            "byFolder": {},
            "byTitle": {},
        }

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            columns = {
                str(row["name"])
                for row in conn.execute("PRAGMA table_info(BaseItems)")
            }
            series_rows = conn.execute(
                """
                SELECT Id, Name, OriginalTitle, Path
                FROM BaseItems
                WHERE Type = ?
                """,
                (_JELLYFIN_SERIES_TYPE,),
            ).fetchall()
            episode_counts: dict[str, int] = {}
            if {"SeriesId", "Type"} <= columns:
                for row in conn.execute(
                    """
                    SELECT SeriesId, COUNT(*)
                    FROM BaseItems
                    WHERE Type = ?
                    GROUP BY SeriesId
                    """,
                    (_JELLYFIN_EPISODE_TYPE,),
                ):
                    series_id = str(row[0] or "").strip()
                    if series_id:
                        episode_counts[series_id] = int(row[1] or 0)
    except sqlite3.Error:
        return {
            "byID": {},
            "byFolder": {},
            "byTitle": {},
        }

    by_id: dict[str, dict[str, Any]] = {}
    by_folder: dict[str, set[str]] = {}
    by_title: dict[str, set[str]] = {}

    for row in series_rows:
        series_id = str(row["Id"] or "").strip()
        if not series_id:
            continue
        path_value = str(row["Path"] or "").strip()
        folder_name = Path(path_value.replace("\\", "/")).name if path_value else ""
        name = str(row["Name"] or "").strip()
        original_title = str(row["OriginalTitle"] or "").strip()
        record = {
            "jellyfinSeriesId": series_id,
            "folderName": folder_name or None,
            "name": name or None,
            "originalTitle": original_title or None,
            "availableEpisodeCount": int(episode_counts.get(series_id, 0)),
        }
        by_id[series_id] = record

        normalized_folder = _normalize(folder_name)
        if normalized_folder:
            by_folder.setdefault(normalized_folder, set()).add(series_id)

        for candidate in [name, original_title, folder_name]:
            normalized = _normalize(candidate)
            if normalized:
                by_title.setdefault(normalized, set()).add(series_id)

    return {
        "byID": by_id,
        "byFolder": by_folder,
        "byTitle": by_title,
    }


def _read_existing_state(state_root: Path) -> dict[int, dict[str, Any]]:
    path = _state_path(state_root)
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}

    records: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        bangumi_id = _safe_int(item.get("bangumiId"))
        if bangumi_id is None:
            continue
        records[bangumi_id] = item
    return records


def _write_state(state_root: Path, records: list[dict[str, Any]]) -> None:
    path = _state_path(state_root)
    try:
        state_root.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "items": records,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def _candidate_series_ids(
    item: dict[str, Any],
    *,
    inventory: dict[str, Any],
    resolver,
) -> tuple[str | None, str | None, int]:
    by_folder = inventory["byFolder"]
    by_title = inventory["byTitle"]

    mapping = _mapping_for_titles(
        [item.get("official_title"), item.get("title_raw"), item.get("title")],
        resolver=resolver,
    )
    if mapping is not None:
        normalized_folder = _normalize(mapping.folder_name)
        folder_ids = set(by_folder.get(normalized_folder, set()))
        if len(folder_ids) == 1:
            return next(iter(folder_ids)), "title_map_folder", len(folder_ids)

    matched_ids: set[str] = set()
    for candidate in [item.get("official_title"), item.get("title_raw"), item.get("title")]:
        normalized = _normalize(candidate)
        if not normalized:
            continue
        matched_ids.update(by_title.get(normalized, set()))
        if len(matched_ids) > 1:
            return None, "ambiguous_title", len(matched_ids)

    if len(matched_ids) == 1:
        return next(iter(matched_ids)), "exact_title", 1

    if mapping is not None:
        normalized_series_title = _normalize(mapping.series_title)
        series_title_ids = set(by_title.get(normalized_series_title, set()))
        if len(series_title_ids) == 1:
            return next(iter(series_title_ids)), "title_map_series_title", 1
        if len(series_title_ids) > 1:
            return None, "ambiguous_title_map_series_title", len(series_title_ids)

    return None, None, 0


def build_series_mapping_index(
    *,
    anime_data_root: Path | None,
    bangumi_items: list[dict[str, Any]],
    state_root: Path,
) -> dict[int, dict[str, Any]]:
    inventory = _read_jellyfin_inventory(anime_data_root)
    previous = _read_existing_state(state_root)
    resolver = _load_title_resolver()
    by_id = inventory["byID"]

    records: list[dict[str, Any]] = []
    index: dict[int, dict[str, Any]] = {}

    for item in bangumi_items:
        bangumi_id = _safe_int(item.get("id"))
        if bangumi_id is None:
            continue

        previous_record = previous.get(bangumi_id)
        preserved_series_id = str(previous_record.get("jellyfinSeriesId") or "").strip() if previous_record else ""
        matched_series_id = preserved_series_id if preserved_series_id in by_id else None
        matched_by = "persisted" if matched_series_id is not None else None
        candidate_count = 1 if matched_series_id is not None else 0

        if matched_series_id is None:
            matched_series_id, matched_by, candidate_count = _candidate_series_ids(
                item,
                inventory=inventory,
                resolver=resolver,
            )

        resolved_mapping = _mapping_for_titles(
            [item.get("official_title"), item.get("title_raw"), item.get("title")],
            resolver=resolver,
        )
        inventory_record = by_id.get(matched_series_id or "")
        record = {
            "bangumiId": bangumi_id,
            "officialTitle": str(item.get("official_title") or item.get("title_raw") or item.get("title") or "").strip(),
            "resolvedFolderName": (
                resolved_mapping.folder_name
                if resolved_mapping is not None
                else str(item.get("official_title") or "").strip() or None
            ),
            "jellyfinSeriesId": matched_series_id,
            "availableEpisodeCount": int(inventory_record["availableEpisodeCount"]) if inventory_record is not None else 0,
            "hasPlayableEpisodes": bool(inventory_record and int(inventory_record["availableEpisodeCount"]) > 0),
            "matchedBy": matched_by,
            "candidateCount": candidate_count,
        }
        records.append(record)
        index[bangumi_id] = record

    _write_state(state_root, records)
    return index
