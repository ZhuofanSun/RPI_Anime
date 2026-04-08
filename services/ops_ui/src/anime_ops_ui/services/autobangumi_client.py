from __future__ import annotations

from typing import Any

import requests


class AutoBangumiClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = session or requests.Session()
        self._authenticated = False

    def login(self) -> None:
        response = self.session.post(
            f"{self.base_url}/api/v1/auth/login",
            data={"username": self.username, "password": self.password},
            timeout=5,
        )
        response.raise_for_status()
        self._authenticated = True

    def fetch_bangumi(self) -> list[dict[str, Any]]:
        if not self._authenticated:
            self.login()
        response = self.session.get(f"{self.base_url}/api/v1/bangumi/get/all", timeout=5)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("AutoBangumi bangumi payload must be a list")
        return [item for item in payload if isinstance(item, dict)]
