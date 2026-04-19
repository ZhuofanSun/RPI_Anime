from __future__ import annotations

import html
import re
import sqlite3
from pathlib import Path
from typing import Any

from anime_ops_ui import runtime_main_module
from anime_ops_ui.domain.mobile_models import HomeFollowingItem
from anime_ops_ui.services.mobile_media_service import build_mobile_jellyfin_poster_url, build_mobile_poster_url
from anime_ops_ui.services.mobile_seasonal_service import build_recent_seasonal

_COLLECTION_APP_ITEM_PREFIX = "app_collection_jf_"
_COLLECTION_ROOT_PATH = "/media/collection"
_JELLYFIN_FOLDER_TYPES = {
    "MediaBrowser.Controller.Entities.CollectionFolder",
    "MediaBrowser.Controller.Entities.Folder",
}
_JELLYFIN_SERIES_TYPE = "MediaBrowser.Controller.Entities.TV.Series"
_JELLYFIN_SEASON_TYPE = "MediaBrowser.Controller.Entities.TV.Season"
_JELLYFIN_EPISODE_TYPE = "MediaBrowser.Controller.Entities.TV.Episode"


def build_favorite_items(*, public_base_url: str | None = None) -> list[HomeFollowingItem]:
    items: list[HomeFollowingItem] = []
    for row in _read_collection_series_rows(_anime_data_root()):
        jellyfin_item_id = str(row["id"])
        episode_count = _safe_int(row.get("episode_count")) or 0
        items.append(
            HomeFollowingItem(
                appItemId=_collection_app_item_id(jellyfin_item_id),
                title=_display_title(row),
                posterUrl=build_mobile_jellyfin_poster_url(
                    jellyfin_item_id=jellyfin_item_id,
                    public_base_url=public_base_url,
                )
                or "",
                unread=False,
                mappingStatus="mapped",
                jellyfinSeriesId=jellyfin_item_id,
                availabilityState="mapped_playable" if episode_count > 0 else "mapped_unplayable",
            )
        )
    return items


