"""网络损伤与故障注入算子库单测 (T1.1)"""

from __future__ import annotations

from app.services.chaos_fault_injector_library import (
    ChaosFaultAction,
    ChaosFaultConfig,
    ChaosFaultType,
    apply_chaos_fault_injection,
    get_global_fault_library,
)


def test_seed_fault_library_rules():
    lib = get_global_fault_library()
    rules = lib.list_rules()
    assert len(rules) >= 3

    pay_fault = lib.get_rule("fault_pay_latency_500ms")
    assert pay_fault is not None
    assert pay_fault.fault_type == ChaosFaultType.NETWORK_LATENCY
    assert pay_fault.latency_ms == 500.0


def test_apply_network_latency_injection():
    config = ChaosFaultConfig(
        fault_id="f_lat",
        name="延迟测试",
        fault_type=ChaosFaultType.NETWORK_LATENCY,
        target_pattern="*/orders/*",
        latency_ms=300.0,
        jitter_ms=50.0,
        effective_probability=1.0,
    )

    res = apply_chaos_fault_injection(
        path="/api/v1/orders/checkout",
        original_status_code=200,
        original_body={"msg": "ok"},
        active_fault=config,
        random_seed=0.5,
    )

    assert res.is_fault_injected is True
    assert res.action == ChaosFaultAction.INJECTED_LATENCY
    assert res.added_latency_ms == 300.0
    assert res.effective_status_code == 200
    assert res.is_dropped is False


def test_apply_packet_loss_injection():
    config = ChaosFaultConfig(
        fault_id="f_loss",
        name="丢包测试",
        fault_type=ChaosFaultType.PACKET_LOSS,
        target_pattern="*/sms/*",
        loss_percentage=30.0,
        effective_probability=1.0,
    )

    # 1. 命中丢包 (seed = 0.1 < 0.3)
    res_drop = apply_chaos_fault_injection(
        path="/api/v1/sms/send",
        original_status_code=200,
        active_fault=config,
        random_seed=0.1,
    )
    assert res_drop.is_fault_injected is True
    assert res_drop.action == ChaosFaultAction.DROPPED
    assert res_drop.is_dropped is True
    assert res_drop.effective_status_code == 0

    # 2. 未命中丢包 (seed = 0.8 > 0.3)
    res_pass = apply_chaos_fault_injection(
        path="/api/v1/sms/send",
        original_status_code=200,
        active_fault=config,
        random_seed=0.8,
    )
    assert res_pass.is_fault_injected is False
    assert res_pass.is_dropped is False
    assert res_pass.effective_status_code == 200


def test_apply_http_status_mutation():
    config = ChaosFaultConfig(
        fault_id="f_status",
        name="502网关故障",
        fault_type=ChaosFaultType.HTTP_STATUS_MUTATION,
        target_pattern="*/payment/*",
        mutated_status_code=502,
        effective_probability=1.0,
    )

    res = apply_chaos_fault_injection(
        path="/api/v1/payment/callback",
        original_status_code=200,
        original_body={"status": "PAID"},
        active_fault=config,
    )

    assert res.is_fault_injected is True
    assert res.action == ChaosFaultAction.INJECTED_STATUS
    assert res.effective_status_code == 502
    assert "由混沌实验注入 HTTP 502" in str(res.effective_response_body)


def test_timeout_and_corruption():
    # 超时熔断
    cfg_timeout = ChaosFaultConfig(
        fault_id="f_to",
        name="超时熔断",
        fault_type=ChaosFaultType.TIMEOUT_ABORT,
        target_pattern="*/billing/*",
    )
    res_to = apply_chaos_fault_injection("/api/v1/billing/charge", active_fault=cfg_timeout)
    assert res_to.action == ChaosFaultAction.TIMED_OUT
    assert res_to.effective_status_code == 504

    # 报文损坏
    cfg_corr = ChaosFaultConfig(
        fault_id="f_cor",
        name="乱码报文",
        fault_type=ChaosFaultType.PAYLOAD_CORRUPTION,
        target_pattern="*/billing/*",
        corrupted_payload="INVALID_JSON_RAW_DATA",
    )
    res_corr = apply_chaos_fault_injection("/api/v1/billing/charge", active_fault=cfg_corr)
    assert res_corr.action == ChaosFaultAction.CORRUPTED
    assert res_corr.effective_response_body == "INVALID_JSON_RAW_DATA"


def test_target_mismatch_and_serialization():
    config = ChaosFaultConfig(
        fault_id="f_mismatch",
        name="不匹配测试",
        fault_type=ChaosFaultType.NETWORK_LATENCY,
        target_pattern="*/inventory/*",
    )

    # 路径不匹配，安全放行
    res = apply_chaos_fault_injection("/api/v1/users/login", original_status_code=200, active_fault=config)
    assert res.is_fault_injected is False
    assert res.action == ChaosFaultAction.PASSTHROUGH
    assert res.effective_status_code == 200

    d = res.to_dict()
    assert d["action"] == "PASSTHROUGH"
    assert d["is_fault_injected"] is False
