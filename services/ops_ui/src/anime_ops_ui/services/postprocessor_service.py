from __future__ import annotations

from typing import Any


def build_postprocessor_snapshot() -> dict[str, Any]:
    from anime_ops_ui import main as main_module

    return main_module.build_postprocessor_payload()
