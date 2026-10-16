"""Unit tests for D3.3 Distributed Trace Flamegraph Service."""

import pytest

from app.services.distributed_trace_flamegraph import (
    build_trace_flamegraph,
    get_trace_report,
    list_traces,
    reset_trace_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_trace_registry()
    yield
    reset_trace_registry()


def test_build_trace_flamegraph_tree_and_self_time():
    raw_spans = [
        {
            "span_id": "span_root",
            "parent_span_id": None,
            "service_name": "api-gateway",
            "operation_name": "POST /orders/checkout",
            "start_time_us": 1000000,
            "duration_us": 300000,  # 300ms
        },
        {
            "span_id": "span_auth",
            "parent_span_id": "span_root",
            "service_name": "auth-service",
            "operation_name": "verify_token",
            "start_time_us": 1005000,
            "duration_us": 50000,  # 50ms
        },
        {
            "span_id": "span_order",
            "parent_span_id": "span_root",
            "service_name": "order-service",
            "operation_name": "create_order",
            "start_time_us": 1060000,
            "duration_us": 200000,  # 200ms
        },
        {
            "span_id": "span_db",
            "parent_span_id": "span_order",
            "service_name": "mysql-db",
            "operation_name": "INSERT INTO orders",
            "start_time_us": 1070000,
            "duration_us": 150000,  # 150ms
        },
    ]

    report = build_trace_flamegraph(
        trace_id="trace_test_001",
        raw_spans=raw_spans,
        slow_span_threshold_ms=100.0,
    )

    assert report.trace_id == "trace_test_001"
    assert report.total_spans_count == 4
    assert report.total_duration_ms == 300.0
    assert set(report.services_involved) == {"api-gateway", "auth-service", "order-service", "mysql-db"}

    # 验证火焰图树结构
    flame_root = report.flamegraph_root
    assert flame_root.name == "api-gateway::POST /orders/checkout"
    assert flame_root.duration_ms == 300.0
    # Root 独占耗时 = 300 - (50 + 200) = 50ms
    assert flame_root.self_time_ms == 50.0
    assert len(flame_root.children) == 2

    order_node = next(c for c in flame_root.children if c.service_name == "order-service")
    # order 独占耗时 = 200 - 150 = 50ms
    assert order_node.self_time_ms == 50.0
    assert len(order_node.children) == 1

    db_node = order_node.children[0]
    assert db_node.service_name == "mysql-db"
    assert db_node.self_time_ms == 150.0
    assert db_node.is_slow is True


def test_detect_slow_span_and_bottleneck_summary():
    raw_spans = [
        {
            "span_id": "span_1",
            "parent_span_id": None,
            "service_name": "frontend-bff",
            "operation_name": "GET /feed",
            "start_time_us": 0,
            "duration_us": 500000,  # 500ms
        },
        {
            "span_id": "span_2",
            "parent_span_id": "span_1",
            "service_name": "recommendation-service",
            "operation_name": "calculate_recommendations",
            "start_time_us": 10000,
            "duration_us": 450000,  # 450ms
        },
    ]

    report = build_trace_flamegraph(
        trace_id="trace_slow_002",
        raw_spans=raw_spans,
        slow_span_threshold_ms=100.0,
    )

    assert report.slow_spans_count >= 1
    assert "recommendation-service" in report.bottleneck_summary
    assert "独占自身计算或排队时长达 450.0ms" in report.bottleneck_summary


def test_empty_spans_raises_error():
    with pytest.raises(ValueError, match="Trace 数据为空"):
        build_trace_flamegraph("empty_trace", [])


def test_trace_lookup_and_filter():
    raw_spans = [
        {
            "span_id": "root_span",
            "parent_span_id": None,
            "service_name": "auth-proxy",
            "operation_name": "check",
            "start_time_us": 0,
            "duration_us": 10000,
        }
    ]
    report = build_trace_flamegraph("trace_single_003", raw_spans)
    assert report.trace_id == "trace_single_003"

    fetched = get_trace_report("trace_single_003")
    assert fetched is not None
    assert fetched.root_service == "auth-proxy"

    all_traces = list_traces()
    assert len(all_traces) == 1
