from anime_ops_ui.services.overview_service import build_overview_payload


def _service_health_rows() -> list[dict]:
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
            "state": "online" if rows else "unknown",
            "detail": "app-facing backend",
        }
    )
    return selected


def build_me_context() -> dict:
    return {
        "identity": {
            "serverLabel": "RPI Anime",
            "connectionState": "在线",
            "connectionTone": "success",
        },
        "about": {"version": "0.1.0", "backendVersion": "ops-ui dev"},
        "serviceHealth": _service_health_rows(),
    }
