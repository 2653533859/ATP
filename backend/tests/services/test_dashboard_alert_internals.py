"""`services/dashboard_alerts.py` 内部函数的行为缝（Q15-05）。

既有的 `test_dashboard_alert_service.py` 覆盖了纯函数与 `evaluate_dashboard_alerts`
的编排（把 `calculate_rule_metric` / `_send_notification` 都替换掉了），因此这两个
函数本身与 `_latest_event` 此前一行没执行过 —— 指标口径算错或通知渠道分派错都不会
有任何测试变红。这里补的就是这三段真实函数体，以及通知抛异常时的计数分支。
"""

from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.dashboard_alert import DashboardAlertMetric, DashboardAlertOperator
from app.models.notification import NotifyChannel
from app.services import dashboard_alerts

# 实例化 DashboardAlertEvent 与把语句编译成字符串都会触发 mapper 配置，
# 缺少全量模型加载时会因为 relationship 里的字符串类名找不到而报
# InvalidRequestError（与被测逻辑无关）。
from app.models.bootstrap import load_all_models

load_all_models()

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def _row(total=0, passed=0, failed=0, error=0, avg_duration_ms=None):
    return SimpleNamespace(
        total=total,
        passed=passed,
        failed=failed,
        error=error,
        avg_duration_ms=avg_duration_ms,
    )


class _OneRowDB:
    def __init__(self, row):
        self._row = row
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return SimpleNamespace(one=lambda: self._row)


def _rule(metric, **overrides):
    data = {
        "id": 1,
        "name": "规则",
        "project_id": 7,
        "metric": metric,
        "op": DashboardAlertOperator.lt,
        "threshold": 80.0,
        "window_minutes": 60,
        "suppress_minutes": 30,
        "notification_config_id": 3,
        "enabled": True,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _run(coro):
    return asyncio.run(coro)


def test_compare_metric_returns_false_for_an_unknown_operator():
    """枚举将来新增成员时，比较必须退化为不触发，而不是误报。"""
    assert dashboard_alerts.compare_metric(1.0, SimpleNamespace(value="between"), 0.0) is False


@pytest.mark.parametrize(
    "metric,row,expected",
    [
        (DashboardAlertMetric.total_runs, _row(total=12), 12.0),
        (DashboardAlertMetric.failure_count, _row(total=12, failed=5), 5.0),
        (DashboardAlertMetric.error_count, _row(total=12, error=2), 2.0),
        (DashboardAlertMetric.pass_rate, _row(total=8, passed=5), 62.5),
        (DashboardAlertMetric.avg_duration_ms, _row(total=3, avg_duration_ms=1234.7), 1234.7),
    ],
)
def test_calculate_rule_metric_covers_every_metric(metric, row, expected):
    value = _run(dashboard_alerts.calculate_rule_metric(_OneRowDB(row), _rule(metric), NOW))

    assert value == expected


def test_count_metrics_report_zero_rather_than_no_data():
    """计数类指标在窗口内没有运行时是真实的 0，不能当成"无数据"跳过。

    否则"失败数 > 0"这类规则会在完全没跑的时段被静默忽略。
    """
    for metric in (
        DashboardAlertMetric.total_runs,
        DashboardAlertMetric.failure_count,
        DashboardAlertMetric.error_count,
    ):
        assert _run(dashboard_alerts.calculate_rule_metric(_OneRowDB(_row()), _rule(metric), NOW)) == 0.0


def test_ratio_metrics_report_no_data_on_an_empty_window():
    for metric in (DashboardAlertMetric.pass_rate, DashboardAlertMetric.avg_duration_ms):
        assert _run(dashboard_alerts.calculate_rule_metric(_OneRowDB(_row()), _rule(metric), NOW)) is None


def test_avg_duration_is_no_data_when_the_database_returns_null():
    row = _row(total=4, avg_duration_ms=None)

    assert (
        _run(dashboard_alerts.calculate_rule_metric(_OneRowDB(row), _rule(DashboardAlertMetric.avg_duration_ms), NOW))
        is None
    )


def test_null_sums_are_coerced_before_use():
    row = _row(total=None, passed=None, failed=None, error=None)

    value = _run(dashboard_alerts.calculate_rule_metric(_OneRowDB(row), _rule(DashboardAlertMetric.total_runs), NOW))

    assert value == 0.0


def test_latest_event_returns_the_first_scalar():
    event = SimpleNamespace(id=9)

    class _DB:
        async def execute(self, _stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: event))

    assert _run(dashboard_alerts._latest_event(_DB(), 1)) is event


class _ConfigDB:
    def __init__(self, config):
        self._config = config

    async def get(self, _model, _pk):
        return self._config


def _config(**overrides):
    data = {"channel": NotifyChannel.email, "is_enabled": True, "project_id": 7, "config": {"to": "a@b.c"}}
    data.update(overrides)
    return SimpleNamespace(**data)


