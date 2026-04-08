from __future__ import annotations

import copy

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

SHELL_COPY = {
    "zh-Hans": {
        "nav": {
            "toggle": "导航",
            "aria_label": "主导航",
            "internal": "工作页",
            "external": "外部服务",
            "controls": "服务动作",
        },
        "preferences": {
            "title": "偏好",
            "theme": "主题",
            "language": "语言",
        },
    },
    "en": {
        "nav": {
            "toggle": "Navigation",
            "aria_label": "Primary navigation",
            "internal": "Workspace",
            "external": "Services",
            "controls": "Controls",
        },
        "preferences": {
            "title": "Preferences",
            "theme": "Theme",
            "language": "Language",
        },
    },
}

CLIENT_COPY = {
    "zh-Hans": {
        "theme": {
            "label": "主题",
            "light": "浅色",
            "dark": "深色",
        },
        "language": {
            "label": "语言",
            "zh-Hans": "zh-Hans",
            "en": "en",
        },
        "services": {
            "restartBusy": "重启中…",
            "stackBusy": "整栈重启中…",
            "confirmReload": "将重启 {name}，当前页面会短暂断开。继续吗？",
            "confirm": "将重启 {name}。继续吗？",
            "success": "{name} 重启指令已发送。",
            "authRequired": "{name} 需要在浏览器里完成授权：{auth_url}",
            "manualAuthRequired": "{name} 需要在终端执行 sudo tailscale login 或 sudo tailscale up 完成授权。",
            "error": "{name} 重启失败。",
            "stackConfirm": "将依次重启 Jellyfin、qBittorrent、AutoBangumi、Glances、Postprocessor 和 Ops UI，不包含 Tailscale。继续吗？",
            "stackSuccess": "整套服务重启已安排。",
            "stackError": "整套服务重启失败。",
        },
    },
    "en": {
        "theme": {
            "label": "Theme",
            "light": "Light",
            "dark": "Dark",
        },
        "language": {
            "label": "Language",
            "zh-Hans": "zh-Hans",
            "en": "en",
        },
        "services": {
            "restartBusy": "Restarting…",
            "stackBusy": "Restarting stack…",
            "confirmReload": "This will restart {name}. This page will briefly disconnect. Continue?",
            "confirm": "This will restart {name}. Continue?",
            "success": "Restart requested for {name}.",
            "authRequired": "Finish {name} sign-in in your browser: {auth_url}",
            "manualAuthRequired": "Finish {name} sign-in from the terminal with sudo tailscale login or sudo tailscale up.",
            "error": "Failed to restart {name}.",
            "stackConfirm": "This will restart Jellyfin, qBittorrent, AutoBangumi, Glances, Postprocessor, and Ops UI in sequence. Tailscale is excluded. Continue?",
            "stackSuccess": "Stack restart scheduled.",
            "stackError": "Failed to restart the stack.",
        },
    },
}


def text(key: str, locale: str | None = None) -> str:
    return COPY[i18n.normalize_locale(locale or i18n.DEFAULT_LOCALE)][key]


def shell_copy(locale: str | None = None) -> dict:
    normalized = i18n.normalize_locale(locale or i18n.DEFAULT_LOCALE)
    return copy.deepcopy(SHELL_COPY[normalized])


def client_copy(locale: str | None = None) -> dict:
    normalized = i18n.normalize_locale(locale or i18n.DEFAULT_LOCALE)
    return copy.deepcopy(CLIENT_COPY[normalized])
