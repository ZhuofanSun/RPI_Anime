from pathlib import Path

from anime_postprocessor.models import ParsedMedia
from anime_postprocessor.publisher import apply_publish_plan, build_publish_plan
from anime_postprocessor.preprocess import PreprocessEntry
from anime_postprocessor.scanner import build_report


def _parsed_media(source_root: Path) -> ParsedMedia:
    relative_path = Path("Demo Show/Season 1/Demo Show S01E01.mkv")
    path = source_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"original-media")
    return ParsedMedia(
        path=path,
        relative_path=relative_path,
        title="Demo Show",
        normalized_title="demo show",
        season=1,
        episode=1,
        extension=".mkv",
        release_group="demo",
    )


def test_apply_publish_plan_preprocesses_supported_winner_before_publish(tmp_path, monkeypatch):
    source_root = tmp_path / "downloads"
    library_root = tmp_path / "library"
    review_root = tmp_path / "review"
    staging_root = tmp_path / "staging"
    backup_root = tmp_path / "backups"

    media = _parsed_media(source_root)
    report = build_report(root=source_root, parsed_files=[media], unparsed_files=[])
    plan = build_publish_plan(
        report=report,
        download_root=source_root,
        library_root=library_root,
        review_root=review_root,
    )

    entry = PreprocessEntry(
        title="Demo Show",
        season=1,
        episode=1,
        queue_key="subtitles_to_webvtt__then__remux_to_mp4_or_fmp4__then__verify_hevc_on_target_devices",
        strategy="mp4_text_remux",
        video_codec="hevc",
        source_path=media.path,
        staging_output_path=staging_root / "Demo Show/Season 1/Demo Show S01E01.mp4",
        library_output_path=library_root / "Demo Show/Season 1/Demo Show S01E01.mp4",
        backup_path=backup_root / media.relative_path,
        actions=[
            "convert_subtitles_to_webvtt",
            "remux_to_mp4_or_fmp4",
            "verify_hevc_on_target_devices",
        ],
        note="demo note",
        strategy_note="demo strategy",
        requires_jellyfin_refresh=False,
    )

    def fake_run_preprocess_entry(materialized_entry, *, ffmpeg_bin):
        assert materialized_entry == entry
        assert ffmpeg_bin == "ffmpeg"
        materialized_entry.staging_output_path.parent.mkdir(parents=True, exist_ok=True)
        materialized_entry.staging_output_path.write_bytes(b"processed-media")

    monkeypatch.setattr(
        "anime_postprocessor.preprocess.run_preprocess_entry",
        fake_run_preprocess_entry,
    )

    result = apply_publish_plan(
        plan,
        preprocess_entries=[entry],
        ffmpeg_bin="ffmpeg",
    )

    published_target = library_root / "Demo Show/Season 1/Demo Show S01E01.mp4"
    assert published_target.exists()
    assert published_target.read_bytes() == b"processed-media"
    assert not media.path.exists()
    assert entry.backup_path.exists()
    assert entry.backup_path.read_bytes() == b"original-media"
    assert result["preprocessed"] == [
        {
            "source": "Demo Show/Season 1/Demo Show S01E01.mkv",
            "target": str(published_target),
            "strategy": "mp4_text_remux",
            "queue_key": entry.queue_key,
            "video_codec": "hevc",
            "backup": str(entry.backup_path),
            "note": "demo note",
            "strategy_note": "demo strategy",
        }
    ]
    assert result["published"][0]["target"] == str(published_target)
    assert result["published"][0]["preprocess"]["strategy"] == "mp4_text_remux"
    assert Path(result["published"][0]["nfo"]).exists()
    assert Path(result["published"][0]["episode_nfo"]).exists()
    assert result["published"][0]["jellyfin_refresh_path"] == str(library_root / "Demo Show")
    assert result["published"][0]["jellyfin_refresh_update_type"] == "Created"
