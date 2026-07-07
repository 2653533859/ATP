import asyncio
import inspect
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.api.conftest import fake_require_admin as _fake_require_admin
from tests.api.conftest import fake_require_engineer as _fake_require_engineer


sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    require_admin=_fake_require_admin,
    require_engineer=_fake_require_engineer,
    get_current_user=lambda: None,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)
sys.modules["app.core.minio_client"] = types.SimpleNamespace(
    list_objects=lambda prefix: [],
    delete_file=lambda object_name: None,
)
sys.modules["app.services.storage_alerts"] = types.SimpleNamespace(
    get_current_alert=lambda: None,
)

# 创建 ORM 实例前需要让 SQLAlchemy mapper 完成全量配置
from app.models.bootstrap import load_all_models

load_all_models()

from app.api.v1 import storage
from app.schemas.storage_policy import StoragePolicyCreateIn, StoragePolicyUpdateIn


class _AwaitableResult:
    """模拟 await db.execute(...) 的链式调用结果。"""

    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _AsyncDB:
    def __init__(self):
        self.added: list[object] = []
        self.commit_calls = 0
        self.refresh_calls = 0
        self.delete_calls: list[object] = []
        self.get_value = None
        self._execute_rows: list[object] = []

    def set_get(self, value):
        self.get_value = value

    def set_execute_rows(self, rows):
        self._execute_rows = list(rows)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commit_calls += 1

    async def refresh(self, obj):
        self.refresh_calls += 1

    async def execute(self, stmt):
        return _AwaitableResult(self._execute_rows)

    async def get(self, model, pk):
        return self.get_value

    async def delete(self, obj):
        self.delete_calls.append(obj)

    async def rollback(self):
        pass


def test_policy_endpoints_require_admin():
    for fn in (
        storage.list_storage_policies,
        storage.create_storage_policy,
        storage.update_storage_policy,
        storage.delete_storage_policy,
    ):
        dep = inspect.signature(fn).parameters["_"].default.dependency
        assert dep is _fake_require_admin


def test_create_policy_normalizes_prefix_and_persists():
    db = _AsyncDB()
    body = StoragePolicyCreateIn(name="logs", prefix="logs", retention_days=14)

    result = asyncio.run(storage.create_storage_policy(body=body, db=db, _=None))

    assert db.added and db.added[0] is result
    assert result.prefix == "logs/"
    assert result.retention_days == 14
    assert db.commit_calls == 1
    assert db.refresh_calls == 1


def test_update_policy_404_when_missing():
    db = _AsyncDB()
    db.set_get(None)
    body = StoragePolicyUpdateIn(retention_days=7)

    try:
        asyncio.run(storage.update_storage_policy(policy_id=99, body=body, db=db, _=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("应抛 404")


def test_update_policy_applies_partial_fields():
    db = _AsyncDB()

    class FakePolicy:
        def __init__(self):
            self.prefix = "screenshots/"
            self.retention_days = 30
            self.enabled = True
            self.name = "screenshots"

    fake = FakePolicy()
    db.set_get(fake)
    body = StoragePolicyUpdateIn(prefix="screens", retention_days=10, enabled=False)

    result = asyncio.run(storage.update_storage_policy(policy_id=1, body=body, db=db, _=None))

    assert result is fake
    assert fake.prefix == "screens/"
    assert fake.retention_days == 10
    assert fake.enabled is False
    assert db.commit_calls == 1


def test_delete_policy_removes_record():
    db = _AsyncDB()

    class FakePolicy:
        pass

    fake = FakePolicy()
    db.set_get(fake)

    result = asyncio.run(storage.delete_storage_policy(policy_id=1, db=db, _=None))

    assert result == {"ok": True}
    assert db.delete_calls == [fake]
    assert db.commit_calls == 1
