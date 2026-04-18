def test_mobile_calendar_returns_day_bucketed_contract(client):
    response = client.get("/api/mobile/calendar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["focusDate"] == "2026-04-18"
    assert payload["updatedAt"] == "2099-01-01T00:00:00Z"
    assert len(payload["days"]) == 7
    focused = next(item for item in payload["days"] if item["date"] == "2026-04-18")
    assert focused["weekdayLabel"] == "周六"
    assert focused["dayLabel"] == "04/18"
    assert focused["items"][0]["appItemId"] == "app_following_demo_1"
    assert {"appItemId", "title", "posterUrl", "availabilityState", "unread"} <= set(focused["items"][0])


def test_mobile_calendar_accepts_focus_date_query(client):
    response = client.get("/api/mobile/calendar", params={"focusDate": "2026-04-17", "window": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["focusDate"] == "2026-04-17"
    assert len(payload["days"]) == 5
    assert payload["days"][0]["date"] == "2026-04-15"
    assert payload["days"][-1]["date"] == "2026-04-19"
