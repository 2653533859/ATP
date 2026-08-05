"""dashboard-alert 规则/事件 API 路由单元测试（Q15-05：此前 49%）。

直接调用路由函数：FakeDB 承载对象与脚本化查询，`assert_project_access` 按测试注入
以便断言"用哪个最小角色校验了哪个项目"。这一层的权限阶梯是有实际意义的 ——
读取只要 viewer，增删改要 owner，而不带 project_id 的全局列举只允许 admin。
"""

from __future__ import annotations

import asyncio
import sys
import types

import pytest
from fastapi import HTTPException

from app.api.v1 import dashboard_alerts as api
from app.models.bootstrap import load_all_models
from app.models.dashboard_alert import DashboardAlertMetric, DashboardAlertOperator
from app.models.user import UserRole
from app.models.user_project import ProjectRole
from app.schemas.dashboard_alert import (
    DashboardAlertEventCreate,
    DashboardAlertRuleCreate,
    DashboardAlertRuleUpdate,
)

load_all_models()


class _FakeDB:
    def __init__(self, objects=None, rows=None):
        self._objects = objects or {}
        self._rows = rows or []
        self.added = []
        self.deleted = []
        self.commits = 0
        self.refreshed = []

    async def get(self, model, _pk):
        return self._objects.get(model.__name__)

    async def execute(self, _statement):
        rows = self._rows
        return types.SimpleNamespace(scalars=lambda: types.SimpleNamespace(all=lambda: rows))

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)


@pytest.fixture
def access(monkeypatch):
    """记录每次 assert_project_access 的 (project_id, min_role)。"""
    calls: list[tuple] = []

    async def fake_assert(_db, _user, project_id, min_role=ProjectRole.viewer):
        calls.append((project_id, min_role))

    monkeypatch.setattr(api, "assert_project_access", fake_assert)
    return calls


@pytest.fixture
def denied(monkeypatch):
    async def fake_assert(_db, _user, _project_id, _min_role=ProjectRole.viewer):
        raise HTTPException(status_code=403, detail="No access to this project")

    monkeypatch.setattr(api, "assert_project_access", fake_assert)


def _user(role=UserRole.engineer):
    return types.SimpleNamespace(id=1, username="alice", role=role)


def _rule(**overrides):
    data = {"id": 11, "project_id": 7, "name": "低通过率", "enabled": True}
    data.update(overrides)
    return types.SimpleNamespace(**data)


def _create_body(**overrides):
    data = {
        "name": "低通过率",
        "project_id": 7,
        "metric": DashboardAlertMetric.pass_rate,
        "op": DashboardAlertOperator.lt,
        "threshold": 80.0,
    }
    data.update(overrides)
    return DashboardAlertRuleCreate(**data)


def _run(coro):
    return asyncio.run(coro)


def test_is_admin_only_matches_the_admin_role():
    assert api._is_admin(_user(UserRole.admin)) is True
    assert api._is_admin(_user(UserRole.engineer)) is False
    assert api._is_admin(object()) is False


def test_create_requires_owner_and_persists_the_rule(access):
    db = _FakeDB({"Project": types.SimpleNamespace(id=7)})

    rule = _run(api.create_dashboard_alert_rule(_create_body(), db, _user()))

    assert access == [(7, ProjectRole.owner)], "建规则必须按 owner 校验"
    assert db.added and db.added[0] is rule
    assert db.commits == 1 and db.refreshed


def test_create_rejects_a_missing_project(access):
    with pytest.raises(HTTPException) as excinfo:
        _run(api.create_dashboard_alert_rule(_create_body(), _FakeDB({}), _user()))

    assert excinfo.value.status_code == 404


