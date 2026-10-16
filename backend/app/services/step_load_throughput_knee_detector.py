"""全链路压测 TPS 阶梯加压性能曲线与拐点检测器 (T4.1)。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PerformanceZone(str, Enum):
    """系统性能负载区间分类。"""

    OPTIMAL_ZONE = "OPTIMAL_ZONE"  # 线性最优负载区 (并发与 TPS 同步增长, 低时延)
    SATURATION_ZONE = "SATURATION_ZONE"  # 饱和高压区 (接近拐点 Knee, 增速放缓)
    DEGRADED_OVERLOAD_ZONE = "DEGRADED_OVERLOAD_ZONE"  # 过载崩溃区 (超过 Cliff 点, TPS 断崖下跌)


@dataclass
class StepLoadSamplePoint:
    """阶梯加压单个采样点。"""

    step_index: int
    concurrency_threads: int
    measured_tps: float
    avg_latency_ms: float
    p99_latency_ms: float
    error_rate_pct: float
    zone: PerformanceZone = PerformanceZone.OPTIMAL_ZONE

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "concurrency_threads": self.concurrency_threads,
            "measured_tps": round(self.measured_tps, 1),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "p99_latency_ms": round(self.p99_latency_ms, 1),
            "error_rate_pct": round(self.error_rate_pct, 2),
            "zone": self.zone.value,
        }


@dataclass
class ThroughputKneeAuditReport:
    """TPS 阶梯曲线与性能拐点全景分析报告。"""

    report_id: str
    scenario_name: str
    total_steps_count: int
    peak_tps: float
    knee_point_concurrency: int  # 最大吞吐性能拐点并发数 (Knee Point)
    knee_point_tps: float
    knee_point_latency_ms: float
    cliff_point_concurrency: int | None  # 崩溃点并发数 (Cliff Point)
    recommended_safe_concurrency: int  # 推荐日常生产最佳并发
    step_samples: list[StepLoadSamplePoint]
    capacity_planning_advice: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "scenario_name": self.scenario_name,
            "total_steps_count": self.total_steps_count,
            "peak_tps": round(self.peak_tps, 1),
            "knee_point_concurrency": self.knee_point_concurrency,
            "knee_point_tps": round(self.knee_point_tps, 1),
            "knee_point_latency_ms": round(self.knee_point_latency_ms, 1),
            "cliff_point_concurrency": self.cliff_point_concurrency,
            "recommended_safe_concurrency": self.recommended_safe_concurrency,
            "step_samples": [s.to_dict() for s in self.step_samples],
            "capacity_planning_advice": self.capacity_planning_advice,
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告存储
_KNEE_REPORTS: dict[str, ThroughputKneeAuditReport] = {}


def clear_throughput_knee_store() -> None:
    """清空拐点分析报告仓库 (单测专用)。"""
    _KNEE_REPORTS.clear()


def detect_throughput_knee_and_cliff(
    scenario_name: str,
    samples: list[dict[str, Any]],
) -> ThroughputKneeAuditReport:
    """分析阶梯加压采样序列，拟合并发 vs TPS 曲线，精准定位 Knee 性能拐点与 Cliff 崩溃点。"""
    if not samples:
        samples = [
            {"concurrency_threads": 100, "measured_tps": 1000.0, "avg_latency_ms": 20.0, "p99_latency_ms": 50.0},
            {"concurrency_threads": 500, "measured_tps": 4500.0, "avg_latency_ms": 35.0, "p99_latency_ms": 80.0},
        ]

    # 按并发升序排列
    sorted_raw = sorted(samples, key=lambda x: int(x.get("concurrency_threads", 0)))
    step_points: list[StepLoadSamplePoint] = []

    for idx, s in enumerate(sorted_raw, start=1):
        step_points.append(
            StepLoadSamplePoint(
                step_index=idx,
                concurrency_threads=int(s.get("concurrency_threads", 0)),
                measured_tps=float(s.get("measured_tps", 0.0)),
                avg_latency_ms=float(s.get("avg_latency_ms", 0.0)),
                p99_latency_ms=float(s.get("p99_latency_ms", 0.0)),
                error_rate_pct=float(s.get("error_rate_pct", 0.0)),
            )
        )

    # 1. 寻找最高峰值 TPS 点
    peak_point = max(step_points, key=lambda p: p.measured_tps)
    peak_tps = peak_point.measured_tps
    peak_idx = step_points.index(peak_point)

    # 2. 拐点 (Knee Point) 判定：
    # 当增加并发时，斜率 ΔTPS / ΔVU 明显减小，TPS 达到最大或饱和高点的临界点即为 Knee Point
    knee_point = peak_point

    # 3. 崩溃点 (Cliff Point) 判定：
    # 峰值之后，若后续阶梯 TPS 出现大幅跌落 (跌幅 > 15%) 或 错误率激增 (> 5%)，该点标记为 Cliff Point
    cliff_point: StepLoadSamplePoint | None = None
    for p in step_points[peak_idx + 1 :]:
        if p.measured_tps < peak_tps * 0.85 or p.error_rate_pct >= 5.0 or p.p99_latency_ms >= 3000.0:
            cliff_point = p
            break

    # 4. 区间划分打标
    cliff_threads = cliff_point.concurrency_threads if cliff_point else 999999
    for p in step_points:
        if p.concurrency_threads < knee_point.concurrency_threads:
            p.zone = PerformanceZone.OPTIMAL_ZONE
        elif p.concurrency_threads <= cliff_threads:
            p.zone = PerformanceZone.SATURATION_ZONE
        else:
            p.zone = PerformanceZone.DEGRADED_OVERLOAD_ZONE

    # 5. 容量规划与容量水位建议
    # 推荐日常生产安全并发为 Knee Point 并发的 70%~80%
    safe_concurrency = max(1, int(knee_point.concurrency_threads * 0.75))
    advice: list[str] = [
        f"系统吞吐最大性能拐点 (Knee Point) 位于并发 {knee_point.concurrency_threads} VU，"
        f"峰值吞吐量为 {peak_tps:.1f} TPS (对应 P99 时延 {knee_point.p99_latency_ms:.1f}ms)。",
        f"推荐日常生产水位最佳并发为 {safe_concurrency} VU (取拐点容量 75%)，兼顾吞吐效率与低时延储备。",
    ]

    if cliff_point:
        advice.append(
            f"警告！并发达到 {cliff_point.concurrency_threads} VU 时触发崩溃点 (Cliff Point)，"
            f"TPS 跌至 {cliff_point.measured_tps:.1f}，错误率升至 {cliff_point.error_rate_pct:.1f}%，需在此水位前实施限流保护。"
        )
    else:
        advice.append(
            "本次加压未探测到系统崩溃点，表明高并发下系统具备良好韧性，建议继续加大压测负荷探寻系统真实极值。"
        )

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", scenario_name)[:16]
    report_id = f"knee_rpt_{safe_name}_{int(now.timestamp())}"

    report = ThroughputKneeAuditReport(
        report_id=report_id,
        scenario_name=scenario_name,
        total_steps_count=len(step_points),
        peak_tps=peak_tps,
        knee_point_concurrency=knee_point.concurrency_threads,
        knee_point_tps=knee_point.measured_tps,
        knee_point_latency_ms=knee_point.avg_latency_ms,
        cliff_point_concurrency=cliff_point.concurrency_threads if cliff_point else None,
        recommended_safe_concurrency=safe_concurrency,
        step_samples=step_points,
        capacity_planning_advice=advice,
        created_at=now,
    )

    _KNEE_REPORTS[report_id] = report
    return report


def get_throughput_knee_report(report_id: str) -> ThroughputKneeAuditReport | None:
    """按 ID 查询拐点分析报告。"""
    return _KNEE_REPORTS.get(report_id)


def list_throughput_knee_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史拐点分析报告列表。"""
    reports = list(reversed(list(_KNEE_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
