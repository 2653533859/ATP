"""金丝雀与基线双轨指标实时对比推演器服务 (T1.2)

聚合对比金丝雀版本 (Canary) 与基线版本 (Baseline) 的实时指标偏离度:
1. 双轨指标采样建模 (TrackMetricsSample: 错误率、成功率、P99/平均延迟、CPU/内存);
2. 相对偏离度算法精算 (error_rate_diff_pct, latency_p99_ratio, cpu_diff_pct);
3. 指标健康度三态评定 (MetricDeviationVerdict: CONFORMANT 合规、WARNING_DEGRADED 预警、BREACHED_DEFICIT 击穿);
4. 综合双轨对比推演报告输出 (CanaryDualTrackComparisonReport)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


class MetricDeviationVerdict(str, enum.Enum):
    CONFORMANT = "CONFORMANT"  # 双轨指标表现平稳，符合预期甚至由于优化更优
    WARNING_DEGRADED = "WARNING_DEGRADED"  # 轻微偏离退化，处于预警监控区间
    BREACHED_DEFICIT = "BREACHED_DEFICIT"  # 严重超标击穿，可能触发自动回滚熔断


@dataclass
class TrackMetricsSample:
    track_name: str  # "baseline" | "canary"
    version_tag: str  # e.g. "v1.0.0" or "v2.0.0-rc1"
    total_requests: int
    error_requests: int
    error_rate_pct: float
    success_rate_pct: float
    p99_latency_ms: float
    avg_latency_ms: float
    cpu_usage_pct: float = 25.0
    mem_usage_mb: float = 512.0
    sampled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanaryDualTrackComparisonReport:
    report_id: str
    target_service: str
    canary_version: str
    baseline_version: str
    overall_verdict: MetricDeviationVerdict
    baseline_metrics: TrackMetricsSample
    canary_metrics: TrackMetricsSample
    error_rate_diff_pct: float  # 金丝雀相对基线的错误率差值 (正数代表金丝雀更高)
    latency_p99_ratio: float  # 金丝雀相对基线的延迟倍数 (> 1.0 代表金丝雀更慢)
    cpu_diff_pct: float
    findings: List[str]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_service": self.target_service,
            "canary_version": self.canary_version,
            "baseline_version": self.baseline_version,
            "overall_verdict": self.overall_verdict.value,
            "baseline_metrics": self.baseline_metrics.to_dict(),
            "canary_metrics": self.canary_metrics.to_dict(),
            "error_rate_diff_pct": round(self.error_rate_diff_pct, 2),
            "latency_p99_ratio": round(self.latency_p99_ratio, 2),
            "cpu_diff_pct": round(self.cpu_diff_pct, 1),
            "findings": self.findings,
            "generated_at": self.generated_at,
        }


def compare_canary_and_baseline_tracks(
    baseline: TrackMetricsSample,
    canary: TrackMetricsSample,
    target_service: str = "payment-service",
    error_rate_tolerance_diff_pct: float = 1.5,
    latency_ratio_tolerance: float = 1.25,
) -> CanaryDualTrackComparisonReport:
    """实时对比金丝雀轨与基线轨运行指标，生成偏离评估结论"""
    report_id = f"cdtr_{uuid.uuid4().hex[:10]}"
    findings: List[str] = []

    # 1. 计算核心指标偏离度
    error_diff = canary.error_rate_pct - baseline.error_rate_pct
    lat_ratio = canary.p99_latency_ms / max(1.0, baseline.p99_latency_ms)
    cpu_diff = canary.cpu_usage_pct - baseline.cpu_usage_pct

    # 2. 判定错误率指标
    error_breached = False
    error_warn = False
    if error_diff > error_rate_tolerance_diff_pct:
        error_breached = True
        findings.append(
            f"【错误率严重击穿】金丝雀错误率 ({canary.error_rate_pct}%) 相比基线 ({baseline.error_rate_pct}%) 增加 {round(error_diff, 2)}%，突破容差阈值 ({error_rate_tolerance_diff_pct}%)"
        )
    elif error_diff > 0.5:
        error_warn = True
        findings.append(f"【错误率轻度上升】金丝雀错误率略高于基线 +{round(error_diff, 2)}%，处于可监控警戒线内")
    else:
        findings.append(f"错误率指标平稳: 金丝雀 ({canary.error_rate_pct}%) vs 基线 ({baseline.error_rate_pct}%)")

    # 3. 判定 P99 响应时延
    latency_breached = False
    latency_warn = False
    if lat_ratio > latency_ratio_tolerance:
        latency_breached = True
        findings.append(
            f"【P99延迟严重退化】金丝雀 P99 延迟 ({canary.p99_latency_ms}ms) 为基线 ({baseline.p99_latency_ms}ms) 的 {round(lat_ratio, 2)}x，超出 {latency_ratio_tolerance}x 容差门槛"
        )
    elif lat_ratio > 1.10:
        latency_warn = True
        findings.append(
            f"【P99延迟轻度增加】金丝雀延迟为基线的 {round(lat_ratio, 2)}x (+{round((lat_ratio - 1) * 100, 1)}%)"
        )
    else:
        findings.append(
            f"P99 响应时延平稳: 金丝雀 {canary.p99_latency_ms}ms vs 基线 {baseline.p99_latency_ms}ms ({round(lat_ratio, 2)}x)"
        )

    # 4. 判定 CPU 与资源负载
    if cpu_diff > 30.0:
        findings.append(f"【CPU 负载显著偏高】金丝雀相比基线高出 {round(cpu_diff, 1)}% 算力占用，建议排查热点循环")

    # 5. 综合确定裁决结论
    if error_breached or latency_breached:
        overall = MetricDeviationVerdict.BREACHED_DEFICIT
    elif error_warn or latency_warn:
        overall = MetricDeviationVerdict.WARNING_DEGRADED
    else:
        overall = MetricDeviationVerdict.CONFORMANT

    return CanaryDualTrackComparisonReport(
        report_id=report_id,
        target_service=target_service,
        canary_version=canary.version_tag,
        baseline_version=baseline.version_tag,
        overall_verdict=overall,
        baseline_metrics=baseline,
        canary_metrics=canary,
        error_rate_diff_pct=error_diff,
        latency_p99_ratio=lat_ratio,
        cpu_diff_pct=cpu_diff,
        findings=findings,
    )
