from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from .models import EpisodeKey, ParsedMedia, UnparsedMedia
from .parser import parse_media_file
from .publisher import apply_publish_plan, build_publish_plan
from .qb import QBClient, QBTorrent
from .scanner import build_report


@dataclass
class GroupState:
    torrents: list[QBTorrent]
    parsed_files: list[ParsedMedia]
    unparsed_files: list[UnparsedMedia]


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


def _cleanup_empty_dirs(path: Path, stop_at: Path) -> None:
    current = path
    while current != stop_at and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _cleanup_entry(entry: GroupEntry | UnparsedEntry, keep_paths: set[Path], stop_at: Path) -> None:
    content_root = entry.content_root

    if content_root.exists() and content_root.is_dir():
        if not any(_is_within(keep_path, content_root) for keep_path in keep_paths):
            shutil.rmtree(content_root, ignore_errors=True)
            _cleanup_empty_dirs(content_root.parent, stop_at)
            return

    for media_path in entry.media_paths:
        if media_path in keep_paths:
            continue
        if media_path.exists() and media_path.is_file():
            media_path.unlink()
            _cleanup_empty_dirs(media_path.parent, stop_at)

    for item in entry.unparsed_files:
        if item.path in keep_paths:
            continue
        if item.path.exists() and item.path.is_file():
            item.path.unlink()
            _cleanup_empty_dirs(item.path.parent, stop_at)


def _run_once(
    *,
    qb: QBClient,
    category: str,
    qb_download_root: Path,
    local_download_root: Path,
    library_root: Path,
    review_root: Path,
    delete_losers: bool,
) -> None:
    torrents = qb.list_torrents(category=category)
    groups, completed_unparsed = _build_groups(
        torrents,
        qb,
        qb_download_root=qb_download_root,
        local_download_root=local_download_root,
    )

    for key, state in sorted(
        groups.items(),
        key=lambda item: (
            item[0].normalized_title,
            item[0].season,
            item[0].episode,
        ),
    ):
        completed_entries = [entry for entry in state if entry.torrent.completed]
        if not completed_entries:
            continue

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
        hashes = sorted({entry.torrent.torrent_hash for entry in state})
        winner_paths = {decision.winner.path for decision in plan.decisions}
        qb.pause(hashes)
        qb.delete(hashes, delete_files=False)
        result = apply_publish_plan(
            plan,
            delete_losers=delete_losers,
            move_unparsed_to_review=True,
        )
        for entry in state:
            _cleanup_entry(entry, keep_paths=winner_paths, stop_at=local_download_root)
        print(
            f"[watch] processed {key.normalized_title} "
            f"S{key.season:02d}E{key.episode:02d}: "
            f"published={len(result['published'])} "
            f"deleted={len(result['deleted'])} "
            f"reviewed={len(result['reviewed'])}"
        )

    for entry in completed_unparsed:
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
    poll_interval: int,
    delete_losers: bool,
    once: bool,
) -> None:
    qb = QBClient(qb_api_url, qb_username, qb_password)
    qb.auth()
    while True:
        _run_once(
            qb=qb,
            category=category,
            qb_download_root=qb_download_root,
            local_download_root=local_download_root,
            library_root=library_root,
            review_root=review_root,
            delete_losers=delete_losers,
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
) -> None:
    qb_api_url = os.environ.get("QBITTORRENT_API_URL", "http://qbittorrent:8080")
    qb_username = os.environ["QBITTORRENT_USERNAME"]
    qb_password = os.environ["QBITTORRENT_PASSWORD"]
    category = os.environ.get("POSTPROCESSOR_CATEGORY", "Bangumi")
    qb_download_root = Path(
        os.environ.get("QBITTORRENT_DOWNLOAD_ROOT", "/downloads/Bangumi")
    )
    interval = poll_interval or int(os.environ.get("POSTPROCESSOR_POLL_INTERVAL", "60"))
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
        poll_interval=interval,
        delete_losers=delete,
        once=once,
    )
