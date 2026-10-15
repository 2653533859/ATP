"""Mobile Network Simulation and Bandwidth/Loss Throttling Service (Q1.1).

Models network profiles (2G/3G/4G, satellite latency, packet loss, offline)
and translates them into Chrome DevTools Protocol (CDP) and Android ADB commands.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any

logger = logging.getLogger(__name__)

# Standard preset network simulation profiles
PRESET_NETWORK_PROFILES: dict[str, dict[str, Any]] = {
    "offline": {
        "name": "离线模式 (Offline)",
        "offline": True,
        "latency_ms": 0,
        "jitter_ms": 0,
        "download_kbps": 0,
        "upload_kbps": 0,
        "packet_loss_percent": 100.0,
        "connection_type": "none",
        "description": "完全断网状态，所有网络数据包 100% 丢弃",
    },
    "2g_gprs": {
        "name": "2G GPRS 弱网",
        "offline": False,
        "latency_ms": 500,
        "jitter_ms": 100,
        "download_kbps": 50,
        "upload_kbps": 20,
        "packet_loss_percent": 2.0,
        "connection_type": "cellular2g",
        "description": "极慢蜂窝网络，高延迟 500ms，下载 50kbps",
    },
    "2g_edge": {
        "name": "2G EDGE 弱网",
        "offline": False,
        "latency_ms": 300,
        "jitter_ms": 60,
        "download_kbps": 250,
        "upload_kbps": 100,
        "packet_loss_percent": 1.0,
        "connection_type": "cellular2g",
        "description": "典型 2G 弱网，延迟 300ms，下载 250kbps",
    },
    "3g_hspa": {
        "name": "3G HSPA 移动网络",
        "offline": False,
        "latency_ms": 100,
        "jitter_ms": 20,
        "download_kbps": 1500,
        "upload_kbps": 750,
        "packet_loss_percent": 0.5,
        "connection_type": "cellular3g",
        "description": "中速 3G 网络，延迟 100ms，下载 1.5Mbps",
    },
    "4g_lte": {
        "name": "4G LTE 高速移动网络",
        "offline": False,
        "latency_ms": 30,
        "jitter_ms": 5,
        "download_kbps": 20000,
        "upload_kbps": 10000,
        "packet_loss_percent": 0.0,
        "connection_type": "cellular4g",
        "description": "高速 4G 蜂窝网络，延迟 30ms，下载 20Mbps",
    },
    "satellite_high_latency": {
        "name": "卫星/长距离高延迟",
        "offline": False,
        "latency_ms": 800,
        "jitter_ms": 150,
        "download_kbps": 2000,
        "upload_kbps": 1000,
        "packet_loss_percent": 1.5,
        "connection_type": "other",
        "description": "极高物理延迟 800ms，抖动 150ms",
    },
    "high_packet_loss": {
        "name": "高丢包恶劣网络",
        "offline": False,
        "latency_ms": 150,
        "jitter_ms": 50,
        "download_kbps": 5000,
        "upload_kbps": 2000,
        "packet_loss_percent": 15.0,
        "connection_type": "wifi",
        "description": "严重网络丢包 15%，用于检验断线重试与容错韧性",
    },
}


def get_preset_network_profiles() -> dict[str, dict[str, Any]]:
    """Return all predefined network simulation profiles."""
    return PRESET_NETWORK_PROFILES


def calculate_network_transmission_delay(
    profile: dict[str, Any],
    payload_bytes: int = 0,
    *,
    seed: int | None = None,
) -> float:
    """Calculate the estimated network transfer delay in seconds based on bandwidth, latency, and jitter."""
    if profile.get("offline"):
        return float("inf")

    latency_s = float(profile.get("latency_ms", 0)) / 1000.0
    jitter_ms = float(profile.get("jitter_ms", 0))

    # Bandwidth transmission delay
    download_kbps = float(profile.get("download_kbps", 0))
    trans_s = 0.0
    if download_kbps > 0 and payload_bytes > 0:
        # payload_bytes * 8 bits / (download_kbps * 1000 bits/s)
        trans_s = (payload_bytes * 8.0) / (download_kbps * 1000.0)

    # Jitter calculation
    rnd = random.Random(seed) if seed is not None else random
    jitter_s = (rnd.uniform(-jitter_ms, jitter_ms) / 1000.0) if jitter_ms > 0 else 0.0

    total_s = max(0.0, latency_s + trans_s + jitter_s)
    return round(total_s, 4)


def is_packet_dropped(
    profile: dict[str, Any],
    *,
    seed: float | None = None,
) -> bool:
    """Return True if a simulated packet should be dropped based on packet loss rate or offline state."""
    if profile.get("offline"):
        return True

    loss_pct = float(profile.get("packet_loss_percent", 0.0))
    if loss_pct <= 0.0:
        return False
    if loss_pct >= 100.0:
        return True

    rnd = random.Random(seed) if seed is not None else random
    return rnd.uniform(0.0, 100.0) < loss_pct


def generate_cdp_network_conditions(profile: dict[str, Any]) -> dict[str, Any]:
    """Generate Chrome DevTools Protocol (CDP) Network.emulateNetworkConditions parameters."""
    offline = bool(profile.get("offline", False))
    latency_ms = int(profile.get("latency_ms", 0))
    dl_kbps = float(profile.get("download_kbps", 0))
    ul_kbps = float(profile.get("upload_kbps", 0))

    # CDP throughput expects bytes/second (-1 for disabled)
    dl_bps = -1 if offline or dl_kbps <= 0 else math.floor((dl_kbps * 1024) / 8)
    ul_bps = -1 if offline or ul_kbps <= 0 else math.floor((ul_kbps * 1024) / 8)

    return {
        "offline": offline,
        "latency": latency_ms,
        "downloadThroughput": dl_bps,
        "uploadThroughput": ul_bps,
        "connectionType": profile.get("connection_type", "cellular3g"),
    }


def generate_adb_network_commands(profile: dict[str, Any]) -> list[list[str]]:
    """Generate Android ADB shell commands to apply or reset device network conditions."""
    if profile.get("offline"):
        return [
            ["svc", "data", "disable"],
            ["svc", "wifi", "disable"],
        ]

    # For online state, ensure interfaces enabled
    commands = [
        ["svc", "data", "enable"],
        ["svc", "wifi", "enable"],
    ]

    loss = float(profile.get("packet_loss_percent", 0.0))
    latency = int(profile.get("latency_ms", 0))
    if latency > 0 or loss > 0:
        # tc qdisc netem command for traffic control
        netem_args = ["tc", "qdisc", "add", "dev", "wlan0", "root", "netem"]
        if latency > 0:
            netem_args.extend(["delay", f"{latency}ms"])
        if loss > 0:
            netem_args.extend(["loss", f"{loss}%"])
        commands.append(netem_args)

    return commands
