from pathlib import Path

from anime_postprocessor.compatibility import (
    CompatibilityAssessment,
    MediaProbe,
    build_compatibility_report,
    classify_media_for_ios,
)
from anime_postprocessor.models import EpisodeKey, ParsedMedia
from anime_postprocessor.selector import CandidateScore, SelectionDecision


def _media(path: str) -> ParsedMedia:
    relative_path = Path(path)
    return ParsedMedia(
        path=Path("/tmp/downloads") / relative_path,
        relative_path=relative_path,
        title="Demo Show",
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


def _probe(
    path: Path,
    *,
    container: str,
    video_codec: str,
    video_profile: str,
    pixel_format: str,
    bit_depth: int | None,
    audio_codecs: list[str],
    subtitle_codecs: list[str],
) -> MediaProbe:
    return MediaProbe(
        path=path,
        container=container,
        video_codec=video_codec,
        video_profile=video_profile,
        pixel_format=pixel_format,
        bit_depth=bit_depth,
        audio_codecs=audio_codecs,
        subtitle_codecs=subtitle_codecs,
        audio_track_count=len(audio_codecs),
        subtitle_track_count=len(subtitle_codecs),
    )


def test_classify_media_for_ios_marks_safe_h264_aac_mp4_as_green():
    media = _media("Show/Season 1/Demo Show S01E01.mp4")
    probe = _probe(
        media.path,
        container="mov",
        video_codec="h264",
        video_profile="High",
        pixel_format="yuv420p",
        bit_depth=8,
        audio_codecs=["aac"],
        subtitle_codecs=[],
    )

    assessment = classify_media_for_ios(media, probe)

    assert assessment.classification == "green"
    assert assessment.suggested_actions == ["publish_direct"]
    assert assessment.sync_risk == "low"
    assert assessment.quality_risk == "low"


def test_classify_media_for_ios_marks_mkv_ass_as_yellow():
    media = _media("Show/Season 1/Demo Show S01E01.mkv")
    probe = _probe(
        media.path,
        container="matroska",
        video_codec="h264",
        video_profile="High",
        pixel_format="yuv420p",
        bit_depth=8,
        audio_codecs=["aac"],
        subtitle_codecs=["ass"],
    )

    assessment = classify_media_for_ios(media, probe)

    assert assessment.classification == "yellow"
    assert "remux_to_mp4_or_fmp4" in assessment.suggested_actions
    assert "convert_subtitles_to_webvtt" in assessment.suggested_actions
    assert assessment.sync_risk == "medium"


def test_classify_media_for_ios_marks_hevc_opus_ass_as_yellow_without_video_transcode():
    media = _media("Show/Season 1/Demo Show S01E01.mkv")
    probe = _probe(
        media.path,
        container="matroska",
        video_codec="hevc",
        video_profile="Main 10",
        pixel_format="yuv420p10le",
        bit_depth=10,
        audio_codecs=["opus"],
        subtitle_codecs=["ass"],
    )

    assessment = classify_media_for_ios(media, probe)

    assert assessment.classification == "yellow"
    assert "offline_video_transcode" not in assessment.suggested_actions
    assert "device_gate_hevc_or_generate_h264_fallback" in assessment.suggested_actions
    assert "transcode_audio_to_aac" in assessment.suggested_actions
    assert "convert_subtitles_to_webvtt" in assessment.suggested_actions
    assert assessment.quality_risk == "medium"


def test_classify_media_for_ios_marks_image_subtitles_as_red():
    media = _media("Show/Season 1/Demo Show S01E01.mkv")
    probe = _probe(
        media.path,
        container="matroska",
        video_codec="hevc",
        video_profile="Main 10",
        pixel_format="yuv420p10le",
        bit_depth=10,
        audio_codecs=["ac3", "flac"],
        subtitle_codecs=["hdmv_pgs_subtitle"],
    )

    assessment = classify_media_for_ios(media, probe)

    assert assessment.classification == "red"
    assert "manual_review_image_subtitles" in assessment.suggested_actions
    assert assessment.sync_risk == "high"


def test_build_compatibility_report_summarizes_classification_counts(monkeypatch):
    green_media = _media("Show/Season 1/Demo Show S01E01.mp4")
    yellow_media = _media("Show/Season 1/Demo Show S01E02.mkv")

    probe_by_path = {
        str(green_media.path): _probe(
            green_media.path,
            container="mov",
            video_codec="h264",
            video_profile="High",
            pixel_format="yuv420p",
            bit_depth=8,
            audio_codecs=["aac"],
            subtitle_codecs=[],
        ),
        str(yellow_media.path): _probe(
            yellow_media.path,
            container="matroska",
            video_codec="h264",
            video_profile="High",
            pixel_format="yuv420p",
            bit_depth=8,
            audio_codecs=["aac"],
            subtitle_codecs=["ass"],
        ),
    }

    def fake_probe(path: Path, *, ffprobe_bin: str = "ffprobe") -> MediaProbe:
        return probe_by_path[str(path)]

    monkeypatch.setattr(
        "anime_postprocessor.compatibility.probe_media",
        fake_probe,
    )

    report = build_compatibility_report(
        [_decision(green_media), _decision(yellow_media)],
    )

    assert report.summary == {
        "green": 1,
        "yellow": 1,
        "red": 0,
        "total": 2,
    }
    assert report.decisions[0].assessment.classification == "green"
    assert report.decisions[1].assessment.classification == "yellow"
