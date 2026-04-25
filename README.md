# RPI Anime

[简体中文](./README.zh-Hans.md)

RPI Anime is a personal hobby project for running an RSS-driven media pipeline on a Raspberry Pi.
It started as an anime stack, but the workflow is broad enough for other subscription-based video libraries that arrive through RSS and benefit from download automation, library cleanup, publishing, and playback in one place.

The repository combines off-the-shelf services with a custom control layer:

- [AutoBangumi](https://github.com/EstrellaXD/Auto_Bangumi) for RSS subscriptions and release tracking
- [qBittorrent](https://github.com/qbittorrent/qBittorrent) for download execution
- a custom `postprocessor` for version selection, renaming, publishing, and review fallback
- [Jellyfin](https://github.com/jellyfin/jellyfin) for library browsing and playback
- a custom `ops-ui` for dashboard, review queue, logs, service controls, and weekly broadcast tracking

## Overview

<p align="center">
  <img src="./docs/media/nekoya-multi-device-en.png" alt="RPI Anime web dashboard, iPhone app, and iPad app mockup" width="920">
</p>

## [Stone Badge](https://github.com/professor-lee/StoneBadge/tree/main)

![Stone Badge for RPI Anime](https://stone.professorlee.work/api/stone/ZhuofanSun/RPI_Anime)

## What It Does

- Pulls new items from RSS subscriptions into the download queue
- Picks a single winning file when multiple releases exist for the same episode
- Publishes clean files into the library and generates `.nfo` metadata
- Sends uncertain cases into a manual review area instead of polluting the media library
- Exposes the whole workflow through a lightweight operations dashboard
- Supports local network and tailnet access through [Tailscale](https://github.com/tailscale/tailscale)

## Dashboard Snapshot

The current UI focuses on a compact control surface and a weekly broadcast wall.

![Dashboard top section](./docs/dash1_new_en.png)

![Dashboard lower section](./docs/dash2_new_en.png)

## Core Workflow

```mermaid
flowchart LR
    RSS["RSS sources"] --> AB["AutoBangumi"]
    AB --> QB["qBittorrent"]
    QB --> DL["/downloads/Bangumi"]
    DL --> PP["postprocessor"]
    PP --> LIB["/library/seasonal"]
    PP --> REVIEW["manual_review"]
    LIB --> JF["Jellyfin"]

    OPS["ops-ui"] --- AB
    OPS --- QB
    OPS --- PP
    OPS --- JF
    OPS --- TS["Tailscale"]
    OPS --- GL["Glances"]
```

## Main Components

| Component | Role | Runtime |
| --- | --- | --- |
| `ops-ui` | Dashboard, review queue, logs, postprocessor and Tailscale pages | Docker |
| `postprocessor` | File selection, renaming, metadata generation, publish/review split | Docker |
| [Jellyfin](https://github.com/jellyfin/jellyfin) | Media library and playback | Docker |
| [qBittorrent](https://github.com/qbittorrent/qBittorrent) | Download execution and queue management | Docker |
| [AutoBangumi](https://github.com/EstrellaXD/Auto_Bangumi) | RSS subscriptions and bangumi tracking | Docker |
| `Glances` | Host metrics for the dashboard | Docker |
| [Tailscale](https://github.com/tailscale/tailscale) | Remote access without public exposure | Host |
| `anime-fan-control` | PWM fan control tied to host temperature | Host |

## Repository Layout

```text
.
├── deploy/
│   ├── compose.yaml
│   ├── fan_control.toml
│   ├── homepage/
│   ├── systemd/
│   └── title_mappings.toml
├── docs/
│   ├── dash1.png
│   └── dash2.png
├── scripts/
│   ├── bootstrap_pi.sh
│   ├── install_fan_control_pi.sh
│   ├── install_tailscale_pi.sh
│   ├── remote_up.sh
│   └── sync_to_pi.sh
└── services/
    ├── ops_ui/
    └── postprocessor/
```

## Notes

- The weekly `Broadcast Wall` is driven by AutoBangumi data and highlights shows that were added to the library during the current week.
- Broadcast wall posters can open the matching Jellyfin series page directly.
- `ops-ui` supports both `zh-Hans` and `en`.
- The repository intentionally keeps public-facing documentation lightweight; internal planning scratch files are not part of the tracked docs set.

## Companion App

NekoYa is the separate iPhone and iPad companion app for this stack.
Its showcase uses one multi-device mockup that places the web dashboard, iPhone app, and iPad app in a single image, plus one short GIF showing synchronized phone and tablet playback.

## Documentation

- [Documentation Index](./docs/README.md)
- [Deployment Notes](./docs/deployment.md)
- [Reliability Hardening Notes](./docs/reliability-hardening.md)

The companion iOS/iPadOS app is maintained as a separate repository and is intentionally excluded from backend sync and deployment flows.
