from __future__ import annotations

import copy
import re

import anime_ops_ui.i18n as i18n

COPY = {
    "zh-Hans": {
        "site.title": "RPI Anime Ops",
        "site.subtitle": "树莓派私人影音库控制台",
        "nav.external": "外部服务",
        "nav.internal": "工作页",
    },
    "en": {
        "site.title": "RPI Anime Ops",
        "site.subtitle": "Private anime ops console on Raspberry Pi",
        "nav.external": "Services",
        "nav.internal": "Workspace",
    },
}

SHELL_COPY = {
    "zh-Hans": {
        "nav": {
            "toggle": "导航",
            "aria_label": "主导航",
            "internal": "工作页",
            "external": "外部服务",
            "controls": "服务动作",
        },
        "preferences": {
            "title": "偏好",
            "theme": "主题",
            "language": "语言",
        },
    },
    "en": {
        "nav": {
            "toggle": "Navigation",
            "aria_label": "Primary navigation",
            "internal": "Workspace",
            "external": "Services",
            "controls": "Controls",
        },
        "preferences": {
            "title": "Preferences",
            "theme": "Theme",
            "language": "Language",
        },
    },
}

CLIENT_COPY = {
    "zh-Hans": {
        "theme": {
            "label": "主题",
            "light": "浅色",
            "dark": "深色",
        },
        "language": {
            "label": "语言",
            "zh-Hans": "zh-Hans",
            "en": "en",
        },
        "services": {
            "restartBusy": "重启中…",
            "stackBusy": "整栈重启中…",
            "confirmReload": "将重启 {name}，当前页面会短暂断开。继续吗？",
            "confirm": "将重启 {name}。继续吗？",
            "success": "{name} 重启指令已发送。",
            "authRequired": "{name} 需要在浏览器里完成授权：{auth_url}",
            "manualAuthRequired": "{name} 需要在终端执行 sudo tailscale login 或 sudo tailscale up 完成授权。",
            "error": "{name} 重启失败。",
            "stackConfirm": "将依次重启 Jellyfin、qBittorrent、AutoBangumi、Glances、Postprocessor 和 Ops UI，不包含 Tailscale。继续吗？",
            "stackSuccess": "整套服务重启已安排。",
            "stackError": "整套服务重启失败。",
        },
    },
    "en": {
        "theme": {
            "label": "Theme",
            "light": "Light",
            "dark": "Dark",
        },
        "language": {
            "label": "Language",
            "zh-Hans": "zh-Hans",
            "en": "en",
        },
        "services": {
            "restartBusy": "Restarting…",
            "stackBusy": "Restarting stack…",
            "confirmReload": "This will restart {name}. This page will briefly disconnect. Continue?",
            "confirm": "This will restart {name}. Continue?",
            "success": "Restart requested for {name}.",
            "authRequired": "Finish {name} sign-in in your browser: {auth_url}",
            "manualAuthRequired": "Finish {name} sign-in from the terminal with sudo tailscale login or sudo tailscale up.",
            "error": "Failed to restart {name}.",
            "stackConfirm": "This will restart Jellyfin, qBittorrent, AutoBangumi, Glances, Postprocessor, and Ops UI in sequence. Tailscale is excluded. Continue?",
            "stackSuccess": "Stack restart scheduled.",
            "stackError": "Failed to restart the stack.",
        },
    },
}

