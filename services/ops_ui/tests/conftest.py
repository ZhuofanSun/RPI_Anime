import pytest
from fastapi.testclient import TestClient

from anime_ops_ui import main as main_module
from anime_ops_ui.main import create_app
from anime_ops_ui.mobile.auth import embedded_password, embedded_username


@pytest.fixture()
def anonymous_client(tmp_path, monkeypatch):
    data_root = tmp_path / "anime-data"
    state_root = tmp_path / "ops-ui-state"
    event_log_path = tmp_path / "events.json"
    monkeypatch.setenv("ANIME_DATA_ROOT", str(data_root))
    monkeypatch.setenv("OPS_UI_STATE_ROOT", str(state_root))
    monkeypatch.setenv("OPS_EVENT_LOG_PATH", str(event_log_path))
    main_module.HISTORY_STATE = None

    app = create_app(enable_lifespan=False)
    app.state.test_paths = {
        "data_root": data_root,
        "state_root": state_root,
        "event_log_path": event_log_path,
    }

    with TestClient(app) as test_client:
        yield test_client

    main_module.HISTORY_STATE = None


@pytest.fixture()
def client(anonymous_client):
    response = anonymous_client.post(
        "/api/mobile/auth/session",
        json={
            "username": embedded_username(),
            "password": embedded_password(),
        },
    )
    token = response.json()["token"]
    anonymous_client.headers.update({"Authorization": f"Bearer {token}"})
    return anonymous_client
