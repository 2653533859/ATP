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
_minio = sys.modules.setdefault("app.core.minio_client", types.SimpleNamespace())
_minio.list_objects = lambda prefix: []
_minio.delete_file = lambda object_name: None
sys.modules["app.services.storage_alerts"] = types.SimpleNamespace(
    get_current_alert=lambda: None,
)

from app.api.v1 import storage


class _FakeAsyncDB:
    def __init__(self, result):
        self.result = result

    async def run_sync(self, fn):
        return fn(object())


def test_storage_endpoints_require_expected_dependencies():
    stats_dep = inspect.signature(storage.storage_stats).parameters["_"].default.dependency
    preview_dep = inspect.signature(storage.storage_cleanup_preview).parameters["_"].default.dependency
    execute_dep = inspect.signature(storage.storage_cleanup_execute).parameters["_"].default.dependency

    # 与路由模块实际绑定的依赖对象比较：整套运行时路由可能已被更早的测试文件用另一份 app.api.deps 替身导入，
    # 本文件顶部的 fake 不一定就是 Depends 捕获的那个对象，但“端点依赖 storage.require_admin”这一契约与导入顺序无关。
    assert stats_dep is storage.require_admin
    assert preview_dep is storage.require_engineer
    assert execute_dep is storage.require_admin


def test_storage_stats_delegates_to_service(monkeypatch):
    called = {}

    def fake_stats(_session):
        called["session"] = _session
        return storage.StorageStatsOut(
            bucket="atp",
            total_object_count=3,
            total_bytes=60,
            prefixes=[
                {"prefix": "reports/", "object_count": 1, "total_bytes": 10},
                {"prefix": "screenshots/", "object_count": 2, "total_bytes": 50},
            ],
        )

    monkeypatch.setattr(storage, "get_storage_stats", fake_stats)

    result = asyncio.run(storage.storage_stats(db=_FakeAsyncDB(None), _=None))

    assert result.total_object_count == 3
    assert result.total_bytes == 60
    assert [item.prefix for item in result.prefixes] == ["reports/", "screenshots/"]
    assert called["session"] is not None


def test_storage_cleanup_preview_delegates_to_service(monkeypatch):
    called = {}

    def fake_preview(_session, *, prefixes, retention_days):
        called["prefixes"] = prefixes
        called["retention_days"] = retention_days
        return storage.StorageCleanupPreviewOut(
            prefixes=prefixes,
            retention_days=retention_days,
            scanned_object_count=1,
            expired_object_count=1,
            deletable_count=1,
            blocked_count=0,
            orphan_reference_count=0,
            deletable_objects=[{"object_name": "reports/a.html", "last_modified": None, "referenced_by_count": 0}],
            blocked_objects=[],
            orphan_references=[],
        )

    monkeypatch.setattr(storage, "preview_storage_cleanup", fake_preview)

    result = asyncio.run(
        storage.storage_cleanup_preview(
            body=storage.StorageCleanupPreviewIn(
                prefixes=["reports/"],
                retention_days=10,
                use_active_policies=False,
            ),
            db=_FakeAsyncDB(None),
            _=None,
        )
    )

    assert result.deletable_count == 1
    assert called == {"prefixes": ["reports/"], "retention_days": 10}


def test_storage_cleanup_execute_delegates_to_service(monkeypatch):
    called = {}

    def fake_execute(_session, *, object_names, prefixes, repair_orphan_references):
        called["object_names"] = object_names
        called["prefixes"] = prefixes
        called["repair_orphan_references"] = repair_orphan_references
        return storage.StorageCleanupExecuteOut(
            requested_count=1,
            deleted_count=1,
            skipped_referenced_count=0,
            missing_count=0,
            repaired_reference_count=0,
            deleted_objects=["reports/a.html"],
            skipped_objects=[],
            repaired_references=[],
        )

    monkeypatch.setattr(storage, "execute_storage_cleanup", fake_execute)

    result = asyncio.run(
        storage.storage_cleanup_execute(
            body=storage.StorageCleanupExecuteIn(object_names=["reports/a.html"], repair_orphan_references=True),
            db=_FakeAsyncDB(None),
            _=None,
        )
    )

    assert result.deleted_objects == ["reports/a.html"]
    assert called == {
        "object_names": ["reports/a.html"],
        "prefixes": None,
        "repair_orphan_references": True,
    }


def test_get_storage_media_requires_auth_and_blocks_sensitive_prefixes(monkeypatch):
    import sys
    from fastapi import HTTPException
    import pytest

    media_dep = inspect.signature(storage.get_storage_media).parameters["_"].default.dependency
    assert media_dep is storage.get_current_user

    with pytest.raises(HTTPException) as exc_traversal:
        asyncio.run(storage.get_storage_media("screenshots/../secret.txt", _=None))
    assert exc_traversal.value.status_code == 400

    with pytest.raises(HTTPException) as exc_forbidden:
        asyncio.run(storage.get_storage_media("storage-states/projects/1/default.json", _=None))
    assert exc_forbidden.value.status_code == 403

    minio_mod = sys.modules["app.core.minio_client"]
    monkeypatch.setattr(minio_mod, "read_bytes", lambda _obj: b"png-bytes", raising=False)
    res = asyncio.run(storage.get_storage_media("screenshots/runs/1/step_0.png", _=None))
    assert res.body == b"png-bytes"
    assert res.headers["cache-control"] == "private, max-age=3600"


def test_get_storage_media_allows_new_prefixes_and_disables_inline_svg(monkeypatch):
    import sys
    from types import SimpleNamespace
    from fastapi import HTTPException
    import pytest

    minio_mod = sys.modules["app.core.minio_client"]
    monkeypatch.setattr(minio_mod, "read_bytes", lambda obj: f"bytes:{obj}".encode("utf-8"), raising=False)

    for allowed_obj in (
        "gifs/runs/1/recording.gif",
        "android-artifacts/runs/1/log.txt",
        "ios-artifacts/runs/1/syslog.txt",
        "web-files/runs/1/capture.png",
    ):
        res = asyncio.run(storage.get_storage_media(allowed_obj, _=None))
        assert res.body == f"bytes:{allowed_obj}".encode("utf-8")
        assert res.headers["x-content-type-options"] == "nosniff"

    svg_res = asyncio.run(storage.get_storage_media('reports/run-1/diagram"evil.svg', _=None))
    assert svg_res.headers["x-content-type-options"] == "nosniff"
    assert svg_res.headers["content-disposition"].startswith('attachment; filename="')
    assert '"' not in svg_res.headers["content-disposition"].split('filename="', 1)[1][:-1]

    class _AccessDB:
        def __init__(self, resolved_project_id):
            self.resolved_project_id = resolved_project_id

        async def execute(self, _stmt):
            return SimpleNamespace(scalar_one_or_none=lambda: self.resolved_project_id)

    async def deny_access(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="无权访问")

    monkeypatch.setattr(storage, "assert_project_access", deny_access)
    with pytest.raises(HTTPException) as exc_denied:
        asyncio.run(
            storage.get_storage_media(
                "screenshots/runs/9/step_0.png",
                _=SimpleNamespace(id=99, role=storage.UserRole.viewer),
                db=_AccessDB(12),
            )
        )
    assert exc_denied.value.status_code == 403
