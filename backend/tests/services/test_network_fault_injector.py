"""Unit tests for Q1.3 Network Packet Capture Analysis and Fault Injection.

Tests:
1. parse_har_capture parses HAR 1.2 entries, metrics, domain breakdown, and slowest requests
2. parse_har_capture handles corrupted data gracefully
3. simulate_network_fault handles DNS spoofing, NXDOMAIN, connection reset, timeout, and HTTP 5xx
4. Unmatched URL pattern passes through without fault
5. archive_network_fault_incident compiles structured incident artifact
"""

from __future__ import annotations

from typing import Any

from app.models.bootstrap import load_all_models
from app.services.network_fault_injector import (
    archive_network_fault_incident,
    parse_har_capture,
    simulate_network_fault,
)

load_all_models()


def test_parse_har_capture_valid_entries():
    sample_har = {
        "log": {
            "version": "1.2",
            "entries": [
                {
                    "request": {"method": "GET", "url": "https://api.example.com/v1/users"},
                    "response": {"status": 200, "headersSize": 200, "bodySize": 1024},
                    "time": 45.0,
                },
                {
                    "request": {"method": "POST", "url": "https://api.example.com/v1/orders"},
                    "response": {"status": 201, "headersSize": 250, "bodySize": 2048},
                    "time": 180.5,
                },
                {
                    "request": {"method": "GET", "url": "https://pay.service.internal/charge"},
                    "response": {"status": 500, "headersSize": 150, "bodySize": 500},
                    "time": 850.0,
                },
            ],
        }
    }

    parsed = parse_har_capture(sample_har)
    assert parsed["valid"] is True
    assert parsed["total_requests"] == 3
    assert parsed["failed_requests"] == 1
    assert parsed["success_rate"] == 66.67
    assert parsed["total_bytes_transferred"] == (200 + 1024 + 250 + 2048 + 150 + 500)
    assert "api.example.com" in parsed["domains_accessed"]
    assert "pay.service.internal" in parsed["domains_accessed"]

    # Slowest request is the 850ms failing charge
    slowest = parsed["slowest_requests"]
    assert len(slowest) == 3
    assert slowest[0]["duration_ms"] == 850.0
    assert slowest[0]["status"] == 500


def test_parse_har_capture_invalid_input():
    assert parse_har_capture("not a json string")["valid"] is False
    invalid_input: Any = 12345
    assert parse_har_capture(invalid_input)["valid"] is False


def test_simulate_network_fault_dns_and_reset():
    # 1. DNS NXDOMAIN failure
    nx_policy = {
        "url_pattern": r".*auth\.internal.*",
        "fault_type": "dns_nxdomain",
        "probability": 1.0,
    }
    nx_res = simulate_network_fault("https://auth.internal/token", nx_policy)
    assert nx_res["fault_injected"] is True
    assert nx_res["action"] == "fail"
    assert "NXDOMAIN" in nx_res["error"]

    # 2. DNS Spoofing / Hijacking
    spoof_policy = {
        "url_pattern": r".*payment\.gateway.*",
        "fault_type": "dns_spoofing",
        "probability": 1.0,
        "params": {"spoofed_host": "127.0.0.1:8888"},
    }
    spoof_res = simulate_network_fault("https://payment.gateway.com/pay", spoof_policy)
    assert spoof_res["fault_injected"] is True
    assert spoof_res["action"] == "redirect"
    assert "127.0.0.1:8888" in spoof_res["hijacked_url"]

    # 3. Connection Reset
    reset_policy = {
        "url_pattern": ".*",
        "fault_type": "connection_reset",
        "probability": 1.0,
    }
    reset_res = simulate_network_fault("https://api.test/data", reset_policy)
    assert reset_res["fault_injected"] is True
    assert "ConnectionResetError" in reset_res["error"]

    # 4. HTTP 502 Bad Gateway
    http_policy = {
        "url_pattern": ".*",
        "fault_type": "http_error",
        "probability": 1.0,
        "params": {"status_code": 502},
    }
    http_res = simulate_network_fault("https://api.test/orders", http_policy)
    assert http_res["fault_injected"] is True
    assert http_res["action"] == "mock_response"
    assert http_res["status_code"] == 502


def test_simulate_network_fault_unmatched_passes():
    policy = {
        "url_pattern": r"https://sensitive\.com/.*",
        "fault_type": "connection_reset",
        "probability": 1.0,
    }
    res = simulate_network_fault("https://public.com/about", policy)
    assert res["fault_injected"] is False
    assert res["action"] == "pass"


def test_archive_network_fault_incident():
    fault = {
        "fault_injected": True,
        "fault_type": "connection_timeout",
        "target_url": "https://service.local/api",
        "error": "TimeoutError: connection timed out",
    }
    incident = archive_network_fault_incident(fault, step_name="支付网关调用", run_id=101)
    assert incident["incident_type"] == "network_fault_injection"
    assert incident["run_id"] == 101
    assert incident["step_name"] == "支付网关调用"
    assert incident["fault_type"] == "connection_timeout"
