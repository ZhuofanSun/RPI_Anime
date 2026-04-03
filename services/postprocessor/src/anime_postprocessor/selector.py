from __future__ import annotations

from dataclasses import dataclass

from .models import EpisodeKey, ParsedMedia


@dataclass(frozen=True)
class CandidateScore:
    subtitle_label: str
    subtitle_rank: int
    codec_label: str
    codec_rank: int
    container_label: str
    container_rank: int
    resolution_label: str
    resolution_rank: int

    @property
    def tuple(self) -> tuple[int, int, int, int]:
        return (
            self.subtitle_rank,
            self.codec_rank,
            self.container_rank,
            self.resolution_rank,
        )

    @property
    def summary(self) -> str:
        return (
            f"subtitle={self.subtitle_label}, "
            f"codec={self.codec_label}, "
            f"container={self.container_label}, "
            f"resolution={self.resolution_label}"
        )


@dataclass(frozen=True)
class SelectionDecision:
    key: EpisodeKey
    winner: ParsedMedia
    winner_score: CandidateScore
    losers: list[ParsedMedia]
    loser_scores: dict[str, CandidateScore]


def _detect_subtitle(name: str) -> tuple[str, int]:
    lower = name.lower()
    if any(token in lower for token in ("chs&cht", "cht&chs", "chs+cht", "cht+chs")):
        return "CHS&CHT", 3
    if "chs" in lower:
        return "CHS", 4
    if "cht" in lower:
        return "CHT", 1
    return "unknown", 2


def _detect_codec(name: str) -> tuple[str, int]:
    lower = name.lower()
    if any(token in lower for token in ("avc", "h264", "x264")):
        return "AVC", 2
    if any(token in lower for token in ("hevc", "h265", "x265")):
        return "HEVC", 1
    return "unknown", 0


def _detect_container(media: ParsedMedia) -> tuple[str, int]:
    if media.extension == ".mp4":
        return "mp4", 2
    if media.extension == ".mkv":
        return "mkv", 1
    return media.extension.lstrip("."), 0


def _detect_resolution(name: str) -> tuple[str, int]:
    lower = name.lower()
    if "1080" in lower:
        return "1080p", 4
    if "1440" in lower:
        return "1440p", 3
    if "720" in lower:
        return "720p", 2
    if "2160" in lower or "4k" in lower:
        return "2160p", 1
    return "unknown", 0


def score_candidate(media: ParsedMedia) -> CandidateScore:
    subtitle_label, subtitle_rank = _detect_subtitle(media.path.name)
    codec_label, codec_rank = _detect_codec(media.path.name)
    container_label, container_rank = _detect_container(media)
    resolution_label, resolution_rank = _detect_resolution(media.path.name)
    return CandidateScore(
        subtitle_label=subtitle_label,
        subtitle_rank=subtitle_rank,
        codec_label=codec_label,
        codec_rank=codec_rank,
        container_label=container_label,
        container_rank=container_rank,
        resolution_label=resolution_label,
        resolution_rank=resolution_rank,
    )


def select_winner(candidates: list[ParsedMedia]) -> SelectionDecision:
    if not candidates:
        raise ValueError("select_winner requires at least one candidate")

    scored = [(candidate, score_candidate(candidate)) for candidate in candidates]
    best_score = max(score.tuple for _, score in scored)
    best_candidates = [
        (candidate, score) for candidate, score in scored if score.tuple == best_score
    ]
    winner, winner_score = sorted(
        best_candidates, key=lambda item: str(item[0].relative_path)
    )[0]

    losers = [candidate for candidate in candidates if candidate != winner]
    loser_scores = {
        str(candidate.relative_path): score_candidate(candidate) for candidate in losers
    }
    return SelectionDecision(
        key=winner.key,
        winner=winner,
        winner_score=winner_score,
        losers=losers,
        loser_scores=loser_scores,
    )


def build_selection_plan(
    parsed_files: list[ParsedMedia],
) -> list[SelectionDecision]:
    grouped: dict[EpisodeKey, list[ParsedMedia]] = {}
    for parsed in parsed_files:
        grouped.setdefault(parsed.key, []).append(parsed)

    decisions = [select_winner(group) for group in grouped.values()]
    return sorted(
        decisions,
        key=lambda item: (
            item.key.normalized_title,
            item.key.season,
            item.key.episode,
        ),
    )
