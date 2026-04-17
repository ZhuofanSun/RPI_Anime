# Reliability Hardening Notes

这份文档用来记录项目下一阶段与长期运行稳定性相关的优化措施。目标不是继续扩功能，而是让这套树莓派上的 RSS 影音流水线更稳、更容易维护，也更不容易因为一次更新或长期运行而突然坏掉。

## 当前最值得优先处理的问题

### 1. 外部镜像一直跟 `latest`

风险：

- 上游镜像更新后，容器行为、接口、依赖或默认配置可能直接变化
- 一次普通部署就可能把已经验证过的工作链路推到未知状态
- 问题出现后很难快速回退到之前那版

措施：

- 不再使用 `latest`
- 先把当前树莓派上已经验证过的运行版本固定到精确镜像 digest
- 后续升级时先单独拉新版本验证，再手动更新 digest

第一轮已落实：

- `deploy/compose.yaml` 中的 `glances / jellyfin / qbittorrent / autobangumi` 已固定到当前在跑的 digest

### 2. 部署路径没有区分 UI-only 和 full stack

风险：

- 只改 `ops-ui` 页面时，顺手重建 `postprocessor` 或整栈，会增加不必要的扰动
- 正在运行的下载、发布或监控链路会被额外影响

措施：

- 把远程部署拆成两条明确路径
- `scripts/remote_up_ui.sh`：只重建 `homepage`
- `scripts/remote_up_stack.sh`：刷新整套运行链路
- `scripts/remote_up.sh` 保留为兼容入口，继续走 full stack

第一轮已落实：

- 新增 `scripts/remote_up_ui.sh`
- 新增 `scripts/remote_up_stack.sh`
- `scripts/remote_up.sh` 现在只是兼容包装器

建议使用方式：

```bash
# 只改 dashboard / 前端 / ops-ui
./scripts/remote_up_ui.sh

# 改了 postprocessor / compose / 整体运行链路
./scripts/remote_up_stack.sh
```

### 3. 关键状态没有显式备份入口

风险：

- `jellyfin`、`qbittorrent`、`autobangumi` 的配置和数据库一旦坏掉，恢复成本很高
- `deploy/.env` 和 `title_mappings.toml` 丢失后，环境难以快速重建

措施：

- 明确“最低必备备份集”
- 在本地提供一个固定脚本，从树莓派把关键状态打包拉回

最低备份集：

- `${ANIME_APPDATA_ROOT}/jellyfin`
- `${ANIME_APPDATA_ROOT}/qbittorrent`
- `${ANIME_APPDATA_ROOT}/autobangumi`
- `${ANIME_APPDATA_ROOT}/ops-ui`
- `${PI_REMOTE_ROOT}/deploy/.env`
- `${PI_REMOTE_ROOT}/deploy/title_mappings.toml`

第一轮已落实：

- 新增 `scripts/backup_pi_state.sh`

示例：

```bash
./scripts/backup_pi_state.sh
```

默认输出到本地 `backups/`，该目录已经加入 `.gitignore`。

### 4. 缺少简单直接的运行健康检查入口

风险：

- 现在更多依赖你“打开页面自己看”
- 一旦 `overview` 降级、`diagnostics` 开始报错、首页 contract 有问题，不容易第一时间发现

措施：

- 提供一条只读 smoke 脚本，至少检查：
  - `/healthz`
  - `/api/overview`
  - `diagnostics` 是否为空
  - `weekly_schedule.days` 是否仍为 7 天

第一轮已落实：

- 新增 `scripts/check_ops_stack.sh`

示例：

```bash
./scripts/check_ops_stack.sh
```

### 5. 数据盘掉线时缺少“阻断误写系统盘”的保护

风险：

- 外置盘掉线后，`/srv/anime-data` 和 `/srv/anime-collection` 可能只剩系统盘上的空目录
- `docker compose` 和同步脚本如果继续运行，会把状态、缓存甚至新文件误写到 SD 卡
- 页面表面上可能还能打开，但链路已经处在“假正常、真漂移”的状态

措施：

- `scripts/sync_to_pi.sh` 在远端同步前对比 `/etc/fstab` 和实时挂载来源；如果目标路径已经回落到 root filesystem，就直接拒绝同步
- `ops-ui` 的 `overview` 增加存储布局诊断，除了“未挂载 / 不可读”之外，也会标记 `/srv/anime-data` 和 `/srv/anime-collection` 共用同一块小容量系统盘的可疑状态
- 对已知在树莓派上容易触发 UAS 掉线的设备，补充宿主机侧 quirk 配置说明

第一轮已落实：

- `scripts/sync_to_pi.sh` 新增远端挂载回退保护
- `ops-ui` 总览新增 `mount:/srv-storage-layout` 诊断
- `README.md` / `README.zh-Hans.md` 补充了挂载核对命令和 `usb-storage.quirks=0781:55ae:u` 运维说明

## 第一轮之外，下一批值得继续做的事

### 6. 给关键状态做定时备份

建议：

- 在本地或另一台机器上定时执行 `scripts/backup_pi_state.sh`
- 每天或每周保留一份滚动备份
- 额外补一个“恢复演练”步骤，确认 tar 包真的能用

### 7. 给只读健康检查加定时执行

建议：

- 定时执行 `scripts/check_ops_stack.sh`
- 一旦失败，至少落本地日志
- 有条件的话再接系统通知、邮件或 IM

### 8. 存储空间和残留文件阈值提醒

建议：

- 对 `/srv/anime-data` 的剩余空间设置阈值
- 对下载残留、`manual_review` 堆积设置提醒
- 把“快满了”从视觉观察变成主动告警

### 9. 周表和首页聚合的轻缓存

建议：

- `weekly_schedule` 的 Jellyfin 标题映射可以加短 TTL 或基于 DB `mtime` 的缓存
- 避免首页轮询时重复读 DB 和重复做标题匹配

### 10. 首页聚合做快路径 / 慢路径隔离

建议：

- `overview` 接口优先保证快速返回
- 某个外部依赖失败时只让对应模块降级，不拖死整页

### 11. 发布动作继续加强幂等保护

建议：

- `postprocessor` 和人工重试发布路径继续坚持“重复触发不造成重复副作用”
- 把重复发布、重复事件、重复覆盖当成显式回归面去锁

## 第一轮交付总结

第一轮已经落地的内容：

- 固定外部镜像 digest
- 拆出 UI-only / full stack 两条部署路径
- 增加关键状态备份脚本
- 增加只读健康检查脚本
- 增加挂载回退保护，避免误写系统盘
- 增加首页存储布局诊断

这 4 项的共同目标不是加功能，而是：

- 减少一次普通更新对正在运行服务的扰动
- 提高回退和恢复能力
- 把“靠人盯页面”变成“脚本可直接验证”