def get_collection_item(
    app_item_id: str,
    *,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> dict[str, Any] | None:
    jellyfin_item_id = _collection_jellyfin_id(app_item_id)
    if jellyfin_item_id is None:
        return None

    series = _read_collection_series_detail(_anime_data_root(), jellyfin_item_id)
    if series is None:
        return None

    context = get_jellyfin_series_context(jellyfin_item_id, public_base_url=public_base_url)
    if context is None:
        return None

    season_payload = _format_series_entries(context["seasons"], prefix=_COLLECTION_APP_ITEM_PREFIX)
    episode_payload = _format_series_entries(context["episodes"], prefix=_COLLECTION_APP_ITEM_PREFIX)
    latest_episode = episode_payload[-1] if episode_payload else None

    return {
        "appItemId": app_item_id,
        "mappingStatus": "mapped",
        "title": str(context["title"]),
        "heroState": "playable_primed" if latest_episode is not None else "unavailable",
        "hero": {
            "posterUrl": str(context["posterUrl"]),
            "backdropUrl": str(context["posterUrl"]),
            **(
                {
                    "latestPlayableEpisodeId": str(context["latestPlayableEpisodeId"]),
                    "primedLabel": str(context["primedLabel"]),
                    "playTarget": "zFuse",
                }
                if latest_episode is not None
                else {}
            ),
        },
        "summary": {
            "freshness": str(context["freshness"]),
            "availableEpisodeCount": int(context["availableEpisodeCount"]),
            "seasonLabel": str(context["seasonLabel"]),
            "score": str(context["score"]),
            "tags": list(context["tags"]),
        },
        "overview": str(context["overview"]),
        "seasons": season_payload,
        "episodes": episode_payload,
        "recentSeasonal": _recent_seasonal_items(
            public_host=public_host,
            public_base_url=public_base_url,
        ),
    }


def get_jellyfin_series_context(
    jellyfin_item_id: str,
    *,
    public_base_url: str | None = None,
) -> dict[str, Any] | None:
    series = _read_series_detail(_anime_data_root(), jellyfin_item_id)
    if series is None:
        return None

    seasons = _read_series_children(_anime_data_root(), jellyfin_item_id, child_type=_JELLYFIN_SEASON_TYPE)
    episodes = _read_series_children(_anime_data_root(), jellyfin_item_id, child_type=_JELLYFIN_EPISODE_TYPE)
    selected_season_id = seasons[-1]["id"] if seasons else None
    selected_episodes = [episode for episode in episodes if episode.get("parent_id") == selected_season_id]
    if not selected_episodes:
        selected_episodes = episodes

    season_entries = [
        {
            "id": str(season["id"]),
            "label": _season_label(season),
            "selected": str(season["id"]) == selected_season_id,
        }
        for season in seasons
    ]
    episode_entries = [
        {
            "id": str(episode["id"]),
            "label": _episode_label(episode),
            "focused": index == len(selected_episodes) - 1,
            "unread": False,
        }
        for index, episode in enumerate(selected_episodes)
    ]
    latest_episode = episode_entries[-1] if episode_entries else None
    selected_season = season_entries[-1] if season_entries else None
    freshness = _premiere_year(series.get("premiere_date"))

    return {
        "title": _display_title(series),
        "posterUrl": build_mobile_jellyfin_poster_url(
            jellyfin_item_id=jellyfin_item_id,
            public_base_url=public_base_url,
        )
        or "",
        "availableEpisodeCount": len(episodes),
        "freshness": freshness,
        "seasonLabel": str(selected_season["label"]) if selected_season is not None else freshness,
        "score": _score_label(series.get("community_rating")),
        "tags": _tags(series.get("tags")),
        "overview": _overview(series.get("overview")),
        "seasons": season_entries,
        "episodes": episode_entries,
        "latestPlayableEpisodeId": str(latest_episode["id"]) if latest_episode is not None else None,
        "primedLabel": str(latest_episode["label"]) if latest_episode is not None else None,
    }


def _anime_data_root() -> Path:
    main_module = runtime_main_module()
    return main_module.Path(main_module._env("ANIME_DATA_ROOT", "/srv/anime-data"))


def _jellyfin_db_path(anime_data_root: Path) -> Path:
    return anime_data_root / "appdata" / "jellyfin" / "config" / "data" / "jellyfin.db"


def _read_collection_series_rows(anime_data_root: Path) -> list[dict[str, Any]]:
    db_path = _jellyfin_db_path(anime_data_root)
    if not db_path.exists():
        return []

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            params: list[Any] = [_JELLYFIN_EPISODE_TYPE, _JELLYFIN_SERIES_TYPE, f"{_COLLECTION_ROOT_PATH}/%"]
            where_clauses = ["series.Path LIKE ?"]
            root_ids = _collection_root_ids(conn)
            if root_ids:
                placeholders = ",".join("?" for _ in root_ids)
                where_clauses.append(f"series.ParentId IN ({placeholders})")
                where_clauses.append(f"series.TopParentId IN ({placeholders})")
                params.extend(root_ids)
                params.extend(root_ids)

            rows = conn.execute(
                f"""
                SELECT
                    series.Id,
                    series.Name,
                    series.OriginalTitle,
                    series.Overview,
                    series.CommunityRating,
                    series.PremiereDate,
                    series.Tags,
                    series.Path,
                    series.DateCreated,
                    COUNT(DISTINCT episode.Id) AS EpisodeCount
                FROM BaseItems AS series
                LEFT JOIN BaseItems AS episode
                    ON episode.SeriesId = series.Id
                    AND episode.Type = ?
                WHERE series.Type = ?
                    AND ({' OR '.join(where_clauses)})
                GROUP BY
                    series.Id, series.Name, series.OriginalTitle, series.Overview, series.CommunityRating,
                    series.PremiereDate, series.Tags, series.Path, series.DateCreated
                ORDER BY series.Name COLLATE NOCASE, series.Id
                """,
                params,
            ).fetchall()
    except sqlite3.Error:
        return []

    return [_row_dict(row) for row in rows]


def _read_collection_series_detail(anime_data_root: Path, jellyfin_item_id: str) -> dict[str, Any] | None:
    db_path = _jellyfin_db_path(anime_data_root)
    if not db_path.exists():
        return None

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            params: list[Any] = [jellyfin_item_id, _JELLYFIN_SERIES_TYPE, f"{_COLLECTION_ROOT_PATH}/%"]
            where_clauses = ["series.Path LIKE ?"]
            root_ids = _collection_root_ids(conn)
            if root_ids:
                placeholders = ",".join("?" for _ in root_ids)
                where_clauses.append(f"series.ParentId IN ({placeholders})")
                where_clauses.append(f"series.TopParentId IN ({placeholders})")
                params.extend(root_ids)
                params.extend(root_ids)

            row = conn.execute(
                f"""
                SELECT
                    series.Id,
                    series.Name,
                    series.OriginalTitle,
                    series.Overview,
                    series.CommunityRating,
                    series.PremiereDate,
                    series.Tags,
                    series.Path,
                    series.DateCreated
                FROM BaseItems AS series
                WHERE series.Id = ?
                    AND series.Type = ?
                    AND ({' OR '.join(where_clauses)})
                LIMIT 1
                """,
                params,
            ).fetchone()
    except sqlite3.Error:
        return None

    return _row_dict(row) if row is not None else None


def _read_series_detail(anime_data_root: Path, jellyfin_item_id: str) -> dict[str, Any] | None:
    db_path = _jellyfin_db_path(anime_data_root)
    if not db_path.exists():
        return None

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT
                    Id,
                    Name,
                    OriginalTitle,
                    Overview,
                    CommunityRating,
                    PremiereDate,
                    Tags,
                    Path,
                    DateCreated
                FROM BaseItems
                WHERE Id = ?
                    AND Type = ?
                LIMIT 1
                """,
                (jellyfin_item_id, _JELLYFIN_SERIES_TYPE),
            ).fetchone()
    except sqlite3.Error:
        return None

    return _row_dict(row) if row is not None else None


def _read_collection_seasons(anime_data_root: Path, jellyfin_item_id: str) -> list[dict[str, Any]]:
    return _read_series_children(
        anime_data_root,
        jellyfin_item_id,
        child_type=_JELLYFIN_SEASON_TYPE,
    )


def _read_collection_episodes(anime_data_root: Path, jellyfin_item_id: str) -> list[dict[str, Any]]:
    return _read_series_children(
        anime_data_root,
        jellyfin_item_id,
        child_type=_JELLYFIN_EPISODE_TYPE,
    )


def _read_series_children(anime_data_root: Path, jellyfin_item_id: str, *, child_type: str) -> list[dict[str, Any]]:
    db_path = _jellyfin_db_path(anime_data_root)
    if not db_path.exists():
        return []

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    Id,
                    Name,
                    ParentId,
                    IndexNumber,
                    ParentIndexNumber
                FROM BaseItems
                WHERE Type = ?
                    AND SeriesId = ?
                ORDER BY
                    COALESCE(ParentIndexNumber, 0),
                    COALESCE(IndexNumber, 0),
                    Name COLLATE NOCASE,
                    Id
                """,
                (child_type, jellyfin_item_id),
            ).fetchall()
    except sqlite3.Error:
        return []

    return [_row_dict(row) for row in rows]


