"""跨协议影子流量染色标动态注入与透明透传校验单元测试 (T1.1)。"""

from __future__ import annotations

import pytest
from app.services.shadow_traffic_taint_propagator import (
    PropagationVerdict,
    ProtocolType,
    clear_shadow_taint_store,
    get_shadow_taint_report,
    inject_shadow_taint,
    list_shadow_taint_reports,
    verify_trace_propagation,
)


@pytest.fixture(autouse=True)
def _reset_shadow_taint_state():
    clear_shadow_taint_store()
    yield
    clear_shadow_taint_store()


def test_inject_shadow_taint_protocols():
    """测试对 HTTP、gRPC、MQ 注入符合标准的染色头。"""
    # 1. HTTP
    http_headers = inject_shadow_taint(ProtocolType.HTTP_REST, {"User-Agent": "ATP-Stress"}, trace_id="trace_http_001")
    assert http_headers["X-ATP-Shadow"] == "true"
    assert http_headers["X-ATP-Shadow-Trace"] == "trace_http_001"
    assert http_headers["X-ATP-Shadow-Cluster"] == "prod_stress_01"

    # 2. gRPC
    grpc_metadata = inject_shadow_taint(ProtocolType.GRPC, trace_id="trace_grpc_002")
    assert grpc_metadata["x-atp-shadow"] == "true"
    assert grpc_metadata["x-atp-shadow-trace"] == "trace_grpc_002"

    # 3. Kafka / RabbitMQ
    mq_headers = inject_shadow_taint(ProtocolType.KAFKA_MQ, trace_id="trace_mq_003")
    assert mq_headers["__atp_shadow_taint__"] == "true"
    assert mq_headers["__atp_shadow_trace__"] == "trace_mq_003"


def test_verify_trace_propagation_full_success():
    """测试网关 -> 微服务 -> MQ -> 存储 4 跳链路 100% 成功透传。"""
    tid = "st_trace_full_001"
    hops = [
        {
            "service_name": "api_gateway",
            "protocol": "HTTP_REST",
            "headers": {"X-ATP-Shadow": "true", "X-ATP-Shadow-Trace": tid},
        },
        {
            "service_name": "order_service",
            "protocol": "HTTP_REST",
            "headers": {"X-ATP-Shadow": "true", "X-ATP-Shadow-Trace": tid},
        },
        {
            "service_name": "payment_service",
            "protocol": "GRPC",
            "headers": {"x-atp-shadow": "true", "x-atp-shadow-trace": tid},
        },
        {
            "service_name": "event_broker",
            "protocol": "KAFKA_MQ",
            "headers": {"__atp_shadow_taint__": "true", "__atp_shadow_trace__": tid},
        },
    ]

    report = verify_trace_propagation(trace_id=tid, hop_traces=hops)
    assert report.total_hops_count == 4
    assert report.lost_hops_count == 0
    assert report.verdict == PropagationVerdict.FULL_PROPAGATION_SUCCESS
    assert report.integrity_score_pct == 100.0
    assert report.has_leakage_risk is False

    saved = get_shadow_taint_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_shadow_taint_reports()) == 1


def test_verify_trace_propagation_leakage_detected():
    """测试中间节点丢标引发 TAINT_LEAKAGE_DETECTED 警报与阻断。"""
    tid = "st_trace_leak_002"
    hops = [
        {
            "service_name": "api_gateway",
            "protocol": "HTTP_REST",
            "headers": {"X-ATP-Shadow": "true", "X-ATP-Shadow-Trace": tid},
        },
        # 丢标节点
        {"service_name": "async_task_worker", "protocol": "HTTP_REST", "headers": {}},
    ]

    report = verify_trace_propagation(trace_id=tid, hop_traces=hops)
    assert report.total_hops_count == 2
    assert report.lost_hops_count == 1
    assert report.verdict == PropagationVerdict.TAINT_LEAKAGE_DETECTED
    assert report.integrity_score_pct == 50.0
    assert report.has_leakage_risk is True
    assert any("async_task_worker" in adv for adv in report.remediation_advice)
