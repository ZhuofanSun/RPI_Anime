import pytest
from fastapi.testclient import TestClient

from anime_ops_ui.main import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data_root = tmp_path / "anime-data"
    state_root = tmp_path / "ops-ui-state"
    event_log_path = tmp_path / "events.json"
    monkeypatch.setenv("ANIME_DATA_ROOT", str(data_root))
    monkeypatch.setenv("OPS_UI_STATE_ROOT", str(state_root))
    monkeypatch.setenv("OPS_EVENT_LOG_PATH", str(event_log_path))

    with TestClient(create_app()) as test_client:
        yield test_client
