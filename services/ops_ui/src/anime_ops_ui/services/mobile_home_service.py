from anime_ops_ui.domain.mobile_models import HomeFollowingItem


def build_following_payload() -> dict:
    items = [
        HomeFollowingItem(
            appItemId="app_following_demo_1",
            title="灵笼 第一季",
            posterUrl="https://example.com/poster-1.jpg",
            unread=True,
            mappingStatus="mapped",
        ),
        HomeFollowingItem(
            appItemId="app_following_demo_2",
            title="凡人修仙传",
            posterUrl="https://example.com/poster-2.jpg",
            unread=False,
            mappingStatus="mapped",
        ),
        HomeFollowingItem(
            appItemId="app_following_demo_3",
            title="有兽焉",
            posterUrl="https://example.com/poster-3.jpg",
            unread=True,
            mappingStatus="mapped",
        ),
        HomeFollowingItem(
            appItemId="app_following_demo_4",
            title="镇魂街 第一季",
            posterUrl="https://example.com/poster-4.jpg",
            unread=False,
            mappingStatus="mapped",
        ),
        HomeFollowingItem(
            appItemId="app_following_demo_5",
            title="时光代理人",
            posterUrl="https://example.com/poster-5.jpg",
            unread=True,
            mappingStatus="mapped",
        ),
        HomeFollowingItem(
            appItemId="app_following_demo_unmapped",
            title="天官赐福",
            posterUrl="https://example.com/poster-6.jpg",
            unread=False,
            mappingStatus="unmapped",
        ),
    ]
    return {"items": [item.model_dump() for item in items], "updatedAt": "2099-01-01T00:00:00Z"}
