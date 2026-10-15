"""Unit tests for P4.1 Enterprise WeChat, DingTalk, and Feishu rich card notification templates.

Tests:
1. build_wechat_template_card generates template_card with status badge, pass rate, and report URL
2. build_dingtalk_action_card generates actionCard with colored Markdown and direct report action
3. build_feishu_interactive_card generates interactive message card with color header templates
4. Feishu signature generation and payload signing
5. Dispatch via send_notification_channel across all three rich card channels
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.models.notification import NotifyChannel
from app.services.notifier import send_notification_channel
from app.services.rich_notification_cards import (
    build_dingtalk_action_card,
    build_feishu_interactive_card,
    build_wechat_template_card,
    compute_feishu_signature,
    sign_feishu_payload,
)


def test_build_wechat_template_card():
    summary = {
        "title": "支付链路冒烟测试计划",
        "status": "passed",
        "total": 10,
        "passed": 10,
        "failed": 0,
        "error": 0,
        "duration_ms": 15400,
        "rps": 350.5,
        "p95_ms": 42.0,
        "report_url": "https://atp.local/runs/108",
    }

    card = build_wechat_template_card(summary)
    assert card["msgtype"] == "template_card"
    t_card = card["template_card"]
    assert t_card["card_type"] == "text_notice"
    assert t_card["main_title"]["title"] == "支付链路冒烟测试计划"
    assert "通过" in t_card["main_title"]["desc"]
    assert t_card["emphasis_content"]["title"] == "100.0%"
    assert t_card["card_action"]["url"] == "https://atp.local/runs/108"
    assert t_card["jump_list"][0]["url"] == "https://atp.local/runs/108"

    keys = [item["keyname"] for item in t_card["horizontal_content_list"]]
    assert "执行状态" in keys
    assert "用例总数" in keys
    assert "TPS / RPS" in keys
    assert "P95 响应耗时" in keys


def test_build_dingtalk_action_card():
    summary = {
        "title": "订票系统压力测试",
        "status": "failed",
        "total": 20,
        "passed": 15,
        "failed": 5,
        "error": 0,
        "duration_ms": 60000,
        "rps": 1200,
        "report_url": "https://atp.local/runs/205",
    }

    card = build_dingtalk_action_card(summary)
    assert card["msgtype"] == "actionCard"
    action = card["actionCard"]
    assert action["title"] == "订票系统压力测试"
    assert action["singleTitle"] == "查看测试报告"
    assert action["singleURL"] == "https://atp.local/runs/205"
    assert "#FA5151" in action["text"]
    assert "75.0%" in action["text"]


def test_build_feishu_interactive_card_color_templates():
    # 1. Passed -> green template
    passed_summary = {
        "title": "会员服务回归计划",
        "status": "passed",
        "total": 5,
        "passed": 5,
        "duration_ms": 4200,
        "report_url": "https://atp.local/runs/301",
    }
    green_card = build_feishu_interactive_card(passed_summary)
    assert green_card["msgtype"] == "interactive"
    assert green_card["card"]["header"]["template"] == "green"
    btn = green_card["card"]["elements"][2]["actions"][0]
    assert btn["url"] == "https://atp.local/runs/301"

    # 2. Failed -> red template
    failed_summary = {"status": "failed", "total": 5, "passed": 3, "failed": 2}
    red_card = build_feishu_interactive_card(failed_summary)
    assert red_card["card"]["header"]["template"] == "red"

    # 3. Error -> orange template
    error_summary = {"status": "error", "total": 1, "passed": 0, "error": 1}
    orange_card = build_feishu_interactive_card(error_summary)
    assert orange_card["card"]["header"]["template"] == "orange"


def test_feishu_signature_generation():
    secret = "test-feishu-secret"
    ts = 1700000000
    sig = compute_feishu_signature(secret, ts)
    assert isinstance(sig, str) and len(sig) > 10

    raw_payload = {"msgtype": "interactive", "card": {}}
    signed = sign_feishu_payload(raw_payload, secret)
    assert "timestamp" in signed
    assert "sign" in signed


@pytest.mark.asyncio
async def test_send_notification_channel_feishu_rich_card():
    config = {
        "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/dummy-token",
        "secret": "feishu-secret",
        "report_url": "https://atp.local/runs/500",
    }
    summary = {
        "title": "飞书卡片集成测试",
        "status": "passed",
        "total": 8,
        "passed": 8,
        "duration_ms": 3500,
    }

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {"code": 0, "msg": "success"}

    with patch("httpx.AsyncClient.post", return_value=mock_resp) as mock_post:
        attempts = await send_notification_channel(NotifyChannel.feishu, config, summary)
        assert attempts == 1
        mock_post.assert_called_once()
        sent_body = mock_post.call_args[1]["json"]
        assert sent_body["msgtype"] == "interactive"
        assert sent_body["card"]["header"]["template"] == "green"
        assert "sign" in sent_body


@pytest.mark.asyncio
async def test_send_notification_channel_wechat_template_card():
    config = {
        "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dummy-key",
        "msgtype": "template_card",
        "report_url": "https://atp.local/runs/600",
    }
    summary = {"title": "企微模板卡片测试", "status": "passed", "total": 10, "passed": 10}

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {"errcode": 0, "errmsg": "ok"}

    with patch("httpx.AsyncClient.post", return_value=mock_resp) as mock_post:
        attempts = await send_notification_channel(NotifyChannel.wechat, config, summary)
        assert attempts == 1
        sent_body = mock_post.call_args[1]["json"]
        assert sent_body["msgtype"] == "template_card"
        assert sent_body["template_card"]["card_action"]["url"] == "https://atp.local/runs/600"


@pytest.mark.asyncio
async def test_send_notification_channel_dingtalk_action_card():
    config = {
        "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=dummy-token",
        "msgtype": "actionCard",
        "report_url": "https://atp.local/runs/700",
    }
    summary = {"title": "钉钉 ActionCard 测试", "status": "passed", "total": 4, "passed": 4}

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {"errcode": 0, "errmsg": "ok"}

    with patch("httpx.AsyncClient.post", return_value=mock_resp) as mock_post:
        attempts = await send_notification_channel(NotifyChannel.dingtalk, config, summary)
        assert attempts == 1
        sent_body = mock_post.call_args[1]["json"]
        assert sent_body["msgtype"] == "actionCard"
        assert sent_body["actionCard"]["singleURL"] == "https://atp.local/runs/700"
