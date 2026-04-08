from __future__ import annotations

from datetime import datetime
from typing import Any

from anime_ops_ui.copy import text
from anime_ops_ui.page_context import build_page_context
from anime_ops_ui.services.dashboard_sections import build_dashboard_hero, build_service_rows, build_summary_strip
from anime_ops_ui.services.weekly_schedule_service import build_phase4_schedule_snapshot


def build_service_summary(*, containers: dict[str, dict[str, Any]], tailscale_running: bool) -> dict[str, Any]:
    running_containers = sum(
        1 for item in containers.values() if str(item.get("status", "")).lower() == "running"
    )
    total = len(containers) + 1
    online = running_containers + (1 if tailscale_running else 0)
    return {
        "label": "Services",
        "value": f"{online} online",
        "detail": f"{total} total · Docker + tailscaled",
    }


def build_overview_payload() -> dict[str, Any]:
    from anime_ops_ui import main as main_module

    try:
        main_module._sample_history_once()
    except Exception:
        pass

    anime_data_root = main_module.Path(main_module._env("ANIME_DATA_ROOT", "/srv/anime-data"))
    anime_collection_root = main_module.Path(main_module._env("ANIME_COLLECTION_ROOT", "/srv/anime-collection"))
    base_host = main_module._env("HOMEPAGE_BASE_HOST", main_module.socket.gethostname())
    autobangumi_port = int(main_module._env("AUTOBANGUMI_PORT", "7892"))
    overview_now = datetime.now().astimezone()
    events = main_module.read_events(limit=300)
    phase4_error: str | None = None
    try:
        phase4 = build_phase4_schedule_snapshot(
            anime_data_root=anime_data_root,
            base_host=base_host,
            autobangumi_port=autobangumi_port,
            autobangumi_base_url=main_module._service_link(base_host, autobangumi_port),
            autobangumi_username=main_module._env("AUTOBANGUMI_USERNAME", ""),
            autobangumi_password=main_module._env("AUTOBANGUMI_PASSWORD", ""),
            state_root=main_module.Path(main_module._env("OPS_UI_STATE_ROOT", "/data")),
            now=overview_now,
            events=events,
        )
    except Exception as exc:
        phase4_error = str(exc)
        labels = ["一", "二", "三", "四", "五", "六", "日"]
        phase4 = {
            "today_focus": {"items": []},
            "weekly_schedule": {
                "week_key": "",
                "today_weekday": overview_now.weekday(),
                "days": [
                    {
                        "weekday": index,
                        "label": label,
                        "is_today": index == overview_now.weekday(),
                        "items": [],
                        "hidden_items": [],
                        "has_hidden_items": False,
                    }
                    for index, label in enumerate(labels)
                ],
                "unknown": {
                    "label": "未知",
                    "hint": "拖拽以设置放送日",
                    "items": [],
                    "hidden_items": [],
                    "has_hidden_items": False,
                },
            },
        }
    glances_base = main_module._glances_base_url()
    anime_data_mount = main_module._mount_health(anime_data_root)
    anime_collection_mount = main_module._mount_health(anime_collection_root)
    if anime_data_mount["mounted"]:
        try:
            disk = main_module._disk_snapshot(anime_data_root)
        except Exception:
            disk = {
                "path": str(anime_data_root),
                "used_bytes": None,
                "free_bytes": None,
                "total_bytes": None,
                "percent": None,
            }
    else:
        disk = {
            "path": str(anime_data_root),
            "used_bytes": None,
            "free_bytes": None,
            "total_bytes": None,
            "percent": None,
        }

    quicklook, quicklook_error = main_module._safe_get_json(f"{glances_base}/quicklook")
    containers_raw, containers_error = main_module._safe_get_json(f"{glances_base}/containers")
    mem, mem_error = main_module._safe_get_json(f"{glances_base}/mem")
    uptime_raw, uptime_error = main_module._safe_get_json(f"{glances_base}/uptime")
    load_raw, load_error = main_module._safe_get_json(f"{glances_base}/load")
    sensors_raw, sensors_error = main_module._safe_get_json(f"{glances_base}/sensors")
    tailscale_socket = main_module._env("TAILSCALE_SOCKET", "/var/run/tailscale/tailscaled.sock")
    tailscale, tailscale_error = main_module._tailscale_status(tailscale_socket)
    qb, qb_error = main_module._qb_snapshot()

    containers_list = containers_raw if isinstance(containers_raw, list) else []
    containers = {
        item.get("name", ""): item
        for item in containers_list
        if isinstance(item, dict)
    }

    manual_review_root = anime_data_root / "processing" / "manual_review"
    seasonal_root = anime_data_root / "library" / "seasonal"
    downloads_root = anime_data_root / "downloads" / "Bangumi"
    data_storage_ready = bool(anime_data_mount["mounted"] and anime_data_mount["readable"] and not anime_data_mount["probe_error"])

    tailscale_self = ((tailscale or {}).get("Self") or {}) if isinstance(tailscale, dict) else {}
    tailscale_peers = ((tailscale or {}).get("Peer") or {}) if isinstance(tailscale, dict) else {}
    tailscale_peer_values = list(tailscale_peers.values()) if isinstance(tailscale_peers, dict) else []
    tailnet_online_peers = sum(1 for peer in tailscale_peer_values if peer.get("Online"))
    tailscaled_online = bool(isinstance(tailscale, dict) and not tailscale_error)
    cpu_percent = (quicklook or {}).get("cpu") if isinstance(quicklook, dict) else None
    memory_percent = (mem or {}).get("percent") if isinstance(mem, dict) else None
    cpu_temp_c = main_module._extract_temperature(sensors_raw)
    jellyfin_container = containers.get("jellyfin", {})
    jellyfin_network = jellyfin_container.get("network", {}) if isinstance(jellyfin_container, dict) else {}
    playback_tx_rate = jellyfin_container.get("network_tx") or jellyfin_network.get("tx")
    fan_state, fan_state_error = main_module._fan_state_snapshot()
    host_uptime = main_module._format_uptime(uptime_raw if isinstance(uptime_raw, str) else None)
    load_min1 = (load_raw or {}).get("min1") if isinstance(load_raw, dict) else None
    load_min5 = (load_raw or {}).get("min5") if isinstance(load_raw, dict) else None
    load_min15 = (load_raw or {}).get("min15") if isinstance(load_raw, dict) else None
    load_detail = "-"
    if all(value is not None for value in (load_min1, load_min5, load_min15)):
        load_detail = f"{float(load_min1):.2f} / {float(load_min5):.2f} / {float(load_min15):.2f}"

    trend_window_hours = main_module._series_window_hours()
    upload_window_days = main_module._upload_window_days()
    cpu_values, cpu_points = main_module._series_values("cpu_percent", window_hours=trend_window_hours)
    temp_values, temp_points = main_module._series_values("cpu_temp_c", window_hours=trend_window_hours)
    playback_values, playback_points = main_module._series_values("playback_tx_rate", window_hours=trend_window_hours)
    download_bars, download_values = main_module._daily_volume_bars(days=upload_window_days, daily_key="download_daily")

    fan_updated_ts = float((fan_state or {}).get("updated_ts") or 0.0) if fan_state else 0.0
    fan_state_age_s = max(0.0, __import__("time").time() - fan_updated_ts) if fan_updated_ts else None
    fan_is_fresh = fan_state_age_s is not None and fan_state_age_s <= max(main_module._refresh_interval_seconds() * 3, 30)
    fan_duty = (fan_state or {}).get("applied_duty_percent") if fan_state else None
    fan_cpu_temp = (fan_state or {}).get("cpu_temp_c") if fan_state else None
    fan_pin = (fan_state or {}).get("pin") if fan_state else None
    fan_status_label = "Online" if fan_is_fresh else "Stale"
    fan_detail = "Fan state unavailable"
    if fan_state and fan_state_age_s is not None:
        fan_detail = (
            f"Fan {int(round(float(fan_duty)))}% · GPIO{fan_pin or '-'} · {int(fan_state_age_s)}s ago"
            if fan_is_fresh
            else f"last update {int(fan_state_age_s)}s ago"
        )

    service_summary_card = build_service_summary(containers=containers, tailscale_running=tailscaled_online)

    system_cards = [
        {
            "label": "CPU Usage",
            "value": main_module._format_percent(cpu_percent),
            "detail": (quicklook or {}).get("cpu_name", "Raspberry Pi") if isinstance(quicklook, dict) else "Raspberry Pi",
        },
        {
            "label": "CPU Temp",
            "value": main_module._format_temperature(cpu_temp_c),
            "detail": f"{trend_window_hours}h avg {main_module._format_temperature(main_module._mean(temp_values))} · {fan_detail}",
        },
        {
            "label": "Memory",
            "value": main_module._format_percent(memory_percent),
            "detail": main_module._format_bytes((mem or {}).get("available") if isinstance(mem, dict) else None),
        },
        {
            "label": "Host Uptime",
            "value": host_uptime,
            "detail": f"load {load_detail}",
        },
        service_summary_card,
        {
            "label": "Anime Data",
            "value": main_module._format_percent(disk.get("percent")),
            "detail": main_module._format_bytes(disk.get("free_bytes")) if data_storage_ready else "数据盘未挂载或不可读",
        },
    ]

    queue_cards = [
        {
            "label": "Bangumi Tasks",
            "value": str((qb or {}).get("task_count", "-")) if qb else "-",
            "detail": (qb or {}).get("category", "Bangumi") if qb else "qB 不可用",
        },
        {
            "label": "Downloading",
            "value": str((qb or {}).get("active_downloads", "-")) if qb else "-",
            "detail": main_module._format_rate((qb or {}).get("download_speed") if qb else None),
        },
        {
            "label": "Seeding",
            "value": str((qb or {}).get("active_seeds", "-")) if qb else "-",
            "detail": main_module._format_rate((qb or {}).get("upload_speed") if qb else None),
        },
        {
            "label": "Seasonal Episodes",
            "value": str(main_module._count_media_files(seasonal_root)) if data_storage_ready else "-",
            "detail": f"{main_module._count_series_dirs(seasonal_root)} 部作品" if data_storage_ready else "数据盘未挂载",
        },
        {
            "label": "Manual Review",
            "value": str(main_module._count_media_files(manual_review_root)) if data_storage_ready else "-",
            "detail": "待人工处理文件" if data_storage_ready else "数据盘未挂载",
        },
        {
            "label": "Download Residue",
            "value": str(main_module._count_media_files(downloads_root)) if data_storage_ready else "-",
            "detail": "下载区剩余媒体文件" if data_storage_ready else "数据盘未挂载",
        },
    ]
    manual_review_count = main_module._count_media_files(manual_review_root) if data_storage_ready else None
    log_count = len(main_module.read_events(limit=None))

    network_cards = [
        {
            "label": "Tailnet",
            "value": (tailscale or {}).get("BackendState", "unknown") if tailscale else "unavailable",
            "detail": tailscale_self.get("HostName") or base_host,
        },
        {
            "label": "Tailscale IP",
            "value": main_module._tailscale_ip_pair(tailscale_self.get("TailscaleIPs") if tailscale_self else None)[0],
            "detail": main_module._strip_trailing_dot(tailscale_self.get("DNSName")) if tailscale_self else "-",
        },
        {
            "label": "Peers",
            "value": str(len(tailscale_peer_values)) if tailscale else "-",
            "detail": f"{tailnet_online_peers} 台在线" if tailscale else "本地 API 不可用",
        },
    ]

    trend_cards = [
        {
            "label": "CPU Usage",
            "value": main_module._format_percent(cpu_percent),
            "detail": f"{trend_window_hours}h · load {load_detail}",
            "points": cpu_points,
            "chart_kind": "line",
            "window_label": f"{trend_window_hours}H",
            "tone": "teal",
        },
        {
            "label": "CPU Temp",
            "value": main_module._format_temperature(cpu_temp_c),
            "detail": f"{trend_window_hours}h avg {main_module._format_temperature(main_module._mean(temp_values))}",
            "points": temp_points,
            "chart_kind": "line",
            "window_label": f"{trend_window_hours}H",
            "tone": "amber",
        },
        {
            "label": "Playback Traffic",
            "value": main_module._format_rate(playback_tx_rate),
            "detail": f"{trend_window_hours}h 平均 {main_module._format_rate(main_module._mean(playback_values))} · 全部客户端",
            "points": playback_points,
            "chart_kind": "line",
            "window_label": f"{trend_window_hours}H",
            "tone": "ocean",
        },
        {
            "label": "Download Volume",
            "value": main_module._format_bytes(sum(download_values)),
            "detail": f"近 {upload_window_days} 天总量 · qBittorrent",
            "bars": download_bars,
            "chart_kind": "bars",
            "window_label": f"{upload_window_days}D",
            "tone": "violet",
        },
    ]

    diagnostics = []
    if phase4_error:
        diagnostics.append(
            {
                "source": "phase4-schedule",
                "message": f"Phase 4 weekly schedule unavailable: {phase4_error}",
            }
        )
    for label, error in (
        ("glances/quicklook", quicklook_error),
        ("glances/containers", containers_error),
        ("glances/mem", mem_error),
        ("glances/uptime", uptime_error),
        ("glances/load", load_error),
        ("glances/sensors", sensors_error),
        ("qBittorrent", qb_error),
        ("tailscale", tailscale_error),
        ("fan-control", fan_state_error),
    ):
        if error:
            diagnostics.append({"source": label, "message": error})
    if fan_state and not fan_is_fresh and fan_state_age_s is not None:
        diagnostics.append(
            {
                "source": "fan-control",
                "message": f"fan state is stale ({int(fan_state_age_s)}s since last update)",
            }
        )
    if not anime_data_mount["mounted"]:
        diagnostics.append(
            {
                "source": "mount:/srv/anime-data",
                "message": "未检测到数据盘挂载，下载、整理和媒体库目录可能已回落到系统盘。",
            }
        )
    elif anime_data_mount["probe_error"]:
        diagnostics.append(
            {
                "source": "mount:/srv/anime-data",
                "message": f"数据盘访问异常：{anime_data_mount['probe_error']}",
            }
        )
    if not anime_collection_mount["mounted"]:
        diagnostics.append(
            {
                "source": "mount:/srv/anime-collection",
                "message": "未检测到收藏盘挂载，收藏库当前不可用。",
            }
        )
    elif anime_collection_mount["probe_error"]:
        diagnostics.append(
            {
                "source": "mount:/srv/anime-collection",
                "message": f"收藏盘访问异常：{anime_collection_mount['probe_error']}",
            }
        )

    services = [
        {
            "id": "jellyfin",
            "name": "Jellyfin",
            "href": main_module._service_link(base_host, int(main_module._env("JELLYFIN_PORT", "8096"))),
            "description": "私人影音库与播放入口",
            "status": containers.get("jellyfin", {}).get("status", "unknown"),
            "meta": "Media server",
            "uptime": containers.get("jellyfin", {}).get("uptime") if isinstance(containers.get("jellyfin", {}), dict) else None,
            "restart_target": "jellyfin",
            "restart_label": "Restart",
        },
        {
            "id": "qbittorrent",
            "name": "qBittorrent",
            "href": main_module._service_link(base_host, int(main_module._env("QBITTORRENT_WEBUI_PORT", "8080"))),
            "description": "下载、任务队列和分类",
            "status": containers.get("qbittorrent", {}).get("status", "unknown"),
            "meta": "Download client",
            "uptime": containers.get("qbittorrent", {}).get("uptime") if isinstance(containers.get("qbittorrent", {}), dict) else None,
            "restart_target": "qbittorrent",
            "restart_label": "Restart",
        },
        {
            "id": "autobangumi",
            "name": "AutoBangumi",
            "href": main_module._service_link(base_host, int(main_module._env("AUTOBANGUMI_PORT", "7892"))),
            "description": "RSS 订阅与自动下载规则",
            "status": containers.get("autobangumi", {}).get("status", "unknown"),
            "meta": "Subscription",
            "uptime": containers.get("autobangumi", {}).get("uptime") if isinstance(containers.get("autobangumi", {}), dict) else None,
            "restart_target": "autobangumi",
            "restart_label": "Restart",
        },
        {
            "id": "glances",
            "name": "Glances",
            "href": main_module._service_link(base_host, int(main_module._env("GLANCES_PORT", "61208"))),
            "description": "系统、容器和进程监控",
            "status": containers.get("glances", {}).get("status", "unknown"),
            "meta": "System monitor",
            "uptime": containers.get("glances", {}).get("uptime") if isinstance(containers.get("glances", {}), dict) else None,
            "restart_target": "glances",
            "restart_label": "Restart",
        },
        {
            "id": "postprocessor",
            "name": "Postprocessor",
            "href": f"{main_module._service_link(base_host, int(main_module._env('HOMEPAGE_PORT', '3000')))} /postprocessor".replace(" ", ""),
            "description": "下载完成后的选优、发布和 NFO 生成",
            "status": containers.get("anime-postprocessor", {}).get("status", "unknown"),
            "meta": "Background worker",
            "uptime": containers.get("anime-postprocessor", {}).get("uptime") if isinstance(containers.get("anime-postprocessor", {}), dict) else None,
            "internal": True,
            "restart_target": "postprocessor",
            "restart_label": "Restart",
        },
        {
            "id": "ops-review",
            "name": "Ops Review",
            "href": f"{main_module._service_link(base_host, int(main_module._env('HOMEPAGE_PORT', '3000')))}/ops-review",
            "description": "人工审核队列与文件处理",
            "status": "online",
            "meta": f"{manual_review_count} files" if manual_review_count is not None else "数据盘未挂载",
            "uptime": "审核工作台",
            "internal": True,
            "restart_target": "homepage",
            "restart_label": "Restart UI",
            "restart_requires_reload": True,
            "restart_name": "Ops UI",
        },
        {
            "id": "logs",
            "name": "Logs",
            "href": f"{main_module._service_link(base_host, int(main_module._env('HOMEPAGE_PORT', '3000')))} /logs".replace(" ", ""),
            "description": "结构化日志、来源筛选和清理",
            "status": "online",
            "meta": f"{log_count} events",
            "uptime": f"上限 {main_module.event_log_cap()} 条",
            "internal": True,
            "restart_target": "homepage",
            "restart_label": "Restart UI",
            "restart_requires_reload": True,
            "restart_name": "Ops UI",
        },
        {
            "id": "tailscale",
            "name": "Tailscale",
            "href": f"{main_module._service_link(base_host, int(main_module._env('HOMEPAGE_PORT', '3000')))} /tailscale".replace(" ", ""),
            "description": "本地 tailnet 状态与远程访问链路",
            "status": "online" if tailscaled_online and tailscale_self.get("Online") else "offline",
            "meta": main_module._tailscale_ip_pair(tailscale_self.get("TailscaleIPs") if tailscale_self else None)[0],
            "uptime": main_module._strip_trailing_dot(tailscale_self.get("DNSName")) if tailscale_self else None,
            "internal": True,
            "restart_target": "tailscale",
            "restart_label": "Restart",
        },
    ]
    active_downloads = int((qb or {}).get("active_downloads", 0) or 0)
    review_count = int(manual_review_count or 0)
    hero = build_dashboard_hero(
        title=text("site.title"),
        active_downloads=active_downloads,
        review_count=review_count,
        diagnostics=diagnostics,
        tailnet_online=bool(tailscale_self.get("Online")),
        host=base_host,
    )
    summary_strip = build_summary_strip(
        active_downloads=active_downloads,
        review_count=review_count,
        diagnostics=diagnostics,
    )
    service_rows = build_service_rows(services=services)
    pipeline_cards = queue_cards
    page_context = build_page_context("dashboard", "Dashboard")

    return {
        **page_context,
        "title": text("site.title"),
        "subtitle": text("site.subtitle"),
        "host": base_host,
        "refresh_interval_seconds": main_module._refresh_interval_seconds(),
        "hero": hero,
        "summary_strip": summary_strip,
        "pipeline_cards": pipeline_cards,
        "system_cards": system_cards,
        "network_cards": network_cards,
        "trend_cards": trend_cards,
        "service_rows": service_rows,
        "today_focus": phase4["today_focus"],
        "weekly_schedule": phase4["weekly_schedule"],
        "stack_control": {
            "label": "Restart Stack",
            "detail": "compose only · homepage last",
        },
        "diagnostics": diagnostics,
        "last_updated": datetime.now().isoformat(timespec="seconds"),
        # Phase 2 compatibility keys retained until Task 4 consumes sectioned payload.
        "services": services,
        "queue_cards": queue_cards,
        "generated_from": {
            "glances": glances_base,
            "tailscale_socket": tailscale_socket,
            "history_file": str(main_module._history_file()),
        },
    }


def build_overview() -> dict[str, Any]:
    return build_overview_payload()
