from importlib.metadata import PackageNotFoundError, version as package_version

from anime_ops_ui.i18n import normalize_locale
from anime_ops_ui.services.overview_service import build_overview_payload


def _locale_text(locale: str | None, *, en: str, zh: str) -> str:
    return en if normalize_locale(locale) == "en" else zh


def _backend_version() -> str:
    try:
        return package_version("anime-ops-ui")
    except PackageNotFoundError:
        return "0.1.0"


def _service_rows(overview: dict | None) -> dict[str, dict]:
    if not isinstance(overview, dict):
        return {}
    return {str(item.get("id")): item for item in overview.get("service_rows", []) if isinstance(item, dict)}


def _service_health_rows(*, overview: dict | None, locale: str | None = None, overview_available: bool) -> list[dict]:
    rows = _service_rows(overview)
    selected: list[dict] = []
    for target in ("jellyfin", "qbittorrent", "autobangumi", "postprocessor", "tailscale"):
        row = rows.get(target)
        if not row:
            continue
        selected.append(
            {
                "target": target,
                "label": row.get("name") or target,
                "state": str(row.get("status") or "unknown"),
                "detail": row.get("uptime") or row.get("meta"),
            }
        )

    selected.append(
        {
            "target": "homepage",
            "label": "Ops UI",
            "state": "online" if overview_available else "offline",
            "detail": _locale_text(
                locale,
                en="app-facing backend" if overview_available else "backend unavailable",
                zh="面向 App 的后端" if overview_available else "后端不可用",
            ),
        }
    )
    return selected


def build_me_context(*, locale: str | None = None, public_host: str | None = None) -> dict:
    try:
        overview = build_overview_payload(public_host=public_host)
        overview_available = True
    except Exception:
        overview = None
        overview_available = False

    server_label = str((overview or {}).get("host") or "").strip() or "RPI Anime"

    return {
        "identity": {
            "serverLabel": server_label,
            "connectionState": "online" if overview_available else "offline",
        },
        "about": {"backendVersion": _backend_version()},
        "serviceHealth": _service_health_rows(
            overview=overview,
            locale=locale,
            overview_available=overview_available,
        ),
    }
