from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from anime_ops_ui.services.jellyfin_auth_service import authenticate_jellyfin_session

_JELLYFIN_EPISODE_TYPE = "MediaBrowser.Controller.Entities.TV.Episode"
_PLAYBACK_USER_CACHE_TTL = timedelta(minutes=5)
_playback_user_cache: tuple[datetime, str | None] | None = None


@dataclass(frozen=True)
class _WatchSchema:
    item_source: str
    join_clause: str


def read_series_watch_states(
    anime_data_root: Path | None,
    *,
    series_ids: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    db_path = _jellyfin_db_path(anime_data_root)
    if db_path is None or not db_path.exists():
        return {}

    user_id = _normalize_user_id(resolve_playback_user_id())
    if not user_id:
        return {}

    normalized_series_ids = [str(series_id or "").strip() for series_id in series_ids or [] if str(series_id or "").strip()]

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            schema = _resolve_watch_schema(conn)
            if schema is None:
                return {}

            where_clauses = ["items.Type = ?"]
            params: list[Any] = [user_id, _JELLYFIN_EPISODE_TYPE]
            if normalized_series_ids:
                placeholders = ",".join("?" for _ in normalized_series_ids)
                where_clauses.append(f"items.SeriesId IN ({placeholders})")
                params.extend(normalized_series_ids)

            rows = conn.execute(
                f"""
                SELECT
                    episode_state.SeriesId AS SeriesId,
                    COUNT(*) AS AvailableEpisodeCount,
                    SUM(
                        CASE
                            WHEN episode_state.Played = 1 THEN 0
                            ELSE 1
                        END
                    ) AS UnwatchedEpisodeCount
                FROM (
                    SELECT
                        items.SeriesId AS SeriesId,
                        items.Id AS ItemId,
                        MAX(COALESCE(user_data.Played, 0)) AS Played
                    FROM {schema.item_source} items
                    {schema.join_clause}
                    WHERE {" AND ".join(where_clauses)}
                    GROUP BY items.SeriesId, items.Id
                ) episode_state
                GROUP BY episode_state.SeriesId
                """,
                params,
            ).fetchall()
    except sqlite3.Error:
        return {}

    watch_states: dict[str, dict[str, Any]] = {}
    for row in rows:
        series_id = str(row["SeriesId"] or "").strip()
        if not series_id:
            continue
        available_episode_count = _safe_int(row["AvailableEpisodeCount"]) or 0
        unwatched_episode_count = _safe_int(row["UnwatchedEpisodeCount"]) or 0
        watch_states[series_id] = {
            "availableEpisodeCount": available_episode_count,
            "unwatchedEpisodeCount": unwatched_episode_count,
            "hasUnwatchedEpisodes": unwatched_episode_count > 0,
        }
    return watch_states


def read_episode_watch_states(
    anime_data_root: Path | None,
    jellyfin_series_id: str,
) -> dict[str, bool]:
    db_path = _jellyfin_db_path(anime_data_root)
    normalized_series_id = str(jellyfin_series_id or "").strip()
    if db_path is None or not db_path.exists() or not normalized_series_id:
        return {}

    user_id = _normalize_user_id(resolve_playback_user_id())
    if not user_id:
        return {}

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            schema = _resolve_watch_schema(conn)
            if schema is None:
                return {}

            rows = conn.execute(
                f"""
                SELECT
                    items.Id AS EpisodeId,
                    MAX(COALESCE(user_data.Played, 0)) AS Played
                FROM {schema.item_source} items
                {schema.join_clause}
                WHERE items.Type = ?
                    AND items.SeriesId = ?
                GROUP BY items.Id
                """,
                [user_id, _JELLYFIN_EPISODE_TYPE, normalized_series_id],
            ).fetchall()
    except sqlite3.Error:
        return {}

    return {
        str(row["EpisodeId"]): not _coerce_bool(row["Played"])
        for row in rows
        if str(row["EpisodeId"] or "").strip()
    }


def resolve_playback_user_id() -> str | None:
    global _playback_user_cache

    current = datetime.now(timezone.utc)
    cached = _playback_user_cache
    if cached is not None:
        expires_at, cached_user_id = cached
        if current < expires_at:
            return cached_user_id

    try:
        user_id = authenticate_jellyfin_session().user_id
    except Exception:
        user_id = None

    _playback_user_cache = (current + _PLAYBACK_USER_CACHE_TTL, user_id)
    return user_id


def _jellyfin_db_path(anime_data_root: Path | None) -> Path | None:
    if anime_data_root is None:
        return None
    return anime_data_root / "appdata" / "jellyfin" / "config" / "data" / "jellyfin.db"


def _resolve_watch_schema(conn: sqlite3.Connection) -> _WatchSchema | None:
    item_source = "TypedBaseItems" if _relation_exists(conn, "TypedBaseItems") else "BaseItems" if _relation_exists(conn, "BaseItems") else None
    if item_source is None:
        return None

    item_columns = _relation_columns(conn, item_source)
    if not {"id", "seriesid", "type"} <= item_columns:
        return None

    if _relation_exists(conn, "UserData"):
        user_columns = _relation_columns(conn, "UserData")
        if {"itemid", "userid", "played"} <= user_columns:
            return _WatchSchema(
                item_source=item_source,
                join_clause=(
                    "LEFT JOIN UserData user_data ON items.Id = user_data.ItemId "
                    "AND replace(lower(user_data.UserId), '-', '') = ?"
                ),
            )

    if _relation_exists(conn, "UserDatas"):
        user_columns = _relation_columns(conn, "UserDatas")
        if {"itemid", "userid", "played"} <= user_columns:
            return _WatchSchema(
                item_source=item_source,
                join_clause=(
                    "LEFT JOIN UserDatas user_data ON items.Id = user_data.ItemId "
                    "AND replace(lower(user_data.UserId), '-', '') = ?"
                ),
            )
        if {"key", "userid", "played"} <= user_columns and "userdatakey" in item_columns:
            return _WatchSchema(
                item_source=item_source,
                join_clause=(
                    "LEFT JOIN UserDatas user_data ON items.UserDataKey = user_data.Key "
                    "AND replace(lower(user_data.UserId), '-', '') = ?"
                ),
            )

    return None


def _relation_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type IN ('table', 'view')
            AND name = ?
        LIMIT 1
        """,
        (name,),
    ).fetchone()
    return row is not None


def _relation_columns(conn: sqlite3.Connection, name: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({name})").fetchall()
    except sqlite3.Error:
        return set()
    return {str(row[1] or "").strip().lower() for row in rows}


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    try:
        return int(value) != 0
    except (TypeError, ValueError):
        return str(value or "").strip().lower() in {"true", "yes", "y"}


def _normalize_user_id(value: Any) -> str:
    return str(value or "").strip().replace("-", "").lower()


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