PAYLOAD_COPY = {
    "zh-Hans": {
        "overview": {
            "hero": {
                "eyebrow": "控制台总览",
                "status_stable": "运行稳定",
                "status_risks": "{count} 个风险待处理",
                "summary": "{downloads} 个下载中 · {reviews} 个待审核 · {tailnet}",
                "tailnet_online": "Tailnet 在线",
                "tailnet_issue": "Tailnet 异常",
            },
            "summary_strip": {
                "watch_question": "今天有什么值得看",
                "watch_answer": "{count} 部已入库，可播放",
                "ingest_question": "下载和入库链路是否正常",
                "ingest_answer": "{count} 个待审核",
                "health_question": "设备和远程访问是否健康",
                "health_ok": "运行稳定",
                "health_issue": "有异常",
            },
            "service_summary": {
                "label": "Services",
                "value": "{count} online",
                "detail": "{total} total · Docker + tailscaled",
            },
            "stack_control": {
                "label": "Restart Stack",
                "detail": "compose only · homepage last",
            },
            "dashboard_copy": {
                "schedule": {
                    "tooltip_labels": {
                        "title_raw": "原题",
                        "group_name": "字幕组",
                        "source": "来源",
                        "subtitle": "字幕",
                        "dpi": "画质",
                        "season_label": "季度",
                    },
                    "list_separator": "，",
                    "title_fallback": "未知",
                    "library_ready": "本周已入库，可播放",
                    "review_note_prefix": "审校提示",
                    "empty_day": "无放送",
                    "empty_week": "暂无本周放送数据。",
                    "unknown_label_fallback": "未知",
                    "unknown_empty": "未知分组暂无条目。",
                    "expand_hidden": "展开 +{count}",
                    "collapse_hidden": "收起",
                },
                "refresh_auto_prefix": "自动",
                "trend_empty": "暂无历史数据。",
                "diagnostics": {
                    "empty": "本地数据源响应正常。",
                    "source_fallback": "diagnostics",
                    "message_fallback": "unknown issue",
                    "frontend_source": "frontend",
                },
            },
            "cards": {
                "system": {
                    "cpu_usage": {"label": "CPU Usage", "fallback_detail": "Raspberry Pi"},
                    "cpu_temp": {
                        "label": "CPU Temp",
                        "detail": "{hours}h avg {average} · {fan_detail}",
                        "fan_unavailable": "风扇状态不可用",
                        "fan_fresh": "Fan {duty}% · GPIO{pin} · {seconds}s ago",
                        "fan_stale": "last update {seconds}s ago",
                    },
                    "memory": {"label": "Memory"},
                    "host_uptime": {"label": "Host Uptime", "detail": "load {load_detail}"},
                    "anime_data": {"label": "Anime Data", "unavailable": "数据盘未挂载或不可读"},
                },
                "queue": {
                    "bangumi_tasks": {"label": "Bangumi Tasks", "unavailable": "qB 不可用"},
                    "downloading": {"label": "Downloading"},
                    "seeding": {"label": "Seeding"},
                    "seasonal_episodes": {"label": "Seasonal Episodes", "detail": "{count} 部作品", "unavailable": "数据盘未挂载"},
                    "manual_review": {"label": "Manual Review", "detail": "待人工处理文件", "unavailable": "数据盘未挂载"},
                    "download_residue": {"label": "Download Residue", "detail": "下载区剩余媒体文件", "unavailable": "数据盘未挂载"},
                },
                "network": {
                    "tailnet": {"label": "Tailnet", "unavailable": "unavailable"},
                    "tailscale_ip": {"label": "Tailscale IP"},
                    "peers": {"label": "Peers", "detail": "{count} 台在线", "unavailable": "本地 API 不可用"},
                },
                "trend": {
                    "cpu_usage": {"label": "CPU Usage", "detail": "{hours}h · load {load_detail}"},
                    "cpu_temp": {"label": "CPU Temp", "detail": "{hours}h avg {average}"},
                    "playback_traffic": {"label": "Playback Traffic", "detail": "{hours}h 平均 {average} · 全部客户端"},
                    "download_volume": {"label": "Download Volume", "detail": "近 {days} 天总量 · qBittorrent"},
                },
            },
            "diagnostics": {
                "phase4_unavailable": "Phase 4 weekly schedule unavailable: {error}",
                "fan_stale": "fan state is stale ({seconds}s since last update)",
                "anime_data_missing": "未检测到数据盘挂载，下载、整理和媒体库目录可能已回落到系统盘。",
                "anime_data_probe": "数据盘访问异常：{error}",
                "anime_collection_missing": "未检测到收藏盘挂载，收藏库当前不可用。",
                "anime_collection_probe": "收藏盘访问异常：{error}",
            },
            "services": {
                "restart": "Restart",
                "restart_ui": "Restart UI",
                "jellyfin": {"description": "私人影音库与播放入口", "meta": "Media server"},
                "qbittorrent": {"description": "下载、任务队列和分类", "meta": "Download client"},
                "autobangumi": {"description": "RSS 订阅与自动下载规则", "meta": "Subscription"},
                "glances": {"description": "系统、容器和进程监控", "meta": "System monitor"},
                "postprocessor": {"description": "下载完成后的选优、发布和 NFO 生成", "meta": "Background worker"},
                "ops_review": {"description": "人工审核队列与文件处理", "meta": "{count} files", "unavailable_meta": "数据盘未挂载", "uptime": "审核工作台"},
                "logs": {"description": "结构化日志、来源筛选和清理", "meta": "{count} events", "uptime": "上限 {count} 条"},
                "tailscale": {"description": "本地 tailnet 状态与远程访问链路"},
            },
        },
        "weekly_schedule": {
            "day_labels": ["一", "二", "三", "四", "五", "六", "日"],
            "title_fallback": "未知",
            "unknown_label": "未知",
            "unknown_hint": "拖拽以设置放送日",
        },
        "review": {
            "title": "人工审核",
            "subtitle": "人工审核队列与未自动入库文件清单",
            "summary_cards": {
                "files": {"label": "待审文件", "detail": "待处理媒体文件"},
                "size": {"label": "总大小"},
                "series": {"label": "作品数", "detail": "不同作品目录"},
                "buckets": {"label": "分组", "empty": "当前没有分组"},
            },
            "detail_title": "审核详情",
            "breadcrumbs": {"dashboard": "控制台", "review": "人工审核"},
            "bucket_labels": {
                "unparsed": "无法解析",
                "duplicates": "重复版本",
                "failed": "处理失败",
                "default": "待审核",
            },
            "bucket_reasons": {
                "unparsed": "无法稳定解析标题或季集信息",
                "duplicates": "重复版本等待人工处理",
                "failed": "自动处理过程中出现异常",
                "default": "等待人工审核",
            },
            "auto_parse_reasons": {
                "unsupported_extension": "不支持的文件扩展名：{extension}",
                "cannot_parse_season_episode": "无法解析季或集信息",
                "empty_title_after_cleanup": "清洗后标题为空",
                "fallback": "自动解析失败：{reason}",
            },
            "list": {
                "filter_all": "全部分组",
                "meta": "{visible} / {total} 个文件",
                "labels": {
                    "season": "季度",
                    "reason": "原因",
                    "extension": "扩展名",
                    "hint": "目录提示",
                    "filename": "文件名",
                    "relative_path": "相对路径",
                },
                "actions": {"view_detail": "查看详情"},
                "flash": {"default_title": "操作已完成"},
                "empty": {
                    "filtered_title": "当前筛选条件下没有匹配文件。",
                    "filtered_detail": "调整分组或关键字后会重新显示列表。",
                    "idle_title": "当前没有待处理文件。",
                    "idle_detail": "下载链路正常时，异常文件会自动进入这里。",
                },
                "status": {
                    "load_failed_title": "加载人工审核队列失败。",
                    "api_unavailable": "API 不可用",
                },
            },
            "detail": {
                "fallback_title": "审核详情",
                "summary": {
                    "size": "大小",
                    "series": "作品",
                    "folder_hint": "目录提示",
                    "siblings": "同目录文件",
                    "siblings_detail": "同一父目录",
                },
                "meta_labels": {
                    "reason": "原因",
                    "filename": "文件名",
                    "relative_path": "相对路径",
                    "series_season": "作品 / 季度",
                    "auto_parse": "自动解析",
                },
                "auto_parse": {
                    "parsed": "可直接发布",
                    "unparsed": "需要人工处理",
                    "fallback": "自动解析失败",
                },
                "actions": {
                    "retry_parse": {
                        "title": "重试解析",
                        "badge_ready": "可执行",
                        "badge_disabled": "不可执行",
                        "score": "评分",
                        "button": "重试解析并发布",
                        "pending": "正在重新解析并发布当前文件。",
                        "description_ready": "自动解析已准备好，可直接发布到：{target_path}",
                        "description_exists": "自动解析命中了目标路径，但目标已存在：{target_path}",
                        "description_failed": "当前自动解析失败：{reason}",
                    },
                    "manual_publish": {
                        "title": "手动发布",
                        "badge": "覆盖发布",
                        "description": "当自动解析不稳定时，手动确认剧名、季号和集号，再直接发布到季度库。",
                        "title_label": "作品名",
                        "title_placeholder": "输入发布后的剧名",
                        "season_label": "季度",
                        "episode_label": "集数",
                        "button": "发布到季度库",
                        "pending": "正在按手动参数发布到季度库。",
                    },
                    "delete": {
                        "title": "删除文件",
                        "badge": "危险操作",
                        "description": "从人工审核队列中直接删除当前文件。这个动作不会移到媒体库，也不会保留副本。",
                        "button": "删除当前文件",
                        "confirm_title": "删除文件",
                        "confirm_message": "确认从人工审核队列删除这个文件？这个动作会直接删掉当前文件。",
                        "pending": "正在删除当前文件。",
                    },
                },
                "status": {
                    "processing_title": "处理中",
                    "processing_message": "正在执行动作。",
                    "success_title": "操作已完成",
                    "success_message": "动作已完成。",
                    "failure_title": "操作失败",
                    "empty_siblings_title": "当前没有同目录文件。",
                    "empty_siblings_detail": "当前目录下只有这一个媒体文件。",
                    "load_failed_title": "加载审核项详情失败。",
                    "missing_id_title": "缺少审核项 ID。",
                    "missing_id_detail": "请从人工审核列表页进入详情页。",
                },
            },
        },
        "logs": {
            "title": "Logs",
            "subtitle": "项目侧结构化事件日志，优先覆盖自动处理、人工审核与运维动作。",
            "summary_cards": {
                "visible": {"label": "Visible", "detail": "{matched} 条匹配 / 共 {total} 条"},
                "sources": {"label": "Sources", "empty": "暂无来源"},
                "errors": {"label": "Errors", "detail": "{warnings} 条 warning"},
                "retention": {"label": "Retention"},
            },
            "page": {
                "filters": {
                    "all_sources": "全部来源",
                    "all_levels": "全部等级",
                    "details_summary": "详细信息",
                },
                "meta": {
                    "refresh_suffix": "s",
                    "retention_badge": "上限 {count}",
                    "list_meta": "可见 {visible} / 总计 {total}",
                },
                "empty": {
                    "title": "当前没有匹配的日志。",
                    "detail": "可以调整筛选条件，或者等待后台动作写入新的结构化事件。",
                },
                "status": {
                    "unavailable_title": "日志页不可用",
                    "clear_failed_title": "清理失败",
                },
                "clear": {
                    "confirm": "确认清理结构化日志？这个动作会清空当前 Logs 页里的历史记录。",
                    "success_title": "日志已清理",
                    "success_message": "已清理结构化日志，清除 {count} 条旧记录。",
                },
            },
        },
        "postprocessor": {
            "title": "Postprocessor",
            "subtitle": "下载完成后的选优、等待窗口、自动发布与 review 分流工作台。",
            "unparsed_reason": "已完成但无法解析，下一轮会送入 manual_review",
            "group_reasons": {
                "no_completed_candidates": "还没有已完成候选",
                "best_candidate_completed": "最佳已完成候选已满足发布条件",
                "all_candidates_completed": "全部候选都已完成，可直接处理",
                "waiting_for_completion_timestamp": "等待记录首个完成时间",
                "wait_timeout_reached": "等待窗口已到期（{elapsed}s）",
                "waiting_for_higher_priority_candidates": "继续等待更高优先级候选（{elapsed}s/{wait_timeout}s）",
                "fallback": "处理决策：{reason}",
            },
            "summary_cards": {
                "worker": {"label": "Worker", "missing_uptime": "容器运行时长不可用"},
                "groups": {"label": "Episode Groups", "detail": "{ready} 组待处理 · {waiting} 组等待中"},
                "queue": {"label": "Queue Tasks", "detail": "{downloads} 个下载中 · {seeds} 个做种中", "unavailable": "qB 不可用"},
                "review": {"label": "Manual Review", "detail": "{count} 个已完成但未解析"},
            },
            "config_cards": {
                "source_root": {"label": "Source Root", "detail": "下载暂存区"},
                "target_root": {"label": "Target Root", "detail": "Jellyfin 季度库"},
                "review_root": {"label": "Review Root", "detail": "人工审核队列"},
                "policy": {"label": "Policy", "detail": "轮询 {poll}s · 等待 {wait}s · 删除落选 {enabled}"},
                "title_map": {"label": "Title Map", "detail": "作品名映射与季号偏移"},
            },
            "delete_losers": {"enabled": "开启", "disabled": "关闭"},
            "commands": {
                "watch_once": {"label": "Watch Once", "description": "手动触发一轮 watch 逻辑，最接近常驻服务实际行为。"},
                "publish_dry_run": {"label": "Publish Dry Run", "description": "查看当前下载区如果手动发布，会生成什么计划。"},
                "live_logs": {"label": "Live Logs", "description": "持续观察常驻 worker 当前每轮处理输出。"},
            },
            "page": {
                "meta": {
                    "refresh_suffix": "s",
                    "details_summary": "详细信息",
                    "command_label": "Command",
                },
                "status_badges": {
                    "ready": "待处理",
                    "waiting": "等待中",
                    "active": "下载中",
                    "unparsed": "待审",
                    "unknown": "未知",
                },
                "item_meta": {
                    "files": "个文件",
                    "completed": "已完成",
                },
                "field_labels": {
                    "best_overall": "最佳候选",
                    "best_completed": "最佳已完成",
                    "candidates": "候选数",
                    "completed": "已完成",
                },
                "empty_section": {
                    "title": "当前没有 {section} 条目。",
                    "detail_fallback": "等待下一轮刷新。",
                },
                "events_empty": {
                    "title": "还没有 postprocessor 事件。",
                    "detail": "等下一轮 watch 处理下载或人工重跑后，这里会出现结构化记录。",
                },
                "diagnostics": {
                    "source_fallback": "postprocessor",
                    "message_fallback": "Unavailable",
                    "unavailable_title": "Postprocessor 不可用",
                },
                "worker_status": {
                    "running": "运行中",
                    "restarting": "重启中",
                    "paused": "已暂停",
                    "exited": "已退出",
                    "created": "已创建",
                    "dead": "已终止",
                    "unknown": "未知",
                },
            },
            "sections": {
                "ready": {"title": "Ready On Next Tick", "description": "已经满足处理条件，下一轮 watch 会直接接管并发布。", "meta": "{count} groups"},
                "waiting": {"title": "Waiting Window", "description": "已有完成候选，但还在为更高优先级版本保留等待窗口。", "meta": "{count} groups"},
                "active": {"title": "Active Downloads", "description": "当前还没有完成候选，继续等待下载完成。", "meta": "{count} groups"},
                "unparsed": {"title": "Completed But Unparsed", "description": "已完成但无法解析的 torrent，下一轮会被送进 manual_review。", "meta": "{count} torrents"},
            },
        },
        "tailscale": {
            "title": "Tailscale",
            "subtitle": "本地 tailnet 状态与远程访问链路。",
            "reachability": {"online": "Online", "stopped": "Stopped", "offline": "Offline"},
            "control": {
                "start_label": "开启 Tailscale",
                "stop_label": "关闭 Tailscale",
                "stop_detail": "仅停止 tailnet 连接，保留当前节点授权与配置。",
                "machinekey_detail": "当前本地 state 已损坏，需要先重建宿主机 Tailscale 状态。",
                "login_detail": "启动 backend 后会进入登录态，需要在树莓派终端或网页登录完成授权。",
                "resume_detail": "恢复 tailnet backend 与远程访问链路。",
            },
            "self_note": {
                "online": "当前节点已在线，可通过 Tailscale IP 或 MagicDNS 从其他设备访问。",
                "machinekey": "当前节点的本地 state 已损坏。请先完整重建 /var/lib/tailscale，然后再重新登录。",
                "logged_out": "当前节点已经脱离 tailnet，会话需要重新登录后才能恢复。",
                "stopped": "当前节点已关闭 Tailscale 网络连接，但授权仍保留，可随时重新开启。",
                "offline": "后台进程仍在运行，但控制面或 peer 可达性异常，节点当前不可用。",
            },
            "summary_cards": {
                "backend": {"label": "Backend", "detail": "只读取本机 socket"},
                "reachability": {"label": "Reachability", "detail": "控制面与 Peer 连通性"},
                "peers": {"label": "Peers", "detail": "{online} 台在线 · {exit_nodes} 台可做出口节点"},
                "tailnet_ip": {"label": "Tailnet IP"},
            },
            "self_cards": {
                "host": {"label": "Host"},
                "reachability": {"label": "Reachability", "yes": "Yes", "no": "No", "yes_detail": "可从 tailnet 访问", "no_detail": "当前无法从 tailnet 访问"},
                "ipv4": {"label": "IPv4", "detail": "主 tailnet 地址"},
                "ipv6": {"label": "IPv6", "detail": "次 tailnet 地址"},
                "current_addr": {"label": "Current Addr", "detail": "relay {relay}"},
                "traffic": {"label": "Traffic"},
            },
            "page": {
                "meta": {
                    "refresh_suffix": "s",
                    "peer_meta": "在线 {online} / 共 {total} 台",
                },
                "defaults": {
                    "control_label": "开启 Tailscale",
                    "self_note": "本机节点摘要会在这里显示。",
                },
                "link_label": "打开登录链接",
                "peer_tags": {
                    "active": "active",
                    "exit_node_option": "可做出口",
                    "exit_node": "出口节点",
                },
                "peer_fields": {
                    "ipv6": "IPv6",
                    "current_addr": "当前地址",
                    "relay": "中继",
                    "traffic": "流量",
                    "last_write": "最后写入",
                    "last_handshake": "最后握手",
                    "last_seen": "最后在线",
                    "key_expiry": "密钥过期",
                },
                "peer_status": {
                    "online": "在线",
                    "offline": "离线",
                    "unknown": "未知",
                },
                "empty": {
                    "title": "当前没有 peer。",
                    "detail": "当其他设备加入 tailnet 后，这里会自动显示在线状态和尾网地址。",
                },
                "action": {
                    "in_progress": "正在执行 Tailscale 控制动作。",
                    "success_fallback": "操作已完成。",
                },
                "diagnostics": {
                    "source_fallback": "tailscale",
                    "message_fallback": "本地 API 不可用",
                    "unavailable_title": "Tailscale 不可用",
                },
            },
            "diagnostics": {"machinekey": "检测到 machinekey 相关错误，本机 state 可能损坏。"},
        },
    },
    "en": {
        "overview": {
            "hero": {
                "eyebrow": "Control surface",
                "status_stable": "Stable",
                "status_risks": "{count} risks need attention",
                "summary": "{downloads} active downloads · {reviews} items in review · {tailnet}",
                "tailnet_online": "Tailnet online",
                "tailnet_issue": "Tailnet issue",
            },
            "summary_strip": {
                "watch_question": "What is worth watching today?",
                "watch_answer": "{count} ready in library",
                "ingest_question": "Is download and library ingest healthy?",
                "ingest_answer": "{count} items in review",
                "health_question": "Are device health and remote access stable?",
                "health_ok": "Stable",
                "health_issue": "Issues detected",
            },
            "service_summary": {
                "label": "Services",
                "value": "{count} online",
                "detail": "{total} total · Docker + tailscaled",
            },
            "stack_control": {
                "label": "Restart Stack",
                "detail": "compose only · homepage last",
            },
            "dashboard_copy": {
                "schedule": {
                    "tooltip_labels": {
                        "title_raw": "Original title",
                        "group_name": "Group",
                        "source": "Source",
                        "subtitle": "Subtitles",
                        "dpi": "Quality",
                        "season_label": "Season",
                    },
                    "list_separator": ", ",
                    "title_fallback": "Unknown",
                    "library_ready": "Added to library this week and ready to play",
                    "review_note_prefix": "Review note",
                    "empty_day": "No broadcast",
                    "empty_week": "No weekly schedule yet.",
                    "unknown_label_fallback": "Unknown",
                    "unknown_empty": "No unscheduled entries.",
                    "expand_hidden": "Show +{count}",
                    "collapse_hidden": "Collapse",
                },
                "refresh_auto_prefix": "Auto",
                "trend_empty": "No history yet.",
                "diagnostics": {
                    "empty": "All local data sources responded normally.",
                    "source_fallback": "diagnostics",
                    "message_fallback": "unknown issue",
                    "frontend_source": "frontend",
                },
            },
            "cards": {
                "system": {
                    "cpu_usage": {"label": "CPU Usage", "fallback_detail": "Raspberry Pi"},
                    "cpu_temp": {
                        "label": "CPU Temp",
                        "detail": "{hours}h avg {average} · {fan_detail}",
                        "fan_unavailable": "Fan state unavailable",
                        "fan_fresh": "Fan {duty}% · GPIO{pin} · {seconds}s ago",
                        "fan_stale": "last update {seconds}s ago",
                    },
                    "memory": {"label": "Memory"},
                    "host_uptime": {"label": "Host Uptime", "detail": "load {load_detail}"},
                    "anime_data": {"label": "Anime Data", "unavailable": "Data disk is not mounted or readable"},
                },
                "queue": {
                    "bangumi_tasks": {"label": "Bangumi Tasks", "unavailable": "qB unavailable"},
                    "downloading": {"label": "Downloading"},
                    "seeding": {"label": "Seeding"},
                    "seasonal_episodes": {"label": "Seasonal Episodes", "detail": "{count} series", "unavailable": "Data disk unavailable"},
                    "manual_review": {"label": "Manual Review", "detail": "Files waiting for manual handling", "unavailable": "Data disk unavailable"},
                    "download_residue": {"label": "Download Residue", "detail": "Media files still left in downloads", "unavailable": "Data disk unavailable"},
                },
                "network": {
                    "tailnet": {"label": "Tailnet", "unavailable": "unavailable"},
                    "tailscale_ip": {"label": "Tailscale IP"},
                    "peers": {"label": "Peers", "detail": "{count} online", "unavailable": "Local API unavailable"},
                },
                "trend": {
                    "cpu_usage": {"label": "CPU Usage", "detail": "{hours}h · load {load_detail}"},
                    "cpu_temp": {"label": "CPU Temp", "detail": "{hours}h avg {average}"},
                    "playback_traffic": {"label": "Playback Traffic", "detail": "{hours}h avg {average} · all clients"},
                    "download_volume": {"label": "Download Volume", "detail": "{days} day total · qBittorrent"},
                },
            },
            "diagnostics": {
                "phase4_unavailable": "Phase 4 weekly schedule unavailable: {error}",
                "fan_stale": "fan state is stale ({seconds}s since last update)",
                "anime_data_missing": "Anime data disk is not mounted. Downloads, organization, and library paths may have fallen back to the system disk.",
                "anime_data_probe": "Anime data disk access error: {error}",
                "anime_collection_missing": "Collection disk is not mounted, so the collection library is unavailable.",
                "anime_collection_probe": "Collection disk access error: {error}",
            },
            "services": {
                "restart": "Restart",
                "restart_ui": "Restart UI",
                "jellyfin": {"description": "Private library and playback entrypoint", "meta": "Media server"},
                "qbittorrent": {"description": "Downloads, queue management, and categories", "meta": "Download client"},
                "autobangumi": {"description": "RSS subscriptions and automatic download rules", "meta": "Subscription"},
                "glances": {"description": "System, container, and process monitoring", "meta": "System monitor"},
                "postprocessor": {"description": "Post-download selection, publish, and NFO generation", "meta": "Background worker"},
                "ops_review": {"description": "Manual review queue and file handling", "meta": "{count} files", "unavailable_meta": "Data disk unavailable", "uptime": "Review workspace"},
                "logs": {"description": "Structured logs, source filtering, and cleanup", "meta": "{count} events", "uptime": "cap {count} events"},
                "tailscale": {"description": "Local tailnet status and remote-access path"},
            },
        },
        "weekly_schedule": {
            "day_labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "title_fallback": "Unknown",
            "unknown_label": "Unknown",
            "unknown_hint": "Drag to assign a broadcast day",
        },
        "review": {
            "title": "Ops Review",
            "subtitle": "Manual review queue and files that were not auto-published",
            "summary_cards": {
                "files": {"label": "Review Files", "detail": "Media files waiting for manual handling"},
                "size": {"label": "Total Size"},
                "series": {"label": "Series", "detail": "Distinct series folders"},
                "buckets": {"label": "Buckets", "empty": "No buckets right now"},
            },
            "detail_title": "Review Detail",
            "breadcrumbs": {"dashboard": "Dashboard", "review": "Ops Review"},
            "bucket_labels": {
                "unparsed": "Unparsed",
                "duplicates": "Duplicates",
                "failed": "Failed",
                "default": "Review",
            },
            "bucket_reasons": {
                "unparsed": "Could not reliably parse title or season/episode",
                "duplicates": "Duplicate version needs manual handling",
                "failed": "Automatic processing hit an exception",
                "default": "Waiting for manual review",
            },
            "auto_parse_reasons": {
                "unsupported_extension": "Unsupported file extension: {extension}",
                "cannot_parse_season_episode": "Could not parse season or episode",
                "empty_title_after_cleanup": "Title became empty after cleanup",
                "fallback": "Automatic parse failed: {reason}",
            },
            "list": {
                "filter_all": "All Buckets",
                "meta": "{visible} / {total} files",
                "labels": {
                    "season": "Season",
                    "reason": "Reason",
                    "extension": "Extension",
                    "hint": "Hint",
                    "filename": "Filename",
                    "relative_path": "Relative Path",
                },
                "actions": {"view_detail": "View Detail"},
                "flash": {"default_title": "Action Complete"},
                "empty": {
                    "filtered_title": "No files match the current filters.",
                    "filtered_detail": "Adjust the bucket or keyword to show files again.",
                    "idle_title": "No files need manual review right now.",
                    "idle_detail": "When the pipeline is healthy, unexpected files will appear here automatically.",
                },
                "status": {
                    "load_failed_title": "Failed to load the manual review queue.",
                    "api_unavailable": "API unavailable",
                },
            },
            "detail": {
                "fallback_title": "Review Detail",
                "summary": {
                    "size": "Size",
                    "series": "Series",
                    "folder_hint": "Folder Hint",
                    "siblings": "Sibling Files",
                    "siblings_detail": "Same parent directory",
                },
                "meta_labels": {
                    "reason": "Reason",
                    "filename": "Filename",
                    "relative_path": "Relative Path",
                    "series_season": "Series / Season",
                    "auto_parse": "Automatic Parse",
                },
                "auto_parse": {
                    "parsed": "Ready to publish",
                    "unparsed": "Needs manual handling",
                    "fallback": "Automatic parse failed",
                },
                "actions": {
                    "retry_parse": {
                        "title": "Retry Parse",
                        "badge_ready": "Ready",
                        "badge_disabled": "Unavailable",
                        "score": "Score",
                        "button": "Retry Parse and Publish",
                        "pending": "Retrying parse and publishing this file.",
                        "description_ready": "Automatic parse is ready and can publish directly to: {target_path}",
                        "description_exists": "Automatic parse resolved a target path, but it already exists: {target_path}",
                        "description_failed": "Automatic parse is still failing: {reason}",
                    },
                    "manual_publish": {
                        "title": "Manual Publish",
                        "badge": "Override",
                        "description": "When automatic parse is unreliable, confirm the series name, season, and episode manually before publishing to the seasonal library.",
                        "title_label": "Series Name",
                        "title_placeholder": "Enter the published series name",
                        "season_label": "Season",
                        "episode_label": "Episode",
                        "button": "Publish to Seasonal Library",
                        "pending": "Publishing to the seasonal library with manual values.",
                    },
                    "delete": {
                        "title": "Delete File",
                        "badge": "Danger",
                        "description": "Delete the current file directly from the manual review queue. It will not move into the library and no copy will be kept.",
                        "button": "Delete Current File",
                        "confirm_title": "Delete File",
                        "confirm_message": "Delete this file from the manual review queue? This removes the current file immediately.",
                        "pending": "Deleting the current file.",
                    },
                },
                "status": {
                    "processing_title": "Working",
                    "processing_message": "Running the requested action.",
                    "success_title": "Action Complete",
                    "success_message": "The action finished successfully.",
                    "failure_title": "Action Failed",
                    "empty_siblings_title": "No sibling files in this directory.",
                    "empty_siblings_detail": "This is the only media file under the current folder.",
                    "load_failed_title": "Failed to load review item details.",
                    "missing_id_title": "Missing Review Item ID.",
                    "missing_id_detail": "Open the detail view from the Ops Review list.",
                },
            },
        },
        "logs": {
            "title": "Logs",
            "subtitle": "Structured project events with emphasis on automation, review, and operations actions.",
            "summary_cards": {
                "visible": {"label": "Visible", "detail": "{matched} matched / {total} total"},
                "sources": {"label": "Sources", "empty": "No sources yet"},
                "errors": {"label": "Errors", "detail": "{warnings} warnings"},
                "retention": {"label": "Retention"},
            },
            "page": {
                "filters": {
                    "all_sources": "All Sources",
                    "all_levels": "All Levels",
                    "details_summary": "Details",
                },
                "meta": {
                    "refresh_suffix": "s",
                    "retention_badge": "Cap {count}",
                    "list_meta": "Visible {visible} / Total {total}",
                },
                "empty": {
                    "title": "No logs match the current filters.",
                    "detail": "Adjust the filters or wait for a new structured event to be written.",
                },
                "status": {
                    "unavailable_title": "Logs unavailable",
                    "clear_failed_title": "Clear Failed",
                },
                "clear": {
                    "confirm": "Clear the structured event log? This removes the current Logs history from the workspace.",
                    "success_title": "Logs Cleared",
                    "success_message": "Cleared {count} structured log entries.",
                },
            },
        },
        "postprocessor": {
            "title": "Postprocessor",
            "subtitle": "Workspace for post-download selection, wait windows, automatic publish, and review routing.",
            "unparsed_reason": "Completed but could not be parsed. It will move into manual_review on the next pass.",
            "group_reasons": {
                "no_completed_candidates": "No completed candidates yet",
                "best_candidate_completed": "Ready because the top-scoring completed candidate is available",
                "all_candidates_completed": "Ready because every candidate has completed",
                "waiting_for_completion_timestamp": "Waiting for the first completion timestamp",
                "wait_timeout_reached": "Ready because the wait timeout was reached ({elapsed}s)",
                "waiting_for_higher_priority_candidates": "Waiting for a higher-priority candidate ({elapsed}s/{wait_timeout}s)",
                "fallback": "Worker decision: {reason}",
            },
            "summary_cards": {
                "worker": {"label": "Worker", "missing_uptime": "Container uptime unavailable"},
                "groups": {"label": "Episode Groups", "detail": "{ready} ready · {waiting} waiting"},
                "queue": {"label": "Queue Tasks", "detail": "{downloads} downloading · {seeds} seeding", "unavailable": "qB unavailable"},
                "review": {"label": "Manual Review", "detail": "{count} completed but unparsed"},
            },
            "config_cards": {
                "source_root": {"label": "Source Root", "detail": "Download staging area"},
                "target_root": {"label": "Target Root", "detail": "Jellyfin seasonal library"},
                "review_root": {"label": "Review Root", "detail": "Manual review queue"},
                "policy": {"label": "Policy", "detail": "Poll {poll}s · wait {wait}s · delete losers {enabled}"},
                "title_map": {"label": "Title Map", "detail": "Series mapping and season offset rules"},
            },
            "delete_losers": {"enabled": "enabled", "disabled": "disabled"},
            "commands": {
                "watch_once": {"label": "Watch Once", "description": "Run one watch pass manually to mirror the long-running worker as closely as possible."},
                "publish_dry_run": {"label": "Publish Dry Run", "description": "Preview what a manual publish would do with the current download area."},
                "live_logs": {"label": "Live Logs", "description": "Follow the live worker output for each processing pass."},
            },
            "page": {
                "meta": {
                    "refresh_suffix": "s",
                    "details_summary": "Details",
                    "command_label": "Command",
                },
                "status_badges": {
                    "ready": "READY",
                    "waiting": "WAITING",
                    "active": "ACTIVE",
                    "unparsed": "REVIEW",
                    "unknown": "UNKNOWN",
                },
                "item_meta": {
                    "files": "files",
                    "completed": "completed",
                },
                "field_labels": {
                    "best_overall": "Best Overall",
                    "best_completed": "Best Completed",
                    "candidates": "Candidates",
                    "completed": "Completed",
                },
                "empty_section": {
                    "title": "No {section} items right now.",
                    "detail_fallback": "Wait for the next refresh.",
                },
                "events_empty": {
                    "title": "No postprocessor events yet.",
                    "detail": "When the next watch pass or manual rerun happens, structured records will appear here.",
                },
                "diagnostics": {
                    "source_fallback": "postprocessor",
                    "message_fallback": "Unavailable",
                    "unavailable_title": "Postprocessor unavailable",
                },
                "worker_status": {
                    "running": "Running",
                    "restarting": "Restarting",
                    "paused": "Paused",
                    "exited": "Exited",
                    "created": "Created",
                    "dead": "Dead",
                    "unknown": "Unknown",
                },
            },
            "sections": {
                "ready": {"title": "Ready On Next Tick", "description": "These groups already meet processing conditions and will be published on the next watch pass.", "meta": "{count} groups"},
                "waiting": {"title": "Waiting Window", "description": "Completed candidates exist, but the worker is still holding for a better version.", "meta": "{count} groups"},
                "active": {"title": "Active Downloads", "description": "No completed candidate yet. Waiting for downloads to finish.", "meta": "{count} groups"},
                "unparsed": {"title": "Completed But Unparsed", "description": "Completed torrents that could not be parsed and will be routed to manual_review.", "meta": "{count} torrents"},
            },
        },
        "tailscale": {
            "title": "Tailscale",
            "subtitle": "Local tailnet status and remote-access path.",
            "reachability": {"online": "Online", "stopped": "Stopped", "offline": "Offline"},
            "control": {
                "start_label": "Start Tailscale",
                "stop_label": "Stop Tailscale",
                "stop_detail": "Stop the tailnet connection only and keep the current node authorization and settings.",
                "machinekey_detail": "Local state looks damaged. Rebuild the host Tailscale state before starting again.",
                "login_detail": "Starting the backend will enter login state. Finish authorization in the browser or on the Raspberry Pi terminal.",
                "resume_detail": "Restore the tailnet backend and remote-access path.",
            },
            "self_note": {
                "online": "This node is online and reachable from other devices through its Tailscale IP or MagicDNS name.",
                "machinekey": "The local node state looks damaged. Rebuild /var/lib/tailscale completely and sign in again.",
                "logged_out": "This node has fallen out of the tailnet and must sign in again before it can recover.",
                "stopped": "The node is disconnected from Tailscale, but its authorization is still retained and can be resumed at any time.",
                "offline": "The backend is still running, but control-plane or peer reachability is degraded and the node is unavailable.",
            },
            "summary_cards": {
                "backend": {"label": "Backend", "detail": "Reads the local socket only"},
                "reachability": {"label": "Reachability", "detail": "Control-plane and peer connectivity"},
                "peers": {"label": "Peers", "detail": "{online} online · {exit_nodes} exit-node candidates"},
                "tailnet_ip": {"label": "Tailnet IP"},
            },
            "self_cards": {
                "host": {"label": "Host"},
                "reachability": {"label": "Reachability", "yes": "Yes", "no": "No", "yes_detail": "Reachable from the tailnet", "no_detail": "Currently unreachable from the tailnet"},
                "ipv4": {"label": "IPv4", "detail": "Primary tailnet address"},
                "ipv6": {"label": "IPv6", "detail": "Secondary tailnet address"},
                "current_addr": {"label": "Current Addr", "detail": "relay {relay}"},
                "traffic": {"label": "Traffic"},
            },
            "page": {
                "meta": {
                    "refresh_suffix": "s",
                    "peer_meta": "{online} online / {total} total",
                },
                "defaults": {
                    "control_label": "Start Tailscale",
                    "self_note": "Node summary will appear here.",
                },
                "link_label": "Open Login Link",
                "peer_tags": {
                    "active": "active",
                    "exit_node_option": "exit-node option",
                    "exit_node": "exit-node",
                },
                "peer_fields": {
                    "ipv6": "IPv6",
                    "current_addr": "Current Addr",
                    "relay": "Relay",
                    "traffic": "Traffic",
                    "last_write": "Last Write",
                    "last_handshake": "Last Handshake",
                    "last_seen": "Last Seen",
                    "key_expiry": "Key Expiry",
                },
                "peer_status": {
                    "online": "Online",
                    "offline": "Offline",
                    "unknown": "Unknown",
                },
                "empty": {
                    "title": "No peers right now.",
                    "detail": "When other devices join the tailnet, this list will populate automatically.",
                },
                "action": {
                    "in_progress": "Running the Tailscale control action.",
                    "success_fallback": "Action complete.",
                },
                "diagnostics": {
                    "source_fallback": "tailscale",
                    "message_fallback": "Local API unavailable",
                    "unavailable_title": "Tailscale unavailable",
                },
            },
            "diagnostics": {"machinekey": "Detected a machinekey-related error. The local node state may be damaged."},
        },
    },
}

