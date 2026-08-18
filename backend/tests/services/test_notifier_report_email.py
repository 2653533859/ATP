"""P1.2 定时报告邮件：notifier 接受 report_html + email_html_report_enabled 检查。"""

import asyncio
import sys
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Keep SQLAlchemy's registry complete when this service test is executed alone.
from app.models.bootstrap import load_all_models
from app.models.notification import NotifyChannel
from app.services import notifier

load_all_models()


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, configs):
        self._configs = configs
        self.added = []

    async def execute(self, _query):
        return _FakeResult(self._configs)

    def add_all(self, rows):
        self.added.extend(rows)

    async def commit(self):
        return None

    async def rollback(self):
        return None


def _summary():
    return {
        "title": "Nightly Plan",
        "status": "failed",
        "total": 5,
        "passed": 3,
        "failed": 1,
        "error": 1,
        "duration_ms": 12500,
        "trigger_type": "cron",
    }


def test_email_html_report_enabled_returns_true_when_any_email_config_opts_in():
    configs = [
        SimpleNamespace(
            id=1,
            channel=NotifyChannel.email,
            config={"recipients": ["a@x"], "attach_html_report": True},
        ),
    ]
    enabled = asyncio.run(notifier.email_html_report_enabled(_FakeDB(configs), 9))
    assert enabled is True


def test_email_html_report_enabled_returns_false_when_no_opt_in():
    # 模拟 query 已按 channel=email 过滤后的结果（_FakeDB 不实现 where 过滤）
    configs = [
        SimpleNamespace(
            id=1,
            channel=NotifyChannel.email,
            config={"recipients": ["a@x"]},  # 未设置 attach_html_report
        ),
    ]
    enabled = asyncio.run(notifier.email_html_report_enabled(_FakeDB(configs), 9))
    assert enabled is False


def test_email_html_report_enabled_returns_false_when_no_configs():
    enabled = asyncio.run(notifier.email_html_report_enabled(_FakeDB([]), 9))
    assert enabled is False


def test_send_notifications_passes_html_only_to_opted_in_email_config(monkeypatch):
    received: list[tuple[dict, str | None]] = []

    async def fake_email(config, summary, html_body=None):
        received.append((config, html_body))

    async def fake_wechat(*_a, **_kw):
        return None

    async def fake_dingtalk(*_a, **_kw):
        return None

    monkeypatch.setattr(notifier, "_send_email", fake_email)
    monkeypatch.setattr(notifier, "_send_wechat", fake_wechat)
    monkeypatch.setattr(notifier, "_send_dingtalk", fake_dingtalk)

    configs = [
        SimpleNamespace(
            id=1,
            channel=NotifyChannel.email,
            config={"recipients": ["opt-in@x"], "attach_html_report": True},
        ),
        SimpleNamespace(
            id=2,
            channel=NotifyChannel.email,
            config={"recipients": ["opt-out@x"]},  # 未启用
        ),
    ]
    html = "<html><body>full report</body></html>"
    asyncio.run(notifier.send_notifications(_FakeDB(configs), 9, _summary(), report_html=html))

    assert len(received) == 2
    # 启用的拿到 html
    opt_in = next((cfg, body) for cfg, body in received if cfg["recipients"] == ["opt-in@x"])
    opt_out = next((cfg, body) for cfg, body in received if cfg["recipients"] == ["opt-out@x"])
    assert opt_in[1] == html
    assert opt_out[1] is None


def test_send_email_with_html_body_uses_multipart_alternative(monkeypatch):
    """SMTP 发送时，html_body 存在则用 multipart/alternative；text 与 html 都附上。"""
    captured = {}

    def fake_smtp_send(msg, recipients):
        captured["msg"] = msg
        captured["recipients"] = recipients

    monkeypatch.setattr(notifier, "_smtp_send", fake_smtp_send)
    monkeypatch.setattr(notifier.settings, "SMTP_FROM", "atp@example.com")

    config = {"recipients": ["x@y.com"], "subject_prefix": "[ATP]", "language": "zh-CN"}
    html = "<html><body><h1>Report</h1></body></html>"

    asyncio.run(notifier._send_email(config, _summary(), html_body=html))

    msg = captured["msg"]
    assert isinstance(msg, MIMEMultipart)
    assert msg.get_content_subtype() == "alternative"
    parts = msg.get_payload()
    assert len(parts) == 2
    subtypes = sorted(p.get_content_subtype() for p in parts)
    assert subtypes == ["html", "plain"]
    # html part 包含 report 内容
    html_part = next(p for p in parts if p.get_content_subtype() == "html")
    assert "Report" in html_part.get_payload(decode=True).decode("utf-8")
    assert captured["recipients"] == ["x@y.com"]


def test_send_email_without_html_falls_back_to_plain_only(monkeypatch):
    captured = {}

    def fake_smtp_send(msg, recipients):
        captured["msg"] = msg

    monkeypatch.setattr(notifier, "_smtp_send", fake_smtp_send)
    monkeypatch.setattr(notifier.settings, "SMTP_FROM", "atp@example.com")

    config = {"recipients": ["x@y.com"]}
    asyncio.run(notifier._send_email(config, _summary()))  # html_body 未传

    msg = captured["msg"]
    parts = msg.get_payload()
    assert len(parts) == 1
    assert parts[0].get_content_subtype() == "plain"


def test_send_email_rejects_when_no_recipients(monkeypatch):
    called = {"value": False}

    def fake_smtp_send(*_a, **_kw):
        called["value"] = True

    monkeypatch.setattr(notifier, "_smtp_send", fake_smtp_send)
    with pytest.raises(ValueError, match="至少需要一个收件人"):
        asyncio.run(notifier._send_email({"recipients": []}, _summary(), html_body="<x/>"))
    assert called["value"] is False
