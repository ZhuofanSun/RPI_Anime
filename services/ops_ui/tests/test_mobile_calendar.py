from datetime import date, timedelta

from anime_ops_ui.domain.mobile_models import CalendarDayBucket, CalendarDayItem


def test_mobile_calendar_returns_day_bucketed_contract(client, monkeypatch):
    from anime_ops_ui.services import mobile_calendar_service

    bucket = CalendarDayBucket(
        date="2026-04-18",
        weekdayLabel="周六",
        dayLabel="04/18",
        items=[
            CalendarDayItem(
                appItemId="app_following_ab_42",
                title="灵笼 第一季",
                posterUrl="https://example.com/poster.jpg",
                unread=True,
                availabilityState="mapped_playable",
            )
        ],
    )
    monkeypatch.setattr(
        mobile_calendar_service,
        "build_calendar_buckets",
        lambda *, focus_date, public_host=None, public_base_url=None, now=None: [bucket] * 7,
    )
    response = client.get("/api/mobile/calendar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["focusDate"] == "2026-04-18"
    assert payload["updatedAt"] != "2099-01-01T00:00:00Z"
    assert len(payload["days"]) == 7
    focused = payload["days"][0]
    assert focused["weekdayLabel"] == "周六"
    assert focused["dayLabel"] == "04/18"
    assert focused["items"][0]["appItemId"] == "app_following_ab_42"
    assert {"appItemId", "title", "posterUrl", "availabilityState", "unread"} <= set(focused["items"][0])


def test_mobile_calendar_accepts_focus_date_query(client, monkeypatch):
    from anime_ops_ui.services import mobile_calendar_service

    base_date = date(2026, 4, 13)
    monkeypatch.setattr(
        mobile_calendar_service,
        "build_calendar_buckets",
        lambda *, focus_date, public_host=None, public_base_url=None, now=None: [
            CalendarDayBucket(
                date=(base_date + timedelta(days=index)).isoformat(),
                weekdayLabel=f"周{index + 1}",
                dayLabel=(base_date + timedelta(days=index)).strftime("%m/%d"),
                items=[],
            )
            for index in range(7)
        ],
    )
    response = client.get("/api/mobile/calendar", params={"focusDate": "2026-04-17", "window": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["focusDate"] == "2026-04-17"
    assert len(payload["days"]) == 7
    assert payload["days"][0]["date"] == "2026-04-13"
    assert payload["days"][-1]["date"] == "2026-04-19"


def test_mobile_calendar_uses_request_host_for_generated_content(client, monkeypatch):
    from anime_ops_ui.services import mobile_calendar_service

    captured: dict[str, str | None] = {}
    bucket = CalendarDayBucket(
        date="2026-04-18",
        weekdayLabel="周六",
        dayLabel="04/18",
        items=[],
    )

    def fake_build_calendar_buckets(*, focus_date, public_host=None, public_base_url=None, now=None):
        captured["public_host"] = public_host
        return [bucket] * 7

    monkeypatch.setattr(mobile_calendar_service, "build_calendar_buckets", fake_build_calendar_buckets)

    response = client.get("/api/mobile/calendar", headers={"host": "100.123.232.73:3000"})

    assert response.status_code == 200
    assert captured["public_host"] == "100.123.232.73"
