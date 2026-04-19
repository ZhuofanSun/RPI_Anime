from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def utc_now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_mobile_timestamp(value: Any, *, default: str | None = None) -> str | None:
    if value is None:
        return default

    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return default
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return default

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo or UTC)

    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
