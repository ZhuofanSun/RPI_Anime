_DETAIL_TITLES = {
    "app_following_demo": "灵笼 第一季",
    "app_following_demo_1": "灵笼 第一季",
    "app_following_demo_2": "凡人修仙传",
    "app_following_demo_3": "有兽焉",
    "app_following_demo_4": "镇魂街 第一季",
    "app_following_demo_5": "时光代理人",
    "app_following_demo_unmapped": "天官赐福",
    "app_following_unmapped": "示例条目",
    "app_collection_demo_1": "罗小黑战记",
    "app_collection_demo_2": "猫之茗",
    "app_collection_demo_3": "第一序列",
    "app_collection_demo_4": "火凤燎原",
    "app_collection_demo_5": "天宝伏妖录",
    "app_collection_demo_6": "大理寺日志",
}


def build_detail_payload(app_item_id: str) -> dict:
    title = _DETAIL_TITLES.get(app_item_id, "示例条目")
    if app_item_id.endswith("unmapped"):
        return {
            "appItemId": app_item_id,
            "mappingStatus": "unmapped",
            "title": title,
            "heroState": "unavailable",
            "hero": {
                "posterUrl": "https://example.com/poster.jpg",
                "backdropUrl": "https://example.com/backdrop.jpg",
            },
            "summary": {
                "freshness": "本周未更新",
                "availableEpisodeCount": 0,
                "seasonLabel": "2026 春",
                "score": "10.0",
                "tags": [],
            },
            "overview": "整理中",
            "seasons": [],
            "episodes": [],
            "recentSeasonal": _recent_seasonal_items(),
        }

    return {
        "appItemId": app_item_id,
        "mappingStatus": "mapped",
        "title": title,
        "heroState": "playable_primed",
        "hero": {
            "posterUrl": "https://example.com/poster.jpg",
            "backdropUrl": "https://example.com/backdrop.jpg",
            "latestPlayableEpisodeId": "ep_16",
            "primedLabel": "第 16 集",
            "playTarget": "zFuse",
        },
        "summary": {
            "freshness": "本周未更新",
            "availableEpisodeCount": 16,
            "seasonLabel": "2019 夏",
            "score": "9.6",
            "tags": ["科幻"],
        },
        "overview": "示例简介",
        "seasons": [{"id": "season_1", "label": "第一季", "selected": True}],
        "episodes": [{"id": "ep_16", "label": "第 16 集", "focused": True, "unread": True}],
        "recentSeasonal": _recent_seasonal_items(),
    }


def _recent_seasonal_items() -> list[dict]:
    return [
        {
            "appItemId": "app_following_demo_5",
            "title": "时光代理人",
            "posterUrl": "https://example.com/poster-5.jpg",
            "subtitle": "更新至第 12 集",
        },
        {
            "appItemId": "app_following_demo_2",
            "title": "凡人修仙传",
            "posterUrl": "https://example.com/poster-2.jpg",
            "subtitle": "更新至第 176 集",
        },
        {
            "appItemId": "app_following_demo_4",
            "title": "镇魂街 第一季",
            "posterUrl": "https://example.com/poster-4.jpg",
            "subtitle": "更新至第 24 集",
        },
        {
            "appItemId": "app_following_demo_3",
            "title": "有兽焉",
            "posterUrl": "https://example.com/poster-3.jpg",
            "subtitle": "整理中",
        },
    ]
