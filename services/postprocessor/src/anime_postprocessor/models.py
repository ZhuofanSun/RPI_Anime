from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EpisodeKey:
    normalized_title: str
    season: int
    episode: int


@dataclass(frozen=True)
class ParsedMedia:
    path: Path
    relative_path: Path
    title: str
    normalized_title: str
    season: int
    episode: int
    extension: str
    release_group: str | None

    @property
    def key(self) -> EpisodeKey:
        return EpisodeKey(
            normalized_title=self.normalized_title,
            season=self.season,
            episode=self.episode,
        )

    @property
    def default_target_name(self) -> str:
        return f"{self.title} S{self.season:02d}E{self.episode:02d}{self.extension}"


@dataclass(frozen=True)
class UnparsedMedia:
    path: Path
    relative_path: Path
    reason: str
