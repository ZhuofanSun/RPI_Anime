from __future__ import annotations

from typing import Any


def list_log_events(
    *,
    source: str | None = None,
    level: str | None = None,
    search: str | None = None,
    limit: int = 300,
) -> dict[str, Any]:
    from anime_ops_ui import main as main_module

    return main_module.build_logs_payload(source=source, level=level, search=search, limit=limit)
