from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from anime_ops_ui import runtime_main_module
from anime_ops_ui.domain.mobile_models import RSSListItem, RSSPreviewItem
from anime_ops_ui.i18n import normalize_locale
from anime_ops_ui.services.autobangumi_client import AutoBangumiClient


def _locale_text(locale: str | None, *, en: str, zh: str) -> str:
    return en if normalize_locale(locale) == "en" else zh


def _system_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _autobangumi_client() -> AutoBangumiClient:
    main_module = runtime_main_module()
    autobangumi_port = int(main_module._env("AUTOBANGUMI_PORT", "7892"))
    autobangumi_base_url = (
        main_module._env("AUTOBANGUMI_API_URL", "").strip()
        or f"http://autobangumi:{autobangumi_port}"
    )
    return AutoBangumiClient(
        base_url=autobangumi_base_url,
        username=main_module._env("AUTOBANGUMI_USERNAME", ""),
        password=main_module._env("AUTOBANGUMI_PASSWORD", ""),
    )


def _normalize_url(url: str) -> str:
    return str(url or "").strip().rstrip("/")


def _rss_title(item: dict[str, Any], *, locale: str | None = None) -> str:
    for key in ("name", "title", "official_title", "rule_name"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    rss_id = item.get("id")
    if rss_id is not None:
        return _locale_text(locale, en=f"RSS #{rss_id}", zh=f"RSS #{rss_id}")
    return _locale_text(locale, en="Unnamed source", zh="未命名订阅")


def _connection_state_info(raw_value: str | None, *, locale: str | None = None) -> tuple[str, str]:
    normalized = str(raw_value or "").strip().lower()
    if not normalized:
        return "unknown", _locale_text(locale, en="Unchecked", zh="未检查")

    connected_markers = {"connected", "success", "ok", "healthy", "已连接"}
    issue_markers = {"error", "failed", "timeout", "abnormal", "异常", "失败", "超时"}

    if normalized in connected_markers or "connect" in normalized or "连接" in normalized:
        return "connected", _locale_text(locale, en="Connected", zh="已连接")
    if normalized in issue_markers or "error" in normalized or "异常" in normalized or "失败" in normalized:
        return "issue", _locale_text(locale, en="Issue", zh="连接异常")
    return "unknown", _locale_text(locale, en="Unchecked", zh="未检查")


def _enabled_state_label(enabled: bool, *, locale: str | None = None) -> str:
    return _locale_text(locale, en="Enabled", zh="启用") if enabled else _locale_text(locale, en="Disabled", zh="禁用")


def _last_checked_label(raw_value: Any) -> str | None:
    value = str(raw_value or "").strip()
    return value or None


def _poster_url(
    *,
    request_scheme: str,
    request_host: str,
    poster_link: str | None,
) -> str | None:
    poster_path = str(poster_link or "").strip()
    if not poster_path:
        return None
    if poster_path.startswith("http://") or poster_path.startswith("https://"):
        return poster_path

    main_module = runtime_main_module()
    autobangumi_port = int(main_module._env("AUTOBANGUMI_PORT", "7892"))
    host = request_host.strip() or "127.0.0.1"
    scheme = request_scheme.strip() or "http"
    return f"{scheme}://{host}:{autobangumi_port}/{poster_path.lstrip('/')}"


def _season_label(payload: dict[str, Any]) -> str | None:
    season_raw = str(payload.get("season_raw") or "").strip()
    if season_raw:
        return season_raw
    season_value = payload.get("season")
    if season_value is None:
        return None
    try:
        return f"S{int(season_value)}"
    except (TypeError, ValueError):
        return None


def _preview_tags(payload: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for key in ("dpi", "subtitle", "group_name"):
        value = str(payload.get(key) or "").strip()
        if value and value not in tags:
            tags.append(value)
    return tags[:4]


def _response_message(payload: dict[str, Any], *, locale: str | None = None, fallback_en: str, fallback_zh: str) -> str:
    key = "msg_en" if normalize_locale(locale) == "en" else "msg_zh"
    value = str(payload.get(key) or "").strip()
    if value:
        return value
    return _locale_text(locale, en=fallback_en, zh=fallback_zh)


def _require_success(payload: dict[str, Any], *, locale: str | None = None) -> None:
    if payload.get("status") is False:
        raise RuntimeError(
            _response_message(
                payload,
                locale=locale,
                fallback_en="AutoBangumi request failed.",
                fallback_zh="AutoBangumi 请求失败。",
            )
        )


def _find_duplicate(sources: list[dict[str, Any]], *, url: str) -> dict[str, Any] | None:
    normalized_url = _normalize_url(url)
    for item in sources:
        if _normalize_url(str(item.get("url") or "")) == normalized_url:
            return item
    return None


def build_rss_list_payload(*, locale: str | None = None) -> dict[str, Any]:
    client = _autobangumi_client()
    items: list[tuple[int, str, dict[str, Any]]] = []
    for item in client.fetch_rss_sources():
        enabled = bool(item.get("enabled"))
        connection_state, connection_state_label = _connection_state_info(
            item.get("connection_status"),
            locale=locale,
        )
        list_item = RSSListItem(
            rssId=int(item.get("id") or 0),
            title=_rss_title(item, locale=locale),
            connectionState=connection_state,
            connectionStateLabel=connection_state_label,
            enabled=enabled,
            enabledStateLabel=_enabled_state_label(enabled, locale=locale),
            lastCheckedLabel=_last_checked_label(item.get("last_checked_at")),
        ).model_dump()
        items.append((0 if enabled else 1, list_item["title"].lower(), list_item))

    items.sort(key=lambda entry: (entry[0], entry[1]))
    return {
        "items": [entry[2] for entry in items],
        "updatedAt": _system_timestamp(),
    }


def analyze_rss_payload(
    *,
    url: str,
    locale: str | None = None,
    request_scheme: str = "http",
    request_host: str = "127.0.0.1",
) -> dict[str, Any]:
    client = _autobangumi_client()
    sources = client.fetch_rss_sources()
    duplicate = _find_duplicate(sources, url=url)
    analysis = client.analyze_rss(url=url)
    _require_success(analysis, locale=locale)

    preview = RSSPreviewItem(
        title=str(analysis.get("official_title") or analysis.get("rule_name") or analysis.get("title_raw") or _rss_title(analysis, locale=locale)),
        originalTitle=str(analysis.get("title_raw") or "").strip() or None,
        posterUrl=_poster_url(
            request_scheme=request_scheme,
            request_host=request_host,
            poster_link=analysis.get("poster_link"),
        ),
        year=str(analysis.get("year") or "").strip() or None,
        season=_season_label(analysis),
        tags=_preview_tags(analysis),
    ).model_dump()

    if preview.get("originalTitle") == preview["title"]:
        preview["originalTitle"] = None

    return {
        "url": _normalize_url(url),
        "duplicate": duplicate is not None,
        "duplicateRssId": int(duplicate.get("id")) if isinstance(duplicate, dict) and duplicate.get("id") is not None else None,
        "preview": preview,
    }


def subscribe_rss_payload(*, url: str, locale: str | None = None) -> dict[str, Any]:
    client = _autobangumi_client()
    sources = client.fetch_rss_sources()
    duplicate = _find_duplicate(sources, url=url)
    if duplicate is not None:
        return {
            "ok": False,
            "duplicate": True,
            "rssId": int(duplicate.get("id") or 0),
            "message": _locale_text(locale, en="RSS source already exists.", zh="RSS 源已存在。"),
        }

    analysis = client.analyze_rss(url=url)
    _require_success(analysis, locale=locale)
    response = client.subscribe_rss(url=url, bangumi_payload=analysis)
    _require_success(response, locale=locale)

    created = _find_duplicate(client.fetch_rss_sources(), url=url)
    return {
        "ok": True,
        "duplicate": False,
        "rssId": int(created.get("id") or 0) if created is not None else None,
        "message": _response_message(
            response,
            locale=locale,
            fallback_en="RSS source subscribed.",
            fallback_zh="RSS 订阅成功。",
        ),
    }


def enable_rss_payload(*, rss_id: int, locale: str | None = None) -> dict[str, Any]:
    response = _autobangumi_client().enable_rss(rss_id=rss_id)
    _require_success(response, locale=locale)
    return {
        "ok": True,
        "action": "enable",
        "rssId": rss_id,
        "message": _response_message(
            response,
            locale=locale,
            fallback_en="RSS source enabled.",
            fallback_zh="RSS 已启用。",
        ),
    }


def disable_rss_payload(*, rss_id: int, locale: str | None = None) -> dict[str, Any]:
    response = _autobangumi_client().disable_rss(rss_id=rss_id)
    _require_success(response, locale=locale)
    return {
        "ok": True,
        "action": "disable",
        "rssId": rss_id,
        "message": _response_message(
            response,
            locale=locale,
            fallback_en="RSS source disabled.",
            fallback_zh="RSS 已禁用。",
        ),
    }


def delete_rss_payload(*, rss_id: int, locale: str | None = None) -> dict[str, Any]:
    response = _autobangumi_client().delete_rss(rss_id=rss_id)
    return {
        "ok": True,
        "action": "delete",
        "rssId": rss_id,
        "message": _response_message(
            response,
            locale=locale,
            fallback_en="RSS source deleted.",
            fallback_zh="RSS 已删除。",
        ),
    }
