"""Scheduled Performance Baseline Alignment and Trend Drift Alerting (Q3.1).

Provides:
1. Automated baseline evaluation and promotion candidates.
2. Performance trend drift detection (RPS drops, P95 latency degradation, error rate spikes).
3. Configurable drift alert thresholds with critical/warning severity levels.
4. Scheduled alignment scan across project performance tests.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.models.performance import PerformanceRun, PerformanceTest

logger = logging.getLogger(__name__)

DEFAULT_RPS_DROP_THRESHOLD_PCT = 15.0
DEFAULT_P95_INCREASE_THRESHOLD_PCT = 20.0
DEFAULT_ERROR_RATE_DELTA_PCT = 2.0


def calculate_baseline_drift_alert(
    baseline_summary: dict[str, Any] | None,
    current_summary: dict[str, Any] | None,
    *,
    rps_drop_threshold_pct: float = DEFAULT_RPS_DROP_THRESHOLD_PCT,
    p95_increase_threshold_pct: float = DEFAULT_P95_INCREASE_THRESHOLD_PCT,
    error_rate_delta_pct: float = DEFAULT_ERROR_RATE_DELTA_PCT,
) -> dict[str, Any]:
    """Calculate performance drift and determine if alerting thresholds are breached."""
    b_sum = baseline_summary if isinstance(baseline_summary, dict) else {}
    c_sum = current_summary if isinstance(current_summary, dict) else {}

    b_rps = float(b_sum.get("rps") or 0.0)
    c_rps = float(c_sum.get("rps") or 0.0)

    b_p95 = float(b_sum.get("p95_ms") or 0.0)
    c_p95 = float(c_sum.get("p95_ms") or 0.0)

    b_err = float(b_sum.get("error_rate") or 0.0)
    c_err = float(c_sum.get("error_rate") or 0.0)

    reasons: list[str] = []
    severity = "none"

    # 1. RPS Drop Check (RPS reduction)
    rps_drift_pct = 0.0
    if b_rps > 0:
        rps_drift_pct = round(((c_rps - b_rps) / b_rps) * 100.0, 2)
        if rps_drift_pct <= -rps_drop_threshold_pct:
            reasons.append(f"吞吐量 (RPS) 较基线严重下跌 {abs(rps_drift_pct)}% (基线: {b_rps}, 当前: {c_rps})")
            severity = "critical"

    # 2. P95 Latency Degradation Check
    p95_drift_pct = 0.0
    if b_p95 > 0:
        p95_drift_pct = round(((c_p95 - b_p95) / b_p95) * 100.0, 2)
        if p95_drift_pct >= p95_increase_threshold_pct:
            reasons.append(f"P95 响应延迟较基线恶化 {p95_drift_pct}% (基线: {b_p95}ms, 当前: {c_p95}ms)")
            if severity != "critical":
                severity = "warning" if p95_drift_pct < 50.0 else "critical"

    # 3. Error Rate Spike Check
    err_delta_pct = round((c_err - b_err) * 100.0, 2)
    if err_delta_pct >= error_rate_delta_pct:
        reasons.append(f"接口错误率较基线增长 {err_delta_pct}% (基线: {b_err * 100:.2f}%, 当前: {c_err * 100:.2f}%)")
        severity = "critical"

    is_drifted = len(reasons) > 0
    return {
        "is_drifted": is_drifted,
        "should_alert": is_drifted,
        "severity": severity,
        "alert_title": f"性能基线严重漂移告警 [{severity.upper()}]" if is_drifted else "性能处于基线容差范围内",
        "alert_reasons": reasons,
        "metrics": {
            "rps": {"baseline": b_rps, "current": c_rps, "drift_percent": rps_drift_pct},
            "p95_ms": {"baseline": b_p95, "current": c_p95, "drift_percent": p95_drift_pct},
            "error_rate": {"baseline": b_err, "current": c_err, "delta_percent": err_delta_pct},
        },
    }


def evaluate_baseline_candidate(
    test: PerformanceTest,
    run: PerformanceRun,
    *,
    baseline_run: PerformanceRun | None = None,
) -> dict[str, Any]:
    """Evaluate whether a successful run qualifies as a new baseline or improvement."""
    if run.status != "success":
        return {"eligible": False, "reason": "只有执行成功的压测运行才能作为性能基准"}

    c_summary = run.summary if isinstance(run.summary, dict) else {}
    c_rps = float(c_summary.get("rps") or 0.0)
    c_p95 = float(c_summary.get("p95_ms") or 0.0)
    c_err = float(c_summary.get("error_rate") or 0.0)

    if c_rps <= 0:
        return {"eligible": False, "reason": "缺少有效的 RPS 吞吐量指标"}

    # If no baseline is currently set on the test, the first success is eligible
    if not test.baseline_run_id or baseline_run is None:
        return {
            "eligible": True,
            "reason": "当前测试尚未设置基准，该运行符合首个基线要求",
            "is_first_baseline": True,
        }

    b_summary = baseline_run.summary if isinstance(baseline_run.summary, dict) else {}
    b_rps = float(b_summary.get("rps") or 0.0)
    b_p95 = float(b_summary.get("p95_ms") or 99999.0)
    b_err = float(b_summary.get("error_rate") or 1.0)

    # Superior candidate rule: higher throughput without significant latency degradation
    is_better = (c_rps > b_rps * 1.05) and (c_p95 <= b_p95 * 1.05) and (c_err <= b_err)
    return {
        "eligible": is_better,
        "reason": "吞吐量显著提升且延迟与错误率不劣于既有基线" if is_better else "未达到超越既有基线的提升标准",
        "current_rps": c_rps,
        "baseline_rps": b_rps,
        "current_p95": c_p95,
        "baseline_p95": b_p95,
    }


async def run_project_baseline_alignment_scan(
    db: Any,
    project_id: int,
) -> list[dict[str, Any]]:
    """Scan all performance tests in a project, detect drift against baseline, and output alert summary."""
    q_tests = select(PerformanceTest).where(PerformanceTest.project_id == project_id)
    tests = (await db.execute(q_tests)).scalars().all()
    results: list[dict[str, Any]] = []

    for t in tests:
        if not t.baseline_run_id:
            continue
        baseline_run = await db.get(PerformanceRun, t.baseline_run_id)
        if not baseline_run:
            continue

        # Get latest finished run
        q_latest = (
            select(PerformanceRun)
            .where(PerformanceRun.performance_test_id == t.id, PerformanceRun.id != t.baseline_run_id)
            .order_by(PerformanceRun.created_at.desc())
            .limit(1)
        )
        latest_run = (await db.execute(q_latest)).scalar_one_or_none()
        if not latest_run:
            continue

        drift_report = calculate_baseline_drift_alert(baseline_run.summary, latest_run.summary)
        results.append(
            {
                "test_id": t.id,
                "test_name": t.name,
                "baseline_run_id": t.baseline_run_id,
                "latest_run_id": latest_run.id,
                "drift_report": drift_report,
            }
        )

    return results
