"""Unit tests for D4.2 Notification Hub Dispatcher Service."""

import pytest

from app.services.notification_hub_dispatcher import (
    DeliveryPriority,
    NotificationCardPayload,
    NotificationChannel,
    NotificationRouteTarget,
    broadcast_notification,
    build_dingtalk_action_card,
    build_feishu_interactive_card,
    build_wechat_card_payload,
    calculate_dispatcher_stats,
    dispatch_notification,
    format_channel_card_payload,
    list_delivery_audit_records,
    mask_webhook_url,
    reset_notification_hub_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_notification_hub_registry()
    yield
    reset_notification_hub_registry()


def _get_mock_card(status: str = "passed") -> NotificationCardPayload:
    return NotificationCardPayload(
        title="ATP 核心冒烟测试执行报告",
        summary="全量回归执行完成，所有关键链路用例均已顺利通过！",
        status=status,
        project_name="支付中台",
        run_id="run_9901",
        pass_rate_pct=100.0,
        duration_sec=35.2,
        report_url="https://atp.internal/reports/run_9901",
        metrics={"quality_score": 95.0, "failed_cases": 0},
        actions=[{"text": "审批发版", "url": "https://atp.internal/release/approve"}],
    )


def test_format_channel_cards():
    card = _get_mock_card(status="passed")

    # 1. 企业微信
    wechat_payload = build_wechat_card_payload(card)
    assert wechat_payload["msgtype"] == "template_card"
    assert wechat_payload["template_card"]["card_type"] == "text_notice"
    assert "【通过】" in wechat_payload["template_card"]["main_title"]["title"]
    assert wechat_payload["template_card"]["emphasis_content"]["title"] == "100.0%"

    # 2. 钉钉
    dingtalk_payload = build_dingtalk_action_card(card)
    assert dingtalk_payload["msgtype"] == "actionCard"
    assert "### ATP 核心冒烟测试执行报告" in dingtalk_payload["actionCard"]["text"]
    assert len(dingtalk_payload["actionCard"]["btns"]) >= 2

    # 3. 飞书
    feishu_payload = build_feishu_interactive_card(card)
    assert feishu_payload["msg_type"] == "interactive"
    assert feishu_payload["card"]["header"]["template"] == "green"
    assert feishu_payload["card"]["header"]["title"]["content"] == card.title

    # 4. 统一适配器格式化
    poly_wechat = format_channel_card_payload(NotificationChannel.WECHAT, card)
    assert poly_wechat["msgtype"] == "template_card"


def test_mask_webhook_url():
    raw_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=d41d8cd98f00b204e9800998ecf8427e"
    masked = mask_webhook_url(raw_url)
    assert "key=******" in masked
    assert "d41d8cd9" not in masked

    dt_url = "https://oapi.dingtalk.com/robot/send?access_token=aabb11223344"
    masked_dt = mask_webhook_url(dt_url)
    assert "access_token=******" in masked_dt


def test_dispatch_notification_and_audit():
    target = NotificationRouteTarget(
        channel=NotificationChannel.WECHAT,
        webhook_url="https://qyapi.weixin.qq.com/webhook?key=secret_123",
    )
    card = _get_mock_card(status="failed")

    record = dispatch_notification(target, card, priority=DeliveryPriority.P1_HIGH)
    assert record.delivery_id.startswith("deliv_")
    assert record.channel == NotificationChannel.WECHAT
    assert record.success is True
    assert record.priority == DeliveryPriority.P1_HIGH
    assert "key=******" in record.target_webhook_masked

    # 校验审计记录
    audits = list_delivery_audit_records()
    assert len(audits) == 1
    assert audits[0].delivery_id == record.delivery_id


def test_broadcast_notification_and_stats():
    targets = [
        NotificationRouteTarget(
            channel=NotificationChannel.WECHAT,
            webhook_url="https://qyapi.weixin.qq.com/webhook?key=wechat_key",
        ),
        NotificationRouteTarget(
            channel=NotificationChannel.DINGTALK,
            webhook_url="https://oapi.dingtalk.com/webhook?access_token=dt_token",
        ),
        NotificationRouteTarget(
            channel=NotificationChannel.FEISHU,
            webhook_url="https://open.feishu.cn/webhook/v2/feishu_token",
        ),
    ]

    card = _get_mock_card(status="passed")
    results = broadcast_notification(targets, card, priority=DeliveryPriority.P0_EMERGENCY)

    assert len(results) == 3
    assert all(r.success for r in results)

    # 统计度量
    stats = calculate_dispatcher_stats()
    assert stats["total_dispatched_count"] == 3
    assert stats["overall_success_rate_pct"] == 100.0
    assert stats["channel_distribution"]["wechat"] == 1
    assert stats["channel_distribution"]["dingtalk"] == 1
    assert stats["channel_distribution"]["feishu"] == 1
