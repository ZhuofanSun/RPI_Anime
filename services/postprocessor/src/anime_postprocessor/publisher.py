from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .models import ParsedMedia, UnparsedMedia
from .scanner import ScanReport
from .selector import SelectionDecision, build_selection_plan
from .title_map import ResolvedSeries, TitleMapResolver, load_title_map

if TYPE_CHECKING:
    from .preprocess import PreprocessEntry


@dataclass(frozen=True)
class PublishPlan:
    report: ScanReport
    decisions: list[SelectionDecision]
    download_root: Path
    library_root: Path
    review_root: Path
    resolver: TitleMapResolver


def resolve_series(media: ParsedMedia, resolver: TitleMapResolver | None = None) -> ResolvedSeries:
    active_resolver = resolver or load_title_map()
    return active_resolver.resolve(media)


def build_target_path(
    library_root: Path,
    media: ParsedMedia,
    resolver: TitleMapResolver | None = None,
) -> Path:
    series = resolve_series(media, resolver=resolver)
    season_folder = f"Season {series.season_number}"
    target_name = (
        f"{series.folder_name} "
        f"S{series.season_number:02d}E{series.episode_number:02d}{media.extension}"
    )
    return library_root / series.folder_name / season_folder / target_name


def build_series_folder_path(
    library_root: Path,
    media: ParsedMedia,
    resolver: TitleMapResolver | None = None,
) -> Path:
    series = resolve_series(media, resolver=resolver)
    return library_root / series.folder_name


def _write_tvshow_nfo(show_dir: Path, series: ResolvedSeries) -> Path:
    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = series.series_title
    if series.original_title:
        ET.SubElement(root, "originaltitle").text = series.original_title
    ET.SubElement(root, "sorttitle").text = series.series_title
    for provider_name, provider_value in series.provider_ids.items():
        ET.SubElement(root, provider_name).text = provider_value

    tree = ET.ElementTree(root)
    nfo_path = show_dir / "tvshow.nfo"
    tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
    return nfo_path


def _write_episode_nfo(
    episode_path: Path,
    *,
    series: ResolvedSeries,
    episode_title: str,
) -> Path:
    root = ET.Element("episodedetails")
    ET.SubElement(root, "title").text = episode_title
    ET.SubElement(root, "showtitle").text = series.series_title
    ET.SubElement(root, "season").text = str(series.season_number)
    ET.SubElement(root, "episode").text = str(series.episode_number)
    if series.original_title:
        ET.SubElement(root, "originaltitle").text = series.original_title

    tree = ET.ElementTree(root)
    nfo_path = episode_path.with_suffix(".nfo")
    tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
    return nfo_path


def write_library_nfo(
    library_root: Path,
    parsed_files: list[ParsedMedia],
    resolver: TitleMapResolver | None = None,
) -> list[dict]:
    active_resolver = resolver or load_title_map()
    written: dict[Path, Path] = {}

    for media in parsed_files:
        series = resolve_series(media, resolver=active_resolver)
        if not series.has_mapping:
            continue
        show_dir = library_root / media.relative_path.parts[0]
        show_dir.mkdir(parents=True, exist_ok=True)
        nfo_path = _write_tvshow_nfo(show_dir, series)
        written[show_dir] = nfo_path
        if media.path.exists():
            _write_episode_nfo(
                media.path,
                series=series,
                episode_title=media.path.stem,
            )

    return [
        {"show_dir": str(show_dir), "nfo": str(nfo_path)}
        for show_dir, nfo_path in sorted(written.items())
    ]


def build_publish_plan(
    report: ScanReport,
    download_root: Path,
    library_root: Path,
    review_root: Path,
) -> PublishPlan:
    resolver = load_title_map()
    return PublishPlan(
        report=report,
        decisions=build_selection_plan(report.parsed_files),
        download_root=download_root,
        library_root=library_root,
        review_root=review_root,
        resolver=resolver,
    )


def build_publish_preprocess_entries(
    plan: PublishPlan,
    *,
    staging_root: Path,
    backup_root: Path,
    ffprobe_bin: str = "ffprobe",
    target_profile: str = "personal_modern_apple",
) -> list["PreprocessEntry"]:
    from .compatibility import build_compatibility_report
    from .preprocess import build_preprocess_entries

    compatibility = build_compatibility_report(
        plan.decisions,
        ffprobe_bin=ffprobe_bin,
        target_profile=target_profile,
    )
    return build_preprocess_entries(
        compatibility,
        library_root=plan.library_root,
        resolver=plan.resolver,
        staging_root=staging_root,
        backup_root=backup_root,
    )


def _cleanup_empty_dirs(path: Path, stop_at: Path) -> None:
    current = path
    while current != stop_at and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _move_to_review(item: UnparsedMedia, review_root: Path, base_dir: Path) -> Path:
    target = review_root / "unparsed" / item.relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(item.path), str(target))
    _cleanup_empty_dirs(item.path.parent, base_dir)
    return target


