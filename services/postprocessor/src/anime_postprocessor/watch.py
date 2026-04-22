from __future__ import annotations

import os
import shutil
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

from .eventlog import append_event
from .models import EpisodeKey, ParsedMedia, UnparsedMedia
from .parser import parse_media_file
from .preprocess import summarize_preprocess_entries
from .publisher import (
    apply_publish_plan,
    build_publish_plan,
    build_publish_preprocess_entries,
)
from .qb import QBClient, QBTorrent
from .scanner import build_report
from .selector import score_candidate


@dataclass(frozen=True)
class GroupEntry:
    torrent: QBTorrent
    content_root: Path
    media_paths: list[Path]
    parsed_files: list[ParsedMedia]
    unparsed_files: list[UnparsedMedia]


@dataclass(frozen=True)
class UnparsedEntry:
    torrent: QBTorrent
    content_root: Path
    media_paths: list[Path]
    unparsed_files: list[UnparsedMedia]


@dataclass(frozen=True)
class TorrentLocalPaths:
    content_root: Path
    media_paths: list[Path]


def _map_qb_path(path: str, qb_root: Path, local_root: Path) -> Path:
    source = Path(path)
    if str(source).startswith(str(qb_root)):
        relative = source.relative_to(qb_root)
        return local_root / relative
    return local_root / source.name


def _torrent_media_paths(
    torrent: QBTorrent,
    qb: QBClient,
    qb_download_root: Path,
    local_download_root: Path,
) -> TorrentLocalPaths:
    files = qb.torrent_files(torrent.torrent_hash)
    mapped_content_path = _map_qb_path(
        torrent.content_path,
        qb_root=qb_download_root,
        local_root=local_download_root,
    )
    if len(files) == 1 and mapped_content_path.suffix:
        return TorrentLocalPaths(
            content_root=mapped_content_path,
            media_paths=[mapped_content_path],
        )

    base_dir = mapped_content_path if not mapped_content_path.suffix else mapped_content_path.parent
    return TorrentLocalPaths(
        content_root=base_dir,
        media_paths=[base_dir / Path(item["name"]) for item in files],
    )


def _build_groups(
    torrents: list[QBTorrent],
    qb: QBClient,
    *,
    qb_download_root: Path,
    local_download_root: Path,
) -> tuple[dict[EpisodeKey, list[GroupEntry]], list[UnparsedEntry]]:
    groups: dict[EpisodeKey, list[GroupEntry]] = {}
    completed_unparsed: list[UnparsedEntry] = []

    for torrent in torrents:
        torrent_paths = _torrent_media_paths(
            torrent,
            qb,
            qb_download_root=qb_download_root,
            local_download_root=local_download_root,
        )
        parsed_in_torrent: list[ParsedMedia] = []
        unparsed_in_torrent: list[UnparsedMedia] = []

        for media_path in torrent_paths.media_paths:
            parsed = parse_media_file(root=local_download_root, path=media_path)
            if isinstance(parsed, UnparsedMedia):
                unparsed_in_torrent.append(parsed)
            else:
                parsed_in_torrent.append(parsed)

        if not parsed_in_torrent:
            if torrent.completed and unparsed_in_torrent:
                completed_unparsed.append(
                    UnparsedEntry(
                        torrent=torrent,
                        content_root=torrent_paths.content_root,
                        media_paths=torrent_paths.media_paths,
                        unparsed_files=unparsed_in_torrent,
                    )
                )
            continue

        keys = {item.key for item in parsed_in_torrent}
        for key in keys:
            groups.setdefault(key, []).append(
                GroupEntry(
                    torrent=torrent,
                    content_root=torrent_paths.content_root,
                    media_paths=torrent_paths.media_paths,
                    parsed_files=[item for item in parsed_in_torrent if item.key == key],
                    unparsed_files=unparsed_in_torrent,
                )
            )

    return groups, completed_unparsed

def _top_score(parsed_files: list[ParsedMedia]) -> tuple[int, int, int, int] | None:
    if not parsed_files:
        return None
    return max(score_candidate(item).tuple for item in parsed_files)


def _first_completion_ts(entries: list[GroupEntry]) -> int | None:
    timestamps = [
        entry.torrent.completion_ts
        for entry in entries
        if entry.torrent.completed and entry.torrent.completion_ts is not None
    ]
    if not timestamps:
        return None
    return min(timestamps)


def _should_process_group(
    *,
    state: list[GroupEntry],
    completed_entries: list[GroupEntry],
    now_ts: int,
    wait_timeout: int,
) -> tuple[bool, str]:
    all_parsed = [item for entry in state for item in entry.parsed_files]
    completed_parsed = [item for entry in completed_entries for item in entry.parsed_files]
    if not completed_parsed:
        return False, "no completed candidates"

    overall_top = _top_score(all_parsed)
    completed_top = _top_score(completed_parsed)
    if overall_top is not None and completed_top == overall_top:
        return True, "best candidate already completed"

    if len(completed_entries) == len(state):
        return True, "all candidates completed"

    first_completion_ts = _first_completion_ts(completed_entries)
    if first_completion_ts is None:
        return False, "waiting for completion timestamp"

    elapsed = now_ts - first_completion_ts
    if elapsed >= wait_timeout:
        return True, f"wait timeout reached ({elapsed}s)"

    return False, f"waiting for higher-priority candidates ({elapsed}s/{wait_timeout}s)"


