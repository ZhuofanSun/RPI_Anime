from anime_ops_ui.domain.mobile_models import HomeFollowingItem


def build_following_payload() -> dict:
    return _build_channel_payload(_following_items())


def build_favorites_payload() -> dict:
    return _build_channel_payload(_favorites_items())


def _build_channel_payload(items: list[HomeFollowingItem]) -> dict:
    return {"items": [item.model_dump() for item in items], "updatedAt": "2099-01-01T00:00:00Z"}


def _following_items() -> list[HomeFollowingItem]:
    return [
        HomeFollowingItem(
            appItemId="app_following_demo_1",
            title="灵笼 第一季",
            posterUrl="https://example.com/poster-1.jpg",
            unread=True,
            mappingStatus="mapped",
            jellyfinSeriesId="series_123",
            availabilityState="mapped_playable",
        ),
        HomeFollowingItem(
            appItemId="app_following_demo_2",
            title="凡人修仙传",
            posterUrl="https://example.com/poster-2.jpg",
            unread=False,
            mappingStatus="mapped",
            jellyfinSeriesId="series_124",
            availabilityState="mapped_playable",
        ),
        HomeFollowingItem(
            appItemId="app_following_demo_3",
            title="有兽焉",
            posterUrl="https://example.com/poster-3.jpg",
            unread=True,
            mappingStatus="mapped",
            jellyfinSeriesId="series_125",
            availabilityState="mapped_unplayable",
        ),
        HomeFollowingItem(
            appItemId="app_following_demo_4",
            title="镇魂街 第一季",
            posterUrl="https://example.com/poster-4.jpg",
            unread=False,
            mappingStatus="mapped",
            jellyfinSeriesId="series_126",
            availabilityState="mapped_playable",
        ),
        HomeFollowingItem(
            appItemId="app_following_demo_5",
            title="时光代理人",
            posterUrl="https://example.com/poster-5.jpg",
            unread=True,
            mappingStatus="mapped",
            jellyfinSeriesId="series_127",
            availabilityState="mapped_playable",
        ),
        HomeFollowingItem(
            appItemId="app_following_demo_unmapped",
            title="天官赐福",
            posterUrl="https://example.com/poster-6.jpg",
            unread=False,
            mappingStatus="unmapped",
            jellyfinSeriesId=None,
            availabilityState="subscription_only",
        ),
    ]


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
