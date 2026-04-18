from __future__ import annotations

import re
from typing import Any

from anime_ops_ui import runtime_main_module
from anime_ops_ui.domain.mobile_models import (
    SystemOverviewBarDatum,
    SystemOverviewBarTrend,
    SystemOverviewLineTrend,
    SystemOverviewStatusCard,
    SystemOverviewSupplementaryItem,
)
from anime_ops_ui.i18n import normalize_locale
from anime_ops_ui.services.overview_service import build_overview


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


def build_system_overview_payload(*, locale: str | None = None) -> dict[str, Any]:
    overview = build_overview(locale=locale)
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
        "updatedAt": overview.get("last_updated"),
    }
