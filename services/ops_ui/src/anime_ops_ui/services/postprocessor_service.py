from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from anime_postprocessor.models import ParsedMedia
from anime_postprocessor.qb import QBClient
from anime_postprocessor.selector import score_candidate


def _best_scored_media(items: list[ParsedMedia]) -> ParsedMedia | None:
    if not items:
        return None
    return max(items, key=lambda item: score_candidate(item).tuple)


def _torrent_progress_label(progress: float) -> str:
    return f"{round(progress * 100):.0f}%"


def _postprocessor_candidate_payload(entry: Any) -> dict[str, Any]:
    top_media = _best_scored_media(entry.parsed_files)
    score_summary = score_candidate(top_media).summary if top_media else "-"
    return {
        "name": entry.torrent.name,
        "state": entry.torrent.state or "-",
        "progress_label": _torrent_progress_label(entry.torrent.progress),
        "completed": bool(entry.torrent.completed),
        "score_summary": score_summary,
        "parsed_count": len(entry.parsed_files),
        "unparsed_count": len(entry.unparsed_files),
        "content_root": str(entry.content_root),
    }


def _postprocessor_group_payload(
    *,
    key: Any,
    state: list[Any],
    completed_entries: list[Any],
    reason: str,
    status: str,
) -> dict[str, Any]:
    all_parsed = [item for entry in state for item in entry.parsed_files]
    completed_parsed = [item for entry in completed_entries for item in entry.parsed_files]
    best_overall = _best_scored_media(all_parsed)
    best_completed = _best_scored_media(completed_parsed)
    display_title = (
        best_overall.title
        if best_overall
        else (all_parsed[0].title if all_parsed else key.normalized_title)
    )
    candidates = sorted(
        [_postprocessor_candidate_payload(entry) for entry in state],
        key=lambda item: (
            not item["completed"],
            item["state"],
            item["name"].lower(),
        ),
    )
    return {
        "id": f"{key.normalized_title}-{key.season}-{key.episode}",
        "title": display_title,
        "episode_label": f"S{key.season:02d}E{key.episode:02d}",
        "status": status,
        "reason": reason,
        "candidate_count": len(state),
        "completed_count": len(completed_entries),
        "best_overall": score_candidate(best_overall).summary if best_overall else "-",
        "best_completed": score_candidate(best_completed).summary if best_completed else "-",
        "candidates": candidates,
    }


