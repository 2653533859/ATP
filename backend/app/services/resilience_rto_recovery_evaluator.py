"""服务断路器/降级策略生效时延与 RTO 恢复指标量化器服务 (T4.2)。

负责在混沌故障注入演练期间与演练后，精准量化微服务系统的弹性韧性指标：
1. 断路器跳闸熔断时延 (Circuit Breaker Tripping Latency)；
2. 降级 Fallback 响应合规率 (Fallback Compliance & Success Ratio)；
3. 故障消除后业务 RTO (Recovery Time Objective) 真实自愈恢复时长；
4. 输出四级系统韧性等级 (EXCELLENT / ADEQUATE / INSUFFICIENT / FRAGILE) 与熔断器参数调优建议。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class ResilienceTier(str, Enum):
    EXCELLENT = "EXCELLENT"  # 卓越韧性: 快速熔断 (<=150ms)、降级率 >=98%、RTO <=800ms
    ADEQUATE = "ADEQUATE"  # 合格稳健: 熔断 <=500ms、降级率 >=90%、RTO <=2500ms
    INSUFFICIENT = "INSUFFICIENT"  # 欠缺待改: 熔断迟钝 (<=1500ms) 或 RTO 恢复较慢 (<=5000ms)
    FRAGILE = "FRAGILE"  # 脆弱缺陷: 断路器未跳闸引发雪崩，或降级失败，RTO > 5000ms


class BreakerState(str, Enum):
    CLOSED = "CLOSED"  # 正常闭合
    OPEN = "OPEN"  # 熔断开启 (直接 Fallback)
    HALF_OPEN = "HALF_OPEN"  # 半开试探自愈


@dataclass
class RtoSamplePoint:
    seq: int
    offset_ms: float
    status_code: int
    duration_ms: float
    is_fault_active: bool
    is_fallback: bool
    breaker_state: BreakerState

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "offset_ms": round(self.offset_ms, 2),
            "status_code": self.status_code,
            "duration_ms": round(self.duration_ms, 2),
            "is_fault_active": self.is_fault_active,
            "is_fallback": self.is_fallback,
            "breaker_state": self.breaker_state.value,
        }


@dataclass
class ResilienceRtoReport:
    report_id: str
    target_service_id: str
    endpoint: str
    resilience_tier: ResilienceTier
    breaker_trip_latency_ms: float  # 故障注入到断路器首次跳闸生效的时间
    fallback_success_ratio_pct: float  # 故障期间降级生效百分比 (0~100%)
    rto_recovery_duration_ms: float  # 故障消除到系统稳定自愈闭合的时长
    total_samples_analyzed: int
    fault_period_requests_count: int
    recovery_period_requests_count: int
    sample_stream: list[RtoSamplePoint]
    verdict_summary: str
    remediation_suggestions: list[str]
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_service_id": self.target_service_id,
            "endpoint": self.endpoint,
            "resilience_tier": self.resilience_tier.value,
            "breaker_trip_latency_ms": round(self.breaker_trip_latency_ms, 2),
            "fallback_success_ratio_pct": round(self.fallback_success_ratio_pct, 2),
            "rto_recovery_duration_ms": round(self.rto_recovery_duration_ms, 2),
            "total_samples_analyzed": self.total_samples_analyzed,
            "fault_period_requests_count": self.fault_period_requests_count,
            "recovery_period_requests_count": self.recovery_period_requests_count,
            "sample_stream": [s.to_dict() for s in self.sample_stream],
            "verdict_summary": self.verdict_summary,
            "remediation_suggestions": self.remediation_suggestions,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


# 全局内存报告仓库
_RTO_REPORTS: dict[str, ResilienceRtoReport] = {}


def analyze_resilience_rto(
    target_service_id: str,
    endpoint: str,
    sample_points: list[dict[str, Any]],
    expected_fallback_status: int = 200,
) -> ResilienceRtoReport:
    """对一组混沌演练时序采样数据进行断路器生效时延与 RTO 自愈时长精准度量。"""
    report_id = f"rto_{uuid.uuid4().hex[:12]}"

    if not sample_points:
        report = ResilienceRtoReport(
            report_id=report_id,
            target_service_id=target_service_id,
            endpoint=endpoint,
            resilience_tier=ResilienceTier.FRAGILE,
            breaker_trip_latency_ms=0.0,
            fallback_success_ratio_pct=0.0,
            rto_recovery_duration_ms=0.0,
            total_samples_analyzed=0,
            fault_period_requests_count=0,
            recovery_period_requests_count=0,
            sample_stream=[],
            verdict_summary="无有效采样数据，无法评定系统韧性指标。",
            remediation_suggestions=["请接入断路器或在演练期间开启指标时序采集"],
        )
        _RTO_REPORTS[report_id] = report
        return report

    # 规范化转换为内部对象
    samples: list[RtoSamplePoint] = []
    for idx, sp in enumerate(sample_points):
        state_str = str(sp.get("breaker_state", "CLOSED")).upper()
        try:
            b_state = BreakerState(state_str)
        except ValueError:
            b_state = BreakerState.CLOSED

        samples.append(
            RtoSamplePoint(
                seq=int(sp.get("seq", idx + 1)),
                offset_ms=float(sp.get("offset_ms", idx * 50.0)),
                status_code=int(sp.get("status_code", 200)),
                duration_ms=float(sp.get("duration_ms", 20.0)),
                is_fault_active=bool(sp.get("is_fault_active", False)),
                is_fallback=bool(sp.get("is_fallback", False)),
                breaker_state=b_state,
            )
        )

    # 1. 定位故障注入区间
    fault_samples = [s for s in samples if s.is_fault_active]
    fault_period_count = len(fault_samples)
    fault_start_offset = fault_samples[0].offset_ms if fault_samples else 0.0
    fault_end_offset = fault_samples[-1].offset_ms if fault_samples else 0.0

    # 2. 定位断路器跳闸生效时机 (首次进入 OPEN 或首个 is_fallback 为 True)
    trip_sample = next(
        (
            s
            for s in samples
            if s.offset_ms >= fault_start_offset and (s.breaker_state == BreakerState.OPEN or s.is_fallback)
        ),
        None,
    )

    if trip_sample:
        trip_latency_ms = max(0.0, trip_sample.offset_ms - fault_start_offset)
    else:
        # 断路器在故障期间从未跳闸熔断！
        trip_latency_ms = 9999.0

    # 3. 统计故障期间降级 Fallback 生效正确率
    if fault_period_count > 0:
        successful_fallbacks = sum(
            1
            for s in fault_samples
            if s.is_fallback and (s.status_code == expected_fallback_status or s.status_code < 400)
        )
        fallback_ratio = (successful_fallbacks / fault_period_count) * 100.0
    else:
        fallback_ratio = 100.0

    # 4. 定位故障消除后的 RTO 自愈恢复时长
    recovery_samples = [s for s in samples if s.offset_ms > fault_end_offset]
    recovery_period_count = len(recovery_samples)

    # 寻找首个稳定闭合且响应正常的点 (CLOSED 且 status < 400)
    healed_sample = next(
        (s for s in recovery_samples if s.breaker_state == BreakerState.CLOSED and s.status_code < 400),
        None,
    )

    if healed_sample:
        rto_duration_ms = max(0.0, healed_sample.offset_ms - fault_end_offset)
    else:
        # 故障结束后未能自愈或仍处于熔断状态
        rto_duration_ms = 9999.0

    # 5. 评定系统韧性等级 (Resilience Tier)
    suggestions: list[str] = []

    if trip_latency_ms <= 150.0 and fallback_ratio >= 98.0 and rto_duration_ms <= 800.0:
        tier = ResilienceTier.EXCELLENT
        verdict = (
            f"卓越韧性！断路器在 {trip_latency_ms:.1f}ms 内极速跳闸，降级成功率达到 {fallback_ratio:.1f}%，"
            f"故障消除后 RTO 自愈耗时仅 {rto_duration_ms:.1f}ms，表现完美。"
        )
    elif trip_latency_ms <= 500.0 and fallback_ratio >= 90.0 and rto_duration_ms <= 2500.0:
        tier = ResilienceTier.ADEQUATE
        verdict = (
            f"合格稳健。断路器在 {trip_latency_ms:.1f}ms 内熔断，降级率为 {fallback_ratio:.1f}%，"
            f"RTO 自愈恢复时长为 {rto_duration_ms:.1f}ms，符合企业级生产基线。"
        )
        if trip_latency_ms > 200.0:
            suggestions.append("可适当调低断路器滑窗失败率阈值或最小调用量，进一步加快跳闸速度")
    elif trip_latency_ms <= 1500.0 and rto_duration_ms <= 5000.0:
        tier = ResilienceTier.INSUFFICIENT
        verdict = (
            f"欠缺待改。熔断响应偏迟钝 ({trip_latency_ms:.1f}ms) 或 RTO 偏长 ({rto_duration_ms:.1f}ms)，"
            f"降级成功率为 {fallback_ratio:.1f}%，可能引起短时堆积。"
        )
        suggestions.append("优化断路器探测频率与自动半开试探探针间隔")
        if fallback_ratio < 90.0:
            suggestions.append("检查 Fallback 降级函数逻辑，避免降级自身引发异常")
    else:
        tier = ResilienceTier.FRAGILE
        verdict = (
            f"【脆弱缺陷】熔断失效或恢复超时 (熔断时延: {trip_latency_ms:.1f}ms, RTO: {rto_duration_ms:.1f}ms)，"
            f"降级率仅为 {fallback_ratio:.1f}%，存在微服务级联雪崩重大风险！"
        )
        suggestions.append("排查服务断路器配置是否正确生效，确保拦截模式激活")
        suggestions.append("重构 Fallback 降级兜底逻辑并缩短熔断恢复计时器")

    report = ResilienceRtoReport(
        report_id=report_id,
        target_service_id=target_service_id,
        endpoint=endpoint,
        resilience_tier=tier,
        breaker_trip_latency_ms=trip_latency_ms,
        fallback_success_ratio_pct=fallback_ratio,
        rto_recovery_duration_ms=rto_duration_ms,
        total_samples_analyzed=len(samples),
        fault_period_requests_count=fault_period_count,
        recovery_period_requests_count=recovery_period_count,
        sample_stream=samples,
        verdict_summary=verdict,
        remediation_suggestions=suggestions,
    )

    _RTO_REPORTS[report_id] = report
    logger.info(
        "韧性 RTO 评估完成 [%s]: 评级 %s, 跳闸时延 %.1fms, RTO %.1fms",
        report_id,
        tier.value,
        trip_latency_ms,
        rto_duration_ms,
    )
    return report


def simulate_circuit_breaker_exercise(
    target_service_id: str = "order-service",
    endpoint: str = "POST /api/v1/orders/checkout",
    tier_preset: str = "EXCELLENT",
) -> ResilienceRtoReport:
    """仿真模拟演练一组标准的 [正常 -> 注入故障 -> 熔断跳闸 -> 故障消除 -> 自愈恢复] 时序数据。"""
    tier_upper = tier_preset.upper()
    points: list[dict[str, Any]] = []

    # 1. 前置正常期 (0~200ms, 4个请求)
    for i in range(4):
        points.append(
            {
                "seq": i + 1,
                "offset_ms": i * 50.0,
                "status_code": 200,
                "duration_ms": 15.0,
                "is_fault_active": False,
                "is_fallback": False,
                "breaker_state": "CLOSED",
            }
        )

    # 2. 故障注入期 (200~800ms, 12个请求)
    fault_start = 200.0
    trip_delay = 50.0 if tier_upper == "EXCELLENT" else (300.0 if tier_upper == "ADEQUATE" else 800.0)

    for i in range(12):
        t = fault_start + i * 50.0
        tripped = t >= (fault_start + trip_delay)

        if tripped:
            # 已经跳闸
            fallback_ok = tier_upper != "FRAGILE" or (i % 2 == 0)
            points.append(
                {
                    "seq": len(points) + 1,
                    "offset_ms": t,
                    "status_code": 200 if fallback_ok else 500,
                    "duration_ms": 5.0,  # 降级快速返回
                    "is_fault_active": True,
                    "is_fallback": True,
                    "breaker_state": "OPEN",
                }
            )
        else:
            # 尚未跳闸，承受 503 错误或高延迟
            points.append(
                {
                    "seq": len(points) + 1,
                    "offset_ms": t,
                    "status_code": 503,
                    "duration_ms": 250.0,
                    "is_fault_active": True,
                    "is_fallback": False,
                    "breaker_state": "CLOSED",
                }
            )

    # 3. 故障消除恢复期 (800~1400ms, 12个请求)
    heal_start = 800.0
    rto_time = 300.0 if tier_upper == "EXCELLENT" else (1200.0 if tier_upper == "ADEQUATE" else 3000.0)

    for i in range(12):
        t = heal_start + i * 50.0
        healed = t >= (heal_start + rto_time)
        state = "CLOSED" if healed else ("HALF_OPEN" if t >= (heal_start + 100.0) else "OPEN")

        points.append(
            {
                "seq": len(points) + 1,
                "offset_ms": t,
                "status_code": 200,
                "duration_ms": 18.0 if healed else 8.0,
                "is_fault_active": False,
                "is_fallback": not healed,
                "breaker_state": state,
            }
        )

    return analyze_resilience_rto(target_service_id, endpoint, points)


def get_rto_report(report_id: str) -> ResilienceRtoReport | None:
    """根据 ID 获取指定 RTO 韧性报告详情。"""
    return _RTO_REPORTS.get(report_id)


def list_rto_reports() -> list[ResilienceRtoReport]:
    """查询历史 RTO 韧性评估报告列表。"""
    reports = list(_RTO_REPORTS.values())
    reports.sort(key=lambda r: r.evaluated_at, reverse=True)
    return reports


def clear_rto_reports() -> int:
    """清空 RTO 报告缓存。"""
    count = len(_RTO_REPORTS)
    _RTO_REPORTS.clear()
    return count
