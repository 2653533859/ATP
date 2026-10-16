"""Unit Tests for Critical Path Profiler and Flamegraph Generator (T1.2)。"""

from __future__ import annotations

import pytest

from app.services.critical_path_flamegraph_profiler import (
    BottleneckCategory,
    profile_spans_critical_path,
    profile_trace_critical_path_by_id,
)
from app.services.distributed_trace_telemetry_relay import (
    clear_telemetry_store,
    ingest_spans,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_telemetry_store()
    yield
    clear_telemetry_store()


def test_critical_path_identification_with_parallel_branches():
    # 模拟拓扑:
    # gateway (root, duration 400ms, self_time 50ms)
    #  ├── branch_fast: auth_check (duration 50ms, self_time 50ms)
    #  └── branch_slow: order_service (duration 350ms, self_time 50ms)
    #       └── pay_service: alipay_charge (duration 300ms, self_time 300ms, external http)
    trace_id = "trace_parallel_101"
    spans = [
        {
            "trace_id": trace_id,
            "span_id": "root",
            "parent_span_id": None,
            "name": "POST /checkout",
            "service_name": "gateway",
            "duration_ms": 400.0,
            "start_time_us": 1000000,
            "end_time_us": 1400000,
        },
        {
            "trace_id": trace_id,
            "span_id": "auth_fast",
            "parent_span_id": "root",
            "name": "verify_token",
            "service_name": "auth-service",
            "duration_ms": 50.0,
            "start_time_us": 1010000,
            "end_time_us": 1060000,
        },
        {
            "trace_id": trace_id,
            "span_id": "order_slow",
            "parent_span_id": "root",
            "name": "submit_order",
            "service_name": "order-service",
            "duration_ms": 350.0,
            "start_time_us": 1050000,
            "end_time_us": 1400000,
        },
        {
            "trace_id": trace_id,
            "span_id": "pay_client",
            "parent_span_id": "order_slow",
            "name": "call_alipay_gateway",
            "service_name": "pay-service",
            "kind": "CLIENT",
            "duration_ms": 300.0,
            "start_time_us": 1060000,
            "end_time_us": 1360000,
            "attributes": {"http.url": "https://api.alipay.com/pay", "http.status_code": 200},
        },
    ]

    report = profile_spans_critical_path(trace_id, spans)

    assert report.trace_id == trace_id
    # 关键路径应为: root -> order_slow -> pay_client
    critical_ids = [s.span_id for s in report.critical_path]
    assert critical_ids == ["root", "order_slow", "pay_client"]
    assert "auth_fast" not in critical_ids

    # 首要瓶颈应为 pay_client (自身耗时 300ms)
    assert report.primary_bottleneck is not None
    assert report.primary_bottleneck.span_id == "pay_client"
    assert report.primary_bottleneck.is_bottleneck is True
    assert report.primary_bottleneck.bottleneck_category == BottleneckCategory.EXTERNAL_HTTP_LATENCY

    # 检查火焰图结构
    flame = report.flamegraph_root
    assert flame.span_id == "root"
    assert flame.is_critical_path is True
    assert len(flame.children) == 2

    # 找到火焰图中的 pay_client 节点
    order_node = next(c for c in flame.children if c.span_id == "order_slow")
    assert order_node.is_critical_path is True
    pay_node = next(c for c in order_node.children if c.span_id == "pay_client")
    assert pay_node.is_bottleneck is True
    assert pay_node.bottleneck_category == BottleneckCategory.EXTERNAL_HTTP_LATENCY


def test_database_bottleneck_detection():
    trace_id = "trace_db_slow"
    spans = [
        {
            "trace_id": trace_id,
            "span_id": "s_root",
            "name": "GET /users",
            "service_name": "user-service",
            "duration_ms": 150.0,
        },
        {
            "trace_id": trace_id,
            "span_id": "s_db",
            "parent_span_id": "s_root",
            "name": "SELECT * FROM users WHERE active = 1",
            "service_name": "user-service",
            "duration_ms": 120.0,
            "attributes": {"db.system": "postgresql", "db.statement": "SELECT * FROM users"},
        },
    ]

    report = profile_spans_critical_path(trace_id, spans)
    assert report.primary_bottleneck is not None
    assert report.primary_bottleneck.span_id == "s_db"
    assert report.primary_bottleneck.bottleneck_category == BottleneckCategory.DATABASE_SLOW_QUERY


def test_profile_by_trace_id_integration():
    trace_id = "trace_telemetry_int_101"
    ingest_spans(
        [
            {
                "trace_id": trace_id,
                "span_id": "sp_1",
                "parent_span_id": None,
                "name": "POST /items",
                "service_name": "item-service",
                "start_time_us": 1000,
                "end_time_us": 201000,  # 200ms
            },
            {
                "trace_id": trace_id,
                "span_id": "sp_2",
                "parent_span_id": "sp_1",
                "name": "heavy_calculation",
                "service_name": "item-service",
                "kind": "INTERNAL",
                "start_time_us": 2000,
                "end_time_us": 182000,  # 180ms
            },
        ]
    )

    report = profile_trace_critical_path_by_id(trace_id)
    assert report is not None
    assert report.trace_id == trace_id
    assert report.critical_path_spans_count == 2
    assert report.primary_bottleneck is not None
    assert report.primary_bottleneck.span_id == "sp_2"
    assert report.primary_bottleneck.bottleneck_category == BottleneckCategory.INTERNAL_COMPUTATION


def test_empty_spans_profile():
    report = profile_spans_critical_path("empty_trace", [])
    assert report.critical_path_spans_count == 0
    assert report.primary_bottleneck is None
    assert report.flamegraph_root.name == "empty"
