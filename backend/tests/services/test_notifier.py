import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# NotificationDelivery has relationships to the shared model registry. Load the
# same complete registry as application startup so this file is standalone.
from app.models.bootstrap import load_all_models
from app.models.notification import NotifyChannel
from app.services import notifier

load_all_models()


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
        self.added = []

    async def execute(self, _query):
        return _FakeExecuteResult(self._configs)

    def add_all(self, rows):
        self.added.extend(rows)

    async def commit(self):
        return None

    async def rollback(self):
        return None


class _FailingDeliveryDB(_FakeDB):
    def __init__(self, configs, *, fail_on: str):
        super().__init__(configs)
        self.fail_on = fail_on
        self.rolled_back = False

    def add(self, _row):
        if self.fail_on == "add":
            raise RuntimeError("delivery add failed")

    def add_all(self, _rows):
        if self.fail_on == "add_all":
            raise RuntimeError("delivery add_all failed")

    async def rollback(self):
        self.rolled_back = True


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


def test_performance_notification_includes_metrics_and_reasons_in_text_and_markdown():
    summary = {
        **_summary(),
        "entity_type": "performance",
        "rps": 12.5,
        "p95_ms": 210,
        "p99_ms": 380,
        "error_rate": 0.025,
        "threshold_status": "failed",
        "performance_event_reasons": ["threshold_failed", "baseline_regression"],
    }

    text = notifier._build_text(summary)
    markdown = notifier._build_markdown(summary, language="en-US")

    assert "请求速率: 12.5" in text
    assert "P95 延迟: 210ms" in text
    assert "错误率: 2.50%" in text
    assert "触发原因: 阈值失败, 基线回归" in text
    assert "**P95 latency**: 210ms" in markdown
    assert "**Error rate**: 2.50%" in markdown
    assert "**Reasons**: Threshold failed, Baseline regression" in markdown


def test_build_markdown_defaults_to_chinese_for_unknown_language():
    content = notifier._build_markdown(_summary(), language="fr-FR")

    assert "**状态**" in content
    assert "**触发**: 定时" in content


def test_send_notifications_dispatches_by_channel(monkeypatch):
    calls = []

    async def fake_email(config, summary, html_body=None):
        calls.append(("email", config, summary["title"], html_body))

    async def fake_wechat(config, summary):
        calls.append(("wechat", config, summary["title"]))

    async def fake_dingtalk(config, summary):
        calls.append(("dingtalk", config, summary["title"]))

    monkeypatch.setattr(notifier, "_send_email", fake_email)
    monkeypatch.setattr(notifier, "_send_wechat", fake_wechat)
    monkeypatch.setattr(notifier, "_send_dingtalk", fake_dingtalk)

    configs = [
        SimpleNamespace(
            project_id=9, id=1, channel=NotifyChannel.email, config={"recipients": ["a@test.com"], "language": "en-US"}
        ),
        SimpleNamespace(project_id=9, id=2, channel=NotifyChannel.wechat, config={"webhook_url": "https://qy.example"}),
        SimpleNamespace(
            project_id=9,
            id=3,
            channel=NotifyChannel.dingtalk,
            config={"webhook_url": "https://dt.example?access_token=1"},
        ),
    ]

    db = _FakeDB(configs)
    asyncio.run(notifier.send_notifications(db, 9, _summary()))

    assert [call[0] for call in calls] == ["email", "wechat", "dingtalk"]
    assert calls[0][1]["language"] == "en-US"
    assert calls[0][3] is None  # html_body 默认未启用

    assert [item.status for item in db.added] == ["sent", "sent", "sent"]


def test_send_notifications_records_delivery_results_without_sensitive_summary(monkeypatch):
    async def failing_email(config, summary, html_body=None):
        raise ConnectionError("webhook?token=secret-value")

    monkeypatch.setattr(notifier, "_send_email", failing_email)
    cfg = SimpleNamespace(
        project_id=9,
        id=11,
        channel=NotifyChannel.email,
        config={"recipients": ["qa@example.com"], "retry_attempts": 1, "retry_backoff_seconds": 0},
    )
    db = _FakeDB([cfg])

    asyncio.run(notifier.send_notifications(db, 9, {**_summary(), "api_token": "must-not-be-recorded"}))

    assert len(db.added) == 1
    assert db.added[0].status == "failed"
    assert db.added[0].attempts == 2
    assert db.added[0].summary["title"] == "Nightly Plan"
    assert "api_token" not in db.added[0].summary
    assert "secret-value" not in (db.added[0].error_message or "")


def test_send_notification_channel_retries_transient_failure(monkeypatch):
    calls = []

    async def flaky_email(config, summary, html_body=None):
        calls.append(summary["title"])
        if len(calls) == 1:
            raise ConnectionError("temporary network failure")

    monkeypatch.setattr(notifier, "_send_email", flaky_email)

    asyncio.run(
        notifier.send_notification_channel(
            NotifyChannel.email,
            {"recipients": ["qa@example.com"], "retry_attempts": 2, "retry_backoff_seconds": 0},
            _summary(),
        )
    )

    assert calls == ["Nightly Plan", "Nightly Plan"]


def test_send_notification_channel_does_not_retry_provider_rejection(monkeypatch):
    calls = []

    async def rejected_wechat(config, summary):
        calls.append(summary["title"])
        raise RuntimeError("企业微信请求失败: HTTP 400")

    monkeypatch.setattr(notifier, "_send_wechat", rejected_wechat)

    with pytest.raises(RuntimeError, match="HTTP 400"):
        asyncio.run(
            notifier.send_notification_channel(
                NotifyChannel.wechat,
                {"webhook_url": "https://qy.example", "retry_attempts": 3, "retry_backoff_seconds": 0},
                _summary(),
            )
        )

    assert calls == ["Nightly Plan"]


