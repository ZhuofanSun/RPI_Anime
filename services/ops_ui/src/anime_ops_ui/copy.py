COPY = {
    "site.title": "RPI Anime Ops",
    "site.subtitle": "树莓派私人影音库控制台",
    "nav.external": "外部服务",
    "nav.internal": "工作页",
}


def text(key: str) -> str:
    return COPY[key]
