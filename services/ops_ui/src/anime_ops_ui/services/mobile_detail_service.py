from anime_ops_ui.services.mobile_collection_service import get_collection_item
from anime_ops_ui.services.mobile_media_service import build_mobile_poster_url
from anime_ops_ui.services.mobile_seasonal_service import build_recent_seasonal, get_seasonal_item


def build_detail_payload(
    app_item_id: str,
    *,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> dict:
    seasonal_item = get_seasonal_item(
        app_item_id,
        public_host=public_host,
        public_base_url=public_base_url,
    )
    if seasonal_item is not None:
        return _build_seasonal_detail_payload(
            seasonal_item,
            public_host=public_host,
            public_base_url=public_base_url,
        )

    collection_item = get_collection_item(
        app_item_id,
        public_host=public_host,
        public_base_url=public_base_url,
    )
    if collection_item is not None:
        return collection_item

    title = "示例条目"
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
            "recentSeasonal": _recent_seasonal_items(public_host=public_host, public_base_url=public_base_url),
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
        "recentSeasonal": _recent_seasonal_items(public_host=public_host, public_base_url=public_base_url),
    }


def _recent_seasonal_items(
    *,
    exclude_app_item_id: str | None = None,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> list[dict]:
    items = build_recent_seasonal(
        exclude_app_item_id=exclude_app_item_id,
        public_host=public_host,
        public_base_url=public_base_url,
    )
    return [
        {
            **item,
            "posterUrl": build_mobile_poster_url(
                poster_link=str(item.get("posterUrl") or "").strip() or None,
                public_base_url=public_base_url,
            )
            or str(item.get("posterUrl") or ""),
        }
        for item in items
    ]


def _build_seasonal_detail_payload(
    item: dict[str, object],
    *,
    public_host: str | None = None,
    public_base_url: str | None = None,
) -> dict:
    app_item_id = str(item["appItemId"])
    title = str(item["title"])
    poster_url = build_mobile_poster_url(
        poster_link=str(item.get("posterUrl") or "").strip() or None,
        public_base_url=public_base_url,
    ) or str(item.get("posterUrl") or "https://example.com/poster.jpg")
    mapping_status = str(item.get("mappingStatus") or "unmapped")
    availability_state = str(item.get("availabilityState") or "subscription_only")
    playable = availability_state == "mapped_playable"
    detail = item.get("detail") if isinstance(item.get("detail"), dict) else {}
    season_label = str(detail.get("season_label") or "2026 春")
    tags = [value for value in [detail.get("source"), detail.get("group_name"), detail.get("dpi")] if value][:5]
    overview = str(detail.get("review_reason") or detail.get("subtitle") or ("示例简介" if playable else "整理中"))

    return {
        "appItemId": app_item_id,
        "mappingStatus": mapping_status,
        "title": title,
        "heroState": "playable_primed" if playable else "unavailable",
        "hero": {
            "posterUrl": poster_url,
            "backdropUrl": poster_url,
            **(
                {
                    "latestPlayableEpisodeId": "latest",
                    "primedLabel": "第 1 集",
                    "playTarget": "zFuse",
                }
                if playable
                else {}
            ),
        },
        "summary": {
            "freshness": "本周更新",
            "availableEpisodeCount": 1 if playable else 0,
            "seasonLabel": season_label,
            "score": "10.0",
            "tags": tags,
        },
        "overview": overview,
        "seasons": [{"id": "season_1", "label": "第一季", "selected": True}] if playable else [],
        "episodes": [{"id": "latest", "label": "第 1 集", "focused": True, "unread": True}] if playable else [],
        "recentSeasonal": _recent_seasonal_items(
            exclude_app_item_id=app_item_id,
            public_host=public_host,
            public_base_url=public_base_url,
        ),
    }
