from __future__ import annotations

import copy
from dataclasses import dataclass, field
import threading
from typing import Any

from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES

_NAVIGATION_STATE_FLIGHT_LOCK = threading.Lock()


@dataclass
class _NavigationStateFlight:
    done: threading.Event = field(default_factory=threading.Event)
    payload: dict[str, list[dict[str, Any]]] | None = None
    error: Exception | None = None


_NAVIGATION_STATE_FLIGHT: _NavigationStateFlight | None = None


def _safe_port(raw: str, fallback: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return fallback


def _build_navigation_state_uncached() -> dict[str, list[dict[str, Any]]]:
    from anime_ops_ui import main as main_module

    review_root = main_module._manual_review_root()
    review_count = main_module._count_media_files(review_root)
    events = main_module.read_events(limit=300)
    error_count = sum(1 for item in events if str(item.get("level", "")).lower() == "error")
    qb_snapshot, _ = main_module._qb_snapshot()
    active_downloads = int((qb_snapshot or {}).get("active_downloads", 0) or 0)

    tailscale_socket = main_module._env("TAILSCALE_SOCKET", "/var/run/tailscale/tailscaled.sock")
    tailscale_status, _ = main_module._tailscale_status(tailscale_socket)
    tailscale_self = ((tailscale_status or {}).get("Self") or {}) if isinstance(tailscale_status, dict) else {}
    tailscale_online = bool(
        isinstance(tailscale_status, dict)
        and tailscale_status.get("BackendState") == "Running"
        and tailscale_self.get("Online")
    )

    badge_by_page = {
        "dashboard": None,
        "ops-review": str(review_count) if review_count > 0 else None,
        "logs": str(error_count) if error_count > 0 else None,
        "postprocessor": str(active_downloads) if active_downloads > 0 else None,
        "tailscale": "Online" if tailscale_online else "Offline",
    }
    tone_by_page = {
        "dashboard": "neutral",
        "ops-review": "warning" if review_count > 0 else "neutral",
        "logs": "danger" if error_count > 0 else "neutral",
        "postprocessor": "info" if active_downloads > 0 else "neutral",
        "tailscale": "success" if tailscale_online else "danger",
    }

    internal_entries: list[dict[str, Any]] = []
    for page_id, item in INTERNAL_PAGES.items():
        internal_entries.append(
            {
                "id": page_id,
                "label": item["label"],
                "icon": item["icon"],
                "target": item["target"],
                "path": item["path"],
                "href": item["path"],
                "badge": badge_by_page.get(page_id),
                "tone": tone_by_page.get(page_id, "neutral"),
            }
        )

    base_host = main_module._env("HOMEPAGE_BASE_HOST", main_module.socket.gethostname())
    external_entries: list[dict[str, Any]] = []
    for service_id, item in EXTERNAL_SERVICES.items():
        fallback_port = int(item.get("default_port", 80))
        port = _safe_port(main_module._env(item["port_env"], str(fallback_port)), fallback_port)
        external_entries.append(
            {
                "id": service_id,
                "label": item["label"],
                "icon": item["icon"],
                "target": item["target"],
                "href": main_module._service_link(base_host, port),
                "badge": None,
                "tone": "neutral",
            }
        )

    return {"internal": internal_entries, "external": external_entries}


def build_navigation_state() -> dict[str, list[dict[str, Any]]]:
    global _NAVIGATION_STATE_FLIGHT

    with _NAVIGATION_STATE_FLIGHT_LOCK:
        flight = _NAVIGATION_STATE_FLIGHT
        if flight is None:
            flight = _NavigationStateFlight()
            _NAVIGATION_STATE_FLIGHT = flight
            is_builder = True
        else:
            is_builder = False

    if is_builder:
        try:
            payload = _build_navigation_state_uncached()
            flight.payload = payload
        except Exception as exc:  # pragma: no cover - defensive pass-through
            flight.error = exc
        finally:
            with _NAVIGATION_STATE_FLIGHT_LOCK:
                _NAVIGATION_STATE_FLIGHT = None
            flight.done.set()
    else:
        flight.done.wait()

    if flight.error is not None:
        raise flight.error
    if flight.payload is None:  # pragma: no cover - defensive guard
        raise RuntimeError("navigation state build completed without payload")
    return copy.deepcopy(flight.payload)
