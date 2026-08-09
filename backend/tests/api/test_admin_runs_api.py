import asyncio
import inspect
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.api.conftest import fake_require_admin as _fake_require_admin


sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    require_admin=_fake_require_admin,
    require_engineer=lambda: None,
    get_current_user=lambda: None,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)
_minio = sys.modules.setdefault("app.core.minio_client", types.SimpleNamespace())
_minio.list_objects = lambda prefix: []
_minio.delete_file = lambda object_name: None

from app.api.v1 import admin_runs


class _FakeAsyncDB:
    async def run_sync(self, fn):
        return fn(object())


def _sample_dict(**overrides):
    base = {
        "cutoff": datetime(2026, 5, 1, tzinfo=timezone.utc),
        "retention_days": 90,
        "plan_runs": 1,
        "suite_runs": 2,
        "test_runs": 3,
        "mobile_runs": 4,
    }
    base.update(overrides)
    return base


def test_admin_runs_endpoints_require_admin():
    preview_dep = inspect.signature(admin_runs.runs_retention_preview).parameters["_"].default.dependency
    per_project_dep = (
        inspect.signature(admin_runs.runs_retention_per_project_preview).parameters["_"].default.dependency
    )
    execute_dep = inspect.signature(admin_runs.runs_retention_run).parameters["_"].default.dependency
    assert preview_dep is _fake_require_admin
    assert per_project_dep is _fake_require_admin
    assert execute_dep is _fake_require_admin


def test_preview_endpoint_delegates_to_service(monkeypatch):
    captured = {}

    def fake_preview(_session, effective_days):
        captured["days"] = effective_days
        return _sample_dict(estimated_objects=10, retention_days=effective_days)

    monkeypatch.setattr(admin_runs, "preview_old_runs", fake_preview)

    result = asyncio.run(admin_runs.runs_retention_preview(days=30, db=_FakeAsyncDB(), _=None))
    assert captured["days"] == 30
    assert result.plan_runs == 1
    assert result.estimated_objects == 10
    assert result.retention_days == 30


def test_preview_uses_default_days_when_omitted(monkeypatch):
    captured = {}

    def fake_preview(_session, effective_days):
        captured["days"] = effective_days
        return _sample_dict(estimated_objects=0, retention_days=effective_days)

    monkeypatch.setattr(admin_runs, "preview_old_runs", fake_preview)
    monkeypatch.setattr(admin_runs.settings, "RUN_RETENTION_DAYS", 120)

    asyncio.run(admin_runs.runs_retention_preview(days=None, db=_FakeAsyncDB(), _=None))
    assert captured["days"] == 120


def test_execute_endpoint_delegates_to_service(monkeypatch):
    captured = {}

    def fake_execute(_session, *, days, batch_size):
        captured["days"] = days
        captured["batch_size"] = batch_size
        return _sample_dict(deleted_objects=5, retention_days=days)

    monkeypatch.setattr(admin_runs, "execute_old_runs_cleanup", fake_execute)
    monkeypatch.setattr(admin_runs.settings, "RUN_CLEANUP_BATCH_SIZE", 250)

    body = admin_runs.RunRetentionExecuteIn(days=60)
    result = asyncio.run(admin_runs.runs_retention_run(body=body, db=_FakeAsyncDB(), _=None))

    assert captured["days"] == 60
    assert captured["batch_size"] == 250
    assert result.test_runs == 3
    assert result.deleted_objects == 5


def test_execute_uses_default_days_when_body_days_none(monkeypatch):
    captured = {}

    def fake_execute(_session, *, days, batch_size):
        captured["days"] = days
        return _sample_dict(deleted_objects=0, retention_days=days)

    monkeypatch.setattr(admin_runs, "execute_old_runs_cleanup", fake_execute)
    monkeypatch.setattr(admin_runs.settings, "RUN_RETENTION_DAYS", 90)

    body = admin_runs.RunRetentionExecuteIn(days=None)
    asyncio.run(admin_runs.runs_retention_run(body=body, db=_FakeAsyncDB(), _=None))
    assert captured["days"] == 90
