"""补齐 configuration_rollbacks.py 未覆盖分支：字段校验、各配置域恢复函数与主流程边界。

基线：test_configuration*.py（center + revisions 合并测量）54.95%，missing 82 行 /
partial 19 分支。本文件只用 fake DB / SimpleNamespace / monkeypatch 直调服务层函数，
不依赖真实 PG / Redis / MinIO，可独立运行。
"""

import asyncio
from types import SimpleNamespace

import pytest

from app.core.encryption import decrypt, decrypt_config
from app.models.bootstrap import load_all_models
from app.models.environment import Environment, EnvVariable
from app.models.global_variable import GlobalVariable, ScopeType
from app.models.notification import NotificationConfig, NotifyChannel
from app.models.performance_node import PerformanceNode
from app.models.storage_policy import StoragePolicy
from app.services import configuration_rollbacks as crb
from app.services.configuration_diffs import ConfigurationRevisionIntegrityError
from app.services.configuration_snapshots import (
    ConfigurationSnapshotNotFound,
    ConfigurationSnapshotUnsupported,
)

load_all_models()


class _FakeResult:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeDB:
    """最小异步会话：get / execute 返回预置数据，写操作只记录调用。"""

    def __init__(self, *, get_value=None, existing_variables=()):
        self.get_value = get_value
        self.existing_variables = list(existing_variables)
        self.added = []
        self.deleted = []
        self.flushes = 0
        self.get_calls = []
        self.executed_statements = []

    async def get(self, model, resource_id, **kwargs):
        self.get_calls.append((model, resource_id, dict(kwargs)))
        return self.get_value

    async def execute(self, statement):
        self.executed_statements.append(statement)
        return _FakeResult(self.existing_variables)

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def flush(self):
        self.flushes += 1