def test_create_rejects_a_notification_config_from_another_project(access):
    db = _FakeDB(
        {
            "Project": types.SimpleNamespace(id=7),
            "NotificationConfig": types.SimpleNamespace(id=3, project_id=999),
        }
    )

    with pytest.raises(HTTPException) as excinfo:
        _run(api.create_dashboard_alert_rule(_create_body(notification_config_id=3), db, _user()))

    assert excinfo.value.status_code == 400
    assert db.added == [], "跨项目通知配置必须在写库前拒绝"


def test_create_rejects_a_missing_notification_config(access):
    db = _FakeDB({"Project": types.SimpleNamespace(id=7)})

    with pytest.raises(HTTPException) as excinfo:
        _run(api.create_dashboard_alert_rule(_create_body(notification_config_id=3), db, _user()))

    assert excinfo.value.status_code == 400


def test_create_accepts_a_notification_config_in_the_same_project(access):
    db = _FakeDB(
        {
            "Project": types.SimpleNamespace(id=7),
            "NotificationConfig": types.SimpleNamespace(id=3, project_id=7),
        }
    )

    _run(api.create_dashboard_alert_rule(_create_body(notification_config_id=3), db, _user()))

    assert db.commits == 1


def test_create_propagates_an_access_denial(denied):
    with pytest.raises(HTTPException) as excinfo:
        _run(api.create_dashboard_alert_rule(_create_body(), _FakeDB({}), _user()))

    assert excinfo.value.status_code == 403


def test_list_by_project_only_needs_viewer(access):
    rules = [_rule()]
    db = _FakeDB(rows=rules)

    assert _run(api.list_dashboard_alert_rules(7, None, db, _user())) == rules
    assert access == [(7, ProjectRole.viewer)]


def test_list_with_enabled_filter_still_returns_rows(access):
    rules = [_rule()]

    assert _run(api.list_dashboard_alert_rules(7, True, _FakeDB(rows=rules), _user())) == rules


def test_global_rule_list_is_admin_only(access):
    rules = [_rule()]

    assert _run(api.list_dashboard_alert_rules(None, None, _FakeDB(rows=rules), _user(UserRole.admin))) == rules
    assert access == [], "全局列举不针对单个项目做校验"

    with pytest.raises(HTTPException) as excinfo:
        _run(api.list_dashboard_alert_rules(None, None, _FakeDB(rows=rules), _user(UserRole.engineer)))

    assert excinfo.value.status_code == 403


def test_get_rule_checks_viewer_on_the_owning_project(access):
    db = _FakeDB({"DashboardAlertRule": _rule()})

    rule = _run(api.get_dashboard_alert_rule(11, db, _user()))

    assert rule.id == 11
    assert access == [(7, ProjectRole.viewer)]


def test_get_rule_404_before_any_access_check(access):
    with pytest.raises(HTTPException) as excinfo:
        _run(api.get_dashboard_alert_rule(11, _FakeDB({}), _user()))

    assert excinfo.value.status_code == 404
    assert access == []


def test_update_applies_only_the_provided_fields(access):
    rule = _rule(threshold=80.0, enabled=True)
    db = _FakeDB({"DashboardAlertRule": rule})

    _run(api.update_dashboard_alert_rule(11, DashboardAlertRuleUpdate(enabled=False), db, _user()))

    assert rule.enabled is False
    assert rule.threshold == 80.0, "未提交的字段不得被默认值覆盖"
    assert access == [(7, ProjectRole.owner)]
    assert db.commits == 1


def test_update_validates_a_newly_pointed_notification_config(access):
    rule = _rule()
    db = _FakeDB(
        {
            "DashboardAlertRule": rule,
            "NotificationConfig": types.SimpleNamespace(id=3, project_id=999),
        }
    )

    with pytest.raises(HTTPException) as excinfo:
        _run(api.update_dashboard_alert_rule(11, DashboardAlertRuleUpdate(notification_config_id=3), db, _user()))

    assert excinfo.value.status_code == 400
    assert db.commits == 0


