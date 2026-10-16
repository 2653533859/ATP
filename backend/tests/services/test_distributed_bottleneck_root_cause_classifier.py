"""压测调用链热点慢调用与资源争用瓶颈归因器单元测试 (T3.2)。"""

from __future__ import annotations

import pytest
from app.services.distributed_bottleneck_root_cause_classifier import (
    BottleneckRootCauseType,
    BottleneckSeverity,
    classify_distributed_bottlenecks,
    clear_bottleneck_report_store,
    get_bottleneck_report,
    list_bottleneck_reports,
)


@pytest.fixture(autouse=True)
def _reset_bottleneck_state():
    clear_bottleneck_report_store()
    yield
    clear_bottleneck_report_store()


def test_classify_distributed_bottlenecks_multi_causes():
    """测试探测行锁死锁争用、慢 SQL、线程池打满与 CPU 饱和。"""
    spans = [
        # 1. 锁争用 (CRITICAL)
        {
            "service_name": "order_service",
            "endpoint_or_sql": "UPDATE t_order SET status = 'PAID'",
            "duration_ms": 350.0,
            "lock_wait_time_ms": 260.0,
            "error_message": "Lock wait timeout exceeded",
        },
        # 2. 线程池打满 (HIGH)
        {
            "service_name": "inventory_service",
            "endpoint_or_sql": "/api/v1/inventory/deduct",
            "duration_ms": 400.0,
            "thread_queue_depth": 85,
        },
        # 3. 慢 SQL 查询 (HIGH)
        {
            "service_name": "report_service",
            "endpoint_or_sql": "SELECT * FROM t_audit_log WHERE created_at > '2026-01-01'",
            "duration_ms": 650.0,
        },
        # 4. 正常极快调用
        {
            "service_name": "gateway",
            "endpoint_or_sql": "/api/v1/health",
            "duration_ms": 15.0,
        },
    ]

    report = classify_distributed_bottlenecks(scenario_name="checkout_stress_run", spans=spans)

    assert report.total_spans_analyzed == 4
    assert report.total_bottlenecks_count == 3
    assert report.p50_latency_ms > 0
    assert report.p99_latency_ms == 650.0

    cause_types = {f.cause_type for f in report.findings}
    assert BottleneckRootCauseType.LOCK_CONTENTION_DEADLOCK in cause_types
    assert BottleneckRootCauseType.THREAD_POOL_EXHAUSTION in cause_types
    assert BottleneckRootCauseType.SLOW_DATABASE_QUERY in cause_types

    lock_finding = next(f for f in report.findings if f.cause_type == BottleneckRootCauseType.LOCK_CONTENTION_DEADLOCK)
    assert lock_finding.severity == BottleneckSeverity.CRITICAL

    saved = get_bottleneck_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_bottleneck_reports()) == 1


def test_classify_distributed_bottlenecks_healthy_run():
    """测试完全丝滑健康的调用链无瓶颈。"""
    spans = [
        {"service_name": "auth", "duration_ms": 10.0},
        {"service_name": "cart", "duration_ms": 25.0},
        {"service_name": "user", "duration_ms": 18.0},
    ]

    report = classify_distributed_bottlenecks(scenario_name="healthy_flow", spans=spans)
    assert report.total_bottlenecks_count == 0
    assert report.system_stress_health_score == 100.0
    assert "NONE" in report.primary_root_cause
