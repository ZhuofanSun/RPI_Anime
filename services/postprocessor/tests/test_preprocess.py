from pathlib import Path

from anime_postprocessor.compatibility import (
    ActionQueue,
    CompatibilityAssessment,
    CompatibilityReport,
    DecisionCompatibility,
    MediaProbe,
)
from anime_postprocessor.models import EpisodeKey, ParsedMedia
from anime_postprocessor.preprocess import build_preprocess_entries
from anime_postprocessor.selector import CandidateScore, SelectionDecision


def _media(path: str, *, title: str = "Demo Show") -> ParsedMedia:
    relative_path = Path(path)
    return ParsedMedia(
        path=Path("/tmp/library") / relative_path,
        relative_path=relative_path,
        title=title,
        normalized_title="demo show",
        season=1,
        episode=1,
        extension=relative_path.suffix.lower(),
        release_group="demo",
    )


def _score() -> CandidateScore:
    return CandidateScore(
        subtitle_label="CHS",
        subtitle_rank=4,
        codec_label="AVC",
        codec_rank=2,
        container_label="mp4",
        container_rank=2,
        resolution_label="1080p",
        resolution_rank=4,
    )


def _decision(media: ParsedMedia) -> SelectionDecision:
    return SelectionDecision(
        key=EpisodeKey(normalized_title="demo show", season=1, episode=1),
        winner=media,
        winner_score=_score(),
        losers=[],
        loser_scores={},
    )


def _probe(path: Path) -> MediaProbe:
    return MediaProbe(
        path=path,
        container="matroska",
        video_codec="h264",
        video_profile="High",
        pixel_format="yuv420p",
        bit_depth=8,
        audio_codecs=["aac"],
        subtitle_codecs=["ass"],
        audio_track_count=1,
        subtitle_track_count=1,
    )


def _report(media: ParsedMedia, queue_key: str) -> CompatibilityReport:
    assessment = CompatibilityAssessment(
        classification="yellow",
        reasons=["demo"],
        suggested_actions=["convert_subtitles_to_webvtt", "remux_to_mp4_or_fmp4"],
        action_queue=ActionQueue(
            key=queue_key,
            steps=["convert_subtitles_to_webvtt", "remux_to_mp4_or_fmp4"],
            summary="subtitles_to_webvtt -> remux_to_mp4_or_fmp4",
            note="demo note",
        ),
        device_validation_required=False,
        device_validation_notes=[],
        sync_risk="medium",
        quality_risk="low",
    )
    return CompatibilityReport(
        decisions=[
            DecisionCompatibility(
                decision=_decision(media),
                probe=_probe(media.path),
                assessment=assessment,
            )
        ]
    )


class _Resolver:
    def resolve(self, media: ParsedMedia):
        class _Resolved:
            folder_name = media.title
            season_number = media.season
            episode_number = media.episode

        return _Resolved()


def test_build_preprocess_entries_maps_supported_queue_to_mp4_output():
    media = _media("Demo Show/Season 1/Demo Show S01E01.mkv")
    report = _report(media, "subtitles_to_webvtt__then__remux_to_mp4_or_fmp4")

    entries = build_preprocess_entries(
        report,
        library_root=Path("/tmp/library"),
        resolver=_Resolver(),
        staging_root=Path("/tmp/staging"),
        backup_root=Path("/tmp/backups"),
    )

    assert len(entries) == 1
    entry = entries[0]
    assert entry.strategy == "mp4_text_remux"
    assert entry.staging_output_path == Path(
        "/tmp/staging/Demo Show/Season 1/Demo Show S01E01.mp4"
    )
    assert entry.library_output_path == Path(
        "/tmp/library/Demo Show/Season 1/Demo Show S01E01.mp4"
    )
    assert entry.backup_path == Path(
        "/tmp/backups/Demo Show/Season 1/Demo Show S01E01.mkv"
    )


def test_build_preprocess_entries_skips_unsupported_queue():
    media = _media("Demo Show/Season 1/Demo Show S01E01.mp4")
    report = _report(media, "publish_direct__then__verify_hevc_on_target_devices")

    entries = build_preprocess_entries(
        report,
        library_root=Path("/tmp/library"),
        resolver=_Resolver(),
        staging_root=Path("/tmp/staging"),
        backup_root=Path("/tmp/backups"),
    )

    assert entries == []


def test_build_preprocess_entries_filters_by_title():
    media = _media("Demo Show/Season 1/Demo Show S01E01.mkv", title="Demo Show")
    report = _report(media, "subtitles_to_webvtt__then__remux_to_mp4_or_fmp4")

    entries = build_preprocess_entries(
        report,
        library_root=Path("/tmp/library"),
        resolver=_Resolver(),
        staging_root=Path("/tmp/staging"),
        backup_root=Path("/tmp/backups"),
        title_filters={"Another Show"},
    )

    assert entries == []
