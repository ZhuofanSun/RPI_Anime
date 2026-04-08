from __future__ import annotations

from typing import Any


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
