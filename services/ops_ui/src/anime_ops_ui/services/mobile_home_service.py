from datetime import datetime, timezone

from anime_ops_ui.domain.mobile_models import HomeFollowingItem
from anime_ops_ui.services.mobile_collection_service import build_favorite_items
from anime_ops_ui.services.mobile_seasonal_service import build_following_items


def build_following_payload(*, public_host: str | None = None, public_base_url: str | None = None) -> dict:
    return _build_channel_payload(_following_items(public_host=public_host, public_base_url=public_base_url))


def build_favorites_payload(*, public_base_url: str | None = None) -> dict:
    return _build_channel_payload(_favorites_items(public_base_url=public_base_url))


def _build_channel_payload(items: list[HomeFollowingItem]) -> dict:
    return {
        "items": [item.model_dump() for item in items],
        "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _following_items(*, public_host: str | None = None, public_base_url: str | None = None) -> list[HomeFollowingItem]:
    return build_following_items(public_host=public_host, public_base_url=public_base_url)


def _favorites_items(*, public_base_url: str | None = None) -> list[HomeFollowingItem]:
    return build_favorite_items(public_base_url=public_base_url)
