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


def _service_health_rows(*, locale: str | None = None) -> list[dict]:
    try:
        overview = build_overview_payload()
        rows = {str(item.get("id")): item for item in overview.get("service_rows", []) if isinstance(item, dict)}
    except Exception:
        rows = {}

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
            "state": "online",
            "detail": _locale_text(locale, en="app-facing backend", zh="面向 App 的后端"),
        }
    )
    return selected


def build_me_context(*, locale: str | None = None) -> dict:
    return {
        "identity": {
            "serverLabel": "RPI Anime",
            "connectionState": "online",
        },
        "about": {"backendVersion": _backend_version()},
        "serviceHealth": _service_health_rows(locale=locale),
    }
