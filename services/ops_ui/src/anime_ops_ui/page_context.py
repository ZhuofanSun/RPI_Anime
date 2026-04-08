from __future__ import annotations

import json

from anime_ops_ui.copy import client_copy, shell_copy, text
from anime_ops_ui.i18n import LANGUAGE_COOKIE_NAME, normalize_locale
from anime_ops_ui.navigation import build_external_services_with_hrefs, build_internal_pages, build_service_actions, build_stack_action


def build_page_context(page_key: str, title: str, locale: str | None = None) -> dict:
    normalized_locale = normalize_locale(locale)
    client_copy_payload = client_copy(normalized_locale)
    return {
        "locale": normalized_locale,
        "page_key": page_key,
        "page_title": title,
        "site_title": text("site.title", normalized_locale),
        "site_subtitle": text("site.subtitle", normalized_locale),
        "shell_copy": shell_copy(normalized_locale),
        "client_copy": client_copy_payload,
        "client_copy_json": json.dumps(client_copy_payload, ensure_ascii=False),
        "language_cookie_name": LANGUAGE_COOKIE_NAME,
        "navigation_api_path": "/api/navigation",
        "internal_pages": build_internal_pages(normalized_locale),
        "external_services": build_external_services_with_hrefs(normalized_locale),
        "service_actions": build_service_actions(normalized_locale),
        "stack_action": build_stack_action(normalized_locale),
    }
