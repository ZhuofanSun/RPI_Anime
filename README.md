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
- `Tailscale` 内页已接入本地状态、peer 列表和节点诊断
- 本地项目可通过 `scripts/sync_to_pi.sh` 同步到树莓派
- `postprocessor` 已作为常驻服务运行
- 下载完成后可自动选优、发布到 `Seasonal` 媒体库
- 发布时会自动生成 `tvshow.nfo` 和分集同名 `.nfo`
- 当前已接入番名映射表和等待窗口策略
- `AniDB` 已在 Jellyfin 中加载，并已手动调整 metadata provider 优先级
- 阶段一运维首页已切到自定义 `ops-ui + Glances`
- `ops-ui` 已支持 light / dark 切换，并补了更强的卡片抬升和悬浮反馈
- `Ops Review` 已进入只读列表版，可查看 `manual_review` 的文件清单、bucket、大小和路径
- `ops-ui` 采用混合导航：外部服务仍新标签页打开，内部工具页改为同站内多页面跳转
- `ops-ui` 首页与 `Ops Review` 已补首屏骨架、会话缓存和返回按钮，减轻页面切换时的空白感
- `Ops Review` 详情页已接入具体动作：`retry parse`、手动发布到 `Seasonal`、删除当前文件
- `Logs` 页已接入结构化事件日志，可按来源、等级和关键字筛选，并支持手动清理
- `Tailscale` 内页已接入本地 tailnet 状态、本机节点详情、peer 列表和手动开/关按钮
- 宿主机 `Tailscale` 已完成一次干净重建，当前处于 `NeedsLogin`，等待重新授权回到 tailnet

当前服务访问地址：

- `Ops UI`: `http://sunzhuofan.local:3000`
- `Jellyfin`: `http://sunzhuofan.local:8096`
- `qBittorrent`: `http://sunzhuofan.local:8080`
- `AutoBangumi`: `http://sunzhuofan.local:7892`
- `Glances`: `http://sunzhuofan.local:61208`

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
│   ├── remote_tailscale.sh
│   ├── remote_up.sh
│   └── sync_to_pi.sh
├── services
│   ├── ops_ui
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

- `scripts/remote_up.sh` 现在会优先重建 `postprocessor`，而 `homepage` 走源码挂载和 `--no-build` 更新，避免树莓派侧反复因为 PyPI/DNS 问题卡在重建前端镜像。
- `scripts/remote_tailscale.sh` 用于从本地直接通过 SSH 控制树莓派宿主机的 `Tailscale`：`start / stop / status / rebuild`。
- `postprocessor` 现在默认作为常驻服务启动，负责自动监听已完成下载并处理。
- `deploy/title_mappings.toml` 用来维护发布目录名、季号修正、集号偏移，以及 Jellyfin 用的 `tvshow.nfo`。
- 不要用 `sudo docker compose run ...` 跑 `postprocessor` 工具命令，否则新建目录和 `nfo` 容易变成 `root:root`。
- `3000` 端口现在跑的是自定义 `ops-ui`，不是第三方 Homepage 镜像。
- `ops-ui` 的前端是静态 `HTML + CSS + JS`，后端是 `FastAPI`，运行时通过 `Glances`、`qBittorrent API` 和本地 `Tailscale` socket 汇总状态。
- `ops-ui` 会把趋势采样数据写到 `${ANIME_APPDATA_ROOT}/ops-ui/history.json`，用于 24 小时折线、Jellyfin 播放流量趋势和 7 日下载柱状图，不会因为容器重启立刻清空。
- `ops-ui` 会把结构化事件日志写到 `${ANIME_APPDATA_ROOT}/ops-ui/events.json`，默认保留最近 `1500` 条，超出后自动裁剪。
- `ops-ui` 现在对 `${ANIME_DATA_ROOT}` 具有写权限，仅用于 `Ops Review` 的受控文件动作。
- 为了调用本地 `Tailscale` LocalAPI 写接口，`homepage` 服务当前以 `root` 运行；`ops-ui` 状态数据仍然只写到 `${ANIME_APPDATA_ROOT}/ops-ui`。
- `ops-ui` 里的 `Tailscale` 按钮现在走真正的 `start / stop` 语义：
  - `start` 通过 LocalAPI 打开 backend，并在需要时进入登录态
  - `stop` 通过 `WantRunning=false` 关闭 tailnet 连接，但不清除当前授权
- `homepage` 现在额外挂载本地源码目录，当前迭代可以用 `docker compose ... up -d --no-build homepage` 热更新页面逻辑，不必每次都重建镜像。

## Tailscale 状态文件

`/var/lib/tailscale/tailscaled.state` 主要存这些内容：

- 本机 machine key / node key
- 登录 profile 与节点偏好
- `WantRunning` 等本地运行状态

如果它正常，这个文件很重要；如果它已经坏到出现 `_machinekey invalid`，那它对运行时就没有继续保留价值了，最多只值得做备份留档。  
你这台树莓派刚才就是这种情况，所以已经做过一次完整目录级备份与重建。

当前备份目录在树莓派宿主机上：

- `/var/lib/tailscale-backup-20260404-030423`

当前新的状态目录已经是干净的，`tailscaled` 处于：

- `BackendState=NeedsLogin`

这说明：

- 坏掉的 machine key 已经清掉了
- 宿主机 `tailscaled` 服务已恢复到可重新登录的正常状态
- 剩下只差一次授权登录

## Tailscale 控制

树莓派宿主机上直接运行：

```bash
cd /srv/anime-data/appdata/rpi-anime
./scripts/tailscale_control_pi.sh status
./scripts/tailscale_control_pi.sh start
./scripts/tailscale_control_pi.sh stop
./scripts/tailscale_control_pi.sh login
```

本地电脑直接远程运行：

```bash
./scripts/remote_tailscale.sh status
./scripts/remote_tailscale.sh start
./scripts/remote_tailscale.sh stop
./scripts/remote_tailscale.sh rebuild
```

完整重建宿主机 Tailscale：

```bash
cd /srv/anime-data/appdata/rpi-anime
./scripts/tailscale_rebuild_pi.sh
```

重建后的标准收尾动作：

```bash
cd /srv/anime-data/appdata/rpi-anime
./scripts/tailscale_control_pi.sh start
sudo tailscale login
```

说明：

- `start` / `stop` 是真正的开关，不是 `logout`
- `stop` 只会断开 tailnet，不会清掉授权
- 如果 `start` 后页面或 API 已经给出登录链接，直接打开授权即可；如果没有，再执行一次 `sudo tailscale login`
- `tailscaled` 本身由宿主机 `systemd` 管理，不依赖 Compose；只要 `sudo systemctl enable --now tailscaled` 生效，它就会随树莓派开机稳定启动

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

1. 下一步先在树莓派宿主机执行一次 `sudo tailscale login`，把当前 `NeedsLogin` 的新状态重新授权回 tailnet。
2. 然后再补 `Postprocessor` 内页和受控的“单服务重启 / 整套重启”动作。
3. 转码优化继续暂缓，等实际出现播放转码问题后再针对性处理。

## 说明

- `Tailscale` 建议装在树莓派宿主机，不放进 Compose。
- `AutoBangumi` 使用官方文档给出的容器镜像。
- `Jellyfin` 使用官方容器镜像。
- `qBittorrent` 当前 Compose 用常见 Docker 镜像作占位，后续可以按你的偏好调整。
- `postprocessor` 现在会默认启动并常驻监听。
