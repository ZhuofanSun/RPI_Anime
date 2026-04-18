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

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        timeout: int = 5,
    ) -> requests.Response:
        if not self._authenticated:
            self.login()
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            json=json,
            timeout=timeout,
        )
        if response.status_code in {401, 403}:
            self.login()
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                json=json,
                timeout=timeout,
            )
        response.raise_for_status()
        return response

    def login(self) -> None:
        response = self.session.post(
            f"{self.base_url}/api/v1/auth/login",
            data={"username": self.username, "password": self.password},
            timeout=5,
        )
        response.raise_for_status()
        self._authenticated = True

    def fetch_bangumi(self) -> list[dict[str, Any]]:
        response = self._request("GET", "/api/v1/bangumi/get/all")
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("AutoBangumi bangumi payload must be a list")
        if any(not isinstance(item, dict) for item in payload):
            raise RuntimeError("AutoBangumi bangumi payload must be a list of dicts")
        return payload

    def fetch_rss_sources(self) -> list[dict[str, Any]]:
        response = self._request("GET", "/api/v1/rss")
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("AutoBangumi RSS payload must be a list")
        if any(not isinstance(item, dict) for item in payload):
            raise RuntimeError("AutoBangumi RSS payload must be a list of dicts")
        return payload

    def analyze_rss(self, *, url: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/api/v1/rss/analysis",
            json={
                "url": url,
                "aggregate": False,
                "parser": "mikan",
            },
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("AutoBangumi RSS analysis payload must be an object")
        return payload

    def subscribe_rss(self, *, url: str, bangumi_payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/api/v1/rss/subscribe",
            json={
                "data": bangumi_payload,
                "rss": {
                    "url": url,
                    "aggregate": False,
                    "parser": "mikan",
                },
            },
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("AutoBangumi RSS subscribe payload must be an object")
        return payload

    def enable_rss(self, *, rss_id: int) -> dict[str, Any]:
        response = self._request("POST", "/api/v1/rss/enable/many", json=[rss_id])
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("AutoBangumi RSS enable payload must be an object")
        return payload

    def disable_rss(self, *, rss_id: int) -> dict[str, Any]:
        response = self._request("PATCH", f"/api/v1/rss/disable/{rss_id}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("AutoBangumi RSS disable payload must be an object")
        return payload

    def delete_rss(self, *, rss_id: int) -> dict[str, Any]:
        response = self._request("DELETE", f"/api/v1/rss/delete/{rss_id}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("AutoBangumi RSS delete payload must be an object")
        return payload
