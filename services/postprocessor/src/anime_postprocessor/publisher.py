from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .models import ParsedMedia, UnparsedMedia
from .scanner import ScanReport
from .selector import SelectionDecision, build_selection_plan


@dataclass(frozen=True)
class PublishPlan:
    report: ScanReport
    decisions: list[SelectionDecision]
    download_root: Path
    library_root: Path
    review_root: Path


def _derive_show_name(media: ParsedMedia) -> str:
    parts = media.relative_path.parts
    if len(parts) >= 2 and parts[1].lower().startswith("season "):
        return parts[0]
    if len(parts) >= 2:
        return parts[0]
    return media.title


def build_target_path(library_root: Path, media: ParsedMedia) -> Path:
    show_name = _derive_show_name(media)
    season_folder = f"Season {media.season}"
    target_name = f"{show_name} S{media.season:02d}E{media.episode:02d}{media.extension}"
    return library_root / show_name / season_folder / target_name


def build_publish_plan(
    report: ScanReport,
    download_root: Path,
    library_root: Path,
    review_root: Path,
) -> PublishPlan:
    return PublishPlan(
        report=report,
        decisions=build_selection_plan(report.parsed_files),
        download_root=download_root,
        library_root=library_root,
        review_root=review_root,
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
) -> dict:
    published: list[dict] = []
    deleted: list[str] = []
    reviewed: list[dict] = []

    for decision in plan.decisions:
        target = build_target_path(plan.library_root, decision.winner)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(decision.winner.path), str(target))
        _cleanup_empty_dirs(decision.winner.path.parent, plan.download_root)
        published.append(
            {
                "source": str(decision.winner.relative_path),
                "target": str(target),
                "score": decision.winner_score.summary,
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
    }