def _run_once(
    *,
    qb: QBClient,
    category: str,
    qb_download_root: Path,
    local_download_root: Path,
    library_root: Path,
    review_root: Path,
    staging_root: Path,
    backup_root: Path,
    ffprobe_bin: str,
    ffmpeg_bin: str,
    target_profile: str,
    delete_losers: bool,
    wait_timeout: int,
) -> None:
    torrents = qb.list_torrents(category=category)
    groups, completed_unparsed = _build_groups(
        torrents,
        qb,
        qb_download_root=qb_download_root,
        local_download_root=local_download_root,
    )
    review_root.mkdir(parents=True, exist_ok=True)
    now_ts = int(time.time())

    for key, state in sorted(
        groups.items(),
        key=lambda item: (
            item[0].normalized_title,
            item[0].season,
            item[0].episode,
        ),
    ):
        completed_entries = [entry for entry in state if entry.torrent.completed]
        should_process, reason = _should_process_group(
            state=state,
            completed_entries=completed_entries,
            now_ts=now_ts,
            wait_timeout=wait_timeout,
        )
        if not should_process:
            if completed_entries:
                print(
                    f"[watch] defer {key.normalized_title} "
                    f"S{key.season:02d}E{key.episode:02d}: {reason}"
                )
            continue

        try:
            report = build_report(
                root=local_download_root,
                parsed_files=[
                    item
                    for entry in completed_entries
                    for item in entry.parsed_files
                    if item.path.exists()
                ],
                unparsed_files=[
                    item
                    for entry in completed_entries
                    for item in entry.unparsed_files
                    if item.path.exists()
                ],
            )
            if not report.parsed_files:
                continue
            plan = build_publish_plan(
                report=report,
                download_root=local_download_root,
                library_root=library_root,
                review_root=review_root,
            )
            preprocess_entries = build_publish_preprocess_entries(
                plan,
                staging_root=staging_root,
                backup_root=backup_root,
                ffprobe_bin=ffprobe_bin,
                target_profile=target_profile,
            )
            preprocess_summary = summarize_preprocess_entries(preprocess_entries)
            hashes = sorted({entry.torrent.torrent_hash for entry in state})
            qb.pause(hashes)
            qb.delete(hashes, delete_files=False)
            result = apply_publish_plan(
                plan,
                delete_losers=delete_losers,
                move_unparsed_to_review=True,
                preprocess_entries=preprocess_entries,
                ffmpeg_bin=ffmpeg_bin,
            )
            print(
                f"[watch] processed {key.normalized_title} "
                f"S{key.season:02d}E{key.episode:02d}: "
                f"reason={reason}; "
                f"preprocessed={preprocess_summary['total']} "
                f"published={len(result['published'])} "
                f"deleted={len(result['deleted'])} "
                f"reviewed={len(result['reviewed'])}"
            )
            append_event(
                source="postprocessor",
                level="success",
                action="watch-process-group",
                message=(
                    f"Processed {key.normalized_title} "
                    f"S{key.season:02d}E{key.episode:02d}"
                ),
                details={
                    "reason": reason,
                    "preprocess_summary": preprocess_summary,
                    "preprocessed": result["preprocessed"],
                    "jellyfin_background_tasks_expected": preprocess_summary["total"] > 0,
                    "published": len(result["published"]),
                    "deleted": len(result["deleted"]),
                    "reviewed": len(result["reviewed"]),
                    "winner_targets": [item["target"] for item in result["published"]],
                },
            )
        except Exception as exc:
            print(
                f"[watch] error processing {key.normalized_title} "
                f"S{key.season:02d}E{key.episode:02d}: {exc}"
            )
            append_event(
                source="postprocessor",
                level="error",
                action="watch-process-group",
                message=(
                    f"Failed to process {key.normalized_title} "
                    f"S{key.season:02d}E{key.episode:02d}"
                ),
                details={
                    "error": str(exc),
                },
            )
            traceback.print_exc()

    for entry in completed_unparsed:
        try:
            hashes = [entry.torrent.torrent_hash]
            qb.pause(hashes)
            qb.delete(hashes, delete_files=False)
            report = build_report(
                root=local_download_root,
                parsed_files=[],
                unparsed_files=[item for item in entry.unparsed_files if item.path.exists()],
            )
            plan = build_publish_plan(
                report=report,
                download_root=local_download_root,
                library_root=library_root,
                review_root=review_root,
            )
            result = apply_publish_plan(
                plan,
                delete_losers=delete_losers,
                move_unparsed_to_review=True,
            )
            print(
                f"[watch] moved unparsed torrent to review: {entry.torrent.name} "
                f"reviewed={len(result['reviewed'])}"
            )
            append_event(
                source="postprocessor",
                level="warning",
                action="watch-unparsed-to-review",
                message=f"Moved unparsed torrent to manual review: {entry.torrent.name}",
                details={
                    "reviewed": len(result["reviewed"]),
                },
            )
        except Exception as exc:
            print(f"[watch] error moving unparsed torrent {entry.torrent.name}: {exc}")
            append_event(
                source="postprocessor",
                level="error",
                action="watch-unparsed-to-review",
                message=f"Failed to move unparsed torrent to manual review: {entry.torrent.name}",
                details={
                    "error": str(exc),
                },
            )
            traceback.print_exc()