def _snapshot(**overrides):
    values = {
        "domain": "storage_policy",
        "resource_id": 1,
        "project_id": None,
        "resource_name": "资源",
        "payload": {},
        "redacted_payload": {},
        "fingerprint": "fp-current",
        "payload_encrypted": "encrypted",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _loader(*snapshots):
    pending = list(snapshots)

    async def _load(*_args, **_kwargs):
        return pending.pop(0)

    return _load


def _user():
    return SimpleNamespace(id=7, username="operator")


# ---- 字段校验辅助函数 ----


def test_resource_rejects_non_mapping_payload():
    assert crb._resource({"resource": {"name": "x"}}) == {"name": "x"}
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._resource({"resource": ["not-a-dict"]})


def test_text_validates_required_length_and_optional_fields():
    assert crb._text({"name": "n"}, "name") == "n"
    assert crb._text({}, "description", required=False) is None
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._text({}, "name")
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._text({"name": "   "}, "name")
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._text({"name": 123}, "name")
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._text({"name": "x" * 65}, "name", max_length=64)


def test_bool_rejects_non_boolean():
    assert crb._bool({"enabled": True}, "enabled") is True
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._bool({"enabled": "yes"}, "enabled")


def test_int_or_none_accepts_positive_int_and_rejects_invalid():
    assert crb._int_or_none({"max_vus": 7}, "max_vus") == 7
    assert crb._int_or_none({}, "max_vus") is None
    for invalid in (True, "7", 0, -2):
        with pytest.raises(ConfigurationRevisionIntegrityError):
            crb._int_or_none({"max_vus": invalid}, "max_vus")


def test_dict_rejects_non_mapping():
    assert crb._dict({"labels": {"a": 1}}, "labels") == {"a": 1}
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._dict({"labels": ["a"]}, "labels")


def test_string_list_rejects_non_list_or_non_string_items():
    assert crb._string_list({"egress_allowlist": ["a", "b"]}, "egress_allowlist") == ["a", "b"]
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._string_list({"egress_allowlist": "a"}, "egress_allowlist")
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._string_list({"egress_allowlist": ["a", 1]}, "egress_allowlist")


def test_encrypted_value_requires_string_and_respects_markers():
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._encrypted_value({"value": 123}, "value")
    assert crb._encrypted_value({"value": "stored", "stored_ciphertext": True}, "value") == "stored"
    assert crb._encrypted_value({"value": ""}, "value") == ""
    encrypted = crb._encrypted_value({"value": "plain"}, "value")
    assert encrypted != "plain"
    assert decrypt(encrypted) == "plain"
    assert crb._encrypted_value({"api_key": "stored", "api_key_stored_ciphertext": True}, "api_key") == "stored"
    assert decrypt(crb._encrypted_value({"api_key": "secret"}, "api_key")) == "secret"


def test_validate_revision_target_checks_domain_and_resource():
    revision = SimpleNamespace(domain="environment", resource_id=5)
    resource = {"name": "x"}
    payload = {"domain": "environment", "resource_id": 5, "resource": resource}
    assert crb._validate_revision_target(revision, payload) == resource
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._validate_revision_target(revision, {"domain": "environment", "resource_id": 6, "resource": resource})
    with pytest.raises(ConfigurationRevisionIntegrityError):
        crb._validate_revision_target(revision, {"domain": "ai_llm", "resource_id": 5, "resource": resource})


def test_historical_project_id_rejects_invalid_values():
    assert crb._historical_project_id_from_resource({"project_id": 9}) == 9
    for invalid in (True, 0, -1, "9", None):
        with pytest.raises(ConfigurationRevisionIntegrityError):
            crb._historical_project_id_from_resource({"project_id": invalid})


# ---- _restore_environment ----


def test_restore_environment_updates_creates_and_deletes_variables():
    item = Environment(id=1, name="旧环境", description="旧描述", project_id=10)
    keep = EnvVariable(id=2, env_id=1, key="KEEP", value="old", is_secret=False)
    drop = EnvVariable(id=3, env_id=1, key="DROP", value="x", is_secret=False)
    db = _FakeDB(existing_variables=[keep, drop])
    resource = {
        "project_id": 10,
        "name": "新环境",
        "description": None,
        "variables": [
            {"key": "KEEP", "value": "new", "is_secret": False},
            {"key": "SECRET", "value": "s3cr3t", "is_secret": True},
            {"key": "CIPHER", "value": "enc-blob", "is_secret": True, "stored_ciphertext": True},
            {"key": "BLANK", "value": "", "is_secret": True},
        ],
    }

    asyncio.run(crb._restore_environment(db, item, resource))

    assert item.name == "新环境"
    assert item.description is None
    assert keep.value == "new"
    added = {variable.key: variable for variable in db.added}
    assert decrypt(added["SECRET"].value) == "s3cr3t"
    assert added["CIPHER"].value == "enc-blob"
    assert added["BLANK"].value == ""
    assert db.deleted == [drop]


def test_restore_environment_rejects_project_change():
    item = Environment(id=1, name="旧环境", project_id=10)
    resource = {"project_id": 99, "name": "x", "variables": []}
    with pytest.raises(crb.ConfigurationRollbackConflict):
        asyncio.run(crb._restore_environment(_FakeDB(), item, resource))


def test_restore_environment_rejects_invalid_variables_container():
    item = Environment(id=1, name="旧环境", project_id=10)
    base = {"project_id": 10, "name": "环境"}
    with pytest.raises(ConfigurationRevisionIntegrityError):
        asyncio.run(crb._restore_environment(_FakeDB(), item, {**base, "variables": "not-a-list"}))
    too_many = [{"key": "K", "value": "", "is_secret": False}] * 201
    with pytest.raises(ConfigurationRevisionIntegrityError):
        asyncio.run(crb._restore_environment(_FakeDB(), item, {**base, "variables": too_many}))


def test_restore_environment_rejects_invalid_variable_fields():
    item = Environment(id=1, name="旧环境", project_id=10)
    base = {"project_id": 10, "name": "环境"}
    invalid_cases = [
        ["not-a-dict"],
        [{"key": "bad key!", "value": "", "is_secret": False}],
        [{"key": "OK", "value": 1, "is_secret": False}],
        [{"key": "OK", "value": "", "is_secret": "yes"}],
        [{"key": "DUP", "value": "", "is_secret": False}, {"key": "DUP", "value": "", "is_secret": False}],
    ]
    for variables in invalid_cases:
        with pytest.raises(ConfigurationRevisionIntegrityError):
            asyncio.run(crb._restore_environment(_FakeDB(), item, {**base, "variables": variables}))


# ---- _restore_global_variable ----


def test_restore_global_variable_validates_project_and_scope():
    item = GlobalVariable(
        id=1, scope_type=ScopeType.project, project_id=10, key="K", value_encrypted="", is_secret=False
    )
    with pytest.raises(ConfigurationRevisionIntegrityError):
        asyncio.run(crb._restore_global_variable(_FakeDB(), item, {"project_id": True}))
    with pytest.raises(crb.ConfigurationRollbackConflict):
        asyncio.run(crb._restore_global_variable(_FakeDB(), item, {"project_id": 11}))
    with pytest.raises(ConfigurationRevisionIntegrityError):
        asyncio.run(crb._restore_global_variable(_FakeDB(), item, {"project_id": 10, "scope_type": "unsupported"}))
    with pytest.raises(crb.ConfigurationRollbackConflict):
        asyncio.run(crb._restore_global_variable(_FakeDB(), item, {"project_id": 10, "scope_type": "global"}))

    global_item = GlobalVariable(
        id=2, scope_type=ScopeType.global_scope, project_id=None, key="G", value_encrypted="", is_secret=False
    )
    with pytest.raises(crb.ConfigurationRollbackConflict):
        asyncio.run(crb._restore_global_variable(_FakeDB(), global_item, {"project_id": None, "scope_type": "project"}))


def test_restore_global_variable_restores_values():
    item = GlobalVariable(
        id=1,
        scope_type=ScopeType.project,
        project_id=10,
        key="OLD_KEY",
        value_encrypted="old",
        is_secret=False,
        description="旧",
    )
    resource = {
        "project_id": 10,
        "scope_type": "project",
        "key": "NEW_KEY",
        "value": "rotated",
        "is_secret": True,
        "description": None,
    }

    asyncio.run(crb._restore_global_variable(_FakeDB(), item, resource))

    assert item.scope_type == ScopeType.project
    assert item.key == "NEW_KEY"
    assert item.is_secret is True
    assert item.description is None
    assert decrypt(item.value_encrypted) == "rotated"

    stored = GlobalVariable(
        id=2, scope_type=ScopeType.global_scope, project_id=None, key="G", value_encrypted="", is_secret=False
    )
    asyncio.run(
        crb._restore_global_variable(
            _FakeDB(),
            stored,
            {
                "project_id": None,
                "scope_type": "global",
                "key": "G2",
                "value": "enc-blob",
                "is_secret": False,
                "stored_ciphertext": True,
            },
        )
    )
    assert stored.value_encrypted == "enc-blob"


# ---- _restore_storage ----


def test_restore_storage_requires_retention_days():
    item = StoragePolicy(id=1, name="策略", prefix="reports/", retention_days=30, enabled=True)
    with pytest.raises(ConfigurationRevisionIntegrityError):
        asyncio.run(crb._restore_storage(_FakeDB(), item, {"name": "策略", "prefix": "reports/", "enabled": True}))


def test_restore_storage_rejects_invalid_max_size_gb():
    item = StoragePolicy(id=1, name="策略", prefix="reports/", retention_days=30, enabled=True)
    base = {"name": "策略", "prefix": "reports/", "retention_days": 30, "enabled": True}
    for invalid in (True, -1, "10"):
        with pytest.raises(ConfigurationRevisionIntegrityError):
            asyncio.run(crb._restore_storage(_FakeDB(), item, {**base, "max_size_gb": invalid}))


def test_restore_storage_restores_values():
    item = StoragePolicy(
        id=1, name="旧", prefix="old/", retention_days=30, max_size_gb=5, enabled=False, description="旧"
    )
    resource = {
        "name": "报告",
        "prefix": "reports/",
        "retention_days": 90,
        "max_size_gb": None,
        "enabled": True,
        "description": None,
    }

    asyncio.run(crb._restore_storage(_FakeDB(), item, resource))

    assert item.name == "报告"
    assert item.prefix == "reports/"
    assert item.retention_days == 90
    assert item.max_size_gb is None
    assert item.enabled is True
    assert item.description is None

    asyncio.run(crb._restore_storage(_FakeDB(), item, {**resource, "max_size_gb": 12.5}))
    assert item.max_size_gb == 12.5


# ---- _restore_notification ----


def test_restore_notification_validates_project_and_channel():
    item = NotificationConfig(
        id=1, name="告警", project_id=10, channel=NotifyChannel.dingtalk, is_enabled=True, config={}
    )
    with pytest.raises(crb.ConfigurationRollbackConflict):
        asyncio.run(crb._restore_notification(_FakeDB(), item, {"project_id": 11}))
    with pytest.raises(ConfigurationRevisionIntegrityError):
        asyncio.run(crb._restore_notification(_FakeDB(), item, {"project_id": 10, "channel": "unknown"}))


def test_restore_notification_restores_values():
    item = NotificationConfig(id=1, name="旧", project_id=10, channel=NotifyChannel.email, is_enabled=True, config={})
    resource = {
        "project_id": 10,
        "channel": "feishu",
        "name": "新告警",
        "is_enabled": False,
        "config": {"webhook_url": "https://example.test/hook", "retry": 3},
    }

    asyncio.run(crb._restore_notification(_FakeDB(), item, resource))

    assert item.channel == NotifyChannel.feishu
    assert item.name == "新告警"
    assert item.is_enabled is False
    assert item.config["retry"] == 3
    assert item.config["webhook_url"] != "https://example.test/hook"
    assert decrypt_config(item.config)["webhook_url"] == "https://example.test/hook"


# ---- _restore_performance_node ----


def test_restore_performance_node_rejects_invalid_identifier():
    item = PerformanceNode(id=1, node_id="perf-1", name="节点", queue_name="performance", enabled=True)
    with pytest.raises(ConfigurationRevisionIntegrityError):
        asyncio.run(crb._restore_performance_node(_FakeDB(), item, {"node_id": "节点 一"}))


def test_restore_performance_node_applies_values_and_disabled_status():
    item = PerformanceNode(id=1, node_id="perf-1", name="旧", queue_name="performance", status="online", enabled=True)
    resource = {
        "node_id": "perf-2",
        "name": "新节点",
        "queue_name": "performance-v2",
        "enabled": True,
        "labels": {"region": "local"},
        "capabilities": {"executors": ["k6"]},
        "max_vus": 50,
        "max_concurrency": 5,
        "egress_allowlist": ["https://example.test"],
    }

    asyncio.run(crb._restore_performance_node(_FakeDB(), item, resource))

    assert item.node_id == "perf-2"
    assert item.name == "新节点"
    assert item.queue_name == "performance-v2"
    assert item.labels == {"region": "local"}
    assert item.capabilities == {"executors": ["k6"]}
    assert item.max_vus == 50
    assert item.max_concurrency == 5
    assert item.egress_allowlist == ["https://example.test"]
    assert item.status == "online"

    asyncio.run(crb._restore_performance_node(_FakeDB(), item, {**resource, "enabled": False, "max_vus": None}))
    assert item.enabled is False
    assert item.status == "disabled"
    assert item.max_vus is None


# ---- rollback_configuration_revision 主流程 ----


def test_rollback_rejects_unsupported_domain():
    revision = SimpleNamespace(domain="web_asset", resource_id=1, project_id=None, fingerprint="fp", id=1)
    with pytest.raises(ConfigurationSnapshotUnsupported):
        asyncio.run(crb.rollback_configuration_revision(_FakeDB(), _user(), revision))


def test_rollback_reports_missing_current_resource(monkeypatch):
    payload = {"domain": "storage_policy", "resource_id": 1, "resource": {"name": "策略"}}
    revision = SimpleNamespace(domain="storage_policy", resource_id=1, project_id=None, fingerprint="fp", id=11)
    db = _FakeDB(get_value=None)
    monkeypatch.setattr(crb, "decode_configuration_revision_payload", lambda _revision: payload)

    with pytest.raises(ConfigurationSnapshotNotFound):
        asyncio.run(crb.rollback_configuration_revision(db, _user(), revision))

    assert db.get_calls[0][2]["with_for_update"] is True


def test_rollback_rejects_project_scope_mismatch(monkeypatch):
    payload = {"domain": "storage_policy", "resource_id": 1, "resource": {"name": "策略"}}
    revision = SimpleNamespace(domain="storage_policy", resource_id=1, project_id=5, fingerprint="fp", id=11)
    db = _FakeDB(get_value=StoragePolicy(id=1, name="策略", prefix="reports/", retention_days=30, enabled=True))
    monkeypatch.setattr(crb, "decode_configuration_revision_payload", lambda _revision: payload)
    monkeypatch.setattr(crb, "load_configuration_snapshot", _loader(_snapshot(project_id=99)))

    with pytest.raises(crb.ConfigurationRollbackConflict):
        asyncio.run(crb.rollback_configuration_revision(db, _user(), revision))


def test_rollback_conflicts_when_global_variable_project_changed(monkeypatch):
    payload = {
        "domain": "global_variable",
        "resource_id": 3,
        "resource": {"project_id": 99, "scope_type": "project", "key": "K", "value": "", "is_secret": False},
    }
    revision = SimpleNamespace(domain="global_variable", resource_id=3, project_id=10, fingerprint="fp", id=12)
    item = GlobalVariable(
        id=3, scope_type=ScopeType.project, project_id=10, key="K", value_encrypted="", is_secret=False
    )
    db = _FakeDB(get_value=item)
    monkeypatch.setattr(crb, "decode_configuration_revision_payload", lambda _revision: payload)
    monkeypatch.setattr(
        crb,
        "load_configuration_snapshot",
        _loader(_snapshot(domain="global_variable", resource_id=3, project_id=10)),
    )

    with pytest.raises(crb.ConfigurationRollbackConflict):
        asyncio.run(crb.rollback_configuration_revision(db, _user(), revision))


def test_rollback_returns_no_change_when_fingerprint_matches(monkeypatch):
    payload = {
        "domain": "global_variable",
        "resource_id": 3,
        "resource": {"project_id": None, "scope_type": "global", "key": "K", "value": "", "is_secret": False},
    }
    revision = SimpleNamespace(domain="global_variable", resource_id=3, project_id=None, fingerprint="same-fp", id=13)
    item = GlobalVariable(
        id=3, scope_type=ScopeType.global_scope, project_id=None, key="K", value_encrypted="", is_secret=False
    )
    db = _FakeDB(get_value=item)
    monkeypatch.setattr(crb, "decode_configuration_revision_payload", lambda _revision: payload)
    monkeypatch.setattr(
        crb,
        "load_configuration_snapshot",
        _loader(_snapshot(domain="global_variable", resource_id=3, project_id=None, fingerprint="same-fp")),
    )

    result = asyncio.run(crb.rollback_configuration_revision(db, _user(), revision))

    assert result.changed is False
    assert result.revision is revision
    assert result.source_revision_id == 13
    assert result.message == "当前配置已是目标版本，无需恢复"
    assert db.added == []
    assert db.flushes == 0
