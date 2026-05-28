import asyncio
import inspect
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _fake_require_engineer():
    return None


async def _noop_access(*_a, **_kw):
    return None


sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(
    require_engineer=_fake_require_engineer,
    assert_project_access=_noop_access,
)

from app.api.v1 import dashboard_alerts
from app.models.dashboard_alert import DashboardAlertMetric, DashboardAlertOperator


class _FakeProject:
    def __init__(self, project_id: int):
        self.id = project_id


class _FakeNotification:
    def __init__(self, project_id: int):
        self.project_id = project_id


class _FakeRule:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeDB:
    def __init__(self, project=None, notification=None, rule=None):
        self.project = project
        self.notification = notification
        self.rule = rule
        self.added = []

    async def get(self, model, _pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "Project":
            return self.project
        if model_name == "NotificationConfig":
            return self.notification
        if model_name == "DashboardAlertRule":
            return self.rule
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        return None

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 123


def _create_body(project_id=1, notification_config_id=None):
    return dashboard_alerts.DashboardAlertRuleCreate(
        name="Low pass rate",
        project_id=project_id,
        metric=DashboardAlertMetric.pass_rate,
        op=DashboardAlertOperator.lt,
        threshold=80,
        window_minutes=60,
        suppress_minutes=60,
        notification_config_id=notification_config_id,
        enabled=True,
    )


def test_dashboard_alert_read_endpoints_require_engineer_dependency():
    list_dep = inspect.signature(dashboard_alerts.list_dashboard_alert_rules).parameters["user"].default.dependency
    events_dep = inspect.signature(dashboard_alerts.list_dashboard_alert_events).parameters["user"].default.dependency

    assert list_dep is _fake_require_engineer
    assert events_dep is _fake_require_engineer


def test_create_dashboard_alert_rule_returns_404_for_missing_project():
    db = _FakeDB(project=None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(dashboard_alerts.create_dashboard_alert_rule(body=_create_body(), db=db, user=None))

    assert exc.value.status_code == 404


def test_list_dashboard_alert_rules_global_scope_requires_admin():
    db = _FakeDB()
    user = types.SimpleNamespace(role="engineer")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(dashboard_alerts.list_dashboard_alert_rules(project_id=None, enabled=None, db=db, user=user))

    assert exc.value.status_code == 403


def test_create_dashboard_alert_rule_rejects_cross_project_notification():
    db = _FakeDB(project=_FakeProject(1), notification=_FakeNotification(project_id=2))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            dashboard_alerts.create_dashboard_alert_rule(
                body=_create_body(project_id=1, notification_config_id=9),
                db=db,
                user=None,
            )
        )

    assert exc.value.status_code == 400


def test_create_dashboard_alert_rule_persists_expected_fields(monkeypatch):
    db = _FakeDB(project=_FakeProject(1), notification=_FakeNotification(project_id=1))
    monkeypatch.setattr(dashboard_alerts, "DashboardAlertRule", _FakeRule)

    result = asyncio.run(
        dashboard_alerts.create_dashboard_alert_rule(
            body=_create_body(project_id=1, notification_config_id=9),
            db=db,
            user=None,
        )
    )

    assert result in db.added
    assert result.id == 123
    assert result.metric == DashboardAlertMetric.pass_rate
    assert result.notification_config_id == 9


def test_update_dashboard_alert_rule_validates_notification_project():
    rule = _FakeRule(id=5, project_id=1, notification_config_id=None)
    db = _FakeDB(notification=_FakeNotification(project_id=2), rule=rule)
    body = dashboard_alerts.DashboardAlertRuleUpdate(notification_config_id=8)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(dashboard_alerts.update_dashboard_alert_rule(rule_id=5, body=body, db=db, user=None))

    assert exc.value.status_code == 400
    assert rule.notification_config_id is None


def test_create_dashboard_alert_event_requires_existing_rule():
    db = _FakeDB(rule=None)
    body = dashboard_alerts.DashboardAlertEventCreate(rule_id=99, actual_value=12.3)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(dashboard_alerts.create_dashboard_alert_event(body=body, db=db, user=None))

    assert exc.value.status_code == 404
