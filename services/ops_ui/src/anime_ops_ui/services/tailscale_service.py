from __future__ import annotations

from typing import Any


def build_tailscale_snapshot() -> dict[str, Any]:
    from anime_ops_ui import main as main_module

    return main_module.build_tailscale_payload()