def test_send_notification_channel_rejects_missing_delivery_target_before_sender(monkeypatch):
    calls = []

    async def fake_wechat(config, summary):
        calls.append(True)

    monkeypatch.setattr(notifier, "_send_wechat", fake_wechat)

    with pytest.raises(ValueError, match="webhook_url"):
        asyncio.run(notifier.send_notification_channel(NotifyChannel.wechat, {}, _summary()))

    assert calls == []


def test_retry_policy_clamps_untrusted_values():
    assert notifier._retry_policy({"retry_attempts": 99, "retry_backoff_seconds": 99}) == (3, 30.0)
    assert notifier._retry_policy({"retry_attempts": "invalid", "retry_backoff_seconds": "invalid"}) == (0, 1.0)


def test_notification_error_messages_redact_provider_credentials():
    raw = "request failed: https://user:pass@example.test/hook?access_token=secret&sign=signature" "\nforged-log-line"

    safe = notifier._safe_exception_message(RuntimeError(raw))

    assert "secret" not in safe
    assert "signature" not in safe
    assert "user:pass@" not in safe
    assert "<redacted>" in safe
    assert "\n" not in safe and "\r" not in safe


def test_notification_error_messages_redact_wechat_webhook_key():
    raw = "request failed: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=wechat-secret&msgtype=markdown"

    safe = notifier._safe_exception_message(RuntimeError(raw))

    assert "wechat-secret" not in safe
    assert "?key=<redacted>" in safe
    assert "msgtype=markdown" in safe


def test_delivery_persistence_failures_do_not_escape_notification_flow(monkeypatch):
    async def successful_email(config, summary, html_body=None):
        return None

    monkeypatch.setattr(notifier, "_send_email", successful_email)
    cfg = SimpleNamespace(project_id=9, id=21, channel=NotifyChannel.email, config={"recipients": ["qa@example.com"]})

    add_all_db = _FailingDeliveryDB([cfg], fail_on="add_all")
    asyncio.run(notifier.send_notifications(add_all_db, 9, _summary()))
    assert add_all_db.rolled_back is True

    add_db = _FailingDeliveryDB([], fail_on="add")
    asyncio.run(
        notifier.persist_notification_delivery(
            add_db,
            cfg,
            _summary(),
            status="failed",
            attempts=1,
            error_message="delivery failed",
        )
    )
    assert add_db.rolled_back is True


def test_should_send_notification_filters_by_status_and_suite_scope():
    config = {"scope": "suites", "suite_ids": [3, "5"], "status_filters": ["failed", "error"]}

    assert notifier.should_send_notification(config, {**_summary(), "entity_type": "suite", "suite_id": 3})
    assert notifier.should_send_notification(config, {**_summary(), "entity_type": "suite", "suite_id": "5"})
    assert not notifier.should_send_notification(
        config, {**_summary(), "status": "passed", "entity_type": "suite", "suite_id": 3}
    )
    assert not notifier.should_send_notification(config, {**_summary(), "entity_type": "plan", "plan_id": 3})
    assert not notifier.should_send_notification(config, {**_summary(), "entity_type": "suite", "suite_id": 8})


def test_should_send_notification_fails_closed_for_unknown_scope():
    config = {"scope": "everything", "status_filters": ["failed"]}

    assert not notifier.should_send_notification(config, {**_summary(), "entity_type": "suite", "suite_id": 3})


def test_validate_notification_strategy_rejects_unknown_scope_and_status():
    with pytest.raises(ValueError, match="通知范围"):
        notifier.validate_notification_channel_config(
            NotifyChannel.email,
            {"recipients": ["qa@example.com"], "scope": "everything"},
        )

    with pytest.raises(ValueError, match="通知状态筛选"):
        notifier.validate_notification_channel_config(
            NotifyChannel.email,
            {"recipients": ["qa@example.com"], "status_filters": ["cancelled"]},
        )

    with pytest.raises(ValueError, match="suite_ids"):
        notifier.validate_notification_channel_config(
            NotifyChannel.email,
            {"recipients": ["qa@example.com"], "scope": "suites", "suite_ids": ["abc"]},
        )


def test_send_notifications_skips_configs_outside_strategy(monkeypatch):
    calls = []

    async def fake_email(config, summary, html_body=None):
        calls.append((config["recipients"], summary["suite_id"]))

    monkeypatch.setattr(notifier, "_send_email", fake_email)

    configs = [
        SimpleNamespace(
            project_id=9,
            id=1,
            channel=NotifyChannel.email,
            config={
                "recipients": ["suite-1@test.com"],
                "scope": "suites",
                "suite_ids": [1],
                "status_filters": ["failed"],
            },
        ),
        SimpleNamespace(
            project_id=9,
            id=2,
            channel=NotifyChannel.email,
            config={
                "recipients": ["suite-2@test.com"],
                "scope": "suites",
                "suite_ids": [2],
                "status_filters": ["failed"],
            },
        ),
    ]

    asyncio.run(notifier.send_notifications(_FakeDB(configs), 9, {**_summary(), "entity_type": "suite", "suite_id": 1}))

    assert calls == [(["suite-1@test.com"], 1)]


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
