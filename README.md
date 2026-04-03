# RPI Anime

本地开发、树莓派运行的番剧库项目骨架。

当前目标：

- 本地维护配置和代码
- 通过 `rsync` 同步到树莓派
- 树莓派上使用 Docker Compose 运行基础服务
- 后处理程序后续逐步补齐

## 当前目录

```text
.
├── deploy
│   ├── .env.example
│   └── compose.yaml
├── scripts
│   ├── bootstrap_pi.sh
│   ├── install_tailscale_pi.sh
│   ├── remote_up.sh
│   └── sync_to_pi.sh
├── services
│   └── postprocessor
└── 树莓派私人影音库方案.md
```

## 远端目录约定

树莓派上建议使用：

- `/srv/anime-data`
- `/srv/anime-collection`
- `/srv/anime-data/appdata/rpi-anime`

其中：

- `/srv/anime-data` 放下载、处理目录、Jellyfin 数据和季度追番库
- `/srv/anime-collection` 放收藏库
- `/srv/anime-data/appdata/rpi-anime` 放这个项目同步过去的代码和部署文件

## 推荐流程

1. 本地修改项目文件。
2. 复制 `deploy/.env.example` 为本地不提交的 `deploy/.env` 并填好树莓派信息。
3. 运行 `scripts/sync_to_pi.sh` 把项目同步到树莓派。
4. 首次部署时，在树莓派运行 `scripts/bootstrap_pi.sh` 安装 Docker 并准备目录。
5. 如需外网访问，在树莓派运行 `scripts/install_tailscale_pi.sh` 安装 Tailscale。
6. 在树莓派上检查 `deploy/.env` 内容。
7. 运行 `scripts/remote_up.sh` 在树莓派启动或更新容器。

## 说明

- `Tailscale` 建议装在树莓派宿主机，不放进 Compose。
- `AutoBangumi` 使用官方文档给出的容器镜像。
- `Jellyfin` 使用官方容器镜像。
- `qBittorrent` 当前 Compose 用常见 Docker 镜像作占位，后续可以按你的偏好调整。
- `postprocessor` 服务还只是占位骨架，不会默认启动。
