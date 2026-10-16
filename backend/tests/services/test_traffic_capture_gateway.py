"""Unit tests for Traffic Capture Gateway Service (T1.1)."""

from __future__ import annotations

import pytest

from app.services.traffic_capture_gateway import (
    CaptureFilterConfig,
    TrafficProtocol,
    capture_traffic_payload,
    clear_captured_traffic,
    configure_capture_filter,
    get_capture_metrics,
    get_captured_traffic_by_id,
    list_captured_traffic,
)


@pytest.fixture(autouse=True)
def clean_traffic_store():
    """每个测试前后重置捕获数据与过滤配置。"""
    clear_captured_traffic()
    configure_capture_filter(
        CaptureFilterConfig(
            include_paths=[r"^/.*"],
            exclude_paths=[r"^/health.*", r"^/metrics.*"],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
            sampling_rate=1.0,
            capture_request_body=True,
            capture_response_body=True,
            max_body_bytes=1048576,
        )
    )
    yield
    clear_captured_traffic()


def test_capture_http_traffic_success():
    """验证正常 HTTP 流量的拦截与字段标准化捕获。"""
    item = capture_traffic_payload(
        protocol="HTTP",
        method="POST",
        path_or_endpoint="/api/v1/orders/checkout",
        headers={"Content-Type": "application/json", "Authorization": "Bearer token123"},
        query_params={"source": "h5", "env": "prod"},
        request_body='{"order_id": 999, "amount": 199.0}',
        response_status_code=200,
        response_body='{"code": 0, "status": "PAID"}',
        duration_ms=45.2,
        client_ip="192.168.1.100",
        tags={"tenant": "mall"},
    )

    assert item is not None
    assert item.protocol == TrafficProtocol.HTTP
    assert item.method == "POST"
    assert item.path_or_endpoint == "/api/v1/orders/checkout"
    assert item.headers["Authorization"] == "Bearer token123"
    assert item.query_params["source"] == "h5"
    assert item.response_status_code == 200
    assert item.duration_ms == 45.2
    assert item.client_ip == "192.168.1.100"

    # 验证可通过 ID 查回
    fetched = get_captured_traffic_by_id(item.traffic_id)
    assert fetched is not None
    assert fetched.traffic_id == item.traffic_id


def test_capture_grpc_traffic_success():
    """验证 gRPC 流量的标准化截获。"""
    item = capture_traffic_payload(
        protocol="GRPC",
        method="POST /order.OrderService/CreateOrder",
        path_or_endpoint="/order.OrderService/CreateOrder",
        headers={"grpc-timeout": "3000m", "content-type": "application/grpc"},
        request_body="\\x00\\x00\\x00\\x00\\x10binary_payload",
        response_status_code=0,  # gRPC OK
        response_body="\\x00\\x00\\x00\\x00\\x08binary_resp",
        duration_ms=18.4,
    )

    assert item is not None
    assert item.protocol == TrafficProtocol.GRPC
    assert item.method == "POST /ORDER.ORDERSERVICE/CREATEORDER"
    assert item.response_status_code == 0


def test_filter_exclude_paths_and_disallowed_methods():
    """验证健康检查排除路径与非放行 HTTP 方法被安全过滤。"""
    # 1. 命中 exclude_paths (/health)
    health_item = capture_traffic_payload(
        protocol="HTTP",
        method="GET",
        path_or_endpoint="/healthz",
        response_status_code=200,
    )
    assert health_item is None

    # 2. 命中 metrics
    metrics_item = capture_traffic_payload(
        protocol="HTTP",
        method="GET",
        path_or_endpoint="/metrics",
        response_status_code=200,
    )
    assert metrics_item is None

    # 3. 未被允许的 OPTIONS 方法
    options_item = capture_traffic_payload(
        protocol="HTTP",
        method="OPTIONS",
        path_or_endpoint="/api/v1/users",
    )
    assert options_item is None


def test_sampling_rate_and_body_truncation():
    """验证采样率截流与请求/响应体超长截断保护。"""
    # 配置采样率 0.0 -> 全数丢弃
    configure_capture_filter({"sampling_rate": 0.0, "max_body_bytes": 10})
    sampled_out = capture_traffic_payload(
        protocol="HTTP",
        method="GET",
        path_or_endpoint="/api/v1/test",
    )
    assert sampled_out is None

    # 配置采样率 1.0, max_body_bytes = 10 -> 截断为 10 字符
    configure_capture_filter({"sampling_rate": 1.0, "max_body_bytes": 10})
    truncated = capture_traffic_payload(
        protocol="HTTP",
        method="POST",
        path_or_endpoint="/api/v1/upload",
        request_body="1234567890EXTRA_BYTES",
        response_body="abcdefghijEXTRA_RESP",
    )
    assert truncated is not None
    assert truncated.request_body == "1234567890"
    assert truncated.response_body == "abcdefghij"


def test_list_and_metrics():
    """验证多维流量检索条件过滤与运行指标统计。"""
    capture_traffic_payload(protocol="HTTP", method="GET", path_or_endpoint="/api/v1/users", response_status_code=200)
    capture_traffic_payload(protocol="HTTP", method="POST", path_or_endpoint="/api/v1/users", response_status_code=201)
    capture_traffic_payload(protocol="HTTP", method="GET", path_or_endpoint="/api/v1/orders", response_status_code=500)
    capture_traffic_payload(
        protocol="GRPC", method="POST", path_or_endpoint="/user.UserService/Get", response_status_code=0
    )

    # 全部记录
    all_recs = list_captured_traffic()
    assert len(all_recs) == 4

    # 仅 gRPC
    grpc_recs = list_captured_traffic(protocol="GRPC")
    assert len(grpc_recs) == 1
    assert grpc_recs[0].protocol == TrafficProtocol.GRPC

    # 状态码过滤 (>=400)
    err_recs = list_captured_traffic(min_status=400)
    assert len(err_recs) == 1
    assert err_recs[0].response_status_code == 500

    # 路径匹配
    user_recs = list_captured_traffic(path_pattern=r"users")
    assert len(user_recs) == 2

    # 指标检查
    metrics = get_capture_metrics()
    assert metrics["active_records_count"] == 4
    assert metrics["protocol_breakdown"]["HTTP"] == 3
    assert metrics["protocol_breakdown"]["GRPC"] == 1
    assert metrics["metrics"]["total_captured"] == 4
