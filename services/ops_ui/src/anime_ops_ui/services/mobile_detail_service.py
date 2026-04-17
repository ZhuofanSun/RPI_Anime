def build_detail_payload(app_item_id: str) -> dict:
    if app_item_id.endswith("unmapped"):
        return {
            "appItemId": app_item_id,
            "mappingStatus": "unmapped",
            "title": "示例条目",
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
        }

    return {
        "appItemId": app_item_id,
        "mappingStatus": "mapped",
        "title": "灵笼 第一季",
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
    }
