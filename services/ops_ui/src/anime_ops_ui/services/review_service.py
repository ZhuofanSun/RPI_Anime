from __future__ import annotations

from typing import Any


def list_manual_review_items() -> dict[str, Any]:
    from anime_ops_ui import main as main_module

    return main_module.build_manual_review_payload()


def get_manual_review_item(item_id: str) -> dict[str, Any]:
    from anime_ops_ui import main as main_module

    return main_module.build_manual_review_item_payload(item_id)
