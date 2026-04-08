from anime_ops_ui.copy import text
from anime_ops_ui.navigation import INTERNAL_PAGES, SERVICE_ACTIONS, STACK_ACTION, build_external_services_with_hrefs


def build_page_context(page_key: str, title: str) -> dict:
    return {
        "page_key": page_key,
        "page_title": title,
        "site_title": text("site.title"),
        "site_subtitle": text("site.subtitle"),
        "navigation_api_path": "/api/navigation",
        "internal_pages": INTERNAL_PAGES,
        "external_services": build_external_services_with_hrefs(),
        "service_actions": SERVICE_ACTIONS,
        "stack_action": STACK_ACTION,
    }
