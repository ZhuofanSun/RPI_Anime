from datetime import datetime, timezone


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = datetime(2026, 4, 20, 15, 30, tzinfo=timezone.utc)
        return base if tz is None else base.astimezone(tz)


def test_mobile_calendar_defaults_focus_date_to_current_local_date(client, monkeypatch):
    from anime_ops_ui.services import mobile_calendar_service

    monkeypatch.setattr(mobile_calendar_service, "datetime", _FrozenDateTime)
    monkeypatch.setattr(
        mobile_calendar_service,
        "build_calendar_buckets",
        lambda focus_date, public_host=None, public_base_url=None: [],
    )

    response = client.get("/api/mobile/calendar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["focusDate"] == "2026-04-20"
    assert payload["updatedAt"] == "2026-04-20T15:30:00Z"


def test_mobile_calendar_invalid_focus_date_falls_back_to_current_local_date(client, monkeypatch):
    from anime_ops_ui.services import mobile_calendar_service

    monkeypatch.setattr(mobile_calendar_service, "datetime", _FrozenDateTime)
    monkeypatch.setattr(
        mobile_calendar_service,
        "build_calendar_buckets",
        lambda focus_date, public_host=None, public_base_url=None: [],
    )

    response = client.get("/api/mobile/calendar?focusDate=bad-date")

    assert response.status_code == 200
    payload = response.json()
    assert payload["focusDate"] == "2026-04-20"
