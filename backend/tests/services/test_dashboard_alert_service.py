import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models.dashboard_alert import DashboardAlertMetric, DashboardAlertOperator
from app.services import dashboard_alerts


class _FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class _FakeExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _FakeScalarResult(self._items)


class _FakeDB:
    def __init__(self, rules):
        self.rules = rules
        self.added = []
        self.commits = 0

    async def execute(self, _stmt):
        return _FakeExecuteResult(self.rules)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


class _FakeEvent:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _rule(**overrides):
    data = {
        "id": 1,
        "name": "Low pass rate",
        "project_id": 7,
        "metric": DashboardAlertMetric.pass_rate,
        "op": DashboardAlertOperator.lt,
        "threshold": 80.0,
        "window_minutes": 60,
        "suppress_minutes": 30,
        "notification_config_id": 3,
        "enabled": True,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_compare_metric_supports_all_operators():
    assert dashboard_alerts.compare_metric(3, DashboardAlertOperator.gt, 2)
    assert dashboard_alerts.compare_metric(3, DashboardAlertOperator.gte, 3)
    assert dashboard_alerts.compare_metric(2, DashboardAlertOperator.lt, 3)
    assert dashboard_alerts.compare_metric(3, DashboardAlertOperator.lte, 3)
    assert dashboard_alerts.compare_metric(3, DashboardAlertOperator.eq, 3)
    assert not dashboard_alerts.compare_metric(3, DashboardAlertOperator.lt, 3)


def test_is_event_suppressed_by_snoozed_until():
    now = datetime(2026, 5, 27, 12, tzinfo=timezone.utc)
    event = SimpleNamespace(
        triggered_at=now - timedelta(hours=2),
        snoozed_until=now + timedelta(minutes=1),
    )

    assert dashboard_alerts.is_event_suppressed(event, now, suppress_minutes=30)


def test_is_event_suppressed_by_triggered_at_window():
    now = datetime(2026, 5, 27, 12, tzinfo=timezone.utc)
    event = SimpleNamespace(
        triggered_at=now - timedelta(minutes=10),
        snoozed_until=None,
    )

    assert dashboard_alerts.is_event_suppressed(event, now, suppress_minutes=30)


def test_build_alert_summary_includes_rule_context():
    summary = dashboard_alerts.build_alert_summary(_rule(), 72.5)

    assert summary["status"] == "error"
    assert "Low pass rate" in summary["title"]
    assert "72.5" in summary["title"]
    assert "80" in summary["title"]


def test_evaluate_dashboard_alerts_triggers_event_and_notification(monkeypatch):
    now = datetime(2026, 5, 27, 12, tzinfo=timezone.utc)
    rule = _rule()
    db = _FakeDB([rule])
    sent = []

    async def fake_metric(_db, _rule, _now):
        return 70.0

    async def fake_latest(_db, _rule_id):
        return None

    async def fake_send(_db, _rule, actual):
        sent.append(actual)
        return True

    monkeypatch.setattr(dashboard_alerts, "calculate_rule_metric", fake_metric)
    monkeypatch.setattr(dashboard_alerts, "_latest_event", fake_latest)
    monkeypatch.setattr(dashboard_alerts, "_send_notification", fake_send)
    monkeypatch.setattr(dashboard_alerts, "DashboardAlertEvent", _FakeEvent)

    result = asyncio.run(dashboard_alerts.evaluate_dashboard_alerts(db, now))

    assert result["rules"] == 1
    assert result["evaluated"] == 1
    assert result["triggered"] == 1
    assert result["notifications_sent"] == 1
    assert db.commits == 1
    assert db.added[0].actual_value == 70.0
    assert sent == [70.0]


def test_evaluate_dashboard_alerts_skips_suppressed_rule(monkeypatch):
    now = datetime(2026, 5, 27, 12, tzinfo=timezone.utc)
    rule = _rule()
    db = _FakeDB([rule])
    event = SimpleNamespace(triggered_at=now - timedelta(minutes=1), snoozed_until=None)

    async def fake_metric(_db, _rule, _now):
        return 70.0

    async def fake_latest(_db, _rule_id):
        return event

    async def fake_send(_db, _rule, actual):
        raise AssertionError("suppressed rules must not notify")

    monkeypatch.setattr(dashboard_alerts, "calculate_rule_metric", fake_metric)
    monkeypatch.setattr(dashboard_alerts, "_latest_event", fake_latest)
    monkeypatch.setattr(dashboard_alerts, "_send_notification", fake_send)

    result = asyncio.run(dashboard_alerts.evaluate_dashboard_alerts(db, now))

    assert result["suppressed"] == 1
    assert result["triggered"] == 0
    assert db.added == []


def test_evaluate_dashboard_alerts_records_no_data(monkeypatch):
    rule = _rule()
    db = _FakeDB([rule])

    async def fake_metric(_db, _rule, _now):
        return None

    monkeypatch.setattr(dashboard_alerts, "calculate_rule_metric", fake_metric)

    result = asyncio.run(dashboard_alerts.evaluate_dashboard_alerts(db))

    assert result["no_data"] == 1
    assert result["evaluated"] == 0
    assert db.added == []
