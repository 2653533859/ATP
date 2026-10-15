"""Performance Chaos Fault Injection and RTO (Recovery Time Objective) Measurement Service (Q3.2).

Provides:
1. Chaos fault injection experiment definitions under load (service_unavailable, latency_spike, packet_loss, connection_reset).
2. Time-series metric evaluation for fault-window degradation.
3. Precision self-healing RTO (Recovery Time Objective) calculation with sustained healthy window checks.
4. Resilience grading (Grade A/B/C/D) and actionable self-healing recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

logger = logging.getLogger(__name__)

VALID_FAULT_TYPES = {
    "service_unavailable",  # HTTP 503 / 502 downstream error
    "latency_spike",  # Downstream injected latency spike
    "packet_loss",  # Network packet drop rate
    "connection_reset",  # TCP connection drop / ECONNRESET
}


@dataclass
class ChaosFaultConfig:
    fault_type: str
    target_service: str
    start_delay_seconds: float = 10.0
    duration_seconds: float = 30.0
    fault_params: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.fault_type not in VALID_FAULT_TYPES:
            raise ValueError(f"不支持的故障类型 '{self.fault_type}'，支持: {sorted(VALID_FAULT_TYPES)}")
        if not self.target_service or not self.target_service.strip():
            raise ValueError("目标服务名称或路径不能为空")
        if self.start_delay_seconds < 0:
            raise ValueError("故障开始延迟秒数不能为负数")
        if self.duration_seconds <= 0:
            raise ValueError("故障持续时间必须大于 0 秒")


def build_chaos_injection_plan(
    run_id: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Validate and build a structured chaos injection schedule for a performance run."""
    fault_config = ChaosFaultConfig(
        fault_type=config.get("fault_type", "service_unavailable"),
        target_service=config.get("target_service", "downstream-api"),
        start_delay_seconds=float(config.get("start_delay_seconds", 10.0)),
        duration_seconds=float(config.get("duration_seconds", 30.0)),
        fault_params=config.get("fault_params", {}),
    )
    fault_config.validate()

    return {
        "run_id": run_id,
        "plan_id": f"chaos_run_{run_id}_{int(datetime.now(timezone.utc).timestamp())}",
        "fault_type": fault_config.fault_type,
        "target_service": fault_config.target_service,
        "start_delay_seconds": fault_config.start_delay_seconds,
        "duration_seconds": fault_config.duration_seconds,
        "fault_params": fault_config.fault_params,
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def calculate_chaos_rto(
    time_series: list[dict[str, Any]],
    *,
    fault_start_offset: float,
    fault_duration: float,
    recovery_rps_ratio: float = 0.85,
    recovery_error_margin: float = 0.03,
    recovery_latency_ratio: float = 1.30,
    sustain_seconds: float = 3.0,
) -> dict[str, Any]:
    """Calculate the system service self-healing RTO (Recovery Time Objective) from time-series metrics.

    Args:
        time_series: List of metric points, each dict containing at least:
                     {"offset_seconds": float, "rps": float, "p95_ms": float, "error_rate": float}
        fault_start_offset: Seconds from test start when fault injection began.
        fault_duration: Duration of fault injection in seconds.
        recovery_rps_ratio: Minimum ratio of baseline RPS needed to consider recovered (default 85%).
        recovery_error_margin: Maximum acceptable error rate above baseline (default 3%).
        recovery_latency_ratio: Maximum acceptable P95 multiplier vs baseline (default 1.3x).
        sustain_seconds: Minimum consecutive seconds conditions must hold to confirm recovery.

    Returns:
        Structured evaluation dict with RTO in seconds, degradation stats, and resilience rating.
    """
    if not time_series:
        return {
            "recovered": False,
            "rto_seconds": None,
            "resilience_score": 0.0,
            "resilience_grade": "F",
            "message": "时序采样数据为空，无法测定 RTO",
        }

    fault_end_offset = fault_start_offset + fault_duration

    # 1. Segment time-series into pre-fault (baseline), in-fault, and post-fault
    pre_fault_points = [p for p in time_series if float(p.get("offset_seconds", 0)) < fault_start_offset]
    in_fault_points = [
        p for p in time_series if fault_start_offset <= float(p.get("offset_seconds", 0)) <= fault_end_offset
    ]
    post_fault_points = [p for p in time_series if float(p.get("offset_seconds", 0)) > fault_end_offset]

    # Baseline calculation
    if pre_fault_points:
        baseline_rps = sum(float(p.get("rps", 0)) for p in pre_fault_points) / len(pre_fault_points)
        baseline_p95 = sum(float(p.get("p95_ms", 0)) for p in pre_fault_points) / len(pre_fault_points)
        baseline_error_rate = sum(float(p.get("error_rate", 0)) for p in pre_fault_points) / len(pre_fault_points)
    else:
        # Fallback if fault starts at 0s
        baseline_rps = float(time_series[0].get("rps", 100.0))
        baseline_p95 = float(time_series[0].get("p95_ms", 50.0))
        baseline_error_rate = 0.0

    # In-fault degradation calculation
    if in_fault_points:
        min_in_fault_rps = min(float(p.get("rps", 0)) for p in in_fault_points)
        max_in_fault_p95 = max(float(p.get("p95_ms", 0)) for p in in_fault_points)
        max_in_fault_error = max(float(p.get("error_rate", 0)) for p in in_fault_points)
    else:
        min_in_fault_rps = baseline_rps
        max_in_fault_p95 = baseline_p95
        max_in_fault_error = baseline_error_rate

    rps_drop_pct = (
        round(((baseline_rps - min_in_fault_rps) / max(baseline_rps, 0.001)) * 100.0, 2) if baseline_rps > 0 else 0.0
    )

    # 2. Recovery thresholds
    target_recovery_rps = baseline_rps * recovery_rps_ratio
    target_recovery_error = baseline_error_rate + recovery_error_margin
    target_recovery_p95 = baseline_p95 * recovery_latency_ratio

    # 3. Sliding scan over post-fault points for sustained recovery
    recovered = False
    recovered_offset: float | None = None
    rto_seconds: float | None = None

    # Sort post fault points chronologically
    sorted_post = sorted(post_fault_points, key=lambda p: float(p.get("offset_seconds", 0)))

    for i in range(len(sorted_post)):
        cand = sorted_post[i]
        c_offset = float(cand.get("offset_seconds", 0))
        c_rps = float(cand.get("rps", 0))
        c_p95 = float(cand.get("p95_ms", 0))
        c_error = float(cand.get("error_rate", 0))

        # Check if single point is healthy
        if c_rps >= target_recovery_rps and c_error <= target_recovery_error and c_p95 <= target_recovery_p95:
            # Check sustained window
            window_points = [
                p for p in sorted_post[i:] if float(p.get("offset_seconds", 0)) <= c_offset + sustain_seconds
            ]
            sustained = True
            for wp in window_points:
                if (
                    float(wp.get("rps", 0)) < target_recovery_rps
                    or float(wp.get("error_rate", 0)) > target_recovery_error
                    or float(wp.get("p95_ms", 0)) > target_recovery_p95
                ):
                    sustained = False
                    break

            if sustained:
                recovered = True
                recovered_offset = c_offset
                rto_seconds = round(max(0.0, recovered_offset - fault_end_offset), 2)
                break

    # 4. Resilience scoring & grading
    # Score 0-100 based on RTO speed and degradation depth
    if not recovered:
        resilience_score = max(0.0, round(40.0 - min(40.0, rps_drop_pct * 0.4), 1))
        resilience_grade = "F"
        recommendation = "服务在故障撤销后未能在测试窗口内自愈恢复，请检查连接池断路保护与重连机制。"
    else:
        # Faster RTO gives higher score
        assert rto_seconds is not None
        if rto_seconds <= 3.0:
            speed_score = 60.0
            grade = "A"
            recommendation = "服务具备秒级极速自愈能力，断路器与快速恢复机制运行优良。"
        elif rto_seconds <= 10.0:
            speed_score = 50.0
            grade = "B"
            recommendation = "服务具备良好自愈能力（RTO < 10s），恢复表现平稳。"
        elif rto_seconds <= 25.0:
            speed_score = 35.0
            grade = "C"
            recommendation = "服务恢复存在延迟（RTO 10-25s），建议优化线程池排队与超时回退逻辑。"
        else:
            speed_score = 20.0
            grade = "D"
            recommendation = "服务恢复严重迟缓（RTO > 25s），存在长时间雪崩效应滞留风险。"

        degradation_penalty = min(20.0, rps_drop_pct * 0.2)
        resilience_score = round(max(0.0, min(100.0, 40.0 + speed_score - degradation_penalty)), 1)
        resilience_grade = grade

    return {
        "recovered": recovered,
        "rto_seconds": rto_seconds,
        "recovered_at_offset": recovered_offset,
        "fault_start_offset": fault_start_offset,
        "fault_end_offset": fault_end_offset,
        "baseline_metrics": {
            "rps": round(baseline_rps, 2),
            "p95_ms": round(baseline_p95, 2),
            "error_rate": round(baseline_error_rate, 4),
        },
        "in_fault_metrics": {
            "min_rps": round(min_in_fault_rps, 2),
            "max_p95_ms": round(max_in_fault_p95, 2),
            "max_error_rate": round(max_in_fault_error, 4),
            "rps_drop_pct": rps_drop_pct,
        },
        "recovery_targets": {
            "target_rps": round(target_recovery_rps, 2),
            "target_p95_ms": round(target_recovery_p95, 2),
            "target_error_rate": round(target_recovery_error, 4),
            "sustain_seconds": sustain_seconds,
        },
        "resilience_score": resilience_score,
        "resilience_grade": resilience_grade,
        "recommendation": recommendation,
    }
