"""Unit Tests for Trace Anomaly and Slow Call Clusterer (T1.3)。"""

from __future__ import annotations

import pytest

from app.services.distributed_trace_telemetry_relay import (
    clear_telemetry_store,
    ingest_spans,
)
from app.services.trace_anomaly_slow_call_clusterer import (
    AnomalyPattern,
    cluster_trace_anomalies,
    diagnose_telemetry_traces,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_telemetry_store()
    yield
    clear_telemetry_store()


def test_cluster_trace_anomalies_patterns_and_statistics():
    spans = [
        # 1. 慢 SQL 查询簇 (2 次)
        {
            "trace_id": "t1",
            "span_id": "s1",
            "service_name": "order-service",
            "name": "SELECT * FROM orders WHERE user_id = ?",
            "duration_ms": 250.0,
            "attributes": {"db.system": "mysql", "db.statement": "SELECT * FROM orders"},
        },
        {
            "trace_id": "t2",
            "span_id": "s2",
            "service_name": "order-service",
            "name": "SELECT * FROM orders WHERE user_id = ?",
            "duration_ms": 350.0,
            "attributes": {"db.system": "mysql", "db.statement": "SELECT * FROM orders"},
        },
        # 2. 超时熔断异常 (1 次)
        {
            "trace_id": "t3",
            "span_id": "s3",
            "service_name": "pay-service",
            "name": "call_alipay",
            "duration_ms": 3200.0,
            "status_code": "ERROR",
            "status_message": "Gateway Timeout (504)",
            "attributes": {"http.status_code": 504},
        },
        # 3. 正常快速调用 (应被过滤不归入异常簇)
        {
            "trace_id": "t4",
            "span_id": "s4",
            "service_name": "auth-service",
            "name": "check_token",
            "duration_ms": 15.0,
            "status_code": "OK",
            "attributes": {"http.status_code": 200},
        },
    ]

    report = cluster_trace_anomalies(spans, slow_threshold_ms=200.0)

    assert report.total_spans_analyzed == 4
    assert report.total_anomalies_detected == 3
    assert report.clusters_count == 2

    # 聚类项校验
    clusters = {c.pattern: c for c in report.clusters}
    assert AnomalyPattern.SLOW_DATABASE_QUERY in clusters
    assert AnomalyPattern.TIMEOUT_BREACH in clusters

    # 检查慢 SQL 聚类
    db_cluster = clusters[AnomalyPattern.SLOW_DATABASE_QUERY]
    assert db_cluster.service_name == "order-service"
    assert db_cluster.occurrences_count == 2
    assert db_cluster.avg_duration_ms == 300.0  # (250 + 350) / 2
    assert db_cluster.max_duration_ms == 350.0
    assert len(db_cluster.actionable_recommendations) > 0
    assert "索引" in db_cluster.actionable_recommendations[0]

    # 检查超时聚类
    timeout_cluster = clusters[AnomalyPattern.TIMEOUT_BREACH]
    assert timeout_cluster.service_name == "pay-service"
    assert timeout_cluster.occurrences_count == 1
    assert timeout_cluster.avg_duration_ms == 3200.0
    assert timeout_cluster.error_ratio_pct == 100.0

    # 检查危害度排序: 超时簇耗时高且有错误，应排在首位
    assert report.clusters[0].pattern == AnomalyPattern.TIMEOUT_BREACH


def test_diagnose_telemetry_traces_integration():
    trace_id = "trace_telemetry_cluster_1"
    ingest_spans(
        [
            {
                "trace_id": trace_id,
                "span_id": "span_root",
                "parent_span_id": None,
                "name": "POST /api/v1/orders",
                "service_name": "api-gateway",
                "duration_ms": 800.0,
                "start_time_us": 1000,
                "end_time_us": 801000,
            },
            {
                "trace_id": trace_id,
                "span_id": "span_downstream_err",
                "parent_span_id": "span_root",
                "name": "call_inventory",
                "service_name": "order-service",
                "duration_ms": 750.0,
                "status_code": "ERROR",
                "attributes": {"http.status_code": 500},
                "start_time_us": 2000,
                "end_time_us": 752000,
            },
        ]
    )

    report = diagnose_telemetry_traces(slow_threshold_ms=200.0)
    assert report.total_spans_analyzed >= 2
    assert report.clusters_count >= 1

    downstream_cluster = next((c for c in report.clusters if c.pattern == AnomalyPattern.DOWNSTREAM_SERVICE_5XX), None)
    assert downstream_cluster is not None
    assert downstream_cluster.service_name == "order-service"
    assert downstream_cluster.error_ratio_pct == 100.0


def test_empty_spans_clustering():
    report = cluster_trace_anomalies([])
    assert report.total_spans_analyzed == 0
    assert report.clusters_count == 0
    assert len(report.clusters) == 0