POSTPROCESSOR_WORKER_STATUS = {
    "zh-Hans": {
        "running": "运行中",
        "restarting": "重启中",
        "paused": "已暂停",
        "exited": "已退出",
        "created": "已创建",
        "dead": "已终止",
        "unknown": "未知",
    },
    "en": {
        "running": "Running",
        "restarting": "Restarting",
        "paused": "Paused",
        "exited": "Exited",
        "created": "Created",
        "dead": "Dead",
        "unknown": "Unknown",
    },
}

PAGE_TEMPLATE_COPY = {
    "zh-Hans": {
        "dashboard": {
            "page_title": "总览",
            "hero": {
                "eyebrow": "控制台总览",
                "summary": "树莓派私人影音库控制台",
                "health_label": "状态",
                "host_label": "主机",
                "updated_label": "更新时间",
                "refresh_label": "自动刷新",
            },
            "panels": {
                "broadcast_wall": {
                    "title": "Broadcast Wall",
                    "description": "一周放送墙，按星期聚合并保留未知分组。",
                },
                "pipeline": {
                    "title": "Pipeline",
                    "description": "下载与入库链路核心指标。",
                },
                "host_network": {
                    "title": "Host + Network",
                    "description": "主机与远程访问状态汇总。",
                },
                "trends": {
                    "title": "Trends",
                    "description": "过去 24 小时折线与近 7 日下载柱状图。",
                },
                "diagnostics": {
                    "title": "Diagnostics",
                    "description": "仅在存在异常时突出显示，正常时保持安静。",
                    "loading": "正在连接本地数据源并刷新面板。",
                },
            },
        },
        "ops_review": {
            "page_title": "人工审核",
            "nav": {
                "back": "← 返回 Dashboard",
                "home": "Dashboard",
                "current": "Ops Review",
            },
            "hero": {
                "eyebrow": "Ops Review",
                "title": "Ops Review",
                "subtitle": "人工审核队列与未自动入库文件清单",
                "root_label": "Root",
                "updated_label": "更新时间",
                "refresh_label": "自动刷新",
            },
            "panels": {
                "overview": {
                    "title": "队列概览",
                    "description": "当前 `manual_review` 的积压规模、体积和分桶分布。",
                    "badge": "详情动作",
                    "note": "列表页保持只读，具体的重试解析、手动发布和删除动作放在详情页里执行。",
                },
                "filters": {
                    "title": "筛选",
                    "description": "先缩小范围，再进入详情页确认上下文和后续动作。",
                    "bucket_label": "Bucket",
                    "bucket_default": "All buckets",
                    "search_label": "Search",
                    "search_placeholder": "搜索番名、文件名或路径…",
                },
                "list": {
                    "title": "待处理文件",
                    "description": "按系列、原因和路径查看当前待确认文件。",
                },
            },
        },
        "ops_review_item": {
            "page_title": "审核详情",
            "nav": {"back": "← 返回 Ops Review"},
            "hero": {
                "eyebrow": "审核项详情",
                "title": "审核项详情",
                "subtitle": "正在加载文件详情",
                "bucket_label": "Bucket",
                "updated_label": "更新时间",
                "refresh_label": "自动刷新",
            },
            "panels": {
                "details": {
                    "title": "文件详情",
                    "description": "第二版先把上下文做完整，危险动作后接。",
                },
                "paths": {
                    "title": "路径与原因",
                    "description": "当前文件的来源位置和留在人工审核区的原因。",
                },
                "siblings": {
                    "title": "同目录文件",
                    "description": "用于确认这一集是不是还有别的版本或分片。",
                },
                "actions": {
                    "title": "执行动作",
                    "description": "优先用自动解析；不稳定时再手动确认剧名、季号和集号。",
                },
            },
        },
        "logs": {
            "page_title": "日志",
            "nav": {
                "back": "← 返回 Dashboard",
                "home": "Dashboard",
                "current": "Logs",
            },
            "hero": {
                "eyebrow": "Logs",
                "title": "Logs",
                "subtitle": "项目侧结构化事件日志",
                "storage_label": "Storage",
                "updated_label": "更新时间",
                "refresh_label": "自动刷新",
            },
            "panels": {
                "overview": {
                    "title": "日志概览",
                    "description": "来源、等级和保留上限都按结构化字段存储，便于后续继续接服务动作。",
                    "retention_badge": "上限 -",
                },
                "filters": {
                    "title": "筛选与清理",
                    "description": "按来源、等级和关键字筛选，列表自动每 10 秒刷新一次。",
                    "clear_button": "清理日志",
                    "source_label": "Source",
                    "source_default": "All sources",
                    "level_label": "Level",
                    "level_default": "All levels",
                    "search_label": "Search",
                    "search_placeholder": "搜索动作、消息或 details…",
                },
                "events": {
                    "title": "事件列表",
                    "description": "颜色区分重要等级，来源和动作字段帮助定位是哪边触发的日志。",
                },
            },
        },
        "postprocessor": {
            "page_title": "Postprocessor",
            "nav": {
                "back": "← 返回 Dashboard",
                "home": "Dashboard",
                "current": "Postprocessor",
            },
            "hero": {
                "eyebrow": "Postprocessor",
                "title": "Postprocessor",
                "subtitle": "下载完成后的选优、等待窗口、自动发布与 review 分流工作台。",
                "worker_label": "Worker",
                "updated_label": "更新时间",
                "refresh_label": "自动刷新",
            },
            "panels": {
                "overview": {
                    "title": "运行概览",
                    "description": "当前 worker 状态、队列规模、等待窗口和人工审核积压。",
                },
                "config": {
                    "title": "路径与策略",
                    "description": "这页显示的根路径和策略，直接对应常驻 watch 使用的配置。",
                    "badge": "只读",
                },
                "commands": {
                    "title": "手动入口",
                    "description": "先给安全命令入口，不直接在页面里执行会改文件的动作。",
                    "logs": "Logs",
                    "review": "Ops Review",
                },
                "queue": {
                    "title": "当前队列",
                    "description": "和真实 watch 逻辑一致的分组快照：已就绪、等待窗口、仍在下载、已完成但未解析。",
                },
                "events": {
                    "title": "最近事件",
                    "description": "只看 `postprocessor` 自己写入的结构化事件，方便判断最近一轮到底做了什么。",
                },
            },
        },
        "tailscale": {
            "page_title": "Tailscale",
            "nav": {
                "back": "← 返回 Dashboard",
                "home": "Dashboard",
                "current": "Tailscale",
            },
            "hero": {
                "eyebrow": "Tailscale",
                "title": "Tailscale",
                "subtitle": "本地 tailnet 状态、peer 列表和节点可达性诊断。",
                "socket_label": "Socket",
                "updated_label": "更新时间",
                "refresh_label": "自动刷新",
            },
            "panels": {
                "peers": {
                    "title": "Peer 列表",
                    "description": "按在线优先排序，显示每台设备的系统、尾网地址、最近写入和 key 到期时间。",
                },
                "overview": {
                    "title": "状态概览",
                    "description": "只读取本机 Tailscale LocalAPI，不依赖官方云接口。",
                },
                "current_node": {
                    "title": "本机节点",
                    "description": "当前这台树莓派在 tailnet 里的身份、地址和有效期。",
                    "action": "开启 Tailscale",
                    "note": "本机节点摘要会在这里显示。",
                },
            },
        },
    },
    "en": {
        "dashboard": {
            "page_title": "Dashboard",
            "hero": {
                "eyebrow": "Control Surface",
                "summary": "Private anime ops console on Raspberry Pi",
                "health_label": "Health",
                "host_label": "Host",
                "updated_label": "Updated",
                "refresh_label": "Auto Refresh",
            },
            "panels": {
                "broadcast_wall": {
                    "title": "Broadcast Wall",
                    "description": "View a week of broadcasts, grouped by weekday with an Unknown row.",
                },
                "pipeline": {
                    "title": "Pipeline",
                    "description": "Core metrics for downloads, review, and library ingestion.",
                },
                "host_network": {
                    "title": "Host + Network",
                    "description": "Host health and remote access status at a glance.",
                },
                "trends": {
                    "title": "Trends",
                    "description": "24-hour lines and 7-day download bars.",
                },
                "diagnostics": {
                    "title": "Diagnostics",
                    "description": "Only gets loud when something is wrong.",
                    "loading": "Connecting to local data sources and refreshing panels.",
                },
            },
        },
        "ops_review": {
            "page_title": "Ops Review",
            "nav": {
                "back": "← Back to Dashboard",
                "home": "Dashboard",
                "current": "Ops Review",
            },
            "hero": {
                "eyebrow": "Ops Review",
                "title": "Ops Review",
                "subtitle": "Manual review queue and files that were not ingested automatically",
                "root_label": "Root",
                "updated_label": "Updated",
                "refresh_label": "Auto Refresh",
            },
            "panels": {
                "overview": {
                    "title": "Queue Overview",
                    "description": "Backlog size, storage, and bucket distribution for manual_review.",
                    "badge": "Detail Actions",
                    "note": "The list stays read-only. Retry parse, manual publish, and delete live on the detail page.",
                },
                "filters": {
                    "title": "Filters",
                    "description": "Narrow the queue first, then open the detail view for context and actions.",
                    "bucket_label": "Bucket",
                    "bucket_default": "All Buckets",
                    "search_label": "Search",
                    "search_placeholder": "Search title, filename, or path…",
                },
                "list": {
                    "title": "Pending Files",
                    "description": "Browse the current queue by series, reason, and path.",
                },
            },
        },
        "ops_review_item": {
            "page_title": "Review Detail",
            "nav": {"back": "← Back to Ops Review"},
            "hero": {
                "eyebrow": "Review Item",
                "title": "Review Item",
                "subtitle": "Loading file details",
                "bucket_label": "Bucket",
                "updated_label": "Updated",
                "refresh_label": "Auto Refresh",
            },
            "panels": {
                "details": {
                    "title": "File Details",
                    "description": "Context first. Destructive actions stay separate.",
                },
                "paths": {
                    "title": "Paths + Reason",
                    "description": "Where this file came from and why it remained in manual_review.",
                },
                "siblings": {
                    "title": "Sibling Files",
                    "description": "Use this to confirm alternate versions or split parts.",
                },
                "actions": {
                    "title": "Actions",
                    "description": "Try auto-parse first. Fall back to manual title, season, and episode when needed.",
                },
            },
        },
        "logs": {
            "page_title": "Logs",
            "nav": {
                "back": "← Back to Dashboard",
                "home": "Dashboard",
                "current": "Logs",
            },
            "hero": {
                "eyebrow": "Logs",
                "title": "Logs",
                "subtitle": "Structured event log for project-side operations",
                "storage_label": "Storage",
                "updated_label": "Updated",
                "refresh_label": "Auto Refresh",
            },
            "panels": {
                "overview": {
                    "title": "Log Overview",
                    "description": "Source, level, and retention are stored as structured fields for debugging and automation.",
                    "retention_badge": "Cap -",
                },
                "filters": {
                    "title": "Filters + Clear",
                    "description": "Filter by source, level, and keyword. The list refreshes every 10 seconds.",
                    "clear_button": "Clear Logs",
                    "source_label": "Source",
                    "source_default": "All Sources",
                    "level_label": "Level",
                    "level_default": "All Levels",
                    "search_label": "Search",
                    "search_placeholder": "Search action, message, or details…",
                },
                "events": {
                    "title": "Event List",
                    "description": "Color carries severity; source and action help pinpoint where the event came from.",
                },
            },
        },
        "postprocessor": {
            "page_title": "Postprocessor",
            "nav": {
                "back": "← Back to Dashboard",
                "home": "Dashboard",
                "current": "Postprocessor",
            },
            "hero": {
                "eyebrow": "Postprocessor",
                "title": "Postprocessor",
                "subtitle": "Workspace for post-download selection, wait windows, automatic publish, and review routing.",
                "worker_label": "Worker",
                "updated_label": "Updated",
                "refresh_label": "Auto Refresh",
            },
            "panels": {
                "overview": {
                    "title": "Operational Snapshot",
                    "description": "Worker status, queue volume, wait windows, and manual review backlog.",
                },
                "config": {
                    "title": "Paths + Policy",
                    "description": "The roots and policy used by the long-running watch worker.",
                    "badge": "Read Only",
                },
                "commands": {
                    "title": "Manual Entry Points",
                    "description": "Expose safe commands here instead of running file-mutating actions in the page.",
                    "logs": "Logs",
                    "review": "Ops Review",
                },
                "queue": {
                    "title": "Current Queue",
                    "description": "A snapshot of the real watch grouping: ready, waiting, active, and completed-but-unparsed.",
                },
                "events": {
                    "title": "Recent Events",
                    "description": "Only structured events written by postprocessor itself, so the last pass is easy to inspect.",
                },
            },
        },
        "tailscale": {
            "page_title": "Tailscale",
            "nav": {
                "back": "← Back to Dashboard",
                "home": "Dashboard",
                "current": "Tailscale",
            },
            "hero": {
                "eyebrow": "Tailscale",
                "title": "Tailscale",
                "subtitle": "Local tailnet status, peers, and node reachability diagnostics.",
                "socket_label": "Socket",
                "updated_label": "Updated",
                "refresh_label": "Auto Refresh",
            },
            "panels": {
                "peers": {
                    "title": "Peer List",
                    "description": "Sorted by online status, with OS, tailnet addresses, recent write time, and key expiry.",
                },
                "overview": {
                    "title": "Status Overview",
                    "description": "Reads only the local Tailscale LocalAPI. No cloud API required.",
                },
                "current_node": {
                    "title": "Current Node",
                    "description": "Identity, addresses, and expiry details for this Raspberry Pi on the tailnet.",
                    "action": "Start Tailscale",
                    "note": "The current node summary will appear here.",
                },
            },
        },
    },
}


