"""消息队列影子队列与死信重试分流隔离分流器单元测试 (T1.3)。"""

from __future__ import annotations

import pytest
from app.services.shadow_mq_queue_router import (
    MqBypassAction,
    clear_mq_shunting_store,
    get_mq_shunting_report,
    list_mq_route_rules,
    list_mq_shunting_reports,
    register_mq_route_rule,
    route_mq_messages,
)


@pytest.fixture(autouse=True)
def _reset_mq_store_state():
    clear_mq_shunting_store()
    yield
    clear_mq_shunting_store()


def test_route_mq_messages_redirection_and_drop():
    """测试将支付/短信影子消息分流至影子 Topic，并对短信执行静默丢弃。"""
    messages = [
        # 1. 影子订单支付事件 -> 重定向到 __shadow_order_paid_events__
        {
            "message_id": "msg_order_01",
            "topic": "order_paid_events",
            "headers": {"__atp_shadow_taint__": "true"},
            "is_shadow_traffic": True,
        },
        # 2. 影子短信发送事件 -> 重定向并标记 DROP_SILENTLY，绝不调用真实外部短信网关
        {
            "message_id": "msg_sms_02",
            "topic": "user_sms_notification",
            "headers": {"__atp_shadow_taint__": "true"},
            "is_shadow_traffic": True,
        },
        # 3. 正常业务消息 -> 直投生产真实队列
        {
            "message_id": "msg_real_03",
            "topic": "order_paid_events",
            "headers": {},
            "is_shadow_traffic": False,
        },
    ]

    report = route_mq_messages(cluster_name="prod_kafka_01", messages=messages)

    assert report.total_messages_processed == 3
    assert report.shadow_messages_count == 2
    assert report.redirected_to_shadow_count == 2
    assert report.bypassed_mock_count == 1  # 短信被 DROP
    assert report.unmapped_leak_count == 0
    assert report.shunting_safety_score_pct == 100.0

    dec_order = next(d for d in report.decisions if d.message_id == "msg_order_01")
    assert dec_order.is_redirected is True
    assert dec_order.routed_topic == "__shadow_order_paid_events__"

    dec_sms = next(d for d in report.decisions if d.message_id == "msg_sms_02")
    assert dec_sms.bypassed_action == MqBypassAction.DROP_SILENTLY


def test_route_mq_messages_unmapped_leak_detected():
    """测试未配置影子 Topic 的影子消息触发高危未映射泄漏告警。"""
    messages = [
        {
            "message_id": "msg_leak_99",
            "topic": "unmapped_external_payment_topic",
            "headers": {"__atp_shadow_taint__": "true"},
            "is_shadow_traffic": True,
        }
    ]

    report = route_mq_messages(cluster_name="prod_kafka_02", messages=messages)
    assert report.unmapped_leak_count == 1
    assert report.shunting_safety_score_pct == 0.0

    dec = report.decisions[0]
    assert dec.is_redirected is False
    assert "高危泄漏" in dec.explanation


def test_register_and_list_mq_rules():
    """测试动态注册新 MQ 影子分流规则与持久化。"""
    rule = register_mq_route_rule(
        production_topic="t_invoice_generate",
        shadow_topic="__shadow_invoice_generate__",
        dead_letter_queue="__shadow_invoice_dlq__",
        bypass_action=MqBypassAction.MOCK_DISPATCH,
    )
    assert rule.production_topic == "t_invoice_generate"

    rules = list_mq_route_rules()
    assert any(r["production_topic"] == "t_invoice_generate" for r in rules)

    rep = route_mq_messages("test_c", [{"topic": "order_paid_events", "is_shadow_traffic": False}])
    saved = get_mq_shunting_report(rep.report_id)
    assert saved is not None
    assert saved.report_id == rep.report_id
    assert len(list_mq_shunting_reports()) == 1
