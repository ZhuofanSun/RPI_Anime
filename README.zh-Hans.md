# RPI Anime

[English](./README.md)

`RPI Anime` 是一个运行在树莓派上的个人兴趣项目，核心目标是把基于 RSS 订阅的影音内容接入一条完整的自动化链路。
它最初围绕追番场景搭建，但整体流程并不只适合动画，任何能通过 RSS 进入下载、整理、入库、播放流程的影音内容都可以套用这套结构。

这个仓库把现成服务和自定义逻辑拼成一套完整系统：

- [AutoBangumi](https://github.com/EstrellaXD/Auto_Bangumi) 负责 RSS 订阅和放送跟踪
- [qBittorrent](https://github.com/qbittorrent/qBittorrent) 负责下载执行
- 自定义 `postprocessor` 负责选优、重命名、发布和人工审核分流
- [Jellyfin](https://github.com/jellyfin/jellyfin) 负责媒体库和播放
- 自定义 `ops-ui` 负责总览、审核队列、日志、服务控制和周放送表

## [石墩子](https://github.com/professor-lee/StoneBadge/tree/main)

![RPI Anime 的石墩子](https://stone.professorlee.work/api/stone/ZhuofanSun/RPI_Anime)

## 这个项目在做什么

- 从 RSS 订阅把新内容送进下载队列
- 同一集有多个版本时自动挑出一个保留版本
- 把干净文件发布进媒体库，并生成 `.nfo` 元数据
- 识别不稳或不适合自动入库的内容进入人工审核区
- 通过一个轻量化运维界面统一查看整条链路
- 结合 [Tailscale](https://github.com/tailscale/tailscale) 提供局域网外访问能力

## 界面概览

当前界面重点是紧凑控制台和首页周放送表。

![首页上半部分](./docs/dash1_new_zh.png)

![首页下半部分](./docs/dash2_new_zh.png)

## 核心工作流

```mermaid
flowchart LR
    RSS["RSS 订阅源"] --> AB["AutoBangumi"]
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

## 主要组件

| 组件 | 作用 | 运行位置 |
| --- | --- | --- |
| `ops-ui` | 总览、审核队列、日志、Postprocessor 和 Tailscale 页面 | Docker |
| `postprocessor` | 选优、重命名、元数据生成、发布/审核分流 | Docker |
| [Jellyfin](https://github.com/jellyfin/jellyfin) | 媒体库和播放 | Docker |
| [qBittorrent](https://github.com/qbittorrent/qBittorrent) | 下载执行和队列管理 | Docker |
| [AutoBangumi](https://github.com/EstrellaXD/Auto_Bangumi) | RSS 订阅和番剧跟踪 | Docker |
| `Glances` | 给 dashboard 提供宿主机指标 | Docker |
| [Tailscale](https://github.com/tailscale/tailscale) | 不暴露公网端口的远程访问 | 宿主机 |
| `anime-fan-control` | 随温度调节的 PWM 风扇控制 | 宿主机 |

## 仓库结构

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

## 说明

- 首页 `Broadcast Wall` 以 AutoBangumi 为主数据源，并高亮“本周已入库”的条目。
- 周放送表里的 poster 可以直接跳到对应的 Jellyfin 剧集页。
- `ops-ui` 目前支持 `zh-Hans` 和 `en` 两种语言。
- 仓库里的公开文档只保留长期有用的说明，阶段性计划和本地草稿不再作为受控文档保留。

## 文档

- [文档索引](./docs/README.zh-Hans.md)
- [部署说明](./docs/deployment.zh-Hans.md)
- [可靠性加固记录](./docs/reliability-hardening.md)

iOS/iPadOS 伴随 APP 位于独立仓库 `RPI_Anime_APP/`，不会参与后端同步和部署流程。
