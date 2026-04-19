from datetime import datetime, timezone

from anime_ops_ui.domain.mobile_models import HomeFollowingItem
from anime_ops_ui.services.mobile_seasonal_service import build_following_items


def build_following_payload(*, public_host: str | None = None, public_base_url: str | None = None) -> dict:
    return _build_channel_payload(_following_items(public_host=public_host, public_base_url=public_base_url))


def build_favorites_payload() -> dict:
    return _build_channel_payload(_favorites_items())


def _build_channel_payload(items: list[HomeFollowingItem]) -> dict:
    return {
        "items": [item.model_dump() for item in items],
        "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _following_items(*, public_host: str | None = None, public_base_url: str | None = None) -> list[HomeFollowingItem]:
    return build_following_items(public_host=public_host, public_base_url=public_base_url)


def _favorites_items() -> list[HomeFollowingItem]:
    return [
        HomeFollowingItem(
            appItemId="app_collection_demo_1",
            title="罗小黑战记",
            posterUrl="https://example.com/collection-poster-1.jpg",
            unread=False,
            mappingStatus="mapped",
            jellyfinSeriesId="collection_123",
            availabilityState="mapped_playable",
        ),
        HomeFollowingItem(
            appItemId="app_collection_demo_2",
            title="猫之茗",
            posterUrl="https://example.com/collection-poster-2.jpg",
            unread=True,
            mappingStatus="mapped",
            jellyfinSeriesId="collection_124",
            availabilityState="mapped_playable",
        ),
        HomeFollowingItem(
            appItemId="app_collection_demo_3",
            title="第一序列",
            posterUrl="https://example.com/collection-poster-3.jpg",
            unread=False,
            mappingStatus="mapped",
            jellyfinSeriesId="collection_125",
            availabilityState="mapped_playable",
        ),
        HomeFollowingItem(
            appItemId="app_collection_demo_4",
            title="火凤燎原",
            posterUrl="https://example.com/collection-poster-4.jpg",
            unread=False,
            mappingStatus="mapped",
            jellyfinSeriesId="collection_126",
            availabilityState="mapped_playable",
        ),
        HomeFollowingItem(
            appItemId="app_collection_demo_5",
            title="天宝伏妖录",
            posterUrl="https://example.com/collection-poster-5.jpg",
            unread=True,
            mappingStatus="mapped",
            jellyfinSeriesId="collection_127",
            availabilityState="mapped_playable",
        ),
        HomeFollowingItem(
            appItemId="app_collection_demo_6",
            title="大理寺日志",
            posterUrl="https://example.com/collection-poster-6.jpg",
            unread=False,
            mappingStatus="mapped",
            jellyfinSeriesId="collection_128",
            availabilityState="mapped_playable",
        ),
    ]