def text(key: str, locale: str | None = None) -> str:
    return COPY[i18n.normalize_locale(locale or i18n.DEFAULT_LOCALE)][key]


def shell_copy(locale: str | None = None) -> dict:
    normalized = i18n.normalize_locale(locale or i18n.DEFAULT_LOCALE)
    return copy.deepcopy(SHELL_COPY[normalized])


def client_copy(locale: str | None = None) -> dict:
    normalized = i18n.normalize_locale(locale or i18n.DEFAULT_LOCALE)
    return copy.deepcopy(CLIENT_COPY[normalized])


def template_copy(template_name: str, locale: str | None = None) -> dict:
    normalized = i18n.normalize_locale(locale or i18n.DEFAULT_LOCALE)
    return copy.deepcopy(PAGE_TEMPLATE_COPY[normalized][template_name])


def payload_copy(section: str, locale: str | None = None) -> dict:
    normalized = i18n.normalize_locale(locale or i18n.DEFAULT_LOCALE)
    return copy.deepcopy(PAYLOAD_COPY[normalized][section])


def review_bucket_reason(bucket: str, locale: str | None = None) -> str:
    reasons = payload_copy("review", locale)["bucket_reasons"]
    return reasons.get(bucket, reasons["default"])


def review_bucket_label(bucket: str, locale: str | None = None) -> str:
    labels = payload_copy("review", locale)["bucket_labels"]
    return labels.get(bucket, labels["default"])