def apply_publish_plan(
    plan: PublishPlan,
    *,
    delete_losers: bool = False,
    move_unparsed_to_review: bool = True,
    preprocess_entries: list["PreprocessEntry"] | None = None,
    ffmpeg_bin: str = "ffmpeg",
) -> dict:
    from .preprocess import run_preprocess_entry

    published: list[dict] = []
    deleted: list[str] = []
    reviewed: list[dict] = []
    preprocessed: list[dict] = []
    preprocess_by_source = {
        str(entry.source_path): entry for entry in (preprocess_entries or [])
    }

    for decision in plan.decisions:
        preprocess_entry = preprocess_by_source.get(str(decision.winner.path))
        target = (
            preprocess_entry.library_output_path
            if preprocess_entry is not None
            else build_target_path(plan.library_root, decision.winner, resolver=plan.resolver)
        )
        show_dir = build_series_folder_path(
            plan.library_root,
            decision.winner,
            resolver=plan.resolver,
        )
        show_dir_preexisting = show_dir.exists()
        if target.exists():
            raise FileExistsError(f"target already exists: {target}")

        target.parent.mkdir(parents=True, exist_ok=True)
        preprocess_details: dict | None = None

        if preprocess_entry is not None:
            run_preprocess_entry(preprocess_entry, ffmpeg_bin=ffmpeg_bin)
            if preprocess_entry.backup_path.exists():
                raise FileExistsError(f"backup already exists: {preprocess_entry.backup_path}")
            preprocess_entry.backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(preprocess_entry.source_path), str(preprocess_entry.backup_path))
            _cleanup_empty_dirs(preprocess_entry.source_path.parent, plan.download_root)
            shutil.move(str(preprocess_entry.staging_output_path), str(target))
            preprocess_details = {
                "strategy": preprocess_entry.strategy,
                "queue_key": preprocess_entry.queue_key,
                "video_codec": preprocess_entry.video_codec,
                "backup": str(preprocess_entry.backup_path),
                "note": preprocess_entry.note,
                "strategy_note": preprocess_entry.strategy_note,
            }
            preprocessed.append(
                {
                    "source": str(decision.winner.relative_path),
                    "target": str(target),
                    **preprocess_details,
                }
            )
        else:
            shutil.move(str(decision.winner.path), str(target))
            _cleanup_empty_dirs(decision.winner.path.parent, plan.download_root)

        series = resolve_series(decision.winner, resolver=plan.resolver)
        show_dir.mkdir(parents=True, exist_ok=True)
        nfo_path = _write_tvshow_nfo(show_dir, series)
        episode_nfo_path = _write_episode_nfo(
            target,
            series=series,
            episode_title=decision.winner.path.stem,
        )
        published.append(
            {
                "source": str(decision.winner.relative_path),
                "target": str(target),
                "score": decision.winner_score.summary,
                "nfo": str(nfo_path),
                "episode_nfo": str(episode_nfo_path),
                "preprocess": preprocess_details,
                "jellyfin_refresh_path": str(show_dir),
                "jellyfin_refresh_update_type": (
                    "Modified" if show_dir_preexisting else "Created"
                ),
            }
        )

        if delete_losers:
            for loser in decision.losers:
                if loser.path.exists():
                    loser.path.unlink()
                    _cleanup_empty_dirs(loser.path.parent, plan.download_root)
                    deleted.append(str(loser.relative_path))

    if move_unparsed_to_review:
        for item in plan.report.unparsed_files:
            if item.path.exists():
                target = _move_to_review(item, plan.review_root, plan.download_root)
                reviewed.append(
                    {
                        "source": str(item.relative_path),
                        "target": str(target),
                        "reason": item.reason,
                    }
                )

    return {
        "published": published,
        "deleted": deleted,
        "reviewed": reviewed,
        "preprocessed": preprocessed,
    }


def publish_media(
    *,
    source_root: Path,
    library_root: Path,
    media: ParsedMedia,
    resolver: TitleMapResolver | None = None,
) -> dict:
    active_resolver = resolver or load_title_map()
    target = build_target_path(
        library_root,
        media,
        resolver=active_resolver,
    )
    if target.exists():
        raise FileExistsError(f"target already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(media.path), str(target))
    _cleanup_empty_dirs(media.path.parent, source_root)

    series = resolve_series(media, resolver=active_resolver)
    show_dir = build_series_folder_path(
        library_root,
        media,
        resolver=active_resolver,
    )
    show_dir.mkdir(parents=True, exist_ok=True)
    nfo_path = _write_tvshow_nfo(show_dir, series)
    episode_nfo_path = _write_episode_nfo(
        target,
        series=series,
        episode_title=media.path.stem,
    )
    return {
        "source": str(media.relative_path),
        "target": str(target),
        "score": None,
        "nfo": str(nfo_path),
        "episode_nfo": str(episode_nfo_path),
    }
