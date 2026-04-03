from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .models import ParsedMedia
from .parser import normalize_title


@dataclass(frozen=True)
class SeriesMapping:
    folder_name: str
    series_title: str
    aliases: tuple[str, ...]
    original_title: str | None = None
    season_number: int | None = None
    episode_offset: int = 0
    tmdbid: str | None = None
    tvdbid: str | None = None
    imdbid: str | None = None

    @property
    def provider_ids(self) -> dict[str, str]:
        ids: dict[str, str] = {}
        if self.tmdbid:
            ids["tmdbid"] = self.tmdbid
        if self.tvdbid:
            ids["tvdbid"] = self.tvdbid
        if self.imdbid:
            ids["imdbid"] = self.imdbid
        return ids


@dataclass(frozen=True)
class ResolvedSeries:
    folder_name: str
    series_title: str
    original_title: str | None
    season_number: int
    episode_number: int
    provider_ids: dict[str, str]
    has_mapping: bool


class TitleMapResolver:
    def __init__(self, mappings: list[SeriesMapping]):
        self.mappings = mappings
        self.alias_index: dict[str, SeriesMapping] = {}
        for mapping in mappings:
            for alias in mapping.aliases:
                normalized = normalize_title(alias)
                if normalized:
                    self.alias_index[normalized] = mapping

    def _default_show_name(self, media: ParsedMedia) -> str:
        parts = media.relative_path.parts
        if len(parts) >= 2 and parts[1].lower().startswith("season "):
            return parts[0]
        if len(parts) >= 2:
            return parts[0]
        return media.title

    def _lookup(self, media: ParsedMedia) -> SeriesMapping | None:
        candidates = [media.title, self._default_show_name(media)]
        for candidate in candidates:
            normalized = normalize_title(candidate)
            if not normalized:
                continue
            mapping = self.alias_index.get(normalized)
            if mapping is not None:
                return mapping
        return None

    def resolve(self, media: ParsedMedia) -> ResolvedSeries:
        mapping = self._lookup(media)
        if mapping is None:
            show_name = self._default_show_name(media)
            return ResolvedSeries(
                folder_name=show_name,
                series_title=show_name,
                original_title=media.title if show_name != media.title else None,
                season_number=media.season,
                episode_number=media.episode,
                provider_ids={},
                has_mapping=False,
            )

        season_number = mapping.season_number or media.season
        episode_number = max(1, media.episode + mapping.episode_offset)
        return ResolvedSeries(
            folder_name=mapping.folder_name,
            series_title=mapping.series_title,
            original_title=mapping.original_title,
            season_number=season_number,
            episode_number=episode_number,
            provider_ids=mapping.provider_ids,
            has_mapping=True,
        )


def _default_title_map_path() -> Path:
    configured = Path(
        os.environ.get(
            "POSTPROCESSOR_TITLE_MAP",
            "/srv/anime-data/appdata/rpi-anime/deploy/title_mappings.toml",
        )
    )
    if configured.exists():
        return configured

    repo_fallback = Path(__file__).resolve().parents[4] / "deploy" / "title_mappings.toml"
    return repo_fallback


def load_title_map(path: Path | None = None) -> TitleMapResolver:
    mapping_path = path or _default_title_map_path()
    if not mapping_path.exists():
        return TitleMapResolver([])

    with mapping_path.open("rb") as handle:
        data = tomllib.load(handle)

    mappings: list[SeriesMapping] = []
    for item in data.get("series", []):
        folder_name = item["folder_name"]
        aliases = {
            *item.get("aliases", []),
            folder_name,
            item.get("series_title", folder_name),
        }
        original_title = item.get("original_title")
        if original_title:
            aliases.add(original_title)
        mappings.append(
            SeriesMapping(
                folder_name=folder_name,
                series_title=item.get("series_title", folder_name),
                aliases=tuple(sorted(aliases)),
                original_title=original_title,
                season_number=item.get("season_number"),
                episode_offset=int(item.get("episode_offset", 0)),
                tmdbid=item.get("tmdbid"),
                tvdbid=item.get("tvdbid"),
                imdbid=item.get("imdbid"),
            )
        )

    return TitleMapResolver(mappings)