def review_auto_parse_reason(reason: str | None, locale: str | None = None) -> str | None:
    if not reason:
        return None
    reasons = payload_copy("review", locale)["auto_parse_reasons"]
    extension_match = re.fullmatch(r"unsupported extension: (.+)", reason)
    if extension_match:
        return reasons["unsupported_extension"].format(extension=extension_match.group(1))
    if reason == "cannot parse season/episode":
        return reasons["cannot_parse_season_episode"]
    if reason == "empty title after cleanup":
        return reasons["empty_title_after_cleanup"]
    return reasons["fallback"].format(reason=reason)


def postprocessor_worker_status(status: str | None, locale: str | None = None) -> str:
    normalized = i18n.normalize_locale(locale or i18n.DEFAULT_LOCALE)
    key = str(status or "unknown").strip().lower()
    translated = POSTPROCESSOR_WORKER_STATUS[normalized].get(key)
    if translated:
        return translated
    return key.replace("_", " ").title() if key else POSTPROCESSOR_WORKER_STATUS[normalized]["unknown"]


def postprocessor_group_reason(reason: str, locale: str | None = None) -> str:
    reasons = payload_copy("postprocessor", locale)["group_reasons"]
    if reason == "no completed candidates":
        return reasons["no_completed_candidates"]
    if reason == "best candidate already completed":
        return reasons["best_candidate_completed"]
    if reason == "all candidates completed":
        return reasons["all_candidates_completed"]
    if reason == "waiting for completion timestamp":
        return reasons["waiting_for_completion_timestamp"]
    timeout_match = re.fullmatch(r"wait timeout reached \((\d+)s\)", reason)
    if timeout_match:
        return reasons["wait_timeout_reached"].format(elapsed=timeout_match.group(1))
    waiting_match = re.fullmatch(
        r"waiting for higher-priority candidates \((\d+)s/(\d+)s\)",
        reason,
    )
    if waiting_match:
        return reasons["waiting_for_higher_priority_candidates"].format(
            elapsed=waiting_match.group(1),
            wait_timeout=waiting_match.group(2),
        )
    return reasons["fallback"].format(reason=reason)
