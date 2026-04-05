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
- `Postprocessor` 内页已接入运行概览、等待窗口快照、最近事件和手动命令入口
- `ops-ui` 首页已接入单服务重启与整套服务重启动作，并带确认与结果提示
- `ops-ui` 首页服务按钮已改成跟随当前访问地址，在 `.local`、`Tailscale IP`、`MagicDNS` 下都会跳到对应 host
- `ops-ui` 首页主机状态已接入风扇当前占空比、GPIO 引脚和最近状态更新时间
- 宿主机 `Tailscale` 已完成干净重建并重新授权，当前已回到 `Running` 在线状态

当前服务访问地址：

- `Ops UI`: `http://<当前访问地址>:3000`
- `Jellyfin`: `http://<当前访问地址>:8096`
- `qBittorrent`: `http://<当前访问地址>:8080`
- `AutoBangumi`: `http://<当前访问地址>:7892`
- `Glances`: `http://<当前访问地址>:61208`

例如：

- 局域网：`sunzhuofan.local`
- Tailscale IP：`100.123.232.73`
- MagicDNS：`rpi.tail9ac25e.ts.net`

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
│   ├── fan_control.toml
│   ├── systemd
│   └── title_mappings.toml
├── scripts
│   ├── bootstrap_pi.sh
│   ├── fan_control.py
│   ├── fan_pwm_test.py
│   ├── install_fan_control_pi.sh
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
- `ops-ui` 首页现在会额外检查 `${ANIME_DATA_ROOT}` 和 `${ANIME_COLLECTION_ROOT}` 是否真的挂在外置盘上：
  - 如果盘没挂上，会在 `诊断` 区块直接报挂载异常
  - 同时把首页里依赖媒体目录的计数卡降级成 `-`，避免误把系统盘目录当成真实媒体库
- 为了调用本地 `Tailscale` LocalAPI 写接口和 Docker 本地 socket，`homepage` 服务当前以 `root` 运行；`ops-ui` 状态数据仍然只写到 `${ANIME_APPDATA_ROOT}/ops-ui`。
- `ops-ui` 里的 `Tailscale` 按钮现在走真正的 `start / stop` 语义：
  - `start` 通过 LocalAPI 打开 backend，并在需要时进入登录态
  - `stop` 通过 `WantRunning=false` 关闭 tailnet 连接，但不清除当前授权
- `ops-ui` 首页里的重启动作只做两类：
  - 单服务重启：支持 `Jellyfin`、`qBittorrent`、`AutoBangumi`、`Glances`、`Postprocessor`、`Ops UI` 和 `Tailscale`
  - 整套服务重启：只重启 compose 栈，不包含 `Tailscale`，并把 `Ops UI` 放到最后一步
- `ops-ui` 首页里的打开按钮不再信任后端返回的固定 host：
  - 外部服务：沿用当前页面的 host，只替换目标端口
  - 内部工作页：沿用当前页面的完整 origin
  - 这样从 `.local`、`Tailscale IP`、`MagicDNS` 打开首页时，按钮都会跳到同一访问链路
- compose 里的主要服务现在都启用了 Docker 日志轮转：
  - driver: `json-file`
  - `max-size=10m`
  - `max-file=3`
  - 这样单个容器默认最多保留约 `30MB` 的本地 Docker 日志
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

当前新的状态目录已经是干净的，宿主机 `tailscaled` 已经重新登录并回到：

- `BackendState=Running`

这说明：

- 坏掉的 machine key 已经清掉了
- 宿主机 `tailscaled` 服务已恢复到可重新登录的正常状态
- 当前 tailnet 已恢复，可通过新的 Tailscale IP 和 MagicDNS 访问

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
- compose 里的各个容器目前都是 `restart: unless-stopped`
  - 正常重启宿主机后，它们会自动回来
  - 但如果你手动 `docker stop ...` 或 `docker compose stop` 过，它们不会在下次开机时自己恢复
  - 如果你执行的是 `docker compose down`，容器会被删除，之后也需要手工 `up -d`

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

## 风扇 PWM 测试

如果机箱风扇的控制线接到了 `GPIO18`，可以先用这个脚本测试几个档位：

```bash
cd /srv/anime-data/appdata/rpi-anime
python3 scripts/fan_pwm_test.py
```

默认行为：

- 先以 `100%` 转 `3` 秒，帮助风扇起转
- 然后在 `100,80,60,40,25` 这几个档位之间循环

常用例子：

```bash
# 只跑一轮
python3 scripts/fan_pwm_test.py --once

# 自定义档位和停留时间
python3 scripts/fan_pwm_test.py --duty 100,70,40 --hold 5
```

说明：

- 脚本会优先尝试 `pigpio` 的硬件 PWM
- 如果树莓派上没有 `pigpio`，会退回 `gpiozero` 做软件 PWM 验证
- 如果蓝线一接上但没有输出 PWM，很多这类风扇会直接停转；先跑脚本再观察是否恢复

## 风扇温控服务

如果风扇的蓝线已经接到 `GPIO18`，并且 `fan_pwm_test.py` 验证过可以响应 PWM，可以把风扇控制装成宿主机 `systemd` 服务：

```bash
cd /srv/anime-data/appdata/rpi-anime
./scripts/install_fan_control_pi.sh
```

默认配置文件在：

- `deploy/fan_control.toml`

安装后，脚本和配置会复制到宿主机系统盘：

- `/usr/local/lib/rpi-anime-fan/fan_control.py`
- `/usr/local/lib/rpi-anime-fan/fan_control.toml`

这样即使外置媒体盘没挂上，风扇控制也不会跟着失效。

默认策略：

- 服务运行时风扇始终至少 `30%`
- 启动时先 `100%` 转 `3` 秒，帮助低速风扇稳定起转
- 每 `3` 秒采样一次 CPU 温度
- 使用 `EMA` 平滑，`alpha=0.32`
- 升速每次最多 `+12%`
- 降速每次最多 `-6%`
- `75°C` 以上直接拉到 `100%`

默认温度曲线：

- `35°C -> 30%`
- `42°C -> 30%`
- `48°C -> 38%`
- `52°C -> 48%`
- `56°C -> 60%`
- `60°C -> 72%`
- `64°C -> 84%`
- `68°C -> 92%`
- `72°C -> 100%`

常用命令：

```bash
# 查看服务状态
systemctl status anime-fan-control.service --no-pager

# 看实时日志
journalctl -u anime-fan-control.service -f

# 如果你改的是仓库里的 deploy/fan_control.toml，先重新安装一遍
./scripts/install_fan_control_pi.sh

# 如果你直接改的是 /usr/local/lib/rpi-anime-fan/fan_control.toml，再重启服务
sudo systemctl restart anime-fan-control.service
```

我这版默认策略偏保守：

- 平时尽量低噪音
- 中高温时拉升比较快
- 降速故意慢一点，减少来回抽动

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

1. 下一步可以补宿主机异常退出、断电和状态备份的兜底措施。
2. 然后再考虑是否给首页加更强的运维统计、服务级健康检查或批量运维动作。
3. 转码优化继续暂缓，等实际出现播放转码问题后再针对性处理。

## 说明

- `Tailscale` 建议装在树莓派宿主机，不放进 Compose。
- `AutoBangumi` 使用官方文档给出的容器镜像。
- `Jellyfin` 使用官方容器镜像。
- `qBittorrent` 当前 Compose 用常见 Docker 镜像作占位，后续可以按你的偏好调整。
- `postprocessor` 现在会默认启动并常驻监听。