def _collection_root_ids(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        f"""
        SELECT Id
        FROM BaseItems
        WHERE Path = ?
            AND Type IN ({','.join('?' for _ in _JELLYFIN_FOLDER_TYPES)})
        """,
        (_COLLECTION_ROOT_PATH, *_JELLYFIN_FOLDER_TYPES),
    ).fetchall()
    return [str(row[0]) for row in rows if row and row[0] is not None]


def _collection_app_item_id(jellyfin_item_id: str) -> str:
    return f"{_COLLECTION_APP_ITEM_PREFIX}{jellyfin_item_id}"


def _collection_jellyfin_id(app_item_id: str) -> str | None:
    normalized = str(app_item_id or "").strip()
    if not normalized.startswith(_COLLECTION_APP_ITEM_PREFIX):
        return None
    candidate = normalized[len(_COLLECTION_APP_ITEM_PREFIX) :].strip()
    if not re.fullmatch(r"[A-Za-z0-9-]+", candidate):
        return None
    return candidate


def _display_title(row: dict[str, Any]) -> str:
    title = str(row.get("name") or "").strip()
    if title:
        return title
    path_value = str(row.get("path") or "").strip()
    if path_value:
        return Path(path_value.replace("\\", "/")).name or "Unknown"
    return "Unknown"


