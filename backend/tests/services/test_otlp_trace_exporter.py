"""OTLP / Jaeger 追踪数据导出适配器单测 (T1.3)"""

from __future__ import annotations

from app.services.otlp_trace_exporter import (
    OtlpSpan,
    SpanKind,
    StatusCode,
    build_otlp_payload,
    clear_otlp_export_buffer,
    export_spans_to_otlp,
    list_otlp_export_batches,
)


def test_otlp_span_serialization_and_payload_building():
    span = OtlpSpan(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="00f067aa0ba902b7",
        parent_span_id="5fb397be34d23b0f",
        name="HTTP GET /api/v1/orders",
        kind=SpanKind.SPAN_KIND_CLIENT,
        attributes={
            "http.method": "GET",
            "http.status_code": 200,
            "http.is_success": True,
            "duration.seconds": 0.045,
        },
        status_code=StatusCode.STATUS_CODE_OK,
    )
    span_dict = span.to_otlp_dict()
    assert span_dict["traceId"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert span_dict["spanId"] == "00f067aa0ba902b7"
    assert span_dict["parentSpanId"] == "5fb397be34d23b0f"
    assert span_dict["kind"] == 3
    assert len(span_dict["attributes"]) == 4

    payload = build_otlp_payload(
        spans=[span],
        service_name="atp-test-service",
        service_version="4.9.0",
        service_environment="staging",
    )
    assert "resourceSpans" in payload
    resource = payload["resourceSpans"][0]["resource"]
    res_attrs = {item["key"]: item["value"]["stringValue"] for item in resource["attributes"]}
    assert res_attrs["service.name"] == "atp-test-service"
    assert res_attrs["deployment.environment"] == "staging"


def test_export_spans_to_otlp_buffer():
    clear_otlp_export_buffer()

    span1 = OtlpSpan(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="00f067aa0ba902b7",
        name="Step 1: 创建订单",
    )
    span2 = OtlpSpan(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="1122334455667788",
        parent_span_id="00f067aa0ba902b7",
        name="Step 2: 账户扣款",
    )

    res = export_spans_to_otlp(
        spans=[span1, span2],
        service_name="order-system",
        target_endpoint="http://otel-collector.infra:4318/v1/traces",
    )
    assert res["status"] == "SUCCESS"
    assert res["spans_count"] == 2
    assert res["target_endpoint"] == "http://otel-collector.infra:4318/v1/traces"

    batches = list_otlp_export_batches(limit=10)
    assert len(batches) == 1
    assert batches[0]["spans_count"] == 2
    assert batches[0]["service_name"] == "order-system"
