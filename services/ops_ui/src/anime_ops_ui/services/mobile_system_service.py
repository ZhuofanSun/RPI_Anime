from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import requests

from anime_ops_ui import runtime_main_module
from anime_ops_ui.domain.mobile_models import (
    SystemDownloadItem,
    SystemLogItem,
    SystemOverviewBarDatum,
    SystemOverviewBarTrend,
    SystemOverviewLineTrend,
    SystemOverviewStatusCard,
    SystemOverviewSupplementaryItem,
    SystemTailscaleLocalNode,
    SystemTailscalePeer,
)
from anime_ops_ui.i18n import normalize_locale
from anime_ops_ui.services.log_service import build_logs_payload as build_logs_payload_service
from anime_ops_ui.services.mobile_timestamp import normalize_mobile_timestamp, utc_now_timestamp
from anime_ops_ui.services.overview_service import build_overview
from anime_ops_ui.services.tailscale_service import build_tailscale_payload as build_tailscale_payload_service


def _locale_text(locale: str | None, *, en: str, zh: str) -> str:
    return en if normalize_locale(locale) == "en" else zh


def _numeric_value(display_value: Any) -> float | None:
    if display_value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(display_value))
    if match is None:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _status_card(raw_card: dict[str, Any] | None, *, fallback_title: str) -> dict[str, Any]:
    raw_card = raw_card if isinstance(raw_card, dict) else {}
    display_value = str(raw_card.get("value") or "--")
    return SystemOverviewStatusCard(
        title=str(raw_card.get("label") or fallback_title),
        displayValue=display_value,
        numericValue=_numeric_value(display_value),
    ).model_dump()


def _line_trend(raw_card: dict[str, Any] | None, *, fallback_title: str) -> dict[str, Any]:
    raw_card = raw_card if isinstance(raw_card, dict) else {}
    points = raw_card.get("points")
    if not isinstance(points, list):
        points = []
    normalized_points: list[float] = []
    for point in points:
        try:
            normalized_points.append(float(point))
        except (TypeError, ValueError):
            continue
    return SystemOverviewLineTrend(
        title=str(raw_card.get("label") or fallback_title),
        displayValue=str(raw_card.get("value") or "--"),
        points=normalized_points,
    ).model_dump()


