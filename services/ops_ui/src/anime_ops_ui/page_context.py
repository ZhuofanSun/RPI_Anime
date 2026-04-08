from anime_ops_ui.copy import text
from anime_ops_ui.navigation import EXTERNAL_SERVICES, INTERNAL_PAGES


def build_page_context(page_key: str, title: str) -> dict:
    return {
        "page_key": page_key,
        "page_title": title,
        "site_title": text("site.title"),
        "site_subtitle": text("site.subtitle"),
        "navigation_api_path": "/api/navigation",
        "internal_pages": INTERNAL_PAGES,
        "external_services": EXTERNAL_SERVICES,
    }
