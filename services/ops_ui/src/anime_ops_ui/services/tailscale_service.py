from __future__ import annotations

from datetime import datetime
from typing import Any

from anime_ops_ui.copy import payload_copy


def build_tailscale_payload(*, locale: str | None = None) -> dict[str, Any]:
    from anime_ops_ui import main as main_module

    copy = payload_copy("tailscale", locale)
    base_host = main_module._env("HOMEPAGE_BASE_HOST", __import__("socket").gethostname())
    tailscale_socket = main_module._env("TAILSCALE_SOCKET", "/var/run/tailscale/tailscaled.sock")
    tailscale, tailscale_error = main_module._tailscale_status(tailscale_socket)
    prefs, prefs_error = main_module._tailscale_prefs(tailscale_socket)
    self_info = ((tailscale or {}).get("Self") or {}) if isinstance(tailscale, dict) else {}
    peer_map = ((tailscale or {}).get("Peer") or {}) if isinstance(tailscale, dict) else {}
    peer_values = list(peer_map.values()) if isinstance(peer_map, dict) else []
    backend_state = (tailscale or {}).get("BackendState", "unavailable") if tailscale else "unavailable"
    health_messages = list((tailscale or {}).get("Health", [])) if isinstance(tailscale, dict) else []
    online_peer_count = sum(1 for peer in peer_values if peer.get("Online"))
    exit_node_candidates = sum(1 for peer in peer_values if peer.get("ExitNodeOption"))
    tail_ip, ipv6 = main_module._tailscale_ip_pair(self_info.get("TailscaleIPs") if self_info else None)
    dns_name = main_module._strip_trailing_dot(self_info.get("DNSName"))
    self_online = bool(self_info.get("Online"))
    want_running = bool((prefs or {}).get("WantRunning")) if isinstance(prefs, dict) else backend_state == "Running"
    reachability = copy["reachability"]["online"] if self_online else (copy["reachability"]["stopped"] if not want_running else copy["reachability"]["offline"])
    logged_out = bool((prefs or {}).get("LoggedOut")) if isinstance(prefs, dict) else backend_state in {"NeedsLogin", "NoState"}
    machinekey_error = any("machinekey" in str(message).lower() for message in health_messages)
    control_action = "stop" if want_running else "start"
    control_label = copy["control"]["stop_label"] if control_action == "stop" else copy["control"]["start_label"]
    if control_action == "stop":
        control_detail = copy["control"]["stop_detail"]
    elif machinekey_error:
        control_detail = copy["control"]["machinekey_detail"]
    elif backend_state in {"NeedsLogin", "NoState"} or logged_out:
        control_detail = copy["control"]["login_detail"]
    else:
        control_detail = copy["control"]["resume_detail"]
    if self_online:
        self_note = copy["self_note"]["online"]
    elif machinekey_error:
        self_note = copy["self_note"]["machinekey"]
    elif backend_state in {"NeedsLogin", "NoState"} or logged_out:
        self_note = copy["self_note"]["logged_out"]
    elif not want_running:
        self_note = copy["self_note"]["stopped"]
    else:
        self_note = copy["self_note"]["offline"]

    summary_cards = [
        {
            "label": copy["summary_cards"]["backend"]["label"],
            "value": backend_state,
            "detail": copy["summary_cards"]["backend"]["detail"],
        },
        {
            "label": copy["summary_cards"]["reachability"]["label"],
            "value": reachability,
            "detail": copy["summary_cards"]["reachability"]["detail"],
        },
        {
            "label": copy["summary_cards"]["peers"]["label"],
            "value": str(len(peer_values)),
            "detail": copy["summary_cards"]["peers"]["detail"].format(online=online_peer_count, exit_nodes=exit_node_candidates),
        },
        {
            "label": copy["summary_cards"]["tailnet_ip"]["label"],
            "value": tail_ip,
            "detail": dns_name,
        },
    ]

    self_cards = [
        {
            "label": copy["self_cards"]["host"]["label"],
            "value": self_info.get("HostName") or base_host,
            "detail": dns_name,
        },
        {
            "label": copy["self_cards"]["reachability"]["label"],
            "value": copy["self_cards"]["reachability"]["yes"] if self_online else copy["self_cards"]["reachability"]["no"],
            "detail": copy["self_cards"]["reachability"]["yes_detail"] if self_online else copy["self_cards"]["reachability"]["no_detail"],
        },
        {
            "label": copy["self_cards"]["ipv4"]["label"],
            "value": tail_ip,
            "detail": copy["self_cards"]["ipv4"]["detail"],
        },
        {
            "label": copy["self_cards"]["ipv6"]["label"],
            "value": ipv6,
            "detail": copy["self_cards"]["ipv6"]["detail"],
        },
        {
            "label": copy["self_cards"]["current_addr"]["label"],
            "value": main_module._strip_trailing_dot(self_info.get("CurAddr")),
            "detail": copy["self_cards"]["current_addr"]["detail"].format(relay=self_info.get("Relay", "-")),
        },
        {
            "label": copy["self_cards"]["traffic"]["label"],
            "value": f"{main_module._format_bytes(self_info.get('RxBytes', 0))} ↓",
            "detail": f"{main_module._format_bytes(self_info.get('TxBytes', 0))} ↑",
        },
    ]

    peer_cards = []
    peer_list = []
    for peer in sorted(peer_values, key=lambda item: str(item.get("HostName", "")).lower()):
        peer_ip, peer_ipv6 = main_module._tailscale_ip_pair(peer.get("TailscaleIPs"))
        peer_status = "online" if peer.get("Online") else "offline"
        peer_cards.append(
            {
                "hostname": peer.get("HostName") or peer.get("DNSName") or "unknown",
                "dns_name": main_module._strip_trailing_dot(peer.get("DNSName")),
                "online": bool(peer.get("Online")),
                "os": peer.get("OS") or "-",
                "tailnet_ips": peer.get("TailscaleIPs") or [],
                "rx_bytes": peer.get("RxBytes", 0),
                "tx_bytes": peer.get("TxBytes", 0),
                "last_seen": _format_peer_time(peer.get("LastSeen")),
                "last_handshake": _format_peer_time(peer.get("LastHandshake")),
                "key_expiry": _format_peer_time(peer.get("KeyExpiry")),
                "exit_node": bool(peer.get("ExitNodeOption")),
                "taildrop": peer.get("TaildropTarget", 0),
            }
        )
        peer_list.append(
            {
                "host_name": peer.get("HostName") or peer.get("DNSName") or "unknown",
                "dns_name": main_module._strip_trailing_dot(peer.get("DNSName")),
                "status": peer_status,
                "active": bool(peer.get("Active")),
                "exit_node_option": bool(peer.get("ExitNodeOption")),
                "exit_node": bool(peer.get("ExitNode")),
                "ip": peer_ip,
                "ipv6": peer_ipv6,
                "current_addr": main_module._strip_trailing_dot(peer.get("CurAddr")),
                "relay": peer.get("Relay") or "-",
                "rx_label": main_module._format_bytes(peer.get("RxBytes", 0)),
                "tx_label": main_module._format_bytes(peer.get("TxBytes", 0)),
                "last_write_label": main_module._format_iso_datetime(peer.get("LastWrite")),
                "last_handshake_label": main_module._format_iso_datetime(peer.get("LastHandshake")),
                "last_seen_label": main_module._format_iso_datetime(peer.get("LastSeen")),
                "key_expiry_label": main_module._format_iso_datetime(peer.get("KeyExpiry")),
                "os": peer.get("OS") or "-",
            }
        )

    diagnostics = []
    for label, error in (
        ("tailscale", tailscale_error),
        ("tailscale/prefs", prefs_error),
    ):
        if error:
            diagnostics.append({"source": label, "message": error})
    if machinekey_error:
        diagnostics.append(
            {
                "source": "tailscale",
                "message": copy["diagnostics"]["machinekey"],
            }
        )

    return {
        "title": copy["title"],
        "subtitle": copy["subtitle"],
        "copy": copy["page"],
        "refresh_interval_seconds": 15,
        "socket_path": tailscale_socket,
        "backend_state": backend_state,
        "reachability": reachability,
        "self_note": self_note,
        "control": {
            "action": control_action,
            "label": control_label,
            "detail": control_detail,
        },
        "peer_total": len(peer_values),
        "peer_online": online_peer_count,
        "peers": peer_list,
        "status": {
            "backend_state": backend_state,
            "reachable": self_online,
            "want_running": want_running,
            "control_action": control_action,
            "control_label": control_label,
            "control_detail": control_detail,
            "self_note": self_note,
        },
        "summary_cards": summary_cards,
        "self_cards": self_cards,
        "peer_cards": peer_cards,
        "diagnostics": diagnostics,
        "current_node": {
            "host": self_info.get("HostName") or base_host,
            "dns_name": dns_name,
            "ipv4": tail_ip,
            "ipv6": ipv6,
            "backend_state": backend_state,
            "reachable": self_online,
            "control_action": control_action,
            "control_label": control_label,
            "control_detail": control_detail,
            "self_note": self_note,
        },
        "current_node_summary": {
            "host": self_info.get("HostName") or base_host,
            "reachable": self_online,
            "status": backend_state,
        },
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


def build_tailscale_snapshot(*, locale: str | None = None) -> dict[str, Any]:
    return build_tailscale_payload(locale=locale)


def _format_peer_time(value: str | None) -> str:
    if not value or value.startswith("0001-01-01"):
        return "-"
    return value
