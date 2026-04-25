# 部署说明

[English](./deployment.md)

这份文档保留当前树莓派部署流程，把偏运维的细节从 README 首页移出来。

## 1. 准备树莓派环境

建议使用 64 位 Raspberry Pi OS，并提前准备好这两个挂载点：

- `/srv/anime-data`
- `/srv/anime-collection`

存储注意事项：

- 这两个路径应该指向预期的外置数据盘，而不是系统盘上的空目录。
- `./scripts/sync_to_pi.sh` 会检查树莓派上的实际挂载来源；如果 `/etc/fstab` 里声明了挂载，但目标路径已经回落到 `/`，脚本会直接拒绝同步，避免误写入 SD 卡。
- 可以在树莓派上用这些命令快速核对：

```bash
lsblk -o NAME,MODEL,SIZE,FSTYPE,MOUNTPOINTS,LABEL,UUID
findmnt /srv/anime-data /srv/anime-collection
df -h /srv/anime-data /srv/anime-collection
```

- 如果你使用的是 SanDisk `Extreme 55AE`，并且在树莓派上反复遇到 UAS 掉盘，可以在 `/boot/firmware/cmdline.txt` 追加 `usb-storage.quirks=0781:55ae:u` 后重启。

然后执行基础引导脚本：

```bash
./scripts/bootstrap_pi.sh
```

如果需要宿主机侧能力，可以继续执行：

```bash
./scripts/install_tailscale_pi.sh
./scripts/install_fan_control_pi.sh
```

## 2. 在本地准备部署配置

在本地创建 `deploy/.env`，至少填写这些值：

- `PI_HOST`
- `PI_REMOTE_USER`
- `PI_REMOTE_ROOT`
- `TZ`
- `JELLYFIN_PLAYBACK_USER_ID`
- `JELLYFIN_PLAYBACK_ACCESS_TOKEN`
- `QBITTORRENT_USERNAME`
- `QBITTORRENT_PASSWORD`
- `AUTOBANGUMI_USERNAME`
- `AUTOBANGUMI_PASSWORD`

对这个项目，当前最稳的 Jellyfin 方案是：

- 所有你自己的设备继续共用一个 Jellyfin 用户，保持 watched / resume truth 统一
- 给 `ops_ui` 单独配置这个同一用户的长期 token，也就是 `JELLYFIN_PLAYBACK_USER_ID` 和 `JELLYFIN_PLAYBACK_ACCESS_TOKEN`
- 不要让移动端 playback bootstrap 依赖每次都重新走 `Users/AuthenticateByName`，因为 Jellyfin 的密码登录链路一旦坏掉，移动端播放会整条一起掉

## 3. 同步仓库到树莓派

```bash
./scripts/sync_to_pi.sh
```

这个脚本会把主仓库同步到 `${PI_REMOTE_ROOT}`，单独同步 `deploy/.env`，并且**不会**同步 `RPI_Anime_APP/`。

当前同步语义是：

- 如果改了 `services/ops_ui/src/`，脚本会 restart `homepage`
- 如果改了 `services/postprocessor/src/`，脚本会 rebuild 并重新拉起 `postprocessor`
- 如果改了 `deploy/compose.yaml`、服务构建输入或 `deploy/.env`，脚本会对远端 compose 栈做一次对齐
- 如果 Pi 上 `${PI_REMOTE_ROOT}/RPI_Anime_APP` 已存在，脚本会直接拒绝继续，避免把 APP 仓库混进 backend deploy tree

## 4. 构建并启动服务

```bash
./scripts/remote_up.sh
```

这个脚本仍然保留为“显式整栈重建”入口，适合你想强制刷新整套 compose 服务时使用。

## 5. 验证部署结果

常用检查方式：

```bash
curl http://<ops-host>:3000/healthz
curl http://<ops-host>:3000/api/overview
```

后续更新通常先执行：

```bash
./scripts/sync_to_pi.sh
```

如果你明确想做一次整栈重建，再执行 `./scripts/remote_up.sh`。