def build_postprocessor_payload() -> dict[str, Any]:
    from anime_ops_ui import main as main_module

    paths = main_module._postprocessor_paths()
    source_root = paths["source_root"]
    target_root = paths["target_root"]
    review_root = paths["review_root"]
    title_map = paths["title_map"]
    category = main_module._env("POSTPROCESSOR_CATEGORY", "Bangumi")
    poll_interval = main_module._env_int("POSTPROCESSOR_POLL_INTERVAL", 60)
    wait_timeout = main_module._env_int("POSTPROCESSOR_WAIT_TIMEOUT", 1800)
    delete_losers = main_module._env("POSTPROCESSOR_DELETE_LOSERS", "true").lower() in {"1", "true", "yes", "on"}

    containers, containers_error = main_module._glances_containers_snapshot()
    worker = containers.get("anime-postprocessor", {})
    worker_status = worker.get("status", "unknown") if isinstance(worker, dict) else "unknown"
    worker_uptime = worker.get("uptime") if isinstance(worker, dict) else None

    qb_snapshot, qb_error = main_module._qb_snapshot()
    diagnostics: list[dict[str, Any]] = []
    if containers_error:
        diagnostics.append({"source": "glances/containers", "message": containers_error})
    if qb_error:
        diagnostics.append({"source": "qbittorrent", "message": qb_error})

    ready_groups: list[dict[str, Any]] = []
    waiting_groups: list[dict[str, Any]] = []
    active_groups: list[dict[str, Any]] = []
    unparsed_torrents: list[dict[str, Any]] = []
    total_groups = 0

    if qb_error is None:
        try:
            qb = QBClient(
                main_module._env("QBITTORRENT_API_URL", "http://qbittorrent:8080"),
                main_module._env("QBITTORRENT_USERNAME", ""),
                main_module._env("QBITTORRENT_PASSWORD", ""),
            )
            qb.auth()
            torrents = qb.list_torrents(category=category)
            groups, completed_unparsed = main_module._build_groups(
                torrents,
                qb,
                qb_download_root=Path(main_module._env("QBITTORRENT_DOWNLOAD_ROOT", "/downloads/Bangumi")),
                local_download_root=source_root,
            )
            total_groups = len(groups)
            now_ts = int(time.time())
            for key, state in sorted(
                groups.items(),
                key=lambda item: (item[0].normalized_title, item[0].season, item[0].episode),
            ):
                completed_entries = [entry for entry in state if entry.torrent.completed]
                should_process, reason = main_module._should_process_group(
                    state=state,
                    completed_entries=completed_entries,
                    now_ts=now_ts,
                    wait_timeout=wait_timeout,
                )
                if should_process:
                    ready_groups.append(
                        _postprocessor_group_payload(
                            key=key,
                            state=state,
                            completed_entries=completed_entries,
                            reason=reason,
                            status="ready",
                        )
                    )
                elif completed_entries:
                    waiting_groups.append(
                        _postprocessor_group_payload(
                            key=key,
                            state=state,
                            completed_entries=completed_entries,
                            reason=reason,
                            status="waiting",
                        )
                    )
                else:
                    active_groups.append(
                        _postprocessor_group_payload(
                            key=key,
                            state=state,
                            completed_entries=completed_entries,
                            reason=reason,
                            status="active",
                        )
                    )

            for entry in completed_unparsed:
                unparsed_torrents.append(
                    {
                        "title": entry.torrent.name,
                        "status": "review",
                        "reason": "已完成但无法解析，下一轮会送入 manual_review",
                        "media_count": len(entry.media_paths),
                        "path": str(entry.content_root),
                    }
                )
        except Exception as exc:
            diagnostics.append({"source": "postprocessor", "message": str(exc)})

    post_events = [
        item
        for item in main_module.read_events(limit=200)
        if str(item.get("source")) == "postprocessor"
    ][:12]

    summary_cards = [
        {
            "label": "Worker",
            "value": str(worker_status).title(),
            "detail": worker_uptime or "容器运行时长不可用",
        },
        {
            "label": "Episode Groups",
            "value": str(total_groups),
            "detail": f"{len(ready_groups)} 组待处理 · {len(waiting_groups)} 组等待中",
        },
        {
            "label": "Queue Tasks",
            "value": str((qb_snapshot or {}).get("task_count", "-")) if qb_snapshot else "-",
            "detail": f"{(qb_snapshot or {}).get('active_downloads', 0)} 个下载中 · {(qb_snapshot or {}).get('active_seeds', 0)} 个做种中" if qb_snapshot else "qB 不可用",
        },
        {
            "label": "Manual Review",
            "value": str(main_module._count_media_files(review_root)),
            "detail": f"{len(unparsed_torrents)} 个已完成但未解析",
        },
    ]

    config_cards = [
        {
            "label": "Source Root",
            "value": str(source_root),
            "detail": "下载暂存区",
        },
        {
            "label": "Target Root",
            "value": str(target_root),
            "detail": "Jellyfin 季度库",
        },
        {
            "label": "Review Root",
            "value": str(review_root),
            "detail": "人工审核队列",
        },
        {
            "label": "Policy",
            "value": category,
            "detail": f"轮询 {poll_interval}s · 等待 {wait_timeout}s · 删除落选 {'开启' if delete_losers else '关闭'}",
        },
        {
            "label": "Title Map",
            "value": str(title_map),
            "detail": "作品名映射与季号偏移",
        },
    ]

    commands = [
        {
            "label": "Watch Once",
            "description": "手动触发一轮 watch 逻辑，最接近常驻服务实际行为。",
            "command": "docker compose --env-file deploy/.env -f deploy/compose.yaml run --rm postprocessor watch --once",
        },
        {
            "label": "Publish Dry Run",
            "description": "查看当前下载区如果手动发布，会生成什么计划。",
            "command": "docker compose --env-file deploy/.env -f deploy/compose.yaml run --rm postprocessor publish",
        },
        {
            "label": "Live Logs",
            "description": "持续观察常驻 worker 当前每轮处理输出。",
            "command": "docker compose --env-file deploy/.env -f deploy/compose.yaml logs -f postprocessor",
        },
    ]

    return {
        "title": "Postprocessor",
        "subtitle": "下载完成后的选优、等待窗口、自动发布与 review 分流工作台。",
        "refresh_interval_seconds": 15,
        "summary_cards": summary_cards,
        "config_cards": config_cards,
        "commands": commands,
        "recent_events": post_events,
        "sections": [
            {
                "id": "ready",
                "title": "Ready On Next Tick",
                "description": "已经满足处理条件，下一轮 watch 会直接接管并发布。",
                "meta": f"{len(ready_groups)} groups",
                "items": ready_groups[:8],
            },
            {
                "id": "waiting",
                "title": "Waiting Window",
                "description": "已有完成候选，但还在为更高优先级版本保留等待窗口。",
                "meta": f"{len(waiting_groups)} groups",
                "items": waiting_groups[:8],
            },
            {
                "id": "active",
                "title": "Active Downloads",
                "description": "当前还没有完成候选，继续等待下载完成。",
                "meta": f"{len(active_groups)} groups",
                "items": active_groups[:8],
            },
            {
                "id": "unparsed",
                "title": "Completed But Unparsed",
                "description": "已完成但无法解析的 torrent，下一轮会被送进 manual_review。",
                "meta": f"{len(unparsed_torrents)} torrents",
                "items": unparsed_torrents[:8],
            },
        ],
        "diagnostics": diagnostics,
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


def build_postprocessor_snapshot() -> dict[str, Any]:
    return build_postprocessor_payload()
