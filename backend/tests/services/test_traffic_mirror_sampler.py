"""分布式流量镜像采集与流量抽样过滤器单测 (T1.2)"""

from __future__ import annotations

import pytest

from app.services.traffic_mirror_sampler import (
    TrafficMirrorBuffer,
    TrafficMirrorFilterCriteria,
    evaluate_and_sample_traffic,
    get_global_mirror_buffer,
    is_health_probe,
    is_sample_selected,
)


@pytest.fixture(autouse=True)
def clean_global_buffer():
    get_global_mirror_buffer().clear()
    yield
    get_global_mirror_buffer().clear()


def test_is_health_probe():
    assert is_health_probe("/health") is True
    assert is_health_probe("/healthz") is True
    assert is_health_probe("/ready") is True
    assert is_health_probe("/metrics") is True
    assert is_health_probe("/actuator/health") is True
    assert is_health_probe("/favicon.ico") is True

    assert is_health_probe("/api/v1/orders") is False
    assert is_health_probe("/users/login") is False


def test_is_sample_selected_deterministic():
    assert is_sample_selected("trace_123", 1.0) is True
    assert is_sample_selected("trace_123", 0.0) is False

    # 相同 trace_id 确定性抽样结果保持一致
    res1 = is_sample_selected("trace_fixed_abc", 0.5)
    res2 = is_sample_selected("trace_fixed_abc", 0.5)
    assert res1 == res2


def test_probe_filtered_out():
    buf = TrafficMirrorBuffer()
    raw = {
        "method": "GET",
        "path": "/healthz",
        "status_code": 200,
    }
    should_record, reason, item = evaluate_and_sample_traffic(raw, buffer=buf)
    assert should_record is False
    assert "剔除健康检查探针" in reason
    assert item is None
    assert buf.metrics.probes_filtered == 1


def test_filter_criteria_mismatches():
    buf = TrafficMirrorBuffer()
    criteria = TrafficMirrorFilterCriteria(
        methods=["POST"],
        url_patterns=["/api/v1/*"],
        status_codes=[200],
        sample_rate=1.0,
    )

    # 1. 方法不匹配 (GET)
    raw_get = {"method": "GET", "path": "/api/v1/users", "status_code": 200}
    ok, reason, _ = evaluate_and_sample_traffic(raw_get, criteria=criteria, buffer=buf)
    assert ok is False
    assert "HTTP 方法 'GET' 未在允许列表" in reason

    # 2. 状态码不匹配 (500)
    raw_500 = {"method": "POST", "path": "/api/v1/users", "status_code": 500}
    ok, reason, _ = evaluate_and_sample_traffic(raw_500, criteria=criteria, buffer=buf)
    assert ok is False
    assert "状态码 500 未在允许列表" in reason

    # 3. URL 模式不匹配 (/internal/admin)
    raw_path = {"method": "POST", "path": "/internal/admin", "status_code": 200}
    ok, reason, _ = evaluate_and_sample_traffic(raw_path, criteria=criteria, buffer=buf)
    assert ok is False
    assert "未匹配任何规则" in reason


def test_successful_sample_and_auto_sanitization():
    buf = TrafficMirrorBuffer()
    criteria = TrafficMirrorFilterCriteria(
        sample_rate=1.0,  # 100% 采样
        auto_sanitize=True,
    )

    raw_traffic = {
        "trace_id": "tr_prod_order_999",
        "method": "POST",
        "url": "/api/v1/orders?mobile=13812345678",
        "path": "/api/v1/orders",
        "status_code": 200,
        "headers": {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature",
        },
        "query_params": {
            "mobile": "13812345678",
        },
        "request_body": {
            "order_id": "OD_888999",
            "user_phone": "13911112222",
            "password": "ClearTextPassword!",
        },
        "response_body": {
            "code": 200,
            "data": {
                "id_card": "110101199001011234",
            },
        },
    }

    ok, reason, item = evaluate_and_sample_traffic(raw_traffic, criteria=criteria, buffer=buf)
    assert ok is True
    assert "成功镜像入库" in reason
    assert item is not None
    assert item.trace_id == "tr_prod_order_999"
    assert item.is_sanitized is True

    # 验证 T1.1 脱敏无缝生效
    assert item.headers["Authorization"] == "Bearer [MASKED_TOKEN]"
    assert item.query_params["mobile"] == "138****5678"
    assert item.request_body["user_phone"] == "139****2222"
    assert item.request_body["password"] == "[MASKED_PASSWORD]"
    assert item.response_body["data"]["id_card"] == "110101********1234"

    # 查验缓冲区列表
    listed = buf.list_items(method="POST")
    assert len(listed) == 1
    assert listed[0].record_id == item.record_id
    assert buf.metrics.recorded_count == 1
    assert buf.metrics.sanitized_count == 1
