"""Unit tests for T1.1 Microservice Reverse Proxy Traffic Recording and Noise Sanitization Gateway.

Tests:
1. is_noise_request detects static assets (.js, .css, .png) and system heartbeats (/healthz, /ping)
2. sanitize_headers redacts sensitive credentials (Authorization, Cookie, X-Api-Key)
3. start_recording_session validates target base URL
4. TrafficRecordingSession records, sanitizes headers, and separates noise from clean entries
5. stop_recording_session stops active session and outputs clean summary
"""

from __future__ import annotations

import pytest

from app.services.traffic_recorder_gateway import (
    is_noise_request,
    sanitize_headers,
    start_recording_session,
    stop_recording_session,
)


def test_is_noise_request():
    # 1. Static asset paths
    is_noise, reason = is_noise_request("/static/bundle.js")
    assert is_noise is True
    assert "static_asset" in str(reason)

    is_noise, _ = is_noise_request("/assets/logo.png?v=123")
    assert is_noise is True

    # 2. Heartbeat paths
    is_noise, reason = is_noise_request("/healthz")
    assert is_noise is True
    assert reason == "system_heartbeat"

    is_noise, _ = is_noise_request("/ping")
    assert is_noise is True

    # 3. Clean business APIs
    is_noise, reason = is_noise_request("/api/v1/orders/create", "POST")
    assert is_noise is False
    assert reason is None

    is_noise, _ = is_noise_request("/api/v1/users/profile", "GET")
    assert is_noise is False


def test_sanitize_headers():
    raw_headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token123",
        "Cookie": "session_id=abc12345678",
        "X-Api-Key": "secret_api_key_value",
        "User-Agent": "ATP-Gateway-Proxy/1.0",
    }

    clean = sanitize_headers(raw_headers)
    assert clean["Content-Type"] == "application/json"
    assert clean["User-Agent"] == "ATP-Gateway-Proxy/1.0"
    assert clean["Authorization"] == "***REDACTED***"
    assert clean["Cookie"] == "***REDACTED***"
    assert clean["X-Api-Key"] == "***REDACTED***"


def test_start_recording_session_validation():
    # Invalid URL scheme
    with pytest.raises(ValueError, match="目标基础 URL 无效"):
        start_recording_session(project_id=1, target_base_url="invalid_url_without_scheme")

    # Valid session
    session = start_recording_session(
        project_id=10,
        target_base_url="https://api.gateway.corp.internal:8080/",
        session_id="rec_test_1001",
    )
    assert session.session_id == "rec_test_1001"
    assert session.project_id == 10
    assert session.target_base_url == "https://api.gateway.corp.internal:8080"
    assert session.status == "active"


def test_traffic_recording_session_record_and_filter():
    session = start_recording_session(
        project_id=1,
        target_base_url="https://api.example.com",
        session_id="rec_test_filter",
    )

    # 1. Record noise request (/healthz)
    e1 = session.record_entry(
        method="GET",
        path="/healthz",
        headers={"User-Agent": "Kube-Probe/1.28"},
        query_params={},
        request_body=None,
        status_code=200,
        response_headers={"Content-Type": "text/plain"},
        response_body="ok",
        duration_ms=5.2,
    )
    assert e1.is_noise is True
    assert e1.noise_reason == "system_heartbeat"

    # 2. Record noise static request (/app.css)
    e2 = session.record_entry(
        method="GET",
        path="/static/app.css",
        headers={"User-Agent": "Mozilla/5.0"},
        query_params={},
        request_body=None,
        status_code=200,
        response_headers={},
        response_body="body{}",
        duration_ms=12.0,
    )
    assert e2.is_noise is True

    # 3. Record business API request (/api/v1/login)
    e3 = session.record_entry(
        method="POST",
        path="/api/v1/auth/login",
        headers={"Authorization": "Bearer secret_user_token", "Content-Type": "application/json"},
        query_params={},
        request_body={"username": "admin", "password": "password123"},
        status_code=200,
        response_headers={"Set-Cookie": "session=abc"},
        response_body={"token": "access_token_xyz", "user_id": 42},
        duration_ms=145.0,
    )
    assert e3.is_noise is False
    assert e3.headers["Authorization"] == "***REDACTED***"
    assert e3.response_headers["Set-Cookie"] == "***REDACTED***"

    # 4. Check summary and clean entries
    clean_entries = session.get_clean_entries()
    assert len(clean_entries) == 1
    assert clean_entries[0]["path"] == "/api/v1/auth/login"

    summary = session.get_summary()
    assert summary["total_entries_count"] == 3
    assert summary["clean_entries_count"] == 1
    assert summary["noise_filtered_count"] == 2
    assert summary["noise_filtering_ratio_pct"] == 66.7

    # 5. Stop session
    stopped = stop_recording_session("rec_test_filter")
    assert stopped is not None
    assert stopped["status"] == "stopped"
