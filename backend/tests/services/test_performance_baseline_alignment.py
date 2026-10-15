"""Unit tests for Q3.1 Scheduled Performance Baseline Alignment and Trend Drift Alerting.

Tests:
1. calculate_baseline_drift_alert detects RPS drops, P95 latency spikes, and error rate increases
2. calculate_baseline_drift_alert passes runs within tolerance thresholds
3. evaluate_baseline_candidate evaluates new runs for baseline eligibility and superiority
4. run_project_baseline_alignment_scan aggregates project test baseline drift reports
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.models.bootstrap import load_all_models
from app.models.performance import PerformanceRun, PerformanceTest
from app.services.performance_baseline_alignment import (
    calculate_baseline_drift_alert,
    evaluate_baseline_candidate,
    run_project_baseline_alignment_scan,
)

load_all_models()


def test_drift_alert_normal_within_tolerance():
    baseline = {"rps": 500.0, "p95_ms": 100.0, "error_rate": 0.01}
    current = {"rps": 490.0, "p95_ms": 105.0, "error_rate": 0.012}

    res = calculate_baseline_drift_alert(baseline, current)
    assert res["is_drifted"] is False
    assert res["should_alert"] is False
    assert res["severity"] == "none"
    assert len(res["alert_reasons"]) == 0


def test_drift_alert_rps_critical_drop():
    baseline = {"rps": 1000.0, "p95_ms": 50.0, "error_rate": 0.005}
    # RPS drops by 25% (threshold is 15%)
    current = {"rps": 750.0, "p95_ms": 52.0, "error_rate": 0.005}

    res = calculate_baseline_drift_alert(baseline, current)
    assert res["is_drifted"] is True
    assert res["should_alert"] is True
    assert res["severity"] == "critical"
    assert any("吞吐量 (RPS) 较基线严重下跌" in r for r in res["alert_reasons"])


def test_drift_alert_p95_latency_degradation():
    baseline = {"rps": 500.0, "p95_ms": 100.0, "error_rate": 0.01}
    # P95 increases by 35% (threshold is 20%)
    current = {"rps": 505.0, "p95_ms": 135.0, "error_rate": 0.01}

    res = calculate_baseline_drift_alert(baseline, current)
    assert res["is_drifted"] is True
    assert res["should_alert"] is True
    assert res["severity"] == "warning"
    assert any("P95 响应延迟较基线恶化" in r for r in res["alert_reasons"])


def test_drift_alert_error_rate_spike():
    baseline = {"rps": 800.0, "p95_ms": 80.0, "error_rate": 0.005}
    # Error rate increases by 3.5% (threshold is 2.0%)
    current = {"rps": 810.0, "p95_ms": 82.0, "error_rate": 0.04}

    res = calculate_baseline_drift_alert(baseline, current)
    assert res["is_drifted"] is True
    assert res["should_alert"] is True
    assert res["severity"] == "critical"
    assert any("错误率较基线增长" in r for r in res["alert_reasons"])


def test_evaluate_baseline_candidate():
    test = PerformanceTest(id=1, name="Order Load Test", baseline_run_id=None)

    # 1. Failed run is never eligible
    run_failed = PerformanceRun(id=10, performance_test_id=1, status="failed")
    assert evaluate_baseline_candidate(test, run_failed)["eligible"] is False

    # 2. First successful run on test without baseline is eligible
    run_success = PerformanceRun(
        id=11,
        performance_test_id=1,
        status="success",
        summary={"rps": 500.0, "p95_ms": 120.0, "error_rate": 0.01},
    )
    eval_first = evaluate_baseline_candidate(test, run_success)
    assert eval_first["eligible"] is True
    assert eval_first["is_first_baseline"] is True

    # 3. New run with existing baseline: superior run (+20% RPS, better P95) is eligible
    test.baseline_run_id = 11
    run_superior = PerformanceRun(
        id=12,
        performance_test_id=1,
        status="success",
        summary={"rps": 600.0, "p95_ms": 110.0, "error_rate": 0.005},
    )
    eval_superior = evaluate_baseline_candidate(test, run_superior, baseline_run=run_success)
    assert eval_superior["eligible"] is True

    # 4. Inferior run (lower RPS) is not eligible
    run_inferior = PerformanceRun(
        id=13,
        performance_test_id=1,
        status="success",
        summary={"rps": 400.0, "p95_ms": 140.0, "error_rate": 0.02},
    )
    eval_inferior = evaluate_baseline_candidate(test, run_inferior, baseline_run=run_success)
    assert eval_inferior["eligible"] is False


@pytest.mark.asyncio
async def test_run_project_baseline_alignment_scan():
    t1 = PerformanceTest(id=1, project_id=77, name="Test 1", baseline_run_id=101)
    base_run = PerformanceRun(
        id=101, performance_test_id=1, status="success", summary={"rps": 500, "p95_ms": 50, "error_rate": 0.01}
    )
    latest_run = PerformanceRun(
        id=102, performance_test_id=1, status="success", summary={"rps": 350, "p95_ms": 90, "error_rate": 0.01}
    )

    class _MockResult:
        def __init__(self, items):
            self.items = items

        def scalars(self):
            return SimpleNamespace(all=lambda: self.items)

        def scalar_one_or_none(self):
            return self.items[0] if self.items else None

    class _MockDB:
        async def get(self, model, obj_id):
            if model is PerformanceRun and obj_id == 101:
                return base_run
            return None

        async def execute(self, stmt):
            sql = str(stmt).lower()
            if "from performance_tests" in sql:
                return _MockResult([t1])
            if "from performance_runs" in sql:
                return _MockResult([latest_run])
            return _MockResult([])

    db: Any = _MockDB()
    reports = await run_project_baseline_alignment_scan(db, project_id=77)
    assert len(reports) == 1
    assert reports[0]["test_id"] == 1
    assert reports[0]["drift_report"]["is_drifted"] is True
    assert reports[0]["drift_report"]["severity"] == "critical"
