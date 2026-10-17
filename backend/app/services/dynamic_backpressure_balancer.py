"""动态反压与队列吞吐自适应均衡器服务 (T2.3)

监控全局队列排队深度与执行延迟，基于 AIMD 自适应算法动态调整并发派发窗口:
1. 队列排队深度与集群饱和度实时感知 (Queue Depth & Fleet Saturation Ratio);
2. AIMD (加法递增、乘法递减) 自适应并发窗口调节模型 (Dynamic Window Size);
3. 四级反压控制等级 (NORMAL | LIGHT_THROTTLING | HEAVY_BACKPRESSURE | OVERFLOW_REJECTION);
4. 动态吞吐快照与反压限流事件审计。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.fleet_health_telemetry import (
    DeviceHealthStatus,
    list_fleet_telemetry,
)


class BackpressureLevel(str, enum.Enum):
    NORMAL = "NORMAL"  # 正常无反压 (集群负载健康，畅通派发)
    LIGHT_THROTTLING = "LIGHT_THROTTLING"  # 轻度流控 (饱和度 70~85%，平缓窗口)
    HEAVY_BACKPRESSURE = "HEAVY_BACKPRESSURE"  # 重度反压 (饱和度 > 85% 或存在过热，窗口乘法收缩)
    OVERFLOW_REJECTION = "OVERFLOW_REJECTION"  # 队列溢出熔断 (排队深度突破最大安全容限)


@dataclass
class BackpressureConfig:
    min_window_size: int = 2  # 最小安全派发并发窗口
    max_window_size: int = 50  # 最大并发吞吐窗口
    default_window_size: int = 10
    queue_overflow_threshold: int = 100  # 队列堆积超过此值触发溢出拒绝
    target_saturation_ratio: float = 0.75  # 期望维持的集群最佳饱和度水位


@dataclass
class BackpressureStatusSnapshot:
    snapshot_id: str
    current_window_size: int
    queue_depth: int
    total_fleet_capacity: int
    used_concurrency: int
    saturation_ratio: float
    average_wait_latency_ms: float
    level: BackpressureLevel
    action_description: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["level"] = self.level.value
        d["saturation_ratio"] = round(self.saturation_ratio, 4)
        d["average_wait_latency_ms"] = round(self.average_wait_latency_ms, 2)
        return d


# 运行时单例状态
_CURRENT_WINDOW_SIZE = 10
_SNAPSHOT_HISTORY: Dict[str, BackpressureStatusSnapshot] = {}


def clear_backpressure_state() -> None:
    """清空反压器内存状态（测试夹具使用）"""
    global _CURRENT_WINDOW_SIZE
    _CURRENT_WINDOW_SIZE = 10
    _SNAPSHOT_HISTORY.clear()


def calculate_fleet_capacity_and_saturation() -> tuple[int, int, float, bool]:
    """计算集群总容量、当前占用、饱和度及是否检测到过热机器

    Returns:
        (total_capacity, used_concurrency, saturation_ratio, has_overheated_device)
    """
    devices = list_fleet_telemetry()
    if not devices:
        return 0, 0, 0.0, False

    total_cap = sum(d.max_concurrency for d in devices)
    used_con = sum(d.current_concurrency for d in devices)
    has_overheated = any(d.health_status == DeviceHealthStatus.OVERHEATED for d in devices)

    saturation = (used_con / total_cap) if total_cap > 0 else 0.0
    return total_cap, used_con, saturation, has_overheated


def adjust_backpressure_window(
    queue_depth: int = 0,
    average_wait_latency_ms: float = 100.0,
    config: Optional[BackpressureConfig] = None,
) -> BackpressureStatusSnapshot:
    """执行 AIMD 自适应算法，根据当前集群压力与排队状况调节并发派发窗口"""
    global _CURRENT_WINDOW_SIZE
    cfg = config or BackpressureConfig()

    total_cap, used_con, saturation, has_overheated = calculate_fleet_capacity_and_saturation()
    sid = f"snap_bp_{uuid.uuid4().hex[:10]}"

    prev_window = _CURRENT_WINDOW_SIZE

    # 1. 检查是否触发极端队列溢出
    if queue_depth >= cfg.queue_overflow_threshold:
        level = BackpressureLevel.OVERFLOW_REJECTION
        _CURRENT_WINDOW_SIZE = cfg.min_window_size
        action = f"排队任务深度 ({queue_depth}) 超过最大容限 ({cfg.queue_overflow_threshold})，触发溢出熔断拒绝，窗口急缩至最小 ({cfg.min_window_size})"

    # 2. 检查是否触发重度反压 (饱和度过高、排队延迟过高或设备过热)
    elif saturation >= 0.85 or average_wait_latency_ms >= 1500.0 or has_overheated:
        level = BackpressureLevel.HEAVY_BACKPRESSURE
        # 乘法递减 (Multiplicative Decrease): 窗口收缩至 60%
        new_window = max(cfg.min_window_size, int(_CURRENT_WINDOW_SIZE * 0.6))
        _CURRENT_WINDOW_SIZE = new_window
        action = (
            f"集群负载过重 (饱和度 {round(saturation * 100, 1)}%, 时延 {round(average_wait_latency_ms, 0)}ms, 过热设备: {has_overheated})，"
            f"触发重度反压 AIMD 乘法递减 ({prev_window} ➔ {new_window})"
        )

    # 3. 检查是否触发轻度流控
    elif saturation >= 0.70:
        level = BackpressureLevel.LIGHT_THROTTLING
        # 维持当前窗口，平缓防冲
        action = (
            f"集群处于警戒负载区 (饱和度 {round(saturation * 100, 1)}%)，维持当前吞吐窗口 ({_CURRENT_WINDOW_SIZE}) 观察"
        )

    # 4. 负载健康充裕: 加法递增 (Additive Increase)
    else:
        level = BackpressureLevel.NORMAL
        new_window = min(cfg.max_window_size, _CURRENT_WINDOW_SIZE + 2)
        _CURRENT_WINDOW_SIZE = new_window
        action = f"集群算力健康充裕 (饱和度 {round(saturation * 100, 1)}%)，执行 AIMD 加法递增扩展派发窗口 ({prev_window} ➔ {new_window})"

    snapshot = BackpressureStatusSnapshot(
        snapshot_id=sid,
        current_window_size=_CURRENT_WINDOW_SIZE,
        queue_depth=queue_depth,
        total_fleet_capacity=total_cap,
        used_concurrency=used_con,
        saturation_ratio=saturation,
        average_wait_latency_ms=average_wait_latency_ms,
        level=level,
        action_description=action,
    )

    _SNAPSHOT_HISTORY[sid] = snapshot
    return snapshot


def get_current_backpressure_status() -> BackpressureStatusSnapshot:
    """获取当前最新反压状态快照"""
    total_cap, used_con, saturation, _ = calculate_fleet_capacity_and_saturation()
    return BackpressureStatusSnapshot(
        snapshot_id=f"current_{uuid.uuid4().hex[:8]}",
        current_window_size=_CURRENT_WINDOW_SIZE,
        queue_depth=0,
        total_fleet_capacity=total_cap,
        used_concurrency=used_con,
        saturation_ratio=saturation,
        average_wait_latency_ms=50.0,
        level=BackpressureLevel.NORMAL if saturation < 0.70 else BackpressureLevel.LIGHT_THROTTLING,
        action_description="当前自适应流控窗口运行平稳",
    )


def list_backpressure_snapshots(limit: int = 50) -> List[Dict[str, Any]]:
    """获取近期反压快照流水历史"""
    items = list(_SNAPSHOT_HISTORY.values())
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return [s.to_dict() for s in items[:limit]]
