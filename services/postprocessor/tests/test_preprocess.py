from pathlib import Path

from anime_postprocessor.compatibility import (
    ActionQueue,
    CompatibilityAssessment,
    CompatibilityReport,
    DecisionCompatibility,
    MediaProbe,
)
from anime_postprocessor.models import EpisodeKey, ParsedMedia
from anime_postprocessor.preprocess import (
    PreprocessEntry,
    _run_preprocess_entry,
    apply_preprocess_entries,
    build_preprocess_entries,
    filter_preprocess_decisions,
    summarize_preprocess_entries,
)
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
    assert entry.video_codec == "h264"
    assert entry.staging_output_path == Path(
        "/tmp/staging/Demo Show/Season 1/Demo Show S01E01.mp4"
    )
    assert entry.library_output_path == Path(
        "/tmp/library/Demo Show/Season 1/Demo Show S01E01.mp4"
    )
    assert entry.backup_path == Path(
        "/tmp/backups/Demo Show/Season 1/Demo Show S01E01.mkv"
    )
    assert entry.strategy_note.startswith("Copy video/audio into MP4")
    assert entry.requires_jellyfin_refresh is True


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


def test_summarize_preprocess_entries_reports_series_and_refresh_counts():
    media = _media("Demo Show/Season 1/Demo Show S01E01.mkv", title="Demo Show")
    report = _report(media, "subtitles_to_webvtt__then__remux_to_mp4_or_fmp4")

    entries = build_preprocess_entries(
        report,
        library_root=Path("/tmp/library"),
        resolver=_Resolver(),
        staging_root=Path("/tmp/staging"),
        backup_root=Path("/tmp/backups"),
    )

    summary = summarize_preprocess_entries(entries)

    assert summary["total"] == 1
    assert summary["strategy_counts"] == {"mp4_text_remux": 1}
    assert summary["title_counts"] == {"Demo Show": 1}
    assert (
        summary["queue_counts"]
        == {"subtitles_to_webvtt__then__remux_to_mp4_or_fmp4": 1}
    )
    assert summary["requires_jellyfin_refresh_count"] == 1


def test_filter_preprocess_decisions_applies_title_filter_before_probe():
    keep = _decision(_media("Demo Show/Season 1/Demo Show S01E01.mkv", title="Keep Show"))
    skip = _decision(_media("Demo Show/Season 1/Demo Show S01E02.mkv", title="Skip Show"))

    filtered = filter_preprocess_decisions(
        [keep, skip],
        title_filters={"Keep Show"},
    )

    assert filtered == [keep]


def test_run_preprocess_entry_tags_hevc_outputs_as_hvc1(tmp_path, monkeypatch):
    source_path = tmp_path / "source.mkv"
    source_path.write_bytes(b"demo")
    output_path = tmp_path / "out.mp4"

    entry = PreprocessEntry(
        title="Demo Show",
        season=1,
        episode=1,
        queue_key="remux_to_mp4_or_fmp4__then__verify_hevc_on_target_devices",
        strategy="mp4_text_remux",
        video_codec="hevc",
        source_path=source_path,
        staging_output_path=output_path,
        library_output_path=output_path,
        backup_path=tmp_path / "backup.mkv",
        actions=["remux_to_mp4_or_fmp4", "verify_hevc_on_target_devices"],
        note="demo",
        strategy_note="demo",
        requires_jellyfin_refresh=True,
    )

    recorded: dict[str, list[str]] = {}

    def fake_run(command, check):
        recorded["command"] = command
        recorded["check"] = check

    monkeypatch.setattr("anime_postprocessor.preprocess.subprocess.run", fake_run)

    _run_preprocess_entry(entry, ffmpeg_bin="ffmpeg")

    assert recorded["check"] is True
    assert "-tag:v" in recorded["command"]
    tag_index = recorded["command"].index("-tag:v")
    assert recorded["command"][tag_index + 1] == "hvc1"


def test_apply_preprocess_entries_marks_series_scoped_jellyfin_refresh_on_replace(
    tmp_path,
    monkeypatch,
):
    source_path = tmp_path / "Demo Show/Season 1/Demo Show S01E01.mkv"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"original")

    output_path = tmp_path / "library/Demo Show/Season 1/Demo Show S01E01.mp4"
    backup_path = tmp_path / "backups/Demo Show/Season 1/Demo Show S01E01.mkv"

    entry = PreprocessEntry(
        title="Demo Show",
        season=1,
        episode=1,
        queue_key="subtitles_to_webvtt__then__remux_to_mp4_or_fmp4",
        strategy="mp4_text_remux",
        video_codec="h264",
        source_path=source_path,
        staging_output_path=tmp_path / "staging/Demo Show/Season 1/Demo Show S01E01.mp4",
        library_output_path=output_path,
        backup_path=backup_path,
        actions=["convert_subtitles_to_webvtt", "remux_to_mp4_or_fmp4"],
        note="demo",
        strategy_note="demo",
        requires_jellyfin_refresh=True,
    )

    def fake_run_preprocess_entry(materialized_entry, *, ffmpeg_bin):
        assert materialized_entry == entry
        assert ffmpeg_bin == "ffmpeg"
        materialized_entry.staging_output_path.parent.mkdir(parents=True, exist_ok=True)
        materialized_entry.staging_output_path.write_bytes(b"processed")

    monkeypatch.setattr(
        "anime_postprocessor.preprocess._run_preprocess_entry",
        fake_run_preprocess_entry,
    )

    result = apply_preprocess_entries(
        [entry],
        ffmpeg_bin="ffmpeg",
        replace_library=True,
    )

    assert result["processed"][0]["replaced_library"] is True
    assert result["processed"][0]["jellyfin_refresh_path"] == str(tmp_path / "library/Demo Show")
    assert result["processed"][0]["jellyfin_refresh_update_type"] == "Modified"
