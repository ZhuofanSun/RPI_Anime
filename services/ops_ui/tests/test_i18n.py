from fastapi import Request

from anime_ops_ui.copy import COPY, text
import anime_ops_ui.i18n as i18n
from anime_ops_ui.i18n import DEFAULT_LOCALE, LANGUAGE_COOKIE_NAME, normalize_locale, resolve_locale


def _request(*, cookie_locale: str | None = None, accept_language: str | None = None) -> Request:
    headers = []
    if accept_language is not None:
        headers.append((b"accept-language", accept_language.encode("utf-8")))
    if cookie_locale is not None:
        headers.append((b"cookie", f"{LANGUAGE_COOKIE_NAME}={cookie_locale}".encode("utf-8")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "client": ("testclient", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
    }
    return Request(scope)


def test_normalize_locale_maps_supported_variants():
    assert normalize_locale("en") == "en"
    assert normalize_locale("EN-us") == "en"
    assert normalize_locale("en-GB") == "en"
    assert normalize_locale("zh") == "zh-Hans"
    assert normalize_locale("zh-cn") == "zh-Hans"


def test_normalize_locale_falls_back_to_default_for_unknown_values():
    assert normalize_locale(None) == DEFAULT_LOCALE
    assert normalize_locale("fr") == DEFAULT_LOCALE
    assert normalize_locale("  ") == DEFAULT_LOCALE


def test_resolve_locale_prefers_cookie_over_accept_language():
    request = _request(cookie_locale="en", accept_language="zh-Hans,zh;q=0.9")

    assert resolve_locale(request) == "en"


def test_resolve_locale_uses_accept_language_when_cookie_is_missing():
    request = _request(accept_language="en-US,en;q=0.9")

    assert resolve_locale(request) == "en"


def test_resolve_locale_respects_accept_language_q_weights():
    request = _request(accept_language="zh-Hans;q=0.1,en-GB;q=0.9")

    assert resolve_locale(request) == "en"


def test_resolve_locale_skips_accept_language_entries_with_zero_quality():
    request = _request(accept_language="en;q=0,fr;q=0.8")

    assert resolve_locale(request) == "zh-Hans"


def test_resolve_locale_ignores_unsupported_cookie_and_falls_back_to_accept_language():
    request = _request(cookie_locale="invalid", accept_language="en-GB,en;q=0.9")

    assert resolve_locale(request) == "en"


def test_resolve_locale_skips_traditional_chinese_accept_language_entries():
    request = _request(accept_language="zh-Hant;q=0.9,en;q=0.8")

    assert resolve_locale(request) == "en"


def test_resolve_locale_accepts_simplified_chinese_script_region_tags():
    request = _request(accept_language="zh-Hans-CN;q=0.9,en;q=0.8")

    assert resolve_locale(request) == "zh-Hans"


def test_text_returns_localized_copy_for_each_locale():
    assert text("site.subtitle", locale="zh-Hans") == "树莓派私人影音库控制台"
    assert text("site.subtitle", locale="en") == "Private anime ops console on Raspberry Pi"


def test_text_normalizes_noncanonical_locale_values():
    assert text("site.subtitle", locale="en-US") == "Private anime ops console on Raspberry Pi"
    assert text("nav.internal", locale="en-GB") == "Workspace"


def test_text_uses_the_shared_default_locale(monkeypatch):
    monkeypatch.setattr(i18n, "DEFAULT_LOCALE", "en")

    assert text("site.subtitle") == "Private anime ops console on Raspberry Pi"


def test_copy_catalogs_expose_the_same_translation_keys():
    catalogs = list(COPY.values())
    baseline_keys = set(catalogs[0])

    assert all(set(catalog) == baseline_keys for catalog in catalogs[1:])
