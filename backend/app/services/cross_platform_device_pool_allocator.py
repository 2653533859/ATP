"""跨端移动设备统一调度分配器服务 (T2.3)

屏蔽 Android (ADB 隧道) 与 iOS (WDA 隧道) 底层差异,
为自动化测试中心、持续集成流水线与远程控制中枢提供跨端统一资源分配:
1. 统一移动真机抽象 (Unified Device Model: Android & iOS);
2. 约束匹配智能调度算法 (Platform, OS Version, Brand, Model, Health);
3. 自动原子抢占租约与直连端口返回 (Auto Lease & Tunnel Direct Connect);
4. 移动真机池容量与负载实时统计 (Pool Capacity Summary)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.ios_device_heartbeat_keeper import list_heartbeat_records
from app.services.ios_lease_scheduler import acquire_ios_lease, get_active_lease
from app.services.ios_tunnel_bridge import list_active_ios_tunnels


@dataclass
class UnifiedDevice:
    unified_id: str  # "ios:<udid>" 或 "android:<serial>"
    raw_id: str  # udid 或 serial
    platform: str  # "ios" | "android"
    name: str
    model: str
    brand: str
    os_version: str
    status: str  # "IDLE" | "BUSY" | "OFFLINE"
    tunnel_port: int
    battery_level: int
    is_charging: bool
    temperature_celsius: float
    current_lease_owner: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unified_id": self.unified_id,
            "raw_id": self.raw_id,
            "platform": self.platform,
            "name": self.name,
            "model": self.model,
            "brand": self.brand,
            "os_version": self.os_version,
            "status": self.status,
            "tunnel_port": self.tunnel_port,
            "battery_level": self.battery_level,
            "is_charging": self.is_charging,
            "temperature_celsius": round(self.temperature_celsius, 1),
            "current_lease_owner": self.current_lease_owner,
        }


# 模拟全局注册的 Android 仿真/物理设备表 (可对接 remote_agent_devices)
_MOCK_ANDROID_DEVICES: Dict[str, Dict[str, Any]] = {}


def register_mock_android_device(
    serial: str,
    name: str = "Xiaomi 14",
    model: str = "23127PN0CC",
    brand: str = "Xiaomi",
    os_version: str = "14.0",
    tunnel_port: int = 5555,
    status: str = "IDLE",
    battery_level: int = 90,
) -> None:
    _MOCK_ANDROID_DEVICES[serial] = {
        "serial": serial,
        "name": name,
        "model": model,
        "brand": brand,
        "os_version": os_version,
        "tunnel_port": tunnel_port,
        "status": status,
        "battery_level": battery_level,
    }


def clear_mock_android_devices() -> None:
    _MOCK_ANDROID_DEVICES.clear()


def list_all_unified_devices() -> List[UnifiedDevice]:
    """汇总并返回当前全平台 (iOS & Android) 所有统一设备列表"""
    devices: List[UnifiedDevice] = []

    # 1. 采集 iOS 真机池
    ios_tunnels = {t["udid"]: t for t in list_active_ios_tunnels()}
    ios_heartbeats = {h["udid"]: h for h in list_heartbeat_records()}

    for udid, t in ios_tunnels.items():
        hb = ios_heartbeats.get(udid, {})
        lease = get_active_lease(udid)

        if hb.get("status") == "OFFLINE":
            dev_status = "OFFLINE"
        elif lease and lease.is_active:
            dev_status = "BUSY"
        else:
            dev_status = "IDLE"

        devices.append(
            UnifiedDevice(
                unified_id=f"ios:{udid}",
                raw_id=udid,
                platform="ios",
                name=t.get("device_name", "iPhone"),
                model=t.get("model", "iPhone"),
                brand="Apple",
                os_version=t.get("ios_version", "17.0"),
                status=dev_status,
                tunnel_port=t.get("local_tunnel_port", 8100),
                battery_level=hb.get("battery_level", 100),
                is_charging=hb.get("battery_charging", True),
                temperature_celsius=hb.get("temperature_celsius", 28.0),
                current_lease_owner=lease.owner_label if lease else None,
            )
        )

    # 2. 采集 Android 真机池
    for serial, a in _MOCK_ANDROID_DEVICES.items():
        devices.append(
            UnifiedDevice(
                unified_id=f"android:{serial}",
                raw_id=serial,
                platform="android",
                name=a.get("name", "Android Phone"),
                model=a.get("model", "Pixel"),
                brand=a.get("brand", "Google"),
                os_version=a.get("os_version", "13.0"),
                status=a.get("status", "IDLE"),
                tunnel_port=a.get("tunnel_port", 5555),
                battery_level=a.get("battery_level", 95),
                is_charging=True,
                temperature_celsius=27.5,
                current_lease_owner=None,
            )
        )

    return devices


def allocate_matching_device(
    platform: str = "any",  # "ios" | "android" | "any"
    brand: str | None = None,
    min_os_version: str | None = None,
    prefer_idle: bool = True,
    auto_lease: bool = False,
    owner_id: str | int = "system",
    owner_label: str = "Automated-Test-Scheduler",
) -> Optional[Dict[str, Any]]:
    """根据测试诉求跨端匹配最佳真机，并可选自动申请租约

    返回: 匹配成功设备信息字典及 lease_token (若 auto_lease=True)
    """
    candidates = list_all_unified_devices()

    # 1. 平台过滤
    if platform.lower() != "any":
        candidates = [d for d in candidates if d.platform.lower() == platform.lower()]

    # 2. 品牌过滤
    if brand:
        candidates = [d for d in candidates if brand.lower() in d.brand.lower()]

    # 3. 最低系统版本过滤
    if min_os_version:
        candidates = [d for d in candidates if d.os_version >= min_os_version]

    # 3. 优先空闲状态
    if prefer_idle:
        idle_only = [d for d in candidates if d.status == "IDLE"]
        if idle_only:
            candidates = idle_only

    # 4. 排序：按空闲优先、电量降序、温度升序择优
    candidates.sort(
        key=lambda d: (
            0 if d.status == "IDLE" else 1,
            -d.battery_level,
            d.temperature_celsius,
        )
    )

    if not candidates:
        return None

    best = candidates[0]
    res = best.to_dict()

    # 5. 若请求自动租用且设备为 iOS
    if auto_lease and best.platform == "ios" and best.status == "IDLE":
        lease = acquire_ios_lease(
            udid=best.raw_id,
            owner_id=owner_id,
            owner_label=owner_label,
            purpose="unified_scheduler_auto_allocation",
        )
        res["lease_token"] = lease.lease_token
        res["status"] = "BUSY"
        res["current_lease_owner"] = owner_label

    return res


def get_device_pool_capacity_summary() -> Dict[str, Any]:
    """获取跨端移动真机池的容量与健康度统计"""
    all_devs = list_all_unified_devices()
    total = len(all_devs)
    ios_devs = [d for d in all_devs if d.platform == "ios"]
    android_devs = [d for d in all_devs if d.platform == "android"]

    idle_count = sum(1 for d in all_devs if d.status == "IDLE")
    busy_count = sum(1 for d in all_devs if d.status == "BUSY")
    offline_count = sum(1 for d in all_devs if d.status == "OFFLINE")

    return {
        "total_devices": total,
        "idle_devices": idle_count,
        "busy_devices": busy_count,
        "offline_devices": offline_count,
        "ios_devices_count": len(ios_devs),
        "android_devices_count": len(android_devs),
        "pool_utilization_rate": round(busy_count / max(1, total), 3),
    }
