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
- `postprocessor` 已作为常驻服务运行
- 下载完成后可自动选优、发布到 `Seasonal` 媒体库
- 发布时会自动生成 `tvshow.nfo` 和分集同名 `.nfo`
- 当前已接入番名映射表和等待窗口策略
- `AniDB` 已在 Jellyfin 中加载，并已手动调整 metadata provider 优先级

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
│   ├── compose.yaml
│   └── title_mappings.toml
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
- `deploy/title_mappings.toml` 用来维护发布目录名、季号修正、集号偏移，以及 Jellyfin 用的 `tvshow.nfo`。
- 不要用 `sudo docker compose run ...` 跑 `postprocessor` 工具命令，否则新建目录和 `nfo` 容易变成 `root:root`。

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

当前 `postprocessor` 已经能做扫描和发布。扫描模式会只报告：

- 哪些文件能解析出番名和集数
- 哪些是同一集多版本
- 哪些会在默认改名时撞名
- 哪些文件解析失败

树莓派上直接运行扫描：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor
```

如果要指定目录：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor scan --root /srv/anime-data/downloads/Bangumi
```

如果想看 JSON 输出：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor scan --json
```

当前 `postprocessor` 第二版已经支持单集选优和发布计划：

- 每集只选一个赢家
- 当前优先级：`CHS > CHS&CHT > unknown > CHT`，`AVC > HEVC`，`mp4 > mkv`，`1080p > 1440p > 720p > 2160p`
- 默认先干跑，不直接改文件
- 常驻 `watch` 服务会轮询 `qBittorrent` 的 `Bangumi` 分类
- 如果最高优先级候选已经完成，会立即发布
- 如果先完成的是低优先级候选，会进入等待窗口；默认等待 `1800` 秒，给更高优先级版本补完机会，超时后再按当时已完成的候选选优
- “已完成”的判断来自 `qBittorrent` Web API 返回的 torrent 状态：`amount_left == 0` 或 `progress >= 1.0`
- 发布时会按 `deploy/title_mappings.toml` 改写目标剧名、季号和集号
- 发布时会在剧集目录下写 `tvshow.nfo`
- 发布时也会在每一集视频旁边写同名 `.nfo`，分集标题默认用文件名

查看发布计划：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor publish
```

执行发布并删除未选中的重复文件：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor publish --apply --delete-losers
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

给现有库补写 `tvshow.nfo`：

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --env-file deploy/.env -f deploy/compose.yaml run --build --rm postprocessor write-nfo
```

## 当前状态总结

- 自动链路现在是：`AutoBangumi -> qBittorrent -> postprocessor -> Jellyfin`
- `postprocessor` 会读取 qB API 判断任务是否完成，不靠文件时间猜测
- 已完成任务会先按优先级比较
- 如果先完成的是低优先级版本，会进入等待窗口，默认 `1800` 秒
- 新入库内容会自动生成本地 `nfo`
- 旧内容可以通过 `write-nfo` 补写本地 `nfo`
- Jellyfin 现在的识别策略是：
  - 本地 `nfo` 兜底剧名、季号、集号和分集标题
  - `AniDB` 等动漫 provider 补简介、封面等远程元数据
  - 其他默认 provider 作为补充
- Jellyfin 不会按远程元数据库去改视频里的字幕轨或字幕内容

## 下一步建议

1. 下一阶段优先做运维首页，方案见 [运维首页计划.md](/Users/sunzhuofan/RPI_Anime/运维首页计划.md)。
2. 先落地 `Homepage`，把 `Jellyfin`、`qBittorrent`、`AutoBangumi`、`Tailscale` 本地状态和项目入口集中到一个页面。
3. 后续再单独补 `ops-review`，把 `manual_review` 的可视化和处理网页化。
4. 转码优化先暂缓，等实际出现播放转码问题后再针对性处理。

## 说明

- `Tailscale` 建议装在树莓派宿主机，不放进 Compose。
- `AutoBangumi` 使用官方文档给出的容器镜像。
- `Jellyfin` 使用官方容器镜像。
- `qBittorrent` 当前 Compose 用常见 Docker 镜像作占位，后续可以按你的偏好调整。
- `postprocessor` 现在会默认启动并常驻监听。
