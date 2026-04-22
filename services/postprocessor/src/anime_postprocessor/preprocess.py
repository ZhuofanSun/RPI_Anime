from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .compatibility import CompatibilityReport
from .publisher import build_target_path


@dataclass(frozen=True)
class PreprocessEntry:
    title: str
    season: int
    episode: int
    queue_key: str
    strategy: str
    source_path: Path
    staging_output_path: Path
    library_output_path: Path
    backup_path: Path
    actions: list[str]
    note: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "season": self.season,
            "episode": self.episode,
            "queue_key": self.queue_key,
            "strategy": self.strategy,
            "source_path": str(self.source_path),
            "staging_output_path": str(self.staging_output_path),
            "library_output_path": str(self.library_output_path),
            "backup_path": str(self.backup_path),
            "actions": self.actions,
            "note": self.note,
        }


def _select_strategy(queue_key: str) -> str | None:
    if queue_key in {
        "subtitles_to_webvtt__then__remux_to_mp4_or_fmp4",
        "subtitles_to_webvtt__then__remux_to_mp4_or_fmp4__then__verify_hevc_on_target_devices",
        "remux_to_mp4_or_fmp4__then__verify_hevc_on_target_devices",
    }:
        return "mp4_text_remux"
    return None


def build_preprocess_entries(
    compatibility: CompatibilityReport,
    *,
    library_root: Path,
    resolver,
    staging_root: Path,
    backup_root: Path,
    queue_filters: set[str] | None = None,
    title_filters: set[str] | None = None,
    limit: int | None = None,
) -> list[PreprocessEntry]:
    entries: list[PreprocessEntry] = []
    normalized_title_filters = {value.casefold() for value in title_filters or set()}

    for item in compatibility.decisions:
        queue = item.assessment.action_queue
        strategy = _select_strategy(queue.key)
        if strategy is None:
            continue
        if queue_filters and queue.key not in queue_filters:
            continue
        if normalized_title_filters and item.decision.winner.title.casefold() not in normalized_title_filters:
            continue

        library_target = build_target_path(
            library_root,
            item.decision.winner,
            resolver=resolver,
        ).with_suffix(".mp4")
        staging_output = staging_root / library_target.relative_to(library_root)
        backup_path = backup_root / item.decision.winner.relative_path

        entries.append(
            PreprocessEntry(
                title=item.decision.winner.title,
                season=item.decision.winner.season,
                episode=item.decision.winner.episode,
                queue_key=queue.key,
                strategy=strategy,
                source_path=item.decision.winner.path,
                staging_output_path=staging_output,
                library_output_path=library_target,
                backup_path=backup_path,
                actions=item.assessment.suggested_actions,
                note=queue.note,
            )
        )

    entries.sort(key=lambda entry: (entry.title, entry.season, entry.episode))
    if limit is not None:
        return entries[:limit]
    return entries


def apply_preprocess_entries(
    entries: list[PreprocessEntry],
    *,
    ffmpeg_bin: str = "ffmpeg",
    replace_library: bool = False,
) -> dict:
    completed: list[dict] = []

    for entry in entries:
        _run_preprocess_entry(entry, ffmpeg_bin=ffmpeg_bin)
        result = entry.to_dict()
        if replace_library:
            result.update(_replace_library_source(entry))
        completed.append(result)

    return {
        "processed": completed,
    }


def _run_preprocess_entry(entry: PreprocessEntry, *, ffmpeg_bin: str) -> None:
    entry.staging_output_path.parent.mkdir(parents=True, exist_ok=True)
    if entry.staging_output_path.exists():
        entry.staging_output_path.unlink()

    if entry.strategy != "mp4_text_remux":
        raise ValueError(f"unsupported preprocess strategy: {entry.strategy}")

    command = [
        ffmpeg_bin,
        "-y",
        "-v",
        "error",
        "-i",
        str(entry.source_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-map",
        "0:s?",
        "-map_metadata",
        "0",
        "-map_chapters",
        "0",
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        "-c:s",
        "mov_text",
        "-movflags",
        "+faststart",
        str(entry.staging_output_path),
    ]
    subprocess.run(command, check=True)


def _replace_library_source(entry: PreprocessEntry) -> dict:
    entry.backup_path.parent.mkdir(parents=True, exist_ok=True)
    if entry.backup_path.exists():
        raise FileExistsError(f"backup already exists: {entry.backup_path}")
    shutil.move(str(entry.source_path), str(entry.backup_path))

    entry.library_output_path.parent.mkdir(parents=True, exist_ok=True)
    if entry.library_output_path.exists():
        entry.library_output_path.unlink()
    shutil.move(str(entry.staging_output_path), str(entry.library_output_path))

    return {
        "replaced_library": True,
        "backup_path": str(entry.backup_path),
        "library_output_path": str(entry.library_output_path),
    }
