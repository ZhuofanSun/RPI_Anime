# RPI Anime

本地开发、树莓派运行的番剧库项目骨架。

当前目标：

- 本地维护配置和代码
- 通过 `rsync` 同步到树莓派
- 树莓派上使用 Docker Compose 运行基础服务
- 后处理程序后续逐步补齐

## 当前进度

当前这套基础链路已经打通：

- 外置盘已完成分区和挂载
- `Jellyfin` 已可登录
- `qBittorrent` 已可登录
- `AutoBangumi` 已可登录
- `Tailscale` 已接入常用设备
- 本地项目可通过 `scripts/sync_to_pi.sh` 同步到树莓派

当前服务访问地址：

- `Jellyfin`: `http://sunzhuofan.local:8096`
- `qBittorrent`: `http://sunzhuofan.local:8080`
- `AutoBangumi`: `http://sunzhuofan.local:7892`

说明：

- `AutoBangumi` 的初始化实际上已经完成，正常入口直接访问根路径 `/` 即可。
- 不要继续使用 `/#/setup` 作为入口。
- 目前建议关闭 `AutoBangumi` 自动重命名，把下载后的改名、去重、发布交给自定义 `postprocessor`。

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

补充：

- `scripts/remote_up.sh` 现在会带 `--build`，确保 `postprocessor` 代码更新后能重建生效。
- `postprocessor` 现在默认作为常驻服务启动，负责自动监听已完成下载并处理。

## 直接在树莓派启动服务

如果你不是在本地执行同步脚本，而是已经通过 `ssh` 连上树莓派，直接这样启动整套服务：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d
```

常用命令：

```bash
cd /srv/anime-data/appdata/rpi-anime

# 查看服务状态
docker compose --env-file deploy/.env -f deploy/compose.yaml ps

# 查看日志
docker compose --env-file deploy/.env -f deploy/compose.yaml logs -f

# 重启整套服务
docker compose --env-file deploy/.env -f deploy/compose.yaml restart

# 停止整套服务
docker compose --env-file deploy/.env -f deploy/compose.yaml down

# 拉起停止的服务或应用配置变更
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d
```

如果你只想重启某一个服务：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --env-file deploy/.env -f deploy/compose.yaml restart autobangumi
docker compose --env-file deploy/.env -f deploy/compose.yaml restart qbittorrent
docker compose --env-file deploy/.env -f deploy/compose.yaml restart jellyfin
```

## 后处理模式

如果改为自己接管改名和去重，建议这样做：

1. 关闭 `AutoBangumi` 自动重命名。
2. 把下载路径放回原始下载区：
   - `qBittorrent` / `AutoBangumi` 下载目录用 `/downloads/Bangumi`
3. 让 `Jellyfin` 只读发布后的媒体库：
   - `/srv/anime-data/library/seasonal`

当前 `postprocessor` 第一版已经能做扫描，不改文件，只报告：

- 哪些文件能解析出番名和集数
- 哪些是同一集多版本
- 哪些会在默认改名时撞名
- 哪些文件解析失败

树莓派上直接运行扫描：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --profile postprocessor --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor
```

如果要指定目录：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --profile postprocessor --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor scan --root /srv/anime-data/downloads/Bangumi
```

如果想看 JSON 输出：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --profile postprocessor --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor scan --json
```

当前 `postprocessor` 第二版已经支持单集选优和发布计划：

- 每集只选一个赢家
- 当前优先级：`CHS > CHS&CHT > unknown > CHT`，`AVC > HEVC`，`mp4 > mkv`，`1080p > 1440p > 720p > 2160p`
- 默认先干跑，不直接改文件
- 常驻 `watch` 服务会轮询 `qBittorrent` 的 `Bangumi` 分类，只要某一集已经有至少一个候选下载完成，就会立刻选优、发布赢家，并停掉/清理其余候选
- “已完成”的判断来自 `qBittorrent` Web API 返回的 torrent 状态：`amount_left == 0` 或 `progress >= 1.0`

查看发布计划：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --profile postprocessor --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor publish
```

执行发布并删除未选中的重复文件：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --profile postprocessor --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor publish --apply --delete-losers
```

建议：

- 先把 `AutoBangumi` 下载路径改回 `/downloads/Bangumi`
- 先运行一轮 `publish` 干跑确认赢家选择
- 确认后再执行 `publish --apply --delete-losers`

自动触发查看方式：

```bash
cd /srv/anime-data/appdata/rpi-anime

# 看 postprocessor 常驻日志
docker compose --env-file deploy/.env -f deploy/compose.yaml logs -f postprocessor

# 手动跑一轮，不持续监听
docker compose --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor watch --once
```

## 说明

- `Tailscale` 建议装在树莓派宿主机，不放进 Compose。
- `AutoBangumi` 使用官方文档给出的容器镜像。
- `Jellyfin` 使用官方容器镜像。
- `qBittorrent` 当前 Compose 用常见 Docker 镜像作占位，后续可以按你的偏好调整。
- `postprocessor` 现在会默认启动并常驻监听。
