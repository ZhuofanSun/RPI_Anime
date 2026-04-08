from anime_ops_ui.services.autobangumi_client import AutoBangumiClient


class _FakeResponse:
    def __init__(self, *, status_code=200, text="{}", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json_data = {} if json_data is None else json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


class _FakeSession:
    def __init__(self):
        self.posts = []
        self.gets = []

    def post(self, url, data=None, timeout=5):
        self.posts.append((url, data, timeout))
        return _FakeResponse(text='{"detail":"ok"}', json_data={"detail": "ok"})

    def get(self, url, timeout=5):
        self.gets.append((url, timeout))
        return _FakeResponse(
            json_data=[
                {
                    "id": 9,
                    "official_title": "尖帽子的魔法工房",
                    "air_weekday": 0,
                    "poster_link": "posters/5cac94c7.jpg",
                    "needs_review": False,
                    "archived": False,
                    "deleted": False,
                }
            ]
        )


def test_autobangumi_client_logs_in_and_fetches_bangumi():
    session = _FakeSession()
    client = AutoBangumiClient(
        base_url="http://ab.local:7892",
        username="sunzhuofan",
        password="root1234",
        session=session,
    )

    items = client.fetch_bangumi()

    assert session.posts == [
        (
            "http://ab.local:7892/api/v1/auth/login",
            {"username": "sunzhuofan", "password": "root1234"},
            5,
        )
    ]
    assert session.gets == [("http://ab.local:7892/api/v1/bangumi/get/all", 5)]
    assert items[0]["official_title"] == "尖帽子的魔法工房"
    assert items[0]["poster_link"] == "posters/5cac94c7.jpg"
