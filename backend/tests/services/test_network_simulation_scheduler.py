"""Unit tests for Q1.2 Mobile Network Simulation Test Scheduling and Metric Collection.

Tests:
1. build_network_run_configuration generates setup and teardown commands
2. NetworkMetricsCollector tracks requests, latencies, timeouts, retries, and dropped packets
3. Resilience score calculation penalizes packet loss, timeouts, and excessive retries
4. Empty metrics collector returns graceful defaults
"""

from __future__ import annotations


from app.services.network_simulation_scheduler import (
    NetworkMetricsCollector,
    build_network_run_configuration,
)


def test_build_network_run_configuration_setup_and_teardown():
    config_2g = build_network_run_configuration("2g_edge")
    assert config_2g["profile_id"] == "2g_edge"
    assert config_2g["offline"] is False
    assert config_2g["cdp_conditions"]["latency"] == 300
    assert len(config_2g["adb_setup_commands"]) >= 2

    # Check teardown commands guarantee clean restoration
    teardown = config_2g["adb_teardown_commands"]
    assert ["svc", "data", "enable"] in teardown
    assert ["svc", "wifi", "enable"] in teardown
    assert any("del" in cmd and "qdisc" in cmd for cmd in teardown)


def test_network_metrics_collector_empty():
    collector = NetworkMetricsCollector("4g_lte")
    summary = collector.compute_summary()
    assert summary["profile_id"] == "4g_lte"
    assert summary["total_requests"] == 0
    assert summary["success_rate"] == 100.0
    assert summary["resilience_score"] == 100.0


def test_network_metrics_collector_records_and_computes_resilience():
    collector = NetworkMetricsCollector("2g_edge")

    # 1. Successful requests
    collector.record_request(payload_bytes=512, custom_latency_ms=120.0)
    collector.record_request(payload_bytes=1024, custom_latency_ms=150.0)
    collector.record_request(payload_bytes=2048, custom_latency_ms=180.0)

    # 2. Retried request
    collector.record_request(payload_bytes=1024, is_retry=True, custom_latency_ms=250.0)

    # 3. Timed out request
    collector.record_request(payload_bytes=4096, timed_out=True, error="Timeout waiting for socket")

    summary = collector.compute_summary()

    assert summary["total_requests"] == 5
    assert summary["retries"] == 1
    assert summary["timeouts"] == 1
    assert summary["failed_requests"] >= 1
    assert summary["avg_latency_ms"] > 100.0
    assert summary["max_latency_ms"] >= 250.0
    assert summary["p95_latency_ms"] >= 180.0

    # Success rate and resilience score penalized
    assert summary["success_rate"] < 100.0
    assert summary["resilience_score"] < 100.0
    assert summary["resilience_score"] > 0.0