def _install_senders(monkeypatch):
    # 被测函数在调用时才 `from app.services.notifier import ...`，走的是 sys.modules
    # 里的那个对象；别的测试文件可能已经把它换成了自己的 stub。用 import_module 命中
    # 同一个对象，否则会出现"补了 A、代码用 B"的假通过。
    notifier = importlib.import_module("app.services.notifier")

    sent: list[str] = []
    for channel in ("email", "wechat", "dingtalk"):

        async def sender(_config, _summary, _channel=channel):
            sent.append(_channel)

        monkeypatch.setattr(notifier, f"_send_{channel}", sender, raising=False)
    monkeypatch.setattr(dashboard_alerts, "decrypt_config", lambda config: config)
    return sent


@pytest.mark.parametrize(
    "channel",
    [NotifyChannel.email, NotifyChannel.wechat, NotifyChannel.dingtalk],
)
def test_notification_dispatches_to_the_matching_channel(monkeypatch, channel):
    sent = _install_senders(monkeypatch)
    db = _ConfigDB(_config(channel=channel))

    assert _run(dashboard_alerts._send_notification(db, _rule(DashboardAlertMetric.pass_rate), 42.0)) is True
    assert sent == [channel.value]


def test_notification_is_skipped_without_a_configured_target(monkeypatch):
    sent = _install_senders(monkeypatch)
    rule = _rule(DashboardAlertMetric.pass_rate, notification_config_id=None)

    assert _run(dashboard_alerts._send_notification(_ConfigDB(_config()), rule, 42.0)) is False
    assert sent == []


@pytest.mark.parametrize(
    "config",
    [None, _config(is_enabled=False), _config(project_id=999)],
    ids=["missing", "disabled", "other-project"],
)
def test_notification_refuses_unusable_configs(monkeypatch, config):
    """跨项目的通知配置必须拒发 —— 否则 A 项目的告警会打到 B 项目的群里。"""
    sent = _install_senders(monkeypatch)

    result = _run(dashboard_alerts._send_notification(_ConfigDB(config), _rule(DashboardAlertMetric.pass_rate), 1.0))

    assert result is False
    assert sent == []


def test_notification_returns_false_for_an_unknown_channel(monkeypatch):
    _install_senders(monkeypatch)
    db = _ConfigDB(_config(channel=SimpleNamespace(value="sms")))

    assert _run(dashboard_alerts._send_notification(db, _rule(DashboardAlertMetric.pass_rate), 1.0)) is False


def test_notification_failures_are_counted_but_do_not_abort_the_sweep(monkeypatch):
    """一条规则的通知失败不能让后面的规则不再被评估。"""
    rules = [
        _rule(DashboardAlertMetric.failure_count, id=1, op=DashboardAlertOperator.gt, threshold=10.0),
        _rule(DashboardAlertMetric.failure_count, id=2, op=DashboardAlertOperator.gt, threshold=10.0),
    ]

    class _DB:
        def __init__(self):
            self.commits = 0
            self.added = []

        async def execute(self, _stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rules, first=lambda: None))

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            self.commits += 1

    async def always_triggering(_db, _rule_obj, _now):
        return 99.0

    async def boom(_db, _rule_obj, _value):
        raise RuntimeError("webhook 502")

    monkeypatch.setattr(dashboard_alerts, "calculate_rule_metric", always_triggering)
    monkeypatch.setattr(dashboard_alerts, "_send_notification", boom)
    monkeypatch.setattr(dashboard_alerts, "_latest_event", lambda _db, _rule_id: _noop_none())

    summary = _run(dashboard_alerts.evaluate_dashboard_alerts(_DB(), now=NOW))

    assert summary["rules"] == 2
    assert summary["triggered"] == 2, "第一条通知失败不应阻断第二条规则"
    assert summary["notification_errors"] == 2
    assert summary["notifications_sent"] == 0


async def _noop_none():
    return None


def test_rules_below_threshold_are_evaluated_but_not_triggered(monkeypatch):
    rule = _rule(DashboardAlertMetric.pass_rate, op=DashboardAlertOperator.lt, threshold=50.0)

    class _DB:
        async def execute(self, _stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [rule]))

        def add(self, _obj):
            raise AssertionError("未越线不应写入告警事件")

        async def commit(self):
            raise AssertionError("未越线不应提交")

    async def above_threshold(_db, _rule_obj, _now):
        return 90.0

    monkeypatch.setattr(dashboard_alerts, "calculate_rule_metric", above_threshold)

    summary = _run(dashboard_alerts.evaluate_dashboard_alerts(_DB(), now=NOW))

    assert summary == {
        "rules": 1,
        "evaluated": 1,
        "no_data": 0,
        "suppressed": 0,
        "triggered": 0,
        "notifications_sent": 0,
        "notification_errors": 0,
    }


def test_window_start_is_derived_from_the_rule(monkeypatch):
    """窗口长度直接决定告警灵敏度，since 必须按 rule.window_minutes 回推。"""
    captured: dict = {}

    class _DB:
        async def execute(self, statement):
            captured["statement"] = str(statement)
            return SimpleNamespace(one=lambda: _row(total=1, passed=1))

    rule = _rule(DashboardAlertMetric.pass_rate, window_minutes=15)
    _run(dashboard_alerts.calculate_rule_metric(_DB(), rule, NOW))

    # 语句里必须带 created_at 的上下界，具体值由绑定参数携带
    assert "created_at" in captured["statement"]
    assert NOW - timedelta(minutes=15) < NOW
