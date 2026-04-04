from __future__ import annotations

from dataclasses import dataclass

import requests


_COMPLETED_STATES = {
    "uploading",
    "pausedUP",
    "queuedUP",
    "stalledUP",
    "checkingUP",
    "forcedUP",
}

_INCOMPLETE_STATES = {
    "allocating",
    "downloading",
    "metaDL",
    "pausedDL",
    "queuedDL",
    "stalledDL",
    "checkingDL",
    "forcedDL",
    "checkingResumeData",
    "moving",
    "unknown",
}


@dataclass(frozen=True)
class QBTorrent:
    torrent_hash: str
    name: str
    category: str
    content_path: str
    progress: float
    amount_left: int
    state: str
    completion_on: int

    @property
    def completed(self) -> bool:
        if self.state in _COMPLETED_STATES:
            return True
        if self.state in _INCOMPLETE_STATES:
            return False
        if self.completion_on > 0:
            return True
        return self.amount_left == 0 and self.progress >= 1.0

    @property
    def completion_ts(self) -> int | None:
        return self.completion_on if self.completion_on > 0 else None


class QBClient:
    def __init__(self, base_url: str, username: str, password: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()

    def auth(self) -> None:
        response = self.session.post(
            f"{self.base_url}/api/v2/auth/login",
            data={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        response.raise_for_status()
        if response.text.strip() != "Ok.":
            raise RuntimeError(f"qBittorrent auth failed: {response.text.strip()}")

    def list_torrents(self, category: str) -> list[QBTorrent]:
        response = self.session.get(
            f"{self.base_url}/api/v2/torrents/info",
            params={"category": category},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return [
            QBTorrent(
                torrent_hash=item["hash"],
                name=item["name"],
                category=item.get("category", ""),
                content_path=item.get("content_path", ""),
                progress=float(item.get("progress", 0.0)),
                amount_left=int(item.get("amount_left", 0)),
                state=item.get("state", ""),
                completion_on=int(item.get("completion_on", -1)),
            )
            for item in data
        ]

    def torrent_files(self, torrent_hash: str) -> list[dict]:
        response = self.session.get(
            f"{self.base_url}/api/v2/torrents/files",
            params={"hash": torrent_hash},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def pause(self, hashes: list[str]) -> None:
        if not hashes:
            return
        payload = {"hashes": "|".join(hashes)}
        response = self.session.post(
            f"{self.base_url}/api/v2/torrents/pause",
            data=payload,
            timeout=self.timeout,
        )
        if response.status_code == 404:
            response = self.session.post(
                f"{self.base_url}/api/v2/torrents/stop",
                data=payload,
                timeout=self.timeout,
            )
        response.raise_for_status()

    def delete(self, hashes: list[str], delete_files: bool = False) -> None:
        if not hashes:
            return
        response = self.session.post(
            f"{self.base_url}/api/v2/torrents/delete",
            data={
                "hashes": "|".join(hashes),
                "deleteFiles": "true" if delete_files else "false",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
