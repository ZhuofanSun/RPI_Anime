from __future__ import annotations

from datetime import datetime
from typing import Any

from anime_ops_ui.copy import payload_copy, text
from anime_ops_ui.page_context import build_page_context
from anime_ops_ui.services.dashboard_sections import build_dashboard_hero, build_service_rows, build_summary_strip
from anime_ops_ui.services.weekly_schedule_service import build_phase4_schedule_snapshot


def build_service_summary(*, containers: dict[str, dict[str, Any]], tailscale_running: bool, locale: str | None = None) -> dict[str, Any]:
    copy = payload_copy("overview", locale)["service_summary"]
    running_containers = sum(
        1 for item in containers.values() if str(item.get("status", "")).lower() == "running"
    )
    total = len(containers) + 1
    online = running_containers + (1 if tailscale_running else 0)
    return {
        "label": copy["label"],
        "value": copy["value"].format(count=online),
        "detail": copy["detail"].format(total=total),
    }


def build_overview_payload(*, locale: str | None = None, public_host: str | None = None) -> dict[str, Any]:
    from anime_ops_ui import main as main_module

    overview_copy = payload_copy("overview", locale)
    weekly_copy = payload_copy("weekly_schedule", locale)
    cards_copy = overview_copy["cards"]
    diagnostics_copy = overview_copy["diagnostics"]
    services_copy = overview_copy["services"]
    try:
        main_module._sample_history_once()
    except Exception:
        pass

    anime_data_root = main_module.Path(main_module._env("ANIME_DATA_ROOT", "/srv/anime-data"))
    anime_collection_root = main_module.Path(main_module._env("ANIME_COLLECTION_ROOT", "/srv/anime-collection"))
    base_host = str(public_host or main_module._env("HOMEPAGE_BASE_HOST", main_module.socket.gethostname())).strip()
    autobangumi_port = int(main_module._env("AUTOBANGUMI_PORT", "7892"))
    jellyfin_port = int(main_module._env("JELLYFIN_PORT", "8096"))
    autobangumi_base_url = main_module._env("AUTOBANGUMI_API_URL", "").strip() or f"http://autobangumi:{autobangumi_port}"
    overview_now = datetime.now().astimezone()
    events = main_module.read_events(limit=300)
    phase4_error: str | None = None
    try:
        phase4 = build_phase4_schedule_snapshot(
            anime_data_root=anime_data_root,
            base_host=base_host,
            autobangumi_port=autobangumi_port,
            jellyfin_port=jellyfin_port,
            autobangumi_base_url=autobangumi_base_url,
            autobangumi_username=main_module._env("AUTOBANGUMI_USERNAME", ""),
            autobangumi_password=main_module._env("AUTOBANGUMI_PASSWORD", ""),
            state_root=main_module.Path(main_module._env("OPS_UI_STATE_ROOT", "/data")),
            now=overview_now,
            events=events,
            locale=locale,
        )
    except Exception as exc:
        phase4_error = str(exc)
        phase4 = {
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
                    for index, label in enumerate(weekly_copy["day_labels"])
                ],
                "unknown": {
                    "label": weekly_copy["unknown_label"],
                    "hint": weekly_copy["unknown_hint"],
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
    fan_detail = cards_copy["system"]["cpu_temp"]["fan_unavailable"]
    if fan_state and fan_state_age_s is not None:
        fan_detail = (
            cards_copy["system"]["cpu_temp"]["fan_fresh"].format(
                duty=int(round(float(fan_duty))),
                pin=fan_pin or "-",
                seconds=int(fan_state_age_s),
            )
            if fan_is_fresh
            else cards_copy["system"]["cpu_temp"]["fan_stale"].format(seconds=int(fan_state_age_s))
        )

    service_summary_card = build_service_summary(containers=containers, tailscale_running=tailscaled_online, locale=locale)

    system_cards = [
        {
            "label": cards_copy["system"]["cpu_usage"]["label"],
            "value": main_module._format_percent(cpu_percent),
            "detail": (quicklook or {}).get("cpu_name", cards_copy["system"]["cpu_usage"]["fallback_detail"]) if isinstance(quicklook, dict) else cards_copy["system"]["cpu_usage"]["fallback_detail"],
        },
        {
            "label": cards_copy["system"]["cpu_temp"]["label"],
            "value": main_module._format_temperature(cpu_temp_c),
            "detail": cards_copy["system"]["cpu_temp"]["detail"].format(
                hours=trend_window_hours,
                average=main_module._format_temperature(main_module._mean(temp_values)),
                fan_detail=fan_detail,
            ),
        },
        {
            "label": cards_copy["system"]["memory"]["label"],
            "value": main_module._format_percent(memory_percent),
            "detail": main_module._format_bytes((mem or {}).get("available") if isinstance(mem, dict) else None),
        },
        {
            "label": cards_copy["system"]["host_uptime"]["label"],
            "value": host_uptime,
            "detail": cards_copy["system"]["host_uptime"]["detail"].format(load_detail=load_detail),
        },
        service_summary_card,
        {
            "label": cards_copy["system"]["anime_data"]["label"],
            "value": main_module._format_percent(disk.get("percent")),
            "detail": main_module._format_bytes(disk.get("free_bytes")) if data_storage_ready else cards_copy["system"]["anime_data"]["unavailable"],
        },
    ]

    queue_cards = [
        {
            "label": cards_copy["queue"]["bangumi_tasks"]["label"],
            "value": str((qb or {}).get("task_count", "-")) if qb else "-",
            "detail": (qb or {}).get("category", "Bangumi") if qb else cards_copy["queue"]["bangumi_tasks"]["unavailable"],
        },
        {
            "label": cards_copy["queue"]["downloading"]["label"],
            "value": str((qb or {}).get("active_downloads", "-")) if qb else "-",
            "detail": main_module._format_rate((qb or {}).get("download_speed") if qb else None),
        },
        {
            "label": cards_copy["queue"]["seeding"]["label"],
            "value": str((qb or {}).get("active_seeds", "-")) if qb else "-",
            "detail": main_module._format_rate((qb or {}).get("upload_speed") if qb else None),
        },
        {
            "label": cards_copy["queue"]["seasonal_episodes"]["label"],
            "value": str(main_module._count_media_files(seasonal_root)) if data_storage_ready else "-",
            "detail": cards_copy["queue"]["seasonal_episodes"]["detail"].format(count=main_module._count_series_dirs(seasonal_root)) if data_storage_ready else cards_copy["queue"]["seasonal_episodes"]["unavailable"],
        },
        {
            "label": cards_copy["queue"]["manual_review"]["label"],
            "value": str(main_module._count_media_files(manual_review_root)) if data_storage_ready else "-",
            "detail": cards_copy["queue"]["manual_review"]["detail"] if data_storage_ready else cards_copy["queue"]["manual_review"]["unavailable"],
        },
        {
            "label": cards_copy["queue"]["download_residue"]["label"],
            "value": str(main_module._count_media_files(downloads_root)) if data_storage_ready else "-",
            "detail": cards_copy["queue"]["download_residue"]["detail"] if data_storage_ready else cards_copy["queue"]["download_residue"]["unavailable"],
        },
    ]
    manual_review_count = main_module._count_media_files(manual_review_root) if data_storage_ready else None
    log_count = len(main_module.read_events(limit=None))

    network_cards = [
        {
            "label": cards_copy["network"]["tailnet"]["label"],
            "value": (tailscale or {}).get("BackendState", "unknown") if tailscale else cards_copy["network"]["tailnet"]["unavailable"],
            "detail": tailscale_self.get("HostName") or base_host,
        },
        {
            "label": cards_copy["network"]["tailscale_ip"]["label"],
            "value": main_module._tailscale_ip_pair(tailscale_self.get("TailscaleIPs") if tailscale_self else None)[0],
            "detail": main_module._strip_trailing_dot(tailscale_self.get("DNSName")) if tailscale_self else "-",
        },
        {
            "label": cards_copy["network"]["peers"]["label"],
            "value": str(len(tailscale_peer_values)) if tailscale else "-",
            "detail": cards_copy["network"]["peers"]["detail"].format(count=tailnet_online_peers) if tailscale else cards_copy["network"]["peers"]["unavailable"],
        },
    ]

    trend_cards = [
        {
            "label": cards_copy["trend"]["cpu_usage"]["label"],
            "value": main_module._format_percent(cpu_percent),
            "detail": cards_copy["trend"]["cpu_usage"]["detail"].format(hours=trend_window_hours, load_detail=load_detail),
            "points": cpu_points,
            "chart_kind": "line",
            "window_label": f"{trend_window_hours}H",
            "tone": "teal",
        },
        {
            "label": cards_copy["trend"]["cpu_temp"]["label"],
            "value": main_module._format_temperature(cpu_temp_c),
            "detail": cards_copy["trend"]["cpu_temp"]["detail"].format(hours=trend_window_hours, average=main_module._format_temperature(main_module._mean(temp_values))),
            "points": temp_points,
            "chart_kind": "line",
            "window_label": f"{trend_window_hours}H",
            "tone": "amber",
        },
        {
            "label": cards_copy["trend"]["playback_traffic"]["label"],
            "value": main_module._format_rate(playback_tx_rate),
            "detail": cards_copy["trend"]["playback_traffic"]["detail"].format(hours=trend_window_hours, average=main_module._format_rate(main_module._mean(playback_values))),
            "points": playback_points,
            "chart_kind": "line",
            "window_label": f"{trend_window_hours}H",
            "tone": "ocean",
        },
        {
            "label": cards_copy["trend"]["download_volume"]["label"],
            "value": main_module._format_bytes(sum(download_values)),
            "detail": cards_copy["trend"]["download_volume"]["detail"].format(days=upload_window_days),
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
                "message": diagnostics_copy["phase4_unavailable"].format(error=phase4_error),
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
                "message": diagnostics_copy["fan_stale"].format(seconds=int(fan_state_age_s)),
            }
        )
    if not anime_data_mount["mounted"]:
        diagnostics.append(
            {
                "source": "mount:/srv/anime-data",
                "message": diagnostics_copy["anime_data_missing"],
            }
        )
    elif anime_data_mount["probe_error"]:
        diagnostics.append(
            {
                "source": "mount:/srv/anime-data",
                "message": diagnostics_copy["anime_data_probe"].format(error=anime_data_mount["probe_error"]),
            }
        )
    if not anime_collection_mount["mounted"]:
        diagnostics.append(
            {
                "source": "mount:/srv/anime-collection",
                "message": diagnostics_copy["anime_collection_missing"],
            }
        )
    elif anime_collection_mount["probe_error"]:
        diagnostics.append(
            {
                "source": "mount:/srv/anime-collection",
                "message": diagnostics_copy["anime_collection_probe"].format(error=anime_collection_mount["probe_error"]),
            }
        )

    services = [
        {
            "id": "jellyfin",
            "name": "Jellyfin",
            "href": main_module._service_link(base_host, int(main_module._env("JELLYFIN_PORT", "8096"))),
            "description": services_copy["jellyfin"]["description"],
            "status": containers.get("jellyfin", {}).get("status", "unknown"),
            "meta": services_copy["jellyfin"]["meta"],
            "uptime": containers.get("jellyfin", {}).get("uptime") if isinstance(containers.get("jellyfin", {}), dict) else None,
            "restart_target": "jellyfin",
            "restart_label": services_copy["restart"],
        },
        {
            "id": "qbittorrent",
            "name": "qBittorrent",
            "href": main_module._service_link(base_host, int(main_module._env("QBITTORRENT_WEBUI_PORT", "8080"))),
            "description": services_copy["qbittorrent"]["description"],
            "status": containers.get("qbittorrent", {}).get("status", "unknown"),
            "meta": services_copy["qbittorrent"]["meta"],
            "uptime": containers.get("qbittorrent", {}).get("uptime") if isinstance(containers.get("qbittorrent", {}), dict) else None,
            "restart_target": "qbittorrent",
            "restart_label": services_copy["restart"],
        },
        {
            "id": "autobangumi",
            "name": "AutoBangumi",
            "href": main_module._service_link(base_host, int(main_module._env("AUTOBANGUMI_PORT", "7892"))),
            "description": services_copy["autobangumi"]["description"],
            "status": containers.get("autobangumi", {}).get("status", "unknown"),
            "meta": services_copy["autobangumi"]["meta"],
            "uptime": containers.get("autobangumi", {}).get("uptime") if isinstance(containers.get("autobangumi", {}), dict) else None,
            "restart_target": "autobangumi",
            "restart_label": services_copy["restart"],
        },
        {
            "id": "glances",
            "name": "Glances",
            "href": main_module._service_link(base_host, int(main_module._env("GLANCES_PORT", "61208"))),
            "description": services_copy["glances"]["description"],
            "status": containers.get("glances", {}).get("status", "unknown"),
            "meta": services_copy["glances"]["meta"],
            "uptime": containers.get("glances", {}).get("uptime") if isinstance(containers.get("glances", {}), dict) else None,
            "restart_target": "glances",
            "restart_label": services_copy["restart"],
        },
        {
            "id": "postprocessor",
            "name": "Postprocessor",
            "href": f"{main_module._service_link(base_host, int(main_module._env('HOMEPAGE_PORT', '3000')))} /postprocessor".replace(" ", ""),
            "description": services_copy["postprocessor"]["description"],
            "status": containers.get("anime-postprocessor", {}).get("status", "unknown"),
            "meta": services_copy["postprocessor"]["meta"],
            "uptime": containers.get("anime-postprocessor", {}).get("uptime") if isinstance(containers.get("anime-postprocessor", {}), dict) else None,
            "internal": True,
            "restart_target": "postprocessor",
            "restart_label": services_copy["restart"],
        },
        {
            "id": "ops-review",
            "name": "Ops Review",
            "href": f"{main_module._service_link(base_host, int(main_module._env('HOMEPAGE_PORT', '3000')))}/ops-review",
            "description": services_copy["ops_review"]["description"],
            "status": "online",
            "meta": services_copy["ops_review"]["meta"].format(count=manual_review_count) if manual_review_count is not None else services_copy["ops_review"]["unavailable_meta"],
            "uptime": services_copy["ops_review"]["uptime"],
            "internal": True,
            "restart_target": "homepage",
            "restart_label": services_copy["restart_ui"],
            "restart_requires_reload": True,
            "restart_name": "Ops UI",
        },
        {
            "id": "logs",
            "name": "Logs",
            "href": f"{main_module._service_link(base_host, int(main_module._env('HOMEPAGE_PORT', '3000')))} /logs".replace(" ", ""),
            "description": services_copy["logs"]["description"],
            "status": "online",
            "meta": services_copy["logs"]["meta"].format(count=log_count),
            "uptime": services_copy["logs"]["uptime"].format(count=main_module.event_log_cap()),
            "internal": True,
            "restart_target": "homepage",
            "restart_label": services_copy["restart_ui"],
            "restart_requires_reload": True,
            "restart_name": "Ops UI",
        },
        {
            "id": "tailscale",
            "name": "Tailscale",
            "href": f"{main_module._service_link(base_host, int(main_module._env('HOMEPAGE_PORT', '3000')))} /tailscale".replace(" ", ""),
            "description": services_copy["tailscale"]["description"],
            "status": "online" if tailscaled_online and tailscale_self.get("Online") else "offline",
            "meta": main_module._tailscale_ip_pair(tailscale_self.get("TailscaleIPs") if tailscale_self else None)[0],
            "uptime": main_module._strip_trailing_dot(tailscale_self.get("DNSName")) if tailscale_self else None,
            "internal": True,
            "restart_target": "tailscale",
            "restart_label": services_copy["restart"],
        },
    ]
    active_downloads = int((qb or {}).get("active_downloads", 0) or 0)
    review_count = int(manual_review_count or 0)
    hero = build_dashboard_hero(
        title=text("site.title", locale),
        active_downloads=active_downloads,
        review_count=review_count,
        diagnostics=diagnostics,
        tailnet_online=bool(tailscale_self.get("Online")),
        host=base_host,
        locale=locale,
    )
    summary_strip = build_summary_strip(
        active_downloads=active_downloads,
        review_count=review_count,
        diagnostics=diagnostics,
        weekly_schedule=phase4["weekly_schedule"],
        locale=locale,
    )
    service_rows = build_service_rows(services=services)
    pipeline_cards = queue_cards
    page_context = build_page_context("dashboard", "Dashboard", locale=locale)
    overview_page_context = {
        key: page_context[key]
        for key in (
            "page_key",
            "page_title",
            "site_title",
            "site_subtitle",
            "navigation_api_path",
            "internal_pages",
            "external_services",
            "service_actions",
            "stack_action",
        )
    }

    return {
        **overview_page_context,
        "title": text("site.title", locale),
        "subtitle": text("site.subtitle", locale),
        "host": base_host,
        "refresh_interval_seconds": main_module._refresh_interval_seconds(),
        "hero": hero,
        "summary_strip": summary_strip,
        "copy": overview_copy["dashboard_copy"],
        "pipeline_cards": pipeline_cards,
        "system_cards": system_cards,
        "network_cards": network_cards,
        "trend_cards": trend_cards,
        "service_rows": service_rows,
        "weekly_schedule": phase4["weekly_schedule"],
        "stack_control": overview_copy["stack_control"],
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


def build_overview(*, locale: str | None = None, public_host: str | None = None) -> dict[str, Any]:
    return build_overview_payload(locale=locale, public_host=public_host)
