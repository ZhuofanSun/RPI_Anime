from __future__ import annotations

from fastapi import Request

SUPPORTED_LOCALES = ("zh-Hans", "en")
DEFAULT_LOCALE = "zh-Hans"
LANGUAGE_COOKIE_NAME = "anime-ops-ui-lang"


def _canonical_locale(raw: str | None) -> str | None:
    value = (raw or "").strip().lower().replace("_", "-")
    if value == "en" or value.startswith("en-"):
        return "en"
    if value == "zh" or value.startswith("zh-hans") or value in {"zh-cn", "zh-sg"}:
        return "zh-Hans"
    return None


def _parse_accept_language(raw: str) -> list[str]:
    parsed: list[tuple[float, int, str]] = []
    for index, token in enumerate(raw.split(",")):
        item = token.strip()
        if not item:
            continue
        locale_part, *params = item.split(";")
        quality = 1.0
        for param in params:
            name, _, value = param.strip().partition("=")
            if name == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
                break
        canonical = _canonical_locale(locale_part)
        if canonical in SUPPORTED_LOCALES and quality > 0:
            parsed.append((quality, index, canonical))
    parsed.sort(key=lambda entry: (-entry[0], entry[1]))
    return [locale for _quality, _index, locale in parsed]


def normalize_locale(raw: str | None) -> str:
    return _canonical_locale(raw) or DEFAULT_LOCALE


def resolve_locale(request: Request | None) -> str:
    if request is None:
        return DEFAULT_LOCALE

    cookie_locale = _canonical_locale(request.cookies.get(LANGUAGE_COOKIE_NAME))
    if cookie_locale in SUPPORTED_LOCALES:
        return cookie_locale

    accept_language = request.headers.get("accept-language", "")
    for locale in _parse_accept_language(accept_language):
        return locale

    return DEFAULT_LOCALE