def watch_loop(
    *,
    qb_api_url: str,
    qb_username: str,
    qb_password: str,
    category: str,
    qb_download_root: Path,
    local_download_root: Path,
    library_root: Path,
    review_root: Path,
    staging_root: Path,
    backup_root: Path,
    ffprobe_bin: str,
    ffmpeg_bin: str,
    target_profile: str,
    poll_interval: int,
    delete_losers: bool,
    wait_timeout: int,
    once: bool,
) -> None:
    qb = QBClient(qb_api_url, qb_username, qb_password)
    qb.auth()
    append_event(
        source="postprocessor",
        level="info",
        action="watch-start",
        message="Postprocessor watch loop started",
        details={
            "category": category,
            "poll_interval": poll_interval,
            "wait_timeout": wait_timeout,
            "delete_losers": delete_losers,
            "once": once,
            "target_profile": target_profile,
            "staging_root": str(staging_root),
            "backup_root": str(backup_root),
        },
    )
    while True:
        _run_once(
            qb=qb,
            category=category,
            qb_download_root=qb_download_root,
            local_download_root=local_download_root,
            library_root=library_root,
            review_root=review_root,
            staging_root=staging_root,
            backup_root=backup_root,
            ffprobe_bin=ffprobe_bin,
            ffmpeg_bin=ffmpeg_bin,
            target_profile=target_profile,
            delete_losers=delete_losers,
            wait_timeout=wait_timeout,
        )
        if once:
            return
        time.sleep(poll_interval)


def watch_from_env(
    *,
    anime_data_root: Path,
    source_root: Path,
    target_root: Path,
    review_root: Path,
    once: bool = False,
    poll_interval: int | None = None,
    delete_losers: bool | None = None,
    wait_timeout: int | None = None,
) -> None:
    qb_api_url = os.environ.get("QBITTORRENT_API_URL", "http://qbittorrent:8080")
    qb_username = os.environ["QBITTORRENT_USERNAME"]
    qb_password = os.environ["QBITTORRENT_PASSWORD"]
    category = os.environ.get("POSTPROCESSOR_CATEGORY", "Bangumi")
    qb_download_root = Path(
        os.environ.get("QBITTORRENT_DOWNLOAD_ROOT", "/downloads/Bangumi")
    )
    interval = poll_interval or int(os.environ.get("POSTPROCESSOR_POLL_INTERVAL", "60"))
    settle_timeout = wait_timeout or int(
        os.environ.get("POSTPROCESSOR_WAIT_TIMEOUT", "1800")
    )
    staging_root = Path(
        os.environ.get(
            "ANIME_PREPROCESS_ROOT",
            anime_data_root / "processing" / "ios_preprocess",
        )
    )
    backup_root = Path(
        os.environ.get(
            "ANIME_PREPROCESS_BACKUP_ROOT",
            anime_data_root / "processing" / "ios_preprocess_backups",
        )
    )
    ffprobe_bin = os.environ.get("POSTPROCESSOR_FFPROBE_BIN", "ffprobe")
    ffmpeg_bin = os.environ.get("POSTPROCESSOR_FFMPEG_BIN", "ffmpeg")
    target_profile = os.environ.get("POSTPROCESSOR_TARGET_PROFILE", "personal_modern_apple")

    missing_tools = [
        name for name in (ffprobe_bin, ffmpeg_bin)
        if shutil.which(name) is None
    ]
    if missing_tools:
        append_event(
            source="postprocessor",
            level="error",
            action="watch-missing-runtime-tools",
            message="Postprocessor runtime is missing required media tools",
            details={
                "missing_tools": missing_tools,
                "ffprobe_bin": ffprobe_bin,
                "ffmpeg_bin": ffmpeg_bin,
            },
        )
        raise RuntimeError(
            f"missing required runtime tools: {', '.join(missing_tools)}"
        )

    delete = (
        delete_losers
        if delete_losers is not None
        else os.environ.get("POSTPROCESSOR_DELETE_LOSERS", "true").lower()
        in {"1", "true", "yes", "on"}
    )
    watch_loop(
        qb_api_url=qb_api_url,
        qb_username=qb_username,
        qb_password=qb_password,
        category=category,
        qb_download_root=qb_download_root,
        local_download_root=source_root,
        library_root=target_root,
        review_root=review_root,
        staging_root=staging_root,
        backup_root=backup_root,
        ffprobe_bin=ffprobe_bin,
        ffmpeg_bin=ffmpeg_bin,
        target_profile=target_profile,
        poll_interval=interval,
        delete_losers=delete,
        wait_timeout=settle_timeout,
        once=once,
    )
