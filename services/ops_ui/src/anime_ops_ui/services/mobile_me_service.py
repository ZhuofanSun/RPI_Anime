from fastapi import HTTPException


def _allowed_restart_targets() -> tuple[str, ...]:
    return ("jellyfin", "qbittorrent", "autobangumi", "postprocessor", "homepage")


def build_me_context() -> dict:
    return {
        "identity": {
            "serverLabel": "RPI Anime",
            "connectionState": "在线",
            "connectionTone": "success",
        },
        "about": {"version": "0.1.0", "backendVersion": "ops-ui dev"},
        "maintenance": {
            "serviceActions": [
                {"target": "jellyfin", "label": "重启 Jellyfin", "enabled": True},
                {"target": "qbittorrent", "label": "重启 qBittorrent", "enabled": True},
                {"target": "autobangumi", "label": "重启 AutoBangumi", "enabled": True},
                {"target": "postprocessor", "label": "重启 Postprocessor", "enabled": True},
                {"target": "homepage", "label": "重启 Ops UI", "enabled": True},
            ],
            "restartAll": {"label": "全部重启", "enabled": True},
        },
    }


def schedule_restart(target: str) -> dict:
    if target not in _allowed_restart_targets():
        raise HTTPException(status_code=404, detail=f"unknown restart target: {target}")
    return {"ok": True, "scheduled": True, "target": target, "message": f"已安排 {target} 重启。"}
