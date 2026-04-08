from anime_ops_ui import main as main_module
from anime_ops_ui.services.log_service import list_log_events
from anime_ops_ui.services.overview_service import build_service_summary
from anime_ops_ui.services.postprocessor_service import build_postprocessor_snapshot
from anime_ops_ui.services.review_service import get_manual_review_item, list_manual_review_items
from anime_ops_ui.services.tailscale_service import build_tailscale_snapshot


def test_build_service_summary_counts_tailscaled():
    summary = build_service_summary(
        containers={
            "jellyfin": {"status": "running"},
            "qbittorrent": {"status": "exited"},
        },
        tailscale_running=True,
    )

    assert summary["value"] == "2 online"
    assert summary["detail"] == "3 total · Docker + tailscaled"


def test_list_log_events_delegates(monkeypatch):
    payload = {"title": "Logs", "items": []}
    monkeypatch.setattr(main_module, "build_logs_payload", lambda **kwargs: payload)

    assert list_log_events(source="ops-ui", level="info", search="restart") == payload


def test_review_service_wrappers_delegate(monkeypatch):
    items_payload = {"title": "Ops Review", "items": []}
    item_payload = {"title": "Review Detail", "item": {"id": "abc"}}
    monkeypatch.setattr(main_module, "build_manual_review_payload", lambda: items_payload)
    monkeypatch.setattr(main_module, "build_manual_review_item_payload", lambda item_id: {**item_payload, "item_id": item_id})

    assert list_manual_review_items() == items_payload
    assert get_manual_review_item("abc")["item_id"] == "abc"


def test_postprocessor_and_tailscale_wrappers_delegate(monkeypatch):
    postprocessor_payload = {"title": "Postprocessor"}
    tailscale_payload = {"title": "Tailscale"}
    monkeypatch.setattr(main_module, "build_postprocessor_payload", lambda: postprocessor_payload)
    monkeypatch.setattr(main_module, "build_tailscale_payload", lambda: tailscale_payload)

    assert build_postprocessor_snapshot() == postprocessor_payload
    assert build_tailscale_snapshot() == tailscale_payload
