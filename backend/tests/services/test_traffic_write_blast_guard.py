"""第三方服务防击穿与写操作拦截看门狗单测 (T4.1)"""

from __future__ import annotations

import pytest

from app.services.traffic_write_blast_guard import (
    BlastProtectionMode,
    BlastProtectionRule,
    BlastRiskCategory,
    TrafficWriteBlastGuard,
    evaluate_and_guard_traffic_write,
    get_global_blast_guard,
)


@pytest.fixture(autouse=True)
def clean_guard():
    get_global_blast_guard().clear_metrics()
    yield
    get_global_blast_guard().clear_metrics()


def test_wechat_payment_mock_bypass():
    url = "https://api.mch.weixin.qq.com/v3/pay/transactions/native"
    allowed, action, mock_resp, reason = evaluate_and_guard_traffic_write("POST", url)

    assert allowed is False
    assert action == BlastProtectionMode.MOCK_BYPASS
    assert mock_resp is not None
    assert mock_resp.get("return_code") == "SUCCESS"
    assert "安全旁路拦截" in reason

    metrics = get_global_blast_guard().metrics
    assert metrics.mocked_count == 1


def test_alipay_and_sms_mock_bypass():
    guard = TrafficWriteBlastGuard()

    # 支付宝
    ok_ali, act_ali, mock_ali, _ = guard.evaluate_traffic_target("POST", "https://openapi.alipay.com/gateway.do")
    assert ok_ali is False
    assert act_ali == BlastProtectionMode.MOCK_BYPASS
    assert mock_ali is not None and "alipay_trade_pay_response" in mock_ali
    # 阿里云短信
    ok_sms, act_sms, mock_sms, _ = guard.evaluate_traffic_target(
        "POST", "https://dysmsapi.aliyuncs.com/?Action=SendSms"
    )
    assert ok_sms is False
    assert act_sms == BlastProtectionMode.MOCK_BYPASS
    assert mock_sms is not None and mock_sms.get("Code") == "OK"


def test_custom_rule_block_mode():
    guard = TrafficWriteBlastGuard()
    rule = BlastProtectionRule(
        rule_id="brule_custom_erp",
        name="阻断外部ERP写入",
        category=BlastRiskCategory.EXTERNAL_WRITE_API,
        url_pattern="*external-erp.enterprise.com*",
        mode=BlastProtectionMode.BLOCK,
        enabled=True,
    )
    guard.add_rule(rule)

    ok, act, mock_resp, reason = guard.evaluate_traffic_target(
        "POST", "https://external-erp.enterprise.com/api/order/create"
    )
    assert ok is False
    assert act == BlastProtectionMode.BLOCK
    assert mock_resp is None
    assert "命中防击穿强阻断规则" in reason
    assert guard.metrics.blocked_count == 1


def test_strict_readonly_mode():
    guard = TrafficWriteBlastGuard()

    # POST 请求在只读模式下阻断
    ok_post, act_post, _, reason_post = guard.evaluate_traffic_target(
        "POST", "http://127.0.0.1:8000/api/v1/orders", read_only_strictly=True
    )
    assert ok_post is False
    assert act_post == BlastProtectionMode.BLOCK
    assert "严格只读安全模式下阻断写操作" in reason_post

    # GET 请求在只读模式下放行
    ok_get, act_get, _, _ = guard.evaluate_traffic_target(
        "GET", "http://127.0.0.1:8000/api/v1/orders", read_only_strictly=True
    )
    assert ok_get is True
    assert act_get == BlastProtectionMode.PASSED


def test_internal_safe_traffic_passed():
    guard = TrafficWriteBlastGuard()
    ok, act, mock_resp, reason = guard.evaluate_traffic_target("GET", "http://test-env.internal:8080/api/v1/items")
    assert ok is True
    assert act == BlastProtectionMode.PASSED
    assert mock_resp is None
    assert "安全放行" in reason
    assert guard.metrics.passed_count == 1
