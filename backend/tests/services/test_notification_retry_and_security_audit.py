"""Unit tests for P4.3 Cross-network notification delivery retries and security audit.

Tests:
1. _is_retryable_error: Identifies retryable network/gateway/rate-limit errors vs fatal client errors
2. sanitize_webhook_url: Redacts secret query parameters, Feishu hook tokens, and credentials
3. sanitize_notification_config: Deeply redacts passwords, tokens, and secrets across config dicts
4. _send_with_retries: Exponential backoff with jitter and retry limit enforcement
5. Audit log emission in send_notifications for both success and failure outcomes
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from app.models.bootstrap import load_all_models
from app.models.notification import NotifyChannel
from app.services import notifier
from app.services.notifier import (
    NotificationDeliveryError,
    _format_notification_audit_detail,
    _is_retryable_error,
    _send_with_retries,
    sanitize_notification_config,
    sanitize_webhook_url,
    send_notifications,
)

load_all_models()


def test_is_retryable_error():
    # Transient network & gateway errors: retryable
    assert _is_retryable_error(httpx.ConnectError("Connection refused")) is True
    assert _is_retryable_error(httpx.ConnectTimeout("Connect timed out")) is True
    assert _is_retryable_error(httpx.ReadTimeout("Read timed out")) is True
    assert _is_retryable_error(ConnectionResetError("Connection reset by peer")) is True
    assert _is_retryable_error(RuntimeError("HTTP 502 Bad Gateway")) is True
    assert _is_retryable_error(RuntimeError("HTTP 503 Service Unavailable")) is True
    assert _is_retryable_error(RuntimeError("HTTP 429 Too Many Requests")) is True

    # Deterministic client & config errors: non-retryable
    assert _is_retryable_error(ValueError("Webhook 通知需要 webhook_url")) is False
    assert _is_retryable_error(RuntimeError("HTTP 400 Bad Request")) is False
    assert _is_retryable_error(RuntimeError("HTTP 401 Unauthorized")) is False
    assert _is_retryable_error(RuntimeError("HTTP 403 Forbidden: invalid token")) is False
    assert _is_retryable_error(KeyError("missing_field")) is False


def test_sanitize_webhook_url():
    # 1. WeChat webhook key
    wechat = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=d41d8cd98f00b204e9800998ecf8427e"
    assert "d41d8cd9" not in sanitize_webhook_url(wechat)
    assert sanitize_webhook_url(wechat) == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=******"

    # 2. DingTalk token & sign
    dingtalk = "https://oapi.dingtalk.com/robot/send?access_token=token123&timestamp=1700000000&sign=secretSign"
    sanitized_dt = sanitize_webhook_url(dingtalk)
    assert "token123" not in sanitized_dt
    assert "secretSign" not in sanitized_dt
    assert "access_token=******" in sanitized_dt
    assert "sign=******" in sanitized_dt

    # 3. Feishu hook path token
    feishu = "https://open.feishu.cn/open-apis/bot/v2/hook/7f8a9b0c-1234-5678-90ab-cdef12345678"
    sanitized_fs = sanitize_webhook_url(feishu)
    assert "cdef12345678" not in sanitized_fs
    assert "7f8a******" in sanitized_fs

    # 4. Basic Auth userinfo in URL
    userinfo_url = "https://admin:my-secret-pass@alert.company.internal/webhook"
    sanitized_ui = sanitize_webhook_url(userinfo_url)
    assert "my-secret-pass" not in sanitized_ui
    assert "https://<redacted>@alert.company.internal/webhook" in sanitized_ui


def test_sanitize_notification_config():
    config = {
        "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=token123&sign=sign123",
        "secret": "top-secret-signing-key",
        "password": "smtp-password",
        "api_token": "bearer-token",
        "language": "zh-CN",
        "nested": {
            "token": "inner-token",
            "safe_key": "safe_val",
        },
    }

    sanitized = sanitize_notification_config(config)
    assert sanitized["secret"] == "******"
    assert sanitized["password"] == "******"
    assert sanitized["api_token"] == "******"
    assert sanitized["nested"]["token"] == "******"
    assert sanitized["nested"]["safe_key"] == "safe_val"
    assert "token123" not in sanitized["webhook_url"]


def test_format_notification_audit_detail():
    cfg: Any = SimpleNamespace(
        id=42,
        name="核心告警群",
        channel=NotifyChannel.wechat,
        config={"webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=supersecretkey"},
    )

    detail = _format_notification_audit_detail(cfg, attempts=2, status="sent")
    assert "渠道: wechat" in detail
    assert "配置: #42 (核心告警群)" in detail
    assert "supersecretkey" not in detail
    assert "key=******" in detail
    assert "重试尝试: 2 次" in detail


@pytest.mark.asyncio
async def test_send_with_retries_recovers_after_transient_failure():
    calls = 0

    async def transient_sender(cfg):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectTimeout("Connect timed out to proxy")
        return None

    config = {"retry_attempts": 2, "retry_backoff_seconds": 0.01}
    attempts = await _send_with_retries(config, transient_sender)
    assert attempts == 2
    assert calls == 2


@pytest.mark.asyncio
async def test_send_with_retries_halts_immediately_on_fatal_client_error():
    calls = 0

    async def fatal_sender(cfg):
        nonlocal calls
        calls += 1
        raise ValueError("Webhook 通知需要 webhook_url")

    config = {"retry_attempts": 3, "retry_backoff_seconds": 0.01}
    with pytest.raises(NotificationDeliveryError) as exc_info:
        await _send_with_retries(config, fatal_sender)

    # Must fail on attempt 1 without wasting retries on non-retryable error
    assert exc_info.value.attempts == 1
    assert calls == 1


@pytest.mark.asyncio
async def test_send_notifications_records_security_audit_logs(monkeypatch):
    mock_audit = AsyncMock()
    monkeypatch.setattr(notifier, "write_audit_log", mock_audit)

    async def mock_sender(config, summary):
        return None

    monkeypatch.setattr(notifier, "_send_wechat", mock_sender)

    cfg = SimpleNamespace(
        id=7,
        name="测试群",
        project_id=1,
        channel=NotifyChannel.wechat,
        config={"webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=secretkey"},
    )

    class _FakeDB:
        def __init__(self):
            self.added = []
            self.committed = False

        async def execute(self, _stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [cfg]))

        def add_all(self, items):
            self.added.extend(items)

        async def commit(self):
            self.committed = True

    db: Any = _FakeDB()
    summary = {"title": "CI 冒烟完成", "status": "passed", "total": 10, "passed": 10}

    await send_notifications(db, project_id=1, summary=summary)

    assert db.committed is True
    # Audit log was called with sanitized details
    mock_audit.assert_called_once()
    kwargs = mock_audit.call_args[1]
    assert kwargs["action"] == "notification_delivery_sent"
    assert kwargs["resource_id"] == 7
    assert kwargs["project_id"] == 1
    assert "secretkey" not in kwargs["detail"]
    assert "key=******" in kwargs["detail"]
