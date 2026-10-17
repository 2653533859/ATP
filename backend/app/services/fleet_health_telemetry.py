"""物理真机集群健康多维遥测与感知器服务 (T1.1)

实时感知并评估大规模真实物理真机 (iOS / Android) 的物理与系统健康度:
1. 物理环境遥测 (电池温度、电池电量、充放电状态);
2. 系统性能与容量水位 (CPU 占用、空闲内存、当前并发任务数/上限);
3. 通信管道质量感知 (USB / WDA / ADB 隧道 RTT 延迟);
4. 多维健康综合评分算法 (Health Score 0~100) 与准入调度资格裁决。
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class DeviceHealthStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"  # 健康优良，可积极派发任务
    WARMING = "WARMING"  # 轻度升温或高负载，需降速限流
    OVERHEATED = "OVERHEATED"  # 严重过热 (>42°C)，强制进入静默冷却
    LOW_BATTERY = "LOW_BATTERY"  # 低电量 (<20%)，暂停高功耗测试
    OFFLINE = "OFFLINE"  # 心跳丢失掉线


class BatteryState(str, enum.Enum):
    CHARGING = "CHARGING"
    DISCHARGING = "DISCHARGING"
    FULL = "FULL"


@dataclass
class DeviceHealthMetric:
    device_id: str
    platform: str  # ios | android
    battery_temperature_c: float
    battery_level_percent: int
    battery_state: BatteryState = BatteryState.CHARGING
    cpu_usage_percent: float = 20.0
    memory_free_mb: int = 1500
    current_concurrency: int = 0
    max_concurrency: int = 2
    tunnel_rtt_ms: float = 12.0
    health_status: DeviceHealthStatus = DeviceHealthStatus.HEALTHY
    health_score: float = 100.0
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["health_status"] = self.health_status.value
        d["battery_state"] = self.battery_state.value
        d["health_score"] = round(self.health_score, 2)
        return d


_FLEET_TELEMETRY_STORE: Dict[str, DeviceHealthMetric] = {}


def clear_fleet_telemetry() -> None:
    """清空遥测内存库（测试夹具使用）"""
    _FLEET_TELEMETRY_STORE.clear()


def calculate_health_score(metric: DeviceHealthMetric) -> Tuple[float, DeviceHealthStatus]:
    """多维加权计算真机综合健康分与健康等级

    权重分配:
    - 电池温度 (40%)
    - 电池电量 (25%)
    - 隧道 RTT 时延 (20%)
    - 算力与并发负载 (15%)
    """
    # 1. 电池温度得分 (40%)
    temp = metric.battery_temperature_c
    if temp <= 35.0:
        temp_score = 100.0
    elif temp <= 39.0:
        temp_score = 85.0
    elif temp <= 42.0:
        temp_score = 50.0
    else:
        temp_score = 0.0

    # 2. 电池电量得分 (25%)
    bat = metric.battery_level_percent
    if bat >= 50:
        bat_score = 100.0
    elif bat >= 20:
        bat_score = 70.0
    else:
        bat_score = 15.0

    # 3. 隧道 RTT 时延得分 (20%)
    rtt = metric.tunnel_rtt_ms
    if rtt <= 25.0:
        rtt_score = 100.0
    elif rtt <= 70.0:
        rtt_score = 80.0
    elif rtt <= 150.0:
        rtt_score = 45.0
    else:
        rtt_score = 10.0

    # 4. 算力与并发负载 (15%)
    if metric.current_concurrency < metric.max_concurrency:
        load_score = 100.0 - (metric.current_concurrency / metric.max_concurrency) * 40.0
    elif metric.current_concurrency == metric.max_concurrency:
        load_score = 30.0
    else:
        load_score = 0.0

    composite = temp_score * 0.40 + bat_score * 0.25 + rtt_score * 0.20 + load_score * 0.15

    # 状态判定
    if temp > 42.0:
        status = DeviceHealthStatus.OVERHEATED
    elif bat < 20:
        status = DeviceHealthStatus.LOW_BATTERY
    elif composite >= 80.0:
        status = DeviceHealthStatus.HEALTHY
    elif composite >= 50.0:
        status = DeviceHealthStatus.WARMING
    else:
        status = DeviceHealthStatus.WARMING

    return composite, status


def record_device_telemetry(
    device_id: str,
    platform: str,
    battery_temp_c: float,
    battery_level: int,
    battery_state: BatteryState = BatteryState.CHARGING,
    cpu_usage: float = 25.0,
    memory_free_mb: int = 1200,
    current_concurrency: int = 0,
    max_concurrency: int = 2,
    tunnel_rtt_ms: float = 15.0,
) -> DeviceHealthMetric:
    """采集或上报真机实时健康遥测数据"""
    metric = DeviceHealthMetric(
        device_id=device_id,
        platform=platform.lower(),
        battery_temperature_c=battery_temp_c,
        battery_level_percent=battery_level,
        battery_state=battery_state,
        cpu_usage_percent=cpu_usage,
        memory_free_mb=memory_free_mb,
        current_concurrency=current_concurrency,
        max_concurrency=max_concurrency,
        tunnel_rtt_ms=tunnel_rtt_ms,
    )

    score, status = calculate_health_score(metric)
    metric.health_score = score
    metric.health_status = status

    _FLEET_TELEMETRY_STORE[device_id] = metric
    return metric


def get_device_telemetry(device_id: str) -> Optional[DeviceHealthMetric]:
    """查询单台真机最新健康遥测数据"""
    return _FLEET_TELEMETRY_STORE.get(device_id)


def list_fleet_telemetry(platform: Optional[str] = None) -> List[DeviceHealthMetric]:
    """列出全集群物理真机健康遥测数据"""
    items = list(_FLEET_TELEMETRY_STORE.values())
    if platform:
        items = [i for i in items if i.platform == platform.lower()]
    # 按健康分从高到低排序
    items.sort(key=lambda x: x.health_score, reverse=True)
    return items


def is_device_eligible_for_dispatch(device_id: str) -> Tuple[bool, str]:
    """校验真机当前是否满足任务调度与派发条件"""
    m = _FLEET_TELEMETRY_STORE.get(device_id)
    if not m:
        return False, f"设备 [{device_id}] 未发现遥测心跳"

    if m.health_status == DeviceHealthStatus.OVERHEATED:
        return False, f"设备过热 ({m.battery_temperature_c}°C > 42°C)，处于强制冷却保护状态"

    if m.health_status == DeviceHealthStatus.LOW_BATTERY:
        return False, f"设备电量不足 ({m.battery_level_percent}% < 20%)，处于充电保护状态"

    if m.health_status == DeviceHealthStatus.OFFLINE:
        return False, "设备离线失联"

    if m.current_concurrency >= m.max_concurrency:
        return False, f"设备已达到并发上限 ({m.current_concurrency}/{m.max_concurrency})"

    return True, "设备健康且算力充裕，允许派发调度"