def _bar_trend(raw_card: dict[str, Any] | None, *, fallback_title: str) -> dict[str, Any]:
    raw_card = raw_card if isinstance(raw_card, dict) else {}
    bars = raw_card.get("bars")
    normalized_bars: list[dict[str, Any]] = []
    if isinstance(bars, list):
        for item in bars:
            if not isinstance(item, dict):
                continue
            try:
                value = float(item.get("value") or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            normalized_bars.append(
                SystemOverviewBarDatum(
                    label=str(item.get("label") or ""),
                    value=value,
                    valueLabel=str(item.get("value_label") or "--"),
                ).model_dump()
            )
    return SystemOverviewBarTrend(
        title=str(raw_card.get("label") or fallback_title),
        displayValue=str(raw_card.get("value") or "--"),
        bars=normalized_bars,
    ).model_dump()


def _fan_value(*, locale: str | None = None) -> str:
    main_module = runtime_main_module()
    fan_state, fan_error = main_module._fan_state_snapshot()
    if fan_error:
        return _locale_text(locale, en="Unavailable", zh="不可用")
    if not isinstance(fan_state, dict):
        return "--"

    duty = fan_state.get("applied_duty_percent")
    if duty is not None:
        try:
            return f"{int(round(float(duty)))}%"
        except (TypeError, ValueError):
            pass

    pin = fan_state.get("pin")
    if pin:
        return str(pin)
    return "--"


def _system_timestamp() -> str:
    return utc_now_timestamp()


def _service_label(service: str, *, locale: str | None = None) -> str:
    normalized = (service or "").strip().lower()
    mapping = {
        "autobangumi": "AutoBangumi",
        "postprocessor": "Postprocessor",
        "homepage": "Ops UI",
        "ops-ui": "Ops UI",
        "qbittorrent": "qBittorrent",
        "service-control": _locale_text(locale, en="Service Control", zh="服务控制"),
        "tailscale-control": "Tailscale",
        "jellyfin": "Jellyfin",
    }
    if normalized in mapping:
        return mapping[normalized]
    if not normalized:
        return _locale_text(locale, en="Unknown", zh="未知")
    return service


def _normalized_level(level: str) -> str:
    normalized = (level or "").strip().lower()
    if normalized in {"error", "warning", "info"}:
        return normalized
    return "info"


def _download_state_info(raw_state: str | None) -> tuple[str, int]:
    state = (raw_state or "").strip()
    downloading_states = {
        "downloading",
        "forcedDL",
        "stalledDL",
    }
    queued_states = {
        "metaDL",
        "queuedDL",
        "checkingDL",
        "checkingUP",
        "queuedUP",
        "pausedDL",
        "pausedUP",
    }
    completed_states = {
        "uploading",
        "forcedUP",
        "stalledUP",
    }

    if state in downloading_states:
        return "downloading", 0
    if state in queued_states:
        return "queued", 1
    if state in completed_states:
        return "completed", 2
    return "other", 3


def _parse_progress(raw_progress: Any, *, normalized_state: str) -> float:
    try:
        progress = float(raw_progress or 0.0)
    except (TypeError, ValueError):
        progress = 0.0
    if normalized_state == "completed":
        return 1.0
    return max(0.0, min(progress, 1.0))


def _parse_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _fetch_qbittorrent_downloads() -> list[dict[str, Any]]:
    main_module = runtime_main_module()
    base_url = main_module._env("QBITTORRENT_API_URL", "http://qbittorrent:8080").rstrip("/")
    username = main_module._env("QBITTORRENT_USERNAME", "")
    password = main_module._env("QBITTORRENT_PASSWORD", "")
    category = main_module._env("POSTPROCESSOR_CATEGORY", "Bangumi")

    session = requests.Session()
    auth = session.post(
        f"{base_url}/api/v2/auth/login",
        data={"username": username, "password": password},
        timeout=5,
    )
    auth.raise_for_status()
    if auth.text.strip() != "Ok.":
        raise RuntimeError(f"qB auth failed: {auth.text.strip()}")

    torrents = session.get(
        f"{base_url}/api/v2/torrents/info",
        params={"category": category},
        timeout=5,
    )
    torrents.raise_for_status()
    payload = torrents.json()
    if not isinstance(payload, list):
        raise RuntimeError("qB torrent payload must be a list")
    return [item for item in payload if isinstance(item, dict)]


def build_system_downloads_payload(*, locale: str | None = None) -> dict[str, Any]:
    try:
        torrent_items = _fetch_qbittorrent_downloads()
    except Exception:
        torrent_items = []
    normalized_items: list[tuple[int, int, dict[str, Any]]] = []

    for item in torrent_items:
        raw_state = str(item.get("state") or "")
        normalized_state, sort_rank = _download_state_info(raw_state)
        progress = _parse_progress(item.get("progress"), normalized_state=normalized_state)
        total_bytes = _parse_int(item.get("size") or item.get("total_size"))
        downloaded_bytes = _parse_int(item.get("completed"))
        if normalized_state == "completed":
            downloaded_bytes = total_bytes if total_bytes > 0 else downloaded_bytes
        download_speed = 0 if normalized_state == "completed" else _parse_int(item.get("dlspeed"))
        added_at = _parse_int(item.get("added_on"))
        added_at_value = None
        if added_at > 0:
            added_at_value = datetime.fromtimestamp(added_at, UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        normalized_items.append(
            (
                sort_rank,
                -added_at,
                SystemDownloadItem(
                    id=str(item.get("hash") or item.get("name") or f"download_{len(normalized_items)}"),
                    name=str(item.get("name") or "--"),
                    downloadedBytes=downloaded_bytes,
                    totalBytes=total_bytes,
                    progress=progress,
                    downloadSpeedBytesPerSec=download_speed,
                    state=normalized_state,
                    addedAt=added_at_value,
                ).model_dump(),
            )
        )

    normalized_items.sort(key=lambda entry: (entry[0], entry[1], entry[2]["name"]))

    return {
        "items": [entry[2] for entry in normalized_items[:30]],
        "updatedAt": _system_timestamp(),
    }


def build_system_logs_payload(*, locale: str | None = None, limit: int = 30) -> dict[str, Any]:
    normalized_limit = max(1, min(limit, 30))
    try:
        payload = build_logs_payload_service(source=None, limit=normalized_limit, locale=locale)
    except Exception:
        payload = {"items": [], "last_updated": _system_timestamp()}

    items: list[dict[str, Any]] = []
    for entry in payload.get("items", []):
        if not isinstance(entry, dict):
            continue
        items.append(
            SystemLogItem(
                id=str(entry.get("id") or f"log_{len(items)}"),
                timestamp=normalize_mobile_timestamp(entry.get("ts"), default=_system_timestamp()) or _system_timestamp(),
                service=_service_label(str(entry.get("source") or ""), locale=locale),
                level=_normalized_level(str(entry.get("level") or "info")),
                summary=str(entry.get("message") or ""),
            ).model_dump()
        )

    return {
        "items": items,
        "updatedAt": normalize_mobile_timestamp(payload.get("last_updated"), default=_system_timestamp()) or _system_timestamp(),
    }


def build_system_tailscale_payload(*, locale: str | None = None) -> dict[str, Any]:
    payload = build_tailscale_payload_service(locale=locale)
    current_node = payload.get("current_node") if isinstance(payload, dict) else {}
    current_node = current_node if isinstance(current_node, dict) else {}
    peers = payload.get("peers") if isinstance(payload, dict) else []
    peers = peers if isinstance(peers, list) else []

    local_name = str(current_node.get("host") or _locale_text(locale, en="Unknown", zh="未知"))
    local_host = str(current_node.get("dns_name") or local_name)
    local_ipv4 = str(current_node.get("ipv4") or "--")
    local_online = bool(current_node.get("reachable"))

    normalized_peers: list[dict[str, Any]] = []
    for peer in peers:
        if not isinstance(peer, dict):
            continue
        peer_name = str(peer.get("host_name") or peer.get("dns_name") or _locale_text(locale, en="Unknown", zh="未知"))
        peer_host = str(peer.get("dns_name") or peer_name)
        peer_ipv4 = str(peer.get("ip") or "--")
        peer_online = str(peer.get("status") or "").lower() == "online"
        normalized_peers.append(
            SystemTailscalePeer(
                name=peer_name,
                host=peer_host,
                ipv4=peer_ipv4,
                online=peer_online,
            ).model_dump()
        )

    normalized_peers.sort(key=lambda item: (0 if item["online"] else 1, item["name"].lower()))

    return {
        "localNode": SystemTailscaleLocalNode(
            name=local_name,
            host=local_host,
            ipv4=local_ipv4,
            online=local_online,
        ).model_dump(),
        "peers": normalized_peers,
    }


def build_system_overview_payload(*, locale: str | None = None) -> dict[str, Any]:
    try:
        overview = build_overview(locale=locale)
    except Exception:
        overview = {}
    system_cards = overview.get("system_cards")
    trend_cards = overview.get("trend_cards")

    system_cards = system_cards if isinstance(system_cards, list) else []
    trend_cards = trend_cards if isinstance(trend_cards, list) else []

    cpu_card = system_cards[0] if len(system_cards) > 0 else None
    temperature_card = system_cards[1] if len(system_cards) > 1 else None
    memory_card = system_cards[2] if len(system_cards) > 2 else None
    uptime_card = system_cards[3] if len(system_cards) > 3 else None
    disk_card = system_cards[5] if len(system_cards) > 5 else None

    cpu_trend = trend_cards[0] if len(trend_cards) > 0 else None
    temperature_trend = trend_cards[1] if len(trend_cards) > 1 else None
    traffic_trend = trend_cards[2] if len(trend_cards) > 2 else None
    download_trend = trend_cards[3] if len(trend_cards) > 3 else None

    uptime_title = _locale_text(locale, en="Host Uptime", zh="主机开机时间")
    fan_title = _locale_text(locale, en="Fan", zh="风扇")

    return {
        "statusCards": {
            "cpu": _status_card(cpu_card, fallback_title=_locale_text(locale, en="CPU Usage", zh="CPU 使用")),
            "temperature": _status_card(
                temperature_card,
                fallback_title=_locale_text(locale, en="CPU Temperature", zh="CPU 温度"),
            ),
            "memory": _status_card(memory_card, fallback_title=_locale_text(locale, en="Memory", zh="内存")),
            "disk": _status_card(disk_card, fallback_title=_locale_text(locale, en="Disk", zh="硬盘")),
        },
        "trends": {
            "cpu24h": _line_trend(cpu_trend, fallback_title=_locale_text(locale, en="24-hour CPU", zh="24 小时 CPU")),
            "temperature24h": _line_trend(
                temperature_trend,
                fallback_title=_locale_text(locale, en="24-hour Temperature", zh="24 小时温度"),
            ),
            "clientTraffic": _line_trend(
                traffic_trend,
                fallback_title=_locale_text(locale, en="Client Traffic", zh="客户端流量"),
            ),
            "downloads7d": _bar_trend(
                download_trend,
                fallback_title=_locale_text(locale, en="7-day Downloads", zh="7 日下载"),
            ),
        },
        "supplementary": {
            "fan": SystemOverviewSupplementaryItem(title=fan_title, value=_fan_value(locale=locale)).model_dump(),
            "uptime": SystemOverviewSupplementaryItem(
                title=str((uptime_card or {}).get("label") or uptime_title),
                value=str((uptime_card or {}).get("value") or "--"),
            ).model_dump(),
        },
        "updatedAt": normalize_mobile_timestamp(overview.get("last_updated"), default=_system_timestamp()) or _system_timestamp(),
    }
