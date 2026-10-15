"""Unit tests for T2.2 OpenTelemetry / Jaeger Distributed Trace Retrieval.

Tests:
1. parse_span_tags extracts key-value map from Jaeger tag objects
2. parse_jaeger_trace_data constructs hierarchical waterfall graph and service metrics
3. Detects error spans via error tag, otel.status_code, or HTTP status >= 400
4. fetch_external_distributed_trace queries Jaeger API and handles offline/missing traces
5. Integration with DistributedTraceWaterfallOut schema validation
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.schemas.trace import DistributedTraceWaterfallOut
from app.services.apm_trace_retriever import (
    fetch_external_distributed_trace,
    parse_jaeger_trace_data,
    parse_span_tags,
)


def test_parse_span_tags():
    raw_tags = [
        {"key": "http.method", "value": "GET"},
        {"key": "http.status_code", "value": 200},
        {"key": "error", "value": False},
        {"invalid": "no-key"},
    ]
    parsed = parse_span_tags(raw_tags)
    assert parsed["http.method"] == "GET"
    assert parsed["http.status_code"] == 200
    assert parsed["error"] is False


def test_parse_jaeger_trace_data_builds_waterfall_tree():
    raw_trace = {
        "traceID": "4bf92f3577b34da6a3ce929d0e0e4736",
        "processes": {
            "p1": {"serviceName": "api-gateway"},
            "p2": {"serviceName": "order-service"},
            "p3": {"serviceName": "payment-service"},
        },
        "spans": [
            # Root span: API Gateway (startTime: 1000us, duration: 50000us -> 50ms)
            {
                "spanID": "span-root",
                "processID": "p1",
                "operationName": "GET /api/orders/1",
                "startTime": 1000,
                "duration": 50000,
                "tags": [{"key": "http.status_code", "value": 200}],
                "references": [],
            },
            # Child 1: Order Service (startTime: 2000us, duration: 30000us -> 30ms)
            {
                "spanID": "span-child-order",
                "processID": "p2",
                "operationName": "FetchOrderDetails",
                "startTime": 2000,
                "duration": 30000,
                "tags": [{"key": "db.system", "value": "mysql"}],
                "references": [{"refType": "CHILD_OF", "spanID": "span-root"}],
            },
            # Child 2: Payment Service with error (startTime: 35000us, duration: 15000us -> 15ms)
            {
                "spanID": "span-child-payment",
                "processID": "p3",
                "operationName": "ProcessPayment",
                "startTime": 35000,
                "duration": 15000,
                "tags": [
                    {"key": "http.status_code", "value": 502},
                    {"key": "error", "value": True},
                ],
                "references": [{"refType": "CHILD_OF", "spanID": "span-root"}],
            },
        ],
    }

    parsed = parse_jaeger_trace_data(raw_trace)

    assert parsed["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert parsed["root_service"] == "api-gateway"
    assert parsed["total_duration_ms"] == 50.0  # (51000 - 1000) / 1000.0
    assert parsed["span_count"] == 3
    assert parsed["service_count"] == 3
    assert parsed["services"] == ["api-gateway", "order-service", "payment-service"]
    assert parsed["has_errors"] is True

    # Root span contains 2 children
    assert len(parsed["spans"]) == 1
    root = parsed["spans"][0]
    assert root["span_id"] == "span-root"
    assert len(root["children"]) == 2

    # Child 2 has error
    payment_span = next(c for c in root["children"] if c["service_name"] == "payment-service")
    assert payment_span["has_error"] is True
    assert payment_span["start_time_offset_ms"] == 34.0  # (35000 - 1000) / 1000.0

    # Validate schema compatibility
    validated = DistributedTraceWaterfallOut.model_validate(parsed)
    assert validated.span_count == 3
    assert validated.has_errors is True


def test_parse_jaeger_trace_empty_returns_fallback():
    parsed = parse_jaeger_trace_data({"traceID": "empty-trace", "spans": []})
    assert parsed["trace_id"] == "empty-trace"
    assert parsed["span_count"] == 0
    assert parsed["spans"] == []


@pytest.mark.asyncio
async def test_fetch_external_distributed_trace_success():
    mock_payload = {
        "data": [
            {
                "traceID": "trace-12345",
                "processes": {"p1": {"serviceName": "auth-service"}},
                "spans": [
                    {
                        "spanID": "span-1",
                        "processID": "p1",
                        "operationName": "VerifyToken",
                        "startTime": 1000,
                        "duration": 5000,
                        "tags": [],
                        "references": [],
                    }
                ],
            }
        ]
    }

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: mock_payload

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    res = await fetch_external_distributed_trace(
        "trace-12345",
        base_url="http://jaeger-query:16686",
        http_client=mock_client,
    )

    assert res is not None
    assert res["trace_id"] == "trace-12345"
    assert res["root_service"] == "auth-service"
    assert res["span_count"] == 1


@pytest.mark.asyncio
async def test_fetch_external_distributed_trace_missing_or_offline():
    # 404 Not Found
    mock_resp_404 = AsyncMock(status_code=404)
    mock_client_404 = AsyncMock()
    mock_client_404.get = AsyncMock(return_value=mock_resp_404)

    res = await fetch_external_distributed_trace(
        "missing-trace",
        base_url="http://jaeger-query:16686",
        http_client=mock_client_404,
    )
    assert res is None

    # Connection Timeout
    mock_client_timeout = AsyncMock()
    mock_client_timeout.get = AsyncMock(side_effect=httpx.ConnectTimeout("Connection refused"))

    res_err = await fetch_external_distributed_trace(
        "timeout-trace",
        base_url="http://jaeger-query:16686",
        http_client=mock_client_timeout,
    )
    assert res_err is None

    # No query URL configured
    res_none = await fetch_external_distributed_trace("any-trace", base_url="")
    assert res_none is None
