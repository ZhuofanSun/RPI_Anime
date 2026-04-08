import anime_ops_ui.i18n as i18n

COPY = {
    "zh-Hans": {
        "site.title": "RPI Anime Ops",
        "site.subtitle": "树莓派私人影音库控制台",
        "nav.external": "外部服务",
        "nav.internal": "工作页",
    },
    "en": {
        "site.title": "RPI Anime Ops",
        "site.subtitle": "Private anime ops console on Raspberry Pi",
        "nav.external": "Services",
        "nav.internal": "Workspace",
    },
}


def text(key: str, locale: str | None = None) -> str:
    return COPY[i18n.normalize_locale(locale or i18n.DEFAULT_LOCALE)][key]
