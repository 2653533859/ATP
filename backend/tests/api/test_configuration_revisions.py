"""Regression tests for encrypted configuration revisions and audit boundaries."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from datetime import datetime, timezone

_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())


async def _noop_async(*_args, **_kwargs):
    return None


_deps.assert_project_access = getattr(_deps, "assert_project_access", _noop_async)
_deps.get_project_role = getattr(_deps, "get_project_role", _noop_async)
_deps.require_engineer = getattr(_deps, "require_engineer", lambda: None)

from fastapi import HTTPException

from app.api.v1 import configuration_center
from app.core.encryption import decrypt, encrypt
from app.models.ai_llm_config import AILLMConfig
from app.models.audit import AuditLog
from app.models.bootstrap import load_all_models
from app.models.configuration_revision import ConfigurationRevision
from app.models.environment import Environment, EnvVariable
from app.models.performance_node import PerformanceNode
from app.models.user import User, UserRole
from app.schemas.configuration_center import ConfigurationRevisionCreateIn

load_all_models()


class _Result:
    def __init__(self, rows=(), scalar=None):
        self._rows = list(rows)
        self._scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one_or_none(self):
        return self._scalar


class _DB:
    def __init__(self, objects=(), variables=(), revisions=()):
        self.objects = {(type(item), item.id): item for item in objects}
        self.variables = list(variables)
        self.revisions = list(revisions)
        self.added: list[object] = []
        self.flush_count = 0
        self.commit_count = 0

    async def get(self, model, resource_id):
        return self.objects.get((model, resource_id))

    async def execute(self, statement):
        entities = {item.get("entity") for item in statement.column_descriptions}
        if EnvVariable in entities:
            return _Result(self.variables)
        if ConfigurationRevision in entities:
            return _Result(self.revisions)
        return _Result([])

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, ConfigurationRevision):
            obj.id = 100 + len([item for item in self.added if isinstance(item, ConfigurationRevision)])
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = obj.created_at
            self.objects[(ConfigurationRevision, obj.id)] = obj

    async def flush(self):
        self.flush_count += 1

    async def commit(self):
        self.commit_count += 1

    async def refresh(self, _obj):
        return None


def _user(role: UserRole) -> User:
    return User(id=7, username="operator", email="operator@example.com", hashed_password="hash", role=role)


def test_create_revision_encrypts_raw_payload_and_returns_only_redacted_payload():
    environment = Environment(id=1, name="staging", project_id=10, description="safe")
    variable = EnvVariable(id=2, env_id=1, key="PASSWORD", value=encrypt("s3cr3t"), is_secret=True)
    db = _DB(objects=[environment], variables=[variable])

    result = asyncio.run(
        configuration_center.create_configuration_revision(
            body=ConfigurationRevisionCreateIn(domain="environment", resource_id=1, reason="发布前备份"),
            db=db,
            user=_user(UserRole.admin),
        )
    )

    assert result.redacted_payload["resource"]["variables"][0]["value"] == "******"
    assert "s3cr3t" not in str(result.model_dump())
    assert result.reason == "发布前备份"
    revision = next(item for item in db.added if isinstance(item, ConfigurationRevision))
    audit = next(item for item in db.added if isinstance(item, AuditLog))
    assert revision.payload_encrypted != ""
    assert "s3cr3t" not in revision.payload_encrypted
    assert "发布前备份" not in (audit.detail or "")
    assert "s3cr3t" not in (audit.detail or "")
    assert db.commit_count == 1


def test_non_admin_cannot_snapshot_ai_configuration():
    ai = AILLMConfig(
        id=1,
        name="restricted",
        provider="ollama",
        api_key_encrypted="",
        model_name="local",
        enabled=True,
    )
    db = _DB(objects=[ai])

    try:
        asyncio.run(
            configuration_center.create_configuration_revision(
                body=ConfigurationRevisionCreateIn(domain="ai_llm", resource_id=1),
                db=db,
                user=_user(UserRole.engineer),
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("非管理员不应创建 AI 配置版本")


def test_plaintext_environment_variable_is_not_marked_as_ciphertext():
    environment = Environment(id=1, name="staging", project_id=10, description="safe")
    variable = EnvVariable(id=2, env_id=1, key="BASE_URL", value="https://example.test", is_secret=False)
    db = _DB(objects=[environment], variables=[variable])

    asyncio.run(
        configuration_center.create_configuration_revision(
            body=ConfigurationRevisionCreateIn(domain="environment", resource_id=1),
            db=db,
            user=_user(UserRole.admin),
        )
    )

    revision = next(item for item in db.added if isinstance(item, ConfigurationRevision))
    payload = json.loads(decrypt(revision.payload_encrypted))
    snapshot_variable = payload["resource"]["variables"][0]
    assert snapshot_variable["value"] == "https://example.test"
    assert "stored_ciphertext" not in snapshot_variable
    redacted = next(item for item in db.added if isinstance(item, ConfigurationRevision)).redacted_payload
    assert redacted["resource"]["variables"][0]["value"] == "******"


def test_revision_list_rejects_ambiguous_resource_filter_and_admin_domains():
    db = _DB()
    engineer = _user(UserRole.engineer)

    for kwargs, expected_status in (
        ({"resource_id": 1}, 422),
        ({"domain": "ai_llm"}, 403),
    ):
        try:
            asyncio.run(
                configuration_center.list_configuration_revisions(
                    project_id=None,
                    resource_id=kwargs.get("resource_id"),
                    domain=kwargs.get("domain"),
                    limit=50,
                    db=db,
                    user=engineer,
                )
            )
        except HTTPException as exc:
            assert exc.status_code == expected_status
        else:
            raise AssertionError(f"应拒绝过滤条件: {kwargs}")


def test_revision_diff_returns_safe_field_changes_and_impacts():
    environment = Environment(id=1, name="staging", project_id=10, description="safe")
    base_url = EnvVariable(id=2, env_id=1, key="TIMEOUT_SECONDS", value="10", is_secret=False)
    password = EnvVariable(id=3, env_id=1, key="PASSWORD", value=encrypt("old-secret"), is_secret=True)
    db = _DB(objects=[environment], variables=[base_url, password])

    asyncio.run(
        configuration_center.create_configuration_revision(
            body=ConfigurationRevisionCreateIn(domain="environment", resource_id=1),
            db=db,
            user=_user(UserRole.admin),
        )
    )
    revision = next(item for item in db.added if isinstance(item, ConfigurationRevision))
    base_url.value = "20"
    password.value = encrypt("new-secret")

    result = asyncio.run(
        configuration_center.diff_configuration_revision(
            revision_id=revision.id,
            db=db,
            user=_user(UserRole.admin),
        )
    )

    assert result.current_available is True
    assert result.current_status == "available"
    assert result.changed is True
    assert result.sensitive_changed_field_count == 1
    assert result.impacts[0].code == "environment_execution"
    assert any(
        change.path.endswith("variables[0].value")
        and change.sensitive is False
        and change.before == "10"
        and change.after == "20"
        for change in result.changes
    )
    secret_changes = [change for change in result.changes if change.sensitive]
    assert len(secret_changes) == 1
    assert secret_changes[0].before is None
    assert secret_changes[0].after is None
    assert "old-secret" not in str(result.model_dump())
    assert "new-secret" not in str(result.model_dump())


def test_revision_diff_allows_project_view_read_without_editor_requirement(monkeypatch):
    environment = Environment(id=1, name="staging", project_id=10, description="safe")
    variable = EnvVariable(id=2, env_id=1, key="BASE_URL", value="https://example.test", is_secret=False)
    db = _DB(objects=[environment], variables=[variable])
    asyncio.run(
        configuration_center.create_configuration_revision(
            body=ConfigurationRevisionCreateIn(domain="environment", resource_id=1),
            db=db,
            user=_user(UserRole.admin),
        )
    )
    revision = next(item for item in db.added if isinstance(item, ConfigurationRevision))
    calls = []

    async def record_access(_db, _user, _project_id, role):
        calls.append(role)

    monkeypatch.setattr(configuration_center, "assert_project_access", record_access)
    from app.services import configuration_snapshots

    monkeypatch.setattr(configuration_snapshots, "assert_project_access", record_access)
    asyncio.run(
        configuration_center.diff_configuration_revision(
            revision_id=revision.id,
            db=db,
            user=_user(UserRole.engineer),
        )
    )

    assert calls
    assert all(role.value == "viewer" for role in calls)
    result = asyncio.run(
        configuration_center.diff_configuration_revision(
            revision_id=revision.id,
            db=db,
            user=_user(UserRole.admin),
        )
    )
    assert result.changed is False
    assert result.impacts == []


def test_revision_diff_reports_missing_current_resource_without_payload():
    environment = Environment(id=1, name="staging", project_id=10, description="safe")
    variable = EnvVariable(id=2, env_id=1, key="PASSWORD", value=encrypt("gone-secret"), is_secret=True)
    db = _DB(objects=[environment], variables=[variable])
    asyncio.run(
        configuration_center.create_configuration_revision(
            body=ConfigurationRevisionCreateIn(domain="environment", resource_id=1),
            db=db,
            user=_user(UserRole.admin),
        )
    )
    revision = next(item for item in db.added if isinstance(item, ConfigurationRevision))
    db.objects.pop((Environment, environment.id))

    result = asyncio.run(
        configuration_center.diff_configuration_revision(
            revision_id=revision.id,
            db=db,
            user=_user(UserRole.admin),
        )
    )

    assert result.current_available is False
    assert result.current_status == "missing"
    assert result.changed is True
    assert result.changes == []
    assert "gone-secret" not in str(result.model_dump())


def test_non_admin_cannot_diff_ai_revision():
    ai = AILLMConfig(
        id=1,
        name="restricted",
        provider="ollama",
        api_key_encrypted=encrypt("ai-secret"),
        model_name="local",
        enabled=True,
    )
    db = _DB(objects=[ai])
    asyncio.run(
        configuration_center.create_configuration_revision(
            body=ConfigurationRevisionCreateIn(domain="ai_llm", resource_id=1),
            db=db,
            user=_user(UserRole.admin),
        )
    )
    revision = next(item for item in db.added if isinstance(item, ConfigurationRevision))

    try:
        asyncio.run(
            configuration_center.diff_configuration_revision(
                revision_id=revision.id,
                db=db,
                user=_user(UserRole.engineer),
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("非管理员不应查看 AI 配置差异")


def test_revision_diff_rejects_tampered_historical_fingerprint():
    environment = Environment(id=1, name="staging", project_id=10, description="safe")
    variable = EnvVariable(id=2, env_id=1, key="TIMEOUT_SECONDS", value="10", is_secret=False)
    db = _DB(objects=[environment], variables=[variable])
    asyncio.run(
        configuration_center.create_configuration_revision(
            body=ConfigurationRevisionCreateIn(domain="environment", resource_id=1),
            db=db,
            user=_user(UserRole.admin),
        )
    )
    revision = next(item for item in db.added if isinstance(item, ConfigurationRevision))
    revision.fingerprint = "0" * 64

    try:
        asyncio.run(
            configuration_center.diff_configuration_revision(
                revision_id=revision.id,
                db=db,
                user=_user(UserRole.admin),
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "校验失败" in str(exc.detail)
    else:
        raise AssertionError("篡改后的配置版本不应通过差异校验")


def test_engineer_can_create_performance_node_revision():
    node = PerformanceNode(
        id=1,
        node_id="perf-local",
        name="本地性能节点",
        queue_name="performance",
        labels={"region": "local"},
        capabilities={"executors": ["k6"]},
        egress_allowlist=["https://example.test"],
        enabled=True,
    )
    db = _DB(objects=[node])

    result = asyncio.run(
        configuration_center.create_configuration_revision(
            body=ConfigurationRevisionCreateIn(domain="performance_node", resource_id=1),
            db=db,
            user=_user(UserRole.engineer),
        )
    )

    assert result.domain == "performance_node"
    assert result.project_id is None
    assert result.redacted_payload["resource"]["egress_allowlist"] == {"count": 1}
