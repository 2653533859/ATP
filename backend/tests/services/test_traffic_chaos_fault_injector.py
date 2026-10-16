"""Unit tests for Traffic Chaos Fault Injector Service (T4.1)."""

from __future__ import annotations

import pytest

from app.services.traffic_chaos_fault_injector import (
    FaultType,
    clear_fault_rules_and_sessions,
    create_or_update_fault_rule,
    evaluate_and_inject_fault,
    start_chaos_session,
    stop_chaos_session,
)


@pytest.fixture(autouse=True)
def clean_chaos_state():
    clear_fault_rules_and_sessions()
    yield
    clear_fault_rules_and_sessions()


def test_latency_fault_injection():
    """验证慢调用网络延迟注入。"""
    rule = create_or_update_fault_rule(
        rule_name="订单慢调用",
        fault_type=FaultType.LATENCY,
        endpoint_pattern=r".*/orders/pay.*",
        methods=["POST"],
        latency_ms=500.0,
        latency_jitter_max_ms=100.0,
    )

    # 1. 命中规则
    res = evaluate_and_inject_fault(
        method="POST",
        path_or_endpoint="/api/v1/orders/pay",
        default_status_code=200,
    )
    assert res.fault_triggered is True
    assert res.fault_type == FaultType.LATENCY
    assert res.rule_id == rule.rule_id
    assert 500.0 <= res.injected_latency_ms <= 600.0
    assert res.effective_status_code == 200

    # 2. 未命中方法 (GET 未被配置)
    unmatched_res = evaluate_and_inject_fault(
        method="GET",
        path_or_endpoint="/api/v1/orders/pay",
        default_status_code=200,
    )
    assert unmatched_res.fault_triggered is False
    assert unmatched_res.injected_latency_ms == 0.0


def test_error_response_and_header_matching():
    """验证基于 Header 特征的 503 错误码精准注入。"""
    rule = create_or_update_fault_rule(
        rule_name="金丝雀 503 注入",
        fault_type=FaultType.ERROR_RESPONSE,
        endpoint_pattern=r".*/payment/.*",
        methods=["POST"],
        header_match={"X-Canary": "chaos_test"},
        error_status_code=503,
        error_response_body='{"code": 503, "error": "Overloaded"}',
    )

    # 1. Header 命中
    res = evaluate_and_inject_fault(
        method="POST",
        path_or_endpoint="/payment/charge",
        headers={"X-Canary": "chaos_test"},
        default_status_code=200,
    )
    assert res.fault_triggered is True
    assert res.effective_status_code == 503
    assert "Overloaded" in res.effective_response_body

    # 2. 缺少 Header 不命中
    no_header_res = evaluate_and_inject_fault(
        method="POST",
        path_or_endpoint="/payment/charge",
        headers={},
        default_status_code=200,
    )
    assert no_header_res.fault_triggered is False
    assert no_header_res.effective_status_code == 200


def test_corruption_and_abrupt_drop_faults():
    """验证数据破坏 (截断/乱码) 与模拟网络断开丢包。"""
    # 1. 截断损坏
    create_or_update_fault_rule(
        rule_id="fault_trunc",
        rule_name="响应截断",
        fault_type=FaultType.CORRUPTION,
        endpoint_pattern=r".*/items.*",
        corruption_mode="TRUNCATE",
    )
    res_trunc = evaluate_and_inject_fault(
        method="GET",
        path_or_endpoint="/items/list",
        default_response_body='{"code": 0, "items": [1, 2, 3, 4, 5]}',
    )
    assert res_trunc.fault_triggered is True
    assert len(res_trunc.effective_response_body) < len('{"code": 0, "items": [1, 2, 3, 4, 5]}')

    # 2. 丢包断开
    create_or_update_fault_rule(
        rule_id="fault_drop",
        rule_name="连接重置",
        fault_type=FaultType.ABRUPT_DROP,
        endpoint_pattern=r".*/drop.*",
    )
    res_drop = evaluate_and_inject_fault(
        method="POST",
        path_or_endpoint="/drop/call",
    )
    assert res_drop.fault_triggered is True
    assert res_drop.effective_status_code == 0
    assert res_drop.effective_response_body == ""


def test_max_triggers_limit_protection():
    """验证当注入达到安全上限时，自动熔断停止注入。"""
    rule = create_or_update_fault_rule(
        rule_name="单次试验",
        fault_type=FaultType.ERROR_RESPONSE,
        endpoint_pattern=r".*/limit.*",
        max_triggers_limit=2,
    )

    # 前 2 次触发
    r1 = evaluate_and_inject_fault(method="GET", path_or_endpoint="/limit/test")
    r2 = evaluate_and_inject_fault(method="GET", path_or_endpoint="/limit/test")
    assert r1.fault_triggered is True
    assert r2.fault_triggered is True

    # 第 3 次超限熔断，原样放行
    r3 = evaluate_and_inject_fault(method="GET", path_or_endpoint="/limit/test")
    assert r3.fault_triggered is False


def test_chaos_experiment_session():
    """验证混沌演练批次的启停与指标累加。"""
    r = create_or_update_fault_rule(
        rule_id="rule_sess_1",
        rule_name="演练规则",
        fault_type=FaultType.LATENCY,
        endpoint_pattern=r".*/sess.*",
        latency_ms=100.0,
    )

    session = start_chaos_session(
        name="生产演练第1期",
        description="测试网关超时防护",
        rule_ids=[r.rule_id],
    )
    assert session.is_active is True

    # 触发两次
    evaluate_and_inject_fault(method="GET", path_or_endpoint="/sess/1")
    evaluate_and_inject_fault(method="GET", path_or_endpoint="/sess/2")

    assert session.total_faults_injected == 2
    assert session.fault_breakdown["LATENCY"] == 2

    stopped = stop_chaos_session(session.experiment_id)
    assert stopped is not None
    assert stopped.is_active is False
    assert stopped.stopped_at is not None
