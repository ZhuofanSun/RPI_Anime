from __future__ import annotations

import re
from pathlib import Path

from .models import ParsedMedia, UnparsedMedia

MEDIA_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".ts"}

_EXPLICIT_SEASON_EPISODE_PATTERNS = (
    re.compile(r"\bS(?P<season>\d{1,2})E(?P<episode>\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\[(?:S|Season\s*)(?P<season>\d{1,2})\]\s*\[(?P<episode>\d{1,3})(?:v\d+)?\]", re.IGNORECASE),
    re.compile(r"\b(?:S|Season)\s*(?P<season>\d{1,2})\s*[-_. ]+\s*(?P<episode>\d{1,3})(?:v\d+)?\b", re.IGNORECASE),
)
_EPISODE_ONLY_PATTERNS = (
    re.compile(r"第(?P<episode>\d{1,3})[话話集]", re.IGNORECASE),
    re.compile(r"\[(?P<episode>\d{1,3})(?:v\d+)?\]"),
    re.compile(r"(?:^|[\s._-])(?P<episode>\d{1,3})(?:v\d+)?(?=[\s._-]|$)"),
)

_RELEASE_GROUP_PATTERN = re.compile(r"^\[(?P<group>[^\]]+)\]\s*")
_TRAILING_METADATA_PATTERN = re.compile(r"[\[(].*$")
_SPACE_PATTERN = re.compile(r"\s+")
_TITLE_NOISE_PATTERN = re.compile(r"[._]+")
_NORMALIZE_PATTERN = re.compile(r"[^\w]+", re.UNICODE)
_SEASON_FOLDER_PATTERN = re.compile(r"^(?:season\s*\d+|s\d+)$", re.IGNORECASE)
_RELATIVE_SEASON_PATTERN = re.compile(r"^(?:season\s*(?P<season>\d+)|s(?P<short>\d+)|第(?P<cn>\d+)季)$", re.IGNORECASE)


def _extract_release_group(stem: str) -> tuple[str | None, str]:
    match = _RELEASE_GROUP_PATTERN.match(stem)
    if not match:
        return None, stem
    group = match.group("group").strip()
    remainder = stem[match.end() :].strip()
    return group, remainder


def _find_explicit_season_episode(stem: str) -> tuple[int, int, tuple[int, int]] | None:
    for pattern in _EXPLICIT_SEASON_EPISODE_PATTERNS:
        match = pattern.search(stem)
        if not match:
            continue
        season = int(match.group("season"))
        episode = int(match.group("episode"))
        return season, episode, match.span()
    return None


def _find_episode_only(stem: str) -> tuple[int, tuple[int, int]] | None:
    for pattern in _EPISODE_ONLY_PATTERNS:
        match = pattern.search(stem)
        if not match:
            continue
        return int(match.group("episode")), match.span()
    return None


def _season_from_relative_path(relative_path: Path) -> int | None:
    for part in reversed(relative_path.parts[:-1]):
        cleaned = part.strip()
        if not cleaned:
            continue
        match = _RELATIVE_SEASON_PATTERN.fullmatch(cleaned)
        if not match:
            continue
        value = match.group("season") or match.group("short") or match.group("cn")
        if value is None:
            continue
        return int(value)
    return None


def _find_season_episode(stem: str, *, relative_path: Path) -> tuple[int, int, tuple[int, int]] | None:
    explicit = _find_explicit_season_episode(stem)
    if explicit is not None:
        return explicit

    episode_only = _find_episode_only(stem)
    if episode_only is None:
        return None

    episode, span = episode_only
    season = _season_from_relative_path(relative_path) or 1
    return season, episode, span


def _clean_title(raw_title: str) -> str:
    title = _TITLE_NOISE_PATTERN.sub(" ", raw_title)
    title = title.strip(" -_.[]()")
    title = _SPACE_PATTERN.sub(" ", title).strip()
    return title


def normalize_title(title: str) -> str:
    normalized = _NORMALIZE_PATTERN.sub(" ", title.lower())
    return _SPACE_PATTERN.sub(" ", normalized).strip()


def _fallback_title_from_relative_path(relative_path: Path) -> str:
    for part in reversed(relative_path.parts[:-1]):
        cleaned = _clean_title(part)
        if not cleaned:
            continue
        if _SEASON_FOLDER_PATTERN.fullmatch(cleaned):
            continue
        return cleaned
    return ""


def parse_media_file(root: Path, path: Path) -> ParsedMedia | UnparsedMedia:
    relative_path = path.relative_to(root)
    extension = path.suffix.lower()
    if extension not in MEDIA_EXTENSIONS:
        return UnparsedMedia(
            path=path,
            relative_path=relative_path,
            reason=f"unsupported extension: {extension}",
        )

    stem = path.stem
    release_group, remainder = _extract_release_group(stem)
    season_episode = _find_season_episode(remainder, relative_path=relative_path)
    if season_episode is None:
        return UnparsedMedia(
            path=path,
            relative_path=relative_path,
            reason="cannot parse season/episode",
        )

    season, episode, span = season_episode
    title_part = remainder[: span[0]]
    title_part = _TRAILING_METADATA_PATTERN.sub("", title_part)
    title = _clean_title(title_part)
    if not title:
        title = _fallback_title_from_relative_path(relative_path)
    if not title:
        return UnparsedMedia(
            path=path,
            relative_path=relative_path,
            reason="empty title after cleanup",
        )

    return ParsedMedia(
        path=path,
        relative_path=relative_path,
        title=title,
        normalized_title=normalize_title(title),
        season=season,
        episode=episode,
        extension=extension,
        release_group=release_group,
    )
