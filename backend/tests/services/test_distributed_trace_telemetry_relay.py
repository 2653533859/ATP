"""Unit Tests for OpenTelemetry Distributed Trace Telemetry Relay (T1.1)。"""

from __future__ import annotations

import pytest

from app.services.distributed_trace_telemetry_relay import (
    SpanStatusCode,
    clear_telemetry_store,
    format_w3c_traceparent,
    ingest_spans,
    list_trace_summaries,
    parse_w3c_traceparent,
    reconstruct_trace_tree,
)


@pytest.fixture(autouse=True)
def clean_telemetry_store():
    clear_telemetry_store()
    yield
    clear_telemetry_store()


def test_parse_and_format_w3c_traceparent():
    raw_header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    parsed = parse_w3c_traceparent(raw_header)
    assert parsed is not None
    trace_id, parent_id, flags = parsed
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert parent_id == "00f067aa0ba902b7"
    assert flags == "01"

    # 错误格式验证
    assert parse_w3c_traceparent("") is None
    assert parse_w3c_traceparent("invalid-header") is None
    assert parse_w3c_traceparent("01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01") is None

    # 重新格式化生成
    formatted = format_w3c_traceparent(trace_id, parent_id, "01")
    assert formatted == raw_header


def test_ingest_spans_and_reconstruct_trace_tree():
    trace_id = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
    root_span_id = "0000000000000001"
    child_span_id = "0000000000000002"
    grandchild_span_id = "0000000000000003"

    spans_data = [
        {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_span_id": None,
            "name": "POST /api/v1/orders/checkout",
            "service_name": "api-gateway",
            "kind": "SERVER",
            "start_time_us": 1000000,
            "end_time_us": 1500000,  # 500ms
            "status_code": "OK",
            "attributes": {"http.status_code": 200},
        },
        {
            "trace_id": trace_id,
            "span_id": child_span_id,
            "parent_span_id": root_span_id,
            "name": "create_order",
            "service_name": "order-service",
            "kind": "INTERNAL",
            "start_time_us": 1050000,
            "end_time_us": 1450000,  # 400ms
            "status_code": "OK",
            "attributes": {"order.id": 1001},
        },
        {
            "trace_id": trace_id,
            "span_id": grandchild_span_id,
            "parent_span_id": child_span_id,
            "name": "process_payment",
            "service_name": "pay-service",
            "kind": "CLIENT",
            "start_time_us": 1100000,
            "end_time_us": 1300000,  # 200ms
            "status_code": "ERROR",
            "status_message": "Payment gateway timeout",
            "attributes": {"pay.channel": "ALIPAY"},
        },
    ]

    # 1. 批量中继接收
    res = ingest_spans(spans_data)
    assert res["ingested_count"] == 3
    assert res["traces_updated_count"] == 1
    assert trace_id in res["trace_ids"]

    # 2. 级联调用树重构
    tree = reconstruct_trace_tree(trace_id)
    assert tree is not None
    assert tree.trace_id == trace_id
    assert tree.total_spans_count == 3
    assert tree.total_duration_ms == 500.0  # (1500000 - 1000000) / 1000
    assert tree.has_error is True
    assert set(tree.services_involved) == {"api-gateway", "order-service", "pay-service"}

    # 检查层级结构
    assert len(tree.root_nodes) == 1
    root = tree.root_nodes[0]
    assert root.span.span_id == root_span_id
    assert root.depth == 0
    assert len(root.children) == 1

    child = root.children[0]
    assert child.span.span_id == child_span_id
    assert child.depth == 1
    assert len(child.children) == 1

    grandchild = child.children[0]
    assert grandchild.span.span_id == grandchild_span_id
    assert grandchild.depth == 2
    assert grandchild.span.status_code == SpanStatusCode.ERROR
    assert grandchild.span.status_message == "Payment gateway timeout"
    assert len(grandchild.children) == 0

    # 导出字典结构
    tree_dict = tree.to_dict()
    assert tree_dict["trace_id"] == trace_id
    assert tree_dict["root_nodes"][0]["children"][0]["children"][0]["service_name"] == "pay-service"


def test_list_trace_summaries_filtering():
    trace_normal = "11111111111111111111111111111111"
    trace_error = "22222222222222222222222222222222"

    ingest_spans(
        [
            {
                "trace_id": trace_normal,
                "span_id": "s1",
                "name": "GET /health",
                "service_name": "auth-service",
                "start_time_us": 1000,
                "end_time_us": 51000,  # 50ms
                "status_code": "OK",
            },
            {
                "trace_id": trace_error,
                "span_id": "s2",
                "name": "POST /charge",
                "service_name": "pay-service",
                "start_time_us": 2000,
                "end_time_us": 1502000,  # 1500ms
                "status_code": "ERROR",
                "status_message": "insufficient funds",
            },
        ]
    )

    # 无过滤
    all_traces = list_trace_summaries()
    assert len(all_traces) == 2

    # 按服务名过滤
    pay_traces = list_trace_summaries(service_name="pay-service")
    assert len(pay_traces) == 1
    assert pay_traces[0]["trace_id"] == trace_error

    # 按错误状态过滤
    err_traces = list_trace_summaries(has_error=True)
    assert len(err_traces) == 1
    assert err_traces[0]["trace_id"] == trace_error

    ok_traces = list_trace_summaries(has_error=False)
    assert len(ok_traces) == 1
    assert ok_traces[0]["trace_id"] == trace_normal

    # 按最小耗时过滤 (>= 500ms)
    slow_traces = list_trace_summaries(min_duration_ms=500.0)
    assert len(slow_traces) == 1
    assert slow_traces[0]["trace_id"] == trace_error


def test_reconstruct_non_existent_trace():
    tree = reconstruct_trace_tree("non-existent-trace-id")
    assert tree is None
