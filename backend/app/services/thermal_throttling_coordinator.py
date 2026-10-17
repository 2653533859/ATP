"""设备过热保护与温备降载协调器服务 (T2.2)

负责物理真机集群的硬件温度防护、阶梯式并发降载与静默冷却轮换:
1. 三级温度阶梯策略 (NORMAL <= 38°C | THROTTLED 38~42°C | EMERGENCY_COOLING > 42°C);
2. 动态并发削减与冷却保护 (并发减半、强制静默、温度回落自动恢复);
3. 设备热力轮换与温备保活 (主动轮换高热设备至健康温备机);
4. 过热事件审计与实时状态监控。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.fleet_health_telemetry import (
    DeviceHealthStatus,
    get_device_telemetry,
    list_fleet_telemetry,
)


class ThermalPolicyTier(str, enum.Enum):
    NORMAL = "NORMAL"  # 正常温区 (<= 38.0°C)
    THROTTLED = "THROTTLED"  # 警戒降载区 (38.1°C ~ 42.0°C)
    EMERGENCY_COOLING = "EMERGENCY_COOLING"  # 紧急冷却区 (> 42.0°C)


class ThermalActionTaken(str, enum.Enum):
    NO_ACTION = "NO_ACTION"  # 保持原状
    CONCURRENCY_HALVED = "CONCURRENCY_HALVED"  # 并发上限减半降载
    ENTER_EMERGENCY_COOLING = "ENTER_EMERGENCY_COOLING"  # 强制静默冷却并冻结调度
    CAPACITY_RESTORED = "CAPACITY_RESTORED"  # 降温达标，恢复初始并发容量


@dataclass
class ThermalThrottlingEvent:
    event_id: str
    device_id: str
    temperature_c: float
    previous_tier: ThermalPolicyTier
    current_tier: ThermalPolicyTier
    action_taken: ThermalActionTaken
    original_max_concurrency: int
    adjusted_max_concurrency: int
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["previous_tier"] = self.previous_tier.value
        d["current_tier"] = self.current_tier.value
        d["action_taken"] = self.action_taken.value
        return d


# 初始默认最大并发基线记录 (device_id -> int)
_BASELINE_CONCURRENCY: Dict[str, int] = {}
# 当前热保护阶梯 (device_id -> ThermalPolicyTier)
_CURRENT_TIERS: Dict[str, ThermalPolicyTier] = {}
# 事件流水
_THROTTLING_EVENTS: Dict[str, ThermalThrottlingEvent] = {}


def clear_thermal_coordinator_state() -> None:
    """清空热保护协调器内存状态（测试夹具使用）"""
    _BASELINE_CONCURRENCY.clear()
    _CURRENT_TIERS.clear()
    _THROTTLING_EVENTS.clear()


def determine_thermal_tier(temp_c: float) -> ThermalPolicyTier:
    """根据电池温度判定所处的温区阶梯"""
    if temp_c > 42.0:
        return ThermalPolicyTier.EMERGENCY_COOLING
    elif temp_c > 38.0:
        return ThermalPolicyTier.THROTTLED
    return ThermalPolicyTier.NORMAL


def coordinate_device_thermal_policy(device_id: str) -> Optional[ThermalThrottlingEvent]:
    """对单台设备执行温度健康检查并执行自适应并发降载/冷却调节"""
    dev = get_device_telemetry(device_id)
    if not dev:
        return None

    # 初始化基线并发配置
    if device_id not in _BASELINE_CONCURRENCY:
        _BASELINE_CONCURRENCY[device_id] = dev.max_concurrency

    baseline_max = _BASELINE_CONCURRENCY[device_id]
    prev_tier = _CURRENT_TIERS.get(device_id, ThermalPolicyTier.NORMAL)
    current_tier = determine_thermal_tier(dev.battery_temperature_c)

    eid = f"threv_{uuid.uuid4().hex[:10]}"
    event: Optional[ThermalThrottlingEvent] = None

    if current_tier == ThermalPolicyTier.EMERGENCY_COOLING:
        # 1. 超过 42°C: 紧急切断调度
        dev.max_concurrency = 0
        dev.health_status = DeviceHealthStatus.OVERHEATED
        _CURRENT_TIERS[device_id] = current_tier

        if prev_tier != ThermalPolicyTier.EMERGENCY_COOLING:
            event = ThermalThrottlingEvent(
                event_id=eid,
                device_id=device_id,
                temperature_c=dev.battery_temperature_c,
                previous_tier=prev_tier,
                current_tier=current_tier,
                action_taken=ThermalActionTaken.ENTER_EMERGENCY_COOLING,
                original_max_concurrency=baseline_max,
                adjusted_max_concurrency=0,
                reason=f"电池温度 ({dev.battery_temperature_c}°C) 突破 42°C 极限门限，强制进入静默降温状态",
            )
            _THROTTLING_EVENTS[eid] = event

    elif current_tier == ThermalPolicyTier.THROTTLED:
        # 2. 处于 38~42°C: 并发减半降载 (至少保留 1 个并发)
        new_max = max(1, baseline_max // 2)
        dev.max_concurrency = new_max
        dev.health_status = DeviceHealthStatus.WARMING
        _CURRENT_TIERS[device_id] = current_tier

        if prev_tier != ThermalPolicyTier.THROTTLED:
            event = ThermalThrottlingEvent(
                event_id=eid,
                device_id=device_id,
                temperature_c=dev.battery_temperature_c,
                previous_tier=prev_tier,
                current_tier=current_tier,
                action_taken=ThermalActionTaken.CONCURRENCY_HALVED,
                original_max_concurrency=baseline_max,
                adjusted_max_concurrency=new_max,
                reason=f"电池温度 ({dev.battery_temperature_c}°C) 达到警戒温区，执行并发上限下调降载 ({baseline_max} ➔ {new_max})",
            )
            _THROTTLING_EVENTS[eid] = event

    else:
        # 3. 正常温区 (<= 38.0°C): 恢复基线并发能力
        _CURRENT_TIERS[device_id] = ThermalPolicyTier.NORMAL
        if prev_tier in (ThermalPolicyTier.THROTTLED, ThermalPolicyTier.EMERGENCY_COOLING):
            dev.max_concurrency = baseline_max
            dev.health_status = DeviceHealthStatus.HEALTHY
            event = ThermalThrottlingEvent(
                event_id=eid,
                device_id=device_id,
                temperature_c=dev.battery_temperature_c,
                previous_tier=prev_tier,
                current_tier=current_tier,
                action_taken=ThermalActionTaken.CAPACITY_RESTORED,
                original_max_concurrency=baseline_max,
                adjusted_max_concurrency=baseline_max,
                reason=f"电池温度已安全回落至 {dev.battery_temperature_c}°C，解除热限流保护，完全恢复初始并发能力 ({baseline_max})",
            )
            _THROTTLING_EVENTS[eid] = event

    return event


def scan_and_coordinate_fleet_thermals() -> List[ThermalThrottlingEvent]:
    """批量扫描并协调全集群真机过热保护状态"""
    devices = list_fleet_telemetry()
    events: List[ThermalThrottlingEvent] = []

    for dev in devices:
        ev = coordinate_device_thermal_policy(dev.device_id)
        if ev:
            events.append(ev)

    return events


def list_thermal_throttling_events(limit: int = 50) -> List[Dict[str, Any]]:
    """查询近期过热降载事件审计记录"""
    items = list(_THROTTLING_EVENTS.values())
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return [i.to_dict() for i in items[:limit]]
