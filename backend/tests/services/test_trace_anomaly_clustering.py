"""Unit tests for T2.3 Trace anomaly clustering and root-cause attribution.

Tests:
1. classify_span identifies slow SQL queries, downstream 5xx faults, timeouts, and slow spans
2. cluster_trace_anomalies groups errors, identifies root cause span and service
3. Clean trace produces empty anomaly cluster
4. TraceAnomalyClusterOut schema validation
"""

from __future__ import annotations

from app.schemas.trace import TraceAnomalyClusterOut
from app.services.trace_anomaly_clustering import (
    classify_span,
    cluster_trace_anomalies,
)


def test_classify_span_slow_sql_query():
    span = {
        "span_id": "span-sql-1",
        "service_name": "order-service",
        "operation_name": "SELECT orders",
        "duration_ms": 320.5,
        "has_error": False,
        "tags": {
            "db.system": "mysql",
            "db.statement": "SELECT * FROM orders WHERE user_id = 123 ORDER BY created_at DESC",
        },
    }

    anomaly = classify_span(span, slow_db_threshold_ms=100.0)
    assert anomaly is not None
    assert anomaly["category"] == "slow_database_query"
    assert anomaly["severity"] == "warning"
    assert "慢数据库查询" in anomaly["description"]
    assert "SELECT * FROM orders" in anomaly["statement"]


def test_classify_span_downstream_http_fault():
    span = {
        "span_id": "span-http-fail",
        "service_name": "payment-gateway",
        "operation_name": "POST /v1/charge",
        "duration_ms": 85.0,
        "has_error": True,
        "tags": {
            "http.status_code": 502,
            "error": True,
        },
    }

    anomaly = classify_span(span)
    assert anomaly is not None
    assert anomaly["category"] == "downstream_service_fault"
    assert anomaly["severity"] == "critical"
    assert anomaly["http_status"] == 502
    assert "调用失败" in anomaly["description"]


def test_classify_span_rpc_timeout():
    span = {
        "span_id": "span-rpc-timeout",
        "service_name": "inventory-service",
        "operation_name": "grpc.CheckStock",
        "duration_ms": 3000.0,
        "has_error": True,
        "tags": {
            "error.message": "Deadline exceeded waiting for lock",
        },
    }

    anomaly = classify_span(span)
    assert anomaly is not None
    assert anomaly["category"] == "rpc_timeout"
    assert anomaly["severity"] == "critical"


def test_classify_span_normal_returns_none():
    span = {
        "span_id": "span-ok",
        "service_name": "user-service",
        "operation_name": "GET /me",
        "duration_ms": 15.0,
        "has_error": False,
        "tags": {"http.status_code": 200},
    }
    assert classify_span(span) is None


def test_cluster_trace_anomalies_root_cause_attribution():
    waterfall_data = {
        "trace_id": "trace-cluster-test-123",
        "spans": [
            {
                "span_id": "root-span",
                "service_name": "api-gateway",
                "operation_name": "GET /checkout",
                "duration_ms": 1200.0,
                "has_error": True,
                "tags": {"http.status_code": 500},
                "children": [
                    {
                        "span_id": "db-span",
                        "service_name": "order-service",
                        "operation_name": "SELECT order_items",
                        "duration_ms": 250.0,
                        "has_error": False,
                        "tags": {
                            "db.system": "postgresql",
                            "db.statement": "SELECT * FROM order_items WHERE order_id = 99",
                        },
                    },
                    {
                        "span_id": "failing-downstream-span",
                        "service_name": "payment-service",
                        "operation_name": "POST /charge",
                        "duration_ms": 800.0,
                        "has_error": True,
                        "tags": {"http.status_code": 504},
                    },
                ],
            }
        ],
    }

    cluster = cluster_trace_anomalies(waterfall_data)

    assert cluster["trace_id"] == "trace-cluster-test-123"
    assert cluster["total_anomalies"] >= 2
    assert cluster["error_span_count"] >= 1
    assert cluster["slow_span_count"] >= 1

    # Attribution targets critical error first
    assert cluster["root_cause_service"] in ("payment-service", "api-gateway")
    assert cluster["root_cause_category"] == "downstream_service_fault"
    assert "调用失败" in cluster["root_cause_summary"]

    # Validate Pydantic schema serialization
    validated = TraceAnomalyClusterOut.model_validate(cluster)
    assert validated.trace_id == "trace-cluster-test-123"
    assert validated.total_anomalies >= 2


def test_cluster_trace_anomalies_clean_trace():
    waterfall_clean = {
        "trace_id": "trace-clean-456",
        "spans": [
            {
                "span_id": "root-span",
                "service_name": "api-gateway",
                "operation_name": "GET /health",
                "duration_ms": 5.0,
                "has_error": False,
                "tags": {"http.status_code": 200},
                "children": [],
            }
        ],
    }

    cluster = cluster_trace_anomalies(waterfall_clean)
    assert cluster["trace_id"] == "trace-clean-456"
    assert cluster["total_anomalies"] == 0
    assert cluster["root_cause_service"] == "none"
    assert cluster["error_span_count"] == 0
    assert cluster["slow_span_count"] == 0
