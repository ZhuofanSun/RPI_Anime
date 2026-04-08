INTERNAL_PAGES = {
    "dashboard": {"label": "Dashboard", "path": "/", "icon": "D", "target": "internal"},
    "ops_review": {"label": "Ops Review", "path": "/ops-review", "icon": "OR", "target": "internal"},
    "logs": {"label": "Logs", "path": "/logs", "icon": "L", "target": "internal"},
    "postprocessor": {"label": "Postprocessor", "path": "/postprocessor", "icon": "P", "target": "internal"},
    "tailscale": {"label": "Tailscale", "path": "/tailscale", "icon": "T", "target": "internal"},
}

EXTERNAL_SERVICES = {
    "jellyfin": {"label": "Jellyfin", "icon": "J", "target": "external", "port_env": "JELLYFIN_PORT"},
    "qbittorrent": {"label": "qBittorrent", "icon": "Q", "target": "external", "port_env": "QBITTORRENT_WEBUI_PORT"},
    "autobangumi": {"label": "AutoBangumi", "icon": "A", "target": "external", "port_env": "AUTOBANGUMI_PORT"},
    "glances": {"label": "Glances", "icon": "G", "target": "external", "port_env": "GLANCES_PORT"},
}