def test_update_allows_clearing_the_notification_config(access):
    rule = _rule(notification_config_id=3)
    db = _FakeDB({"DashboardAlertRule": rule})

    _run(api.update_dashboard_alert_rule(11, DashboardAlertRuleUpdate(notification_config_id=None), db, _user()))

    assert rule.notification_config_id is None
    assert db.commits == 1


def test_update_404(access):
    with pytest.raises(HTTPException) as excinfo:
        _run(api.update_dashboard_alert_rule(11, DashboardAlertRuleUpdate(enabled=False), _FakeDB({}), _user()))

    assert excinfo.value.status_code == 404


def test_delete_requires_owner(access):
    rule = _rule()
    db = _FakeDB({"DashboardAlertRule": rule})

    _run(api.delete_dashboard_alert_rule(11, db, _user()))

    assert db.deleted == [rule]
    assert db.commits == 1
    assert access == [(7, ProjectRole.owner)]


def test_delete_404(access):
    with pytest.raises(HTTPException) as excinfo:
        _run(api.delete_dashboard_alert_rule(11, _FakeDB({}), _user()))

    assert excinfo.value.status_code == 404


def test_event_list_by_rule_resolves_the_project_from_the_rule(access):
    events = [types.SimpleNamespace(id=1)]
    db = _FakeDB({"DashboardAlertRule": _rule()}, rows=events)

    assert _run(api.list_dashboard_alert_events(None, 11, 50, db, _user())) == events
    assert access == [(7, ProjectRole.viewer)]


def test_event_list_by_rule_404_for_an_unknown_rule(access):
    with pytest.raises(HTTPException) as excinfo:
        _run(api.list_dashboard_alert_events(None, 11, 50, _FakeDB({}), _user()))

    assert excinfo.value.status_code == 404


def test_event_list_by_project(access):
    events = [types.SimpleNamespace(id=1)]

    assert _run(api.list_dashboard_alert_events(7, None, 50, _FakeDB(rows=events), _user())) == events
    assert access == [(7, ProjectRole.viewer)]


def test_global_event_list_is_admin_only(access):
    events = [types.SimpleNamespace(id=1)]

    assert _run(api.list_dashboard_alert_events(None, None, 50, _FakeDB(rows=events), _user(UserRole.admin))) == events

    with pytest.raises(HTTPException) as excinfo:
        _run(api.list_dashboard_alert_events(None, None, 50, _FakeDB(rows=events), _user()))

    assert excinfo.value.status_code == 403


def test_create_event_defaults_triggered_at_to_now(access):
    db = _FakeDB({"DashboardAlertRule": _rule()})
    body = DashboardAlertEventCreate(rule_id=11, actual_value=42.5)

    event = _run(api.create_dashboard_alert_event(body, db, _user()))

    assert event.triggered_at is not None
    assert event.actual_value == 42.5
    assert access == [(7, ProjectRole.owner)]
    assert db.commits == 1


def test_create_event_keeps_an_explicit_triggered_at(access):
    from datetime import datetime, timezone

    moment = datetime(2026, 8, 1, 9, 30, tzinfo=timezone.utc)
    db = _FakeDB({"DashboardAlertRule": _rule()})
    body = DashboardAlertEventCreate(rule_id=11, actual_value=1.0, triggered_at=moment, snoozed_until=moment)

    event = _run(api.create_dashboard_alert_event(body, db, _user()))

    assert event.triggered_at == moment
    assert event.snoozed_until == moment


def test_create_event_404_for_an_unknown_rule(access):
    body = DashboardAlertEventCreate(rule_id=11, actual_value=1.0)

    with pytest.raises(HTTPException) as excinfo:
        _run(api.create_dashboard_alert_event(body, _FakeDB({}), _user()))

    assert excinfo.value.status_code == 404


def test_module_import_does_not_depend_on_a_prior_deps_stub():
    """本文件必须能单独跑：路由模块 import 期就要 assert_project_access。"""
    assert hasattr(sys.modules["app.api.deps"], "assert_project_access")
