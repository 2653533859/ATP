"""Regression tests for the safe configuration-center aggregation."""

from __future__ import annotations

import asyncio
import inspect
import sys
import types
from datetime import datetime, timezone

# Some historical API tests replace this module during collection.  Fill only
# the symbols needed by this test before importing the route, preserving any
# test-specific dependency functions already installed by the suite.
_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())
_deps.require_engineer = getattr(_deps, "require_engineer", lambda: None)


async def _noop_async(*_args, **_kwargs):
    return None


_deps.assert_project_access = getattr(_deps, "assert_project_access", _noop_async)
_deps.get_project_role = getattr(_deps, "get_project_role", _noop_async)

from app.api.v1 import configuration_center
from app.api.deps import require_engineer
from app.models.ai_llm_config import AILLMConfig
from app.models.bootstrap import load_all_models
from app.models.environment import Environment, EnvVariable
from app.models.global_variable import GlobalVariable, ScopeType
from app.models.notification import NotificationConfig, NotifyChannel
from app.models.performance_node import PerformanceNode
from app.models.storage_policy import StoragePolicy
from app.models.user import User, UserRole
from app.models.user_project import UserProject

load_all_models()


class _Result:
    def __init__(self, rows, scalar=None):
        self._rows = list(rows)
        self._scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one_or_none(self):
        return self._scalar


class _DB:
    def __init__(
        self,
        *,
        environment_rows=(),
        variable_rows=(),
        global_rows=(),
        notification_rows=(),
        ai_rows=(),
        storage_rows=(),
        node_rows=(),
    ):
        self.rows = {
            Environment: list(environment_rows),
            EnvVariable: list(variable_rows),
            GlobalVariable: list(global_rows),
            NotificationConfig: list(notification_rows),
            AILLMConfig: list(ai_rows),
            StoragePolicy: list(storage_rows),
            PerformanceNode: list(node_rows),
        }

    async def execute(self, statement):
        entities = {item.get("entity") for item in statement.column_descriptions}
        for model, rows in self.rows.items():
            if model in entities:
                return _Result(rows)
        if UserProject in entities:
            return _Result([], scalar=None)
        return _Result([])


def _admin() -> User:
    return User(id=1, username="admin", email="admin@example.com", hashed_password="hash", role=UserRole.admin)


def _engineer() -> User:
    return User(id=2, username="engineer", email="engineer@example.com", hashed_password="hash", role=UserRole.engineer)


def test_overview_dependency_requires_engineer():
    dependency = (
        inspect.signature(configuration_center.get_configuration_center_overview).parameters["user"].default.dependency
    )
    assert dependency is require_engineer


def test_admin_overview_aggregates_domains_without_secret_values():
    updated_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
    environment = Environment(id=1, name="测试环境", project_id=10, updated_at=updated_at)
    variable = EnvVariable(id=1, env_id=1, key="PASSWORD", value="encrypted-secret", is_secret=True)
    global_variable = GlobalVariable(
        id=2,
        scope_type=ScopeType.global_scope,
        project_id=None,
        key="GLOBAL_TOKEN",
        value_encrypted="encrypted-global-secret",
        is_secret=True,
        updated_at=updated_at,
    )
    notification = NotificationConfig(
        id=3,
        name="告警",
        project_id=10,
        channel=NotifyChannel.dingtalk,
        config={"webhook_url": "https://secret.example.invalid?token=do-not-return"},
        is_enabled=True,
        updated_at=updated_at,
    )
    ai = AILLMConfig(
        id=4,
        name="模型",
        provider="openai_compatible",
        api_key_encrypted="encrypted-api-key",
        endpoint="https://secret-model.example.invalid/v1",
        model_name="vision-model",
        enabled=True,
        supports_vision=True,
        updated_at=updated_at,
    )
    storage = StoragePolicy(
        id=5,
        name="报告",
        prefix="reports/",
        retention_days=30,
        max_size_gb=10,
        enabled=True,
        updated_at=updated_at,
    )
    node = PerformanceNode(
        id=6,
        node_id="node-1",
        name="节点",
        queue_name="performance",
        status="online",
        enabled=True,
        capabilities={"executors": ["k6", {"token": "must-not-leak"}], "password": "must-not-leak"},
        labels={"secret": "must-not-leak"},
        egress_allowlist=["10.0.0.1"],
        updated_at=updated_at,
    )
    db = _DB(
        environment_rows=[environment],
        variable_rows=[variable],
        global_rows=[global_variable],
        notification_rows=[notification],
        ai_rows=[ai],
        storage_rows=[storage],
        node_rows=[node],
    )

    result = asyncio.run(configuration_center.get_configuration_center_overview(project_id=None, db=db, user=_admin()))
    payload = result.model_dump()
    sections = {item["key"]: item for item in payload["sections"]}

    assert set(sections) == {
        "startup",
        "environment",
        "global_variable",
        "ai_llm",
        "storage_policy",
        "notification",
        "performance_node",
    }
    assert sections["environment"]["entries"][0]["summary"] == {"variable_count": 1, "secret_count": 1}
    assert sections["ai_llm"]["entries"][0]["summary"]["has_api_key"] is True
    assert sections["performance_node"]["entries"][0]["summary"]["executors"] == ["k6"]
    assert sections["startup"]["readonly"] is True
    assert "encrypted-secret" not in str(payload)
    assert "encrypted-global-secret" not in str(payload)
    assert "secret-model.example.invalid" not in str(payload)
    assert "do-not-return" not in str(payload)
    assert "must-not-leak" not in str(payload)


def test_engineer_cannot_see_admin_only_domains():
    db = _DB(
        ai_rows=[
            AILLMConfig(
                id=1,
                name="管理员模型",
                provider="ollama",
                api_key_encrypted="",
                model_name="local",
                enabled=True,
            )
        ],
        storage_rows=[StoragePolicy(id=2, name="策略", prefix="reports/", retention_days=30, enabled=True)],
    )

    result = asyncio.run(
        configuration_center.get_configuration_center_overview(project_id=None, db=db, user=_engineer())
    )
    sections = {item.key: item for item in result.sections}

    assert sections["ai_llm"].available is False
    assert sections["ai_llm"].entries == []
    assert sections["storage_policy"].available is False
    assert sections["storage_policy"].entries == []


def test_safe_executors_discards_non_string_capabilities():
    assert configuration_center._safe_executors({"executors": [" k6 ", "k6", {"token": "secret"}, ""]}) == ["k6"]
    assert configuration_center._safe_executors({"token": "secret"}) == []
