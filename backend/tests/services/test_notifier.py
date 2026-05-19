import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.notification import NotifyChannel
from app.services import notifier


class _FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, configs):
        self._configs = configs

    async def execute(self, _query):
        return _FakeExecuteResult(self._configs)


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


def test_build_text_includes_summary_fields():
    content = notifier._build_text(_summary())

    assert "Nightly Plan" in content
    assert "3 / 5" in content
    assert "12.5s" in content
    assert "触发: 定时" in content


def test_build_text_supports_english_labels():
    content = notifier._build_text(_summary(), language="en-US")

    assert "Status: Failed" in content
    assert "Passed: 3 / 5" in content
    assert "Trigger: Scheduled" in content


def test_build_markdown_defaults_to_chinese_for_unknown_language():
    content = notifier._build_markdown(_summary(), language="fr-FR")

    assert "**状态**" in content
    assert "**触发**: 定时" in content


def test_send_notifications_dispatches_by_channel(monkeypatch):
    calls = []

    async def fake_email(config, summary):
        calls.append(("email", config, summary["title"]))

    async def fake_wechat(config, summary):
        calls.append(("wechat", config, summary["title"]))

    async def fake_dingtalk(config, summary):
        calls.append(("dingtalk", config, summary["title"]))

    monkeypatch.setattr(notifier, "_send_email", fake_email)
    monkeypatch.setattr(notifier, "_send_wechat", fake_wechat)
    monkeypatch.setattr(notifier, "_send_dingtalk", fake_dingtalk)

    configs = [
        SimpleNamespace(id=1, channel=NotifyChannel.email, config={"recipients": ["a@test.com"], "language": "en-US"}),
        SimpleNamespace(id=2, channel=NotifyChannel.wechat, config={"webhook_url": "https://qy.example"}),
        SimpleNamespace(id=3, channel=NotifyChannel.dingtalk, config={"webhook_url": "https://dt.example?access_token=1"}),
    ]

    asyncio.run(notifier.send_notifications(_FakeDB(configs), 9, _summary()))

    assert [call[0] for call in calls] == ["email", "wechat", "dingtalk"]
    assert calls[0][1]["language"] == "en-US"


def test_wechat_sender_raises_when_provider_rejects(monkeypatch):
    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {"errcode": 40013, "errmsg": "invalid webhook key"}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            return _Response()

    monkeypatch.setattr(notifier.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(notifier._send_wechat({"webhook_url": "https://qy.example"}, _summary()))

    assert "invalid webhook key" in str(exc.value)


def test_dingtalk_sender_raises_when_http_request_fails(monkeypatch):
    class _Response:
        status_code = 403

        @staticmethod
        def json():
            return {"errcode": 310000, "errmsg": "sign not match"}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            return _Response()

    monkeypatch.setattr(notifier.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(
            notifier._send_dingtalk(
                {"webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=token"},
                _summary(),
            )
        )

    assert "HTTP 403" in str(exc.value)


def test_dingtalk_sender_appends_signed_query(monkeypatch):
    captured = {}

    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {"errcode": 0}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return _Response()

    monkeypatch.setattr(notifier.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(notifier.time, "time", lambda: 1700000000.0)

    asyncio.run(
        notifier._send_dingtalk(
            {
                "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=token",
                "secret": "SEC_TEST",
            },
            _summary(),
        )
    )

    assert "timestamp=" in captured["url"]
    assert "sign=" in captured["url"]
    assert captured["json"]["msgtype"] == "markdown"
    assert "Nightly Plan" in captured["json"]["markdown"]["text"]