def _premiere_year(value: Any) -> str:
    raw = str(value or "").strip()
    return raw[:4] if len(raw) >= 4 else ""


def _score_label(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "--"
    return f"{numeric:.1f}"


def _tags(value: Any) -> list[str]:
    return [tag for tag in (str(value or "").split("|")) if tag][:5]


def _overview(value: Any) -> str:
    raw = html.unescape(str(value or "").strip())
    if not raw:
        return ""
    return re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)


def _season_label(season: dict[str, Any]) -> str:
    index = _safe_int(season.get("index_number"))
    if index is not None:
        return f"S{index:02d}"
    name = str(season.get("name") or "").strip()
    return name or "S?"


def _episode_label(episode: dict[str, Any]) -> str:
    index = _safe_int(episode.get("index_number"))
    if index is not None:
        return f"E{index:02d}"
    name = str(episode.get("name") or "").strip()
    return name or "Episode"


def _format_series_entries(entries: list[dict[str, Any]], *, prefix: str, mark_focused_unread: bool = False) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for entry in entries:
        focused = bool(entry.get("focused"))
        formatted.append(
            {
                "id": f"{prefix}{entry['id']}",
                "label": entry["label"],
                **({"selected": bool(entry.get("selected"))} if "selected" in entry else {}),
                **({"focused": focused} if "focused" in entry else {}),
                **({"unread": focused if mark_focused_unread else bool(entry.get("unread"))} if "unread" in entry else {}),
            }
        )
    return formatted


def _recent_seasonal_items(
    *,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> list[dict[str, Any]]:
    items = build_recent_seasonal(
        public_host=public_host,
        public_base_url=public_base_url,
    )
    return [
        {
            **item,
            "posterUrl": build_mobile_poster_url(
                poster_link=str(item.get("posterUrl") or "").strip() or None,
                public_base_url=public_base_url,
            )
            or str(item.get("posterUrl") or ""),
        }
        for item in items
    ]


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["Id"],
        "name": row["Name"],
        "original_title": row["OriginalTitle"] if "OriginalTitle" in row.keys() else None,
        "overview": row["Overview"] if "Overview" in row.keys() else None,
        "community_rating": row["CommunityRating"] if "CommunityRating" in row.keys() else None,
        "premiere_date": row["PremiereDate"] if "PremiereDate" in row.keys() else None,
        "tags": row["Tags"] if "Tags" in row.keys() else None,
        "path": row["Path"] if "Path" in row.keys() else None,
        "date_created": row["DateCreated"] if "DateCreated" in row.keys() else None,
        "parent_id": row["ParentId"] if "ParentId" in row.keys() else None,
        "index_number": row["IndexNumber"] if "IndexNumber" in row.keys() else None,
        "parent_index_number": row["ParentIndexNumber"] if "ParentIndexNumber" in row.keys() else None,
        "episode_count": row["EpisodeCount"] if "EpisodeCount" in row.keys() else None,
    }


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
