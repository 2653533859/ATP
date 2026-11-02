"""补齐 projects.py 的未覆盖分支：导入冲突/重命名/AI 绑定、MinIO 异常回滚、审计日志端点与 CSV 防注入。

基线：test_project*.py 合并测量 76.64%（missing 81 / partial 51）。本文件只使用
fake DB 与 monkeypatch，不依赖真实数据库/Redis/MinIO，可独立运行。
"""

import asyncio
import re
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import projects as prj
from app.models.bootstrap import load_all_models
from app.models.user import UserRole
from app.models.user_project import ProjectRole
from app.schemas.project import (
    ModuleUpdate,
    ProjectCopyIn,
    ProjectExportPayload,
    ProjectImportIn,
    ProjectTransferAIModel,
    ProjectTransferDataset,
    ProjectTransferModule,
    ProjectTransferProject,
    ProjectUpdate,
)
from app.schemas.user_project import ProjectMemberUpdateIn
from app.services.dataset_storage import DatasetStorageError

load_all_models()

NOW = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows if rows is not None else []

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    """极简异步会话：execute/scalar 走预置队列，写操作只记录调用。"""

    def __init__(self, objects=None, results=None, scalars=None):
        self.objects = dict(objects or {})
        self.results = list(results or [])
        self.scalar_queue = list(scalars or [])
        self.added = []
        self.deleted = []
        self.commits = 0
        self.rollbacks = 0
        self.execute_calls = 0
        self._next_id = 500

    async def get(self, model, ident):
        value = self.objects.get(model)
        return value(ident) if callable(value) else value

    async def execute(self, _statement):
        self.execute_calls += 1
        return self.results.pop(0) if self.results else _Result()

    async def scalar(self, _statement):
        return self.scalar_queue.pop(0) if self.scalar_queue else None

    def add(self, value):
        if getattr(value, "id", None) is None:
            value.id = self._next_id
            self._next_id += 1
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def flush(self):
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = self._next_id
                self._next_id += 1

    async def refresh(self, value):
        if getattr(value, "created_at", None) is None:
            value.created_at = NOW
        if getattr(value, "updated_at", None) is None:
            value.updated_at = NOW
        return value


async def _noop_async(*_args, **_kwargs):
    return None


@pytest.fixture(autouse=True)
def _stub_stats_cache(monkeypatch):
    monkeypatch.setattr(prj, "invalidate_stats_cache", _noop_async)


def _user(user_id=9, role=UserRole.engineer):
    return SimpleNamespace(id=user_id, username="amy", email="amy@x.com", role=role)


def _project_row(project_id=1, **overrides):
    data = dict(
        id=project_id,
        name="P1",
        project_code="P1",
        description=None,
        owner_id=9,
        ai_llm_config_id=None,
        status="active",
        run_retention_days_override=None,
        created_at=NOW,
        updated_at=NOW,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def _payload(**overrides):
    data = {
        "exported_at": NOW,
        "project": ProjectTransferProject(name="Imported"),
        "modules": [],
        "environments": [],
        "datasets": [],
    }
    data.update(overrides)
    return ProjectExportPayload(**data)


def _audit_row(entry_id=1, **overrides):
    data = dict(
        id=entry_id,
        action="project_created",
        resource_type="project",
        resource_id=1,
        user_id=7,
        username="amy",
        detail=None,
        ip_address="127.0.0.1",
        project_id=5,
        created_at=NOW,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def _minio_payload():
    datasets = [
        ProjectTransferDataset(name="d1", storage_mode="minio", rows=[{"id": 1}]),
        ProjectTransferDataset(name="d2", storage_mode="minio", rows=[{"id": 2}]),
    ]
    return _payload(datasets=datasets)


# ── 预览与导入 ───────────────────────────────────────────────


def test_preview_project_import_warns_about_ai_model_matching():
    ai_model = ProjectTransferAIModel(name="gpt4", provider="openai", model_name="gpt-4o")
    body = ProjectImportIn(payload=_payload(project=ProjectTransferProject(name="AI", ai_model=ai_model)))

    preview = asyncio.run(prj.preview_project_import(body=body, db=_FakeDB(), _=None))

    assert preview.valid is True and preview.conflicts == []
    assert any("仅按模型名称匹配" in warning for warning in preview.warnings)


def test_import_project_conflict_fails_with_409():
    body = ProjectImportIn(payload=_payload(project=ProjectTransferProject(name="Dup", project_code="DUP")))
    db = _FakeDB(results=[_Result(scalar=SimpleNamespace(id=9))])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(prj.import_project(body=body, db=db, current_user=_user()))

    assert exc.value.status_code == 409
    assert exc.value.detail["message"] == "项目编码冲突"
    assert exc.value.detail["conflicts"]


def test_import_project_rename_policy_generates_unique_code():
    body = ProjectImportIn(
        payload=_payload(project=ProjectTransferProject(name="Imported", project_code="DUP")),
        conflict_policy="rename",
    )
    db = _FakeDB(results=[_Result(scalar=SimpleNamespace(id=9)), _Result(scalar=SimpleNamespace(id=9))])

    result = asyncio.run(prj.import_project(body=body, db=db, current_user=_user()))

    assert re.fullmatch(r"IMPO-[0-9A-F]{6}", result.project.project_code)
    assert result.imported == {"modules": 0, "environments": 0, "variables": 0, "datasets": 0}
    assert db.commits == 1


def test_import_project_binds_matching_ai_model_and_stores_db_dataset():
    ai_model = ProjectTransferAIModel(name="gpt4", provider="openai", model_name="gpt-4o")
    payload = _payload(
        project=ProjectTransferProject(name="AI Bound", ai_model=ai_model),
        datasets=[ProjectTransferDataset(name="rows", rows=[{"a": 1}, {"a": 2}])],
    )
    db = _FakeDB(results=[_Result(scalar=None), _Result(scalar=SimpleNamespace(id=42))])

    result = asyncio.run(prj.import_project(body=ProjectImportIn(payload=payload), db=db, current_user=_user()))

    assert result.project.ai_llm_config_id == 42
    stored = [item for item in db.added if item.__class__.__name__ == "TestDataset"]
    assert stored and stored[0].storage_mode == "database"
    assert stored[0].rows == [{"a": 1}, {"a": 2}] and stored[0].row_count == 2
    assert not any("未找到匹配的 AI 模型配置" in warning for warning in result.warnings)


def test_import_project_warns_when_ai_model_missing():
    ai_model = ProjectTransferAIModel(name="gpt4", provider="openai", model_name="gpt-4o")
    payload = _payload(project=ProjectTransferProject(name="AI Miss", ai_model=ai_model))
    db = _FakeDB(results=[_Result(scalar=None), _Result(scalar=None)])

    result = asyncio.run(prj.import_project(body=ProjectImportIn(payload=payload), db=db, current_user=_user()))

    assert result.project.ai_llm_config_id is None
    assert any("未找到匹配的 AI 模型配置" in warning for warning in result.warnings)


def test_import_project_falls_back_for_orphan_module_parent():
    modules = [
        ProjectTransferModule(id=1, name="根", module_code="ROOT"),
        ProjectTransferModule(id=2, name="孤儿", module_code="ORPH", parent_id=999),
    ]
    db = _FakeDB(results=[_Result(scalar=None)])

    result = asyncio.run(
        prj.import_project(body=ProjectImportIn(payload=_payload(modules=modules)), db=db, current_user=_user())
    )

    assert result.imported["modules"] == 2
    added = {item.name: item for item in db.added if item.__class__.__name__ == "Module"}
    assert added["根"].parent_id is None
    assert added["孤儿"].parent_id is None


def test_import_project_minio_failure_rolls_back_and_cleans_objects(monkeypatch):
    uploads = []

    def fake_upload(*, project_id, dataset_id, rows, **_kwargs):
        uploads.append(dataset_id)
        if len(uploads) == 1:
            return "datasets/obj-1.json"
        raise DatasetStorageError("bucket unavailable")

    cleanups = []
    monkeypatch.setattr(prj, "upload_dataset_rows", fake_upload)
    monkeypatch.setattr(prj, "cleanup_dataset_object_names", lambda pid, did, names: cleanups.append((pid, did, names)))
    db = _FakeDB(results=[_Result(scalar=None)])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(prj.import_project(body=ProjectImportIn(payload=_minio_payload()), db=db, current_user=_user()))

    assert exc.value.status_code == 503
    assert "MinIO 数据集导入失败" in exc.value.detail
    assert db.rollbacks == 1
    datasets = [item for item in db.added if item.__class__.__name__ == "TestDataset"]
    assert cleanups == [(db.added[0].id, datasets[0].id, ["datasets/obj-1.json"])]


def test_import_project_generic_failure_rolls_back_and_reraises(monkeypatch):
    uploads = []

    def fake_upload(*, project_id, dataset_id, rows, **_kwargs):
        uploads.append(dataset_id)
        if len(uploads) == 1:
            return "datasets/obj-2.json"
        raise RuntimeError("db commit exploded")

    cleanups = []
    monkeypatch.setattr(prj, "upload_dataset_rows", fake_upload)
    monkeypatch.setattr(prj, "cleanup_dataset_object_names", lambda pid, did, names: cleanups.append((pid, did, names)))
    db = _FakeDB(results=[_Result(scalar=None)])

    with pytest.raises(RuntimeError):
        asyncio.run(prj.import_project(body=ProjectImportIn(payload=_minio_payload()), db=db, current_user=_user()))

    assert db.rollbacks == 1
    datasets = [item for item in db.added if item.__class__.__name__ == "TestDataset"]
    assert cleanups == [(db.added[0].id, datasets[0].id, ["datasets/obj-2.json"])]


# ── 项目导出/拷贝/读取/更新 ────────────────────────────────────


def test_export_project_missing_is_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(prj.export_project(project_id=404, db=_FakeDB(), _=None))
    assert exc.value.status_code == 404


def test_export_project_maps_dataset_storage_error_to_503(monkeypatch):
    project = SimpleNamespace(id=1, ai_llm_config_id=None)
    db = _FakeDB(objects={prj.Project: project}, results=[_Result(rows=[]), _Result(rows=[]), _Result(rows=[])])

    def boom(*_args, **_kwargs):
        raise DatasetStorageError("export reader down")

    monkeypatch.setattr(prj, "build_project_export", boom)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(prj.export_project(project_id=1, db=db, _=None))

    assert exc.value.status_code == 503
    assert "MinIO 数据集导出失败" in exc.value.detail


def test_copy_project_missing_is_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            prj.copy_project(project_id=404, body=ProjectCopyIn(name="x"), db=_FakeDB(), current_user=_user(), _=None)
        )
    assert exc.value.status_code == 404


def test_copy_project_orphan_module_becomes_root():
    source = SimpleNamespace(id=1, name="S", description=None, ai_llm_config_id=None, run_retention_days_override=None)
    orphan = SimpleNamespace(id=11, name="孤儿", module_code="ORPH", parent_id=999, sort_order=0)
    db = _FakeDB(objects={prj.Project: source}, results=[_Result(rows=[orphan])])

    copied = asyncio.run(
        prj.copy_project(project_id=1, body=ProjectCopyIn(name="副本"), db=db, current_user=_user(), _=None)
    )

    assert copied.name == "副本" and copied.status == "active"
    module = [item for item in db.added if item.__class__.__name__ == "Module"][0]
    assert module.parent_id is None and module.name == "孤儿"


def test_get_project_returns_row():
    project = _project_row(2)
    result = asyncio.run(prj.get_project(project_id=2, db=_FakeDB(objects={prj.Project: project}), _=None))
    assert result is project


def test_update_project_missing_is_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(prj.update_project(project_id=404, body=ProjectUpdate(name="x"), db=_FakeDB(), _=None))
    assert exc.value.status_code == 404


def test_update_project_skips_code_backfill_when_code_already_present():
    project = _project_row(1, name="old", project_code="EXISTING")
    updated = asyncio.run(
        prj.update_project(
            project_id=1, body=ProjectUpdate(name="new"), db=_FakeDB(objects={prj.Project: project}), _=None
        )
    )
    assert updated.name == "new" and project.project_code == "EXISTING"

    explicit = _project_row(2, name="old2", project_code=None)
    asyncio.run(
        prj.update_project(
            project_id=2,
            body=ProjectUpdate(name="n2", project_code="NEW-1"),
            db=_FakeDB(objects={prj.Project: explicit}),
            _=None,
        )
    )
    assert explicit.project_code == "NEW-1" and explicit.name == "n2"


def test_archive_and_restore_missing_are_404():
    with pytest.raises(HTTPException) as archive_exc:
        asyncio.run(prj.archive_project(project_id=404, db=_FakeDB(), current_user=_user()))
    assert archive_exc.value.status_code == 404

    with pytest.raises(HTTPException) as restore_exc:
        asyncio.run(prj.restore_project(project_id=404, db=_FakeDB(), current_user=_user()))
    assert restore_exc.value.status_code == 404


# ── 模块更新 ─────────────────────────────────────────────────


def test_update_module_success_and_code_backfill(monkeypatch):
    calls = []

    async def fake_access(_db, _user_obj, project_id, role):
        calls.append((project_id, role))

    monkeypatch.setattr(prj, "assert_project_access", fake_access)
    module = SimpleNamespace(id=5, name="old", module_code=None, project_id=8)
    db = _FakeDB(objects={prj.Module: module})

    updated = asyncio.run(
        prj.update_module(module_id=5, body=ModuleUpdate(name="登录模块"), db=db, current_user=_user())
    )

    assert updated is module and module.name == "登录模块"
    assert module.module_code == "MODULE" and calls == [(8, ProjectRole.editor)]
    assert db.commits == 1


def test_update_module_keeps_code_and_accepts_empty_payload(monkeypatch):
    monkeypatch.setattr(prj, "assert_project_access", _noop_async)
    module = SimpleNamespace(id=6, name="old", module_code="KEEP", project_id=8)
    db = _FakeDB(objects={prj.Module: module})

    asyncio.run(prj.update_module(module_id=6, body=ModuleUpdate(name="改名"), db=db, current_user=_user()))
    assert module.module_code == "KEEP" and module.name == "改名"

    empty = SimpleNamespace(id=7, name="unchanged", module_code="E", project_id=8)
    empty_db = _FakeDB(objects={prj.Module: empty})
    asyncio.run(prj.update_module(module_id=7, body=ModuleUpdate(), db=empty_db, current_user=_user()))
    assert empty.name == "unchanged" and empty.module_code == "E"
    assert empty_db.commits == 1


# ── 成员管理补充分支 ─────────────────────────────────────────


def test_update_project_member_demotes_owner_with_backup_and_missing_user(monkeypatch):
    workspace_calls = []
    monkeypatch.setattr(prj, "require_server_workspace", lambda feature: workspace_calls.append(feature))
    up = SimpleNamespace(id=1, user_id=7, role=ProjectRole.owner, created_at=NOW)
    backup = SimpleNamespace(id=2, user_id=8, role=ProjectRole.owner, created_at=NOW)
    db = _FakeDB(results=[_Result(scalar=up), _Result(rows=[up, backup])])

    out = asyncio.run(
        prj.update_project_member(
            project_id=5, user_id=7, body=ProjectMemberUpdateIn(role="editor"), db=db, current_user=_user()
        )
    )

    assert up.role is ProjectRole.editor
    assert out.role == "editor" and out.username == "" and out.email == ""
    assert workspace_calls == ["修改项目成员"]
    assert db.commits == 1


# ── 审计日志：过滤器、CSV 与端点 ──────────────────────────────


def test_audit_log_filters_build_where_clauses_and_validate_window():
    assert prj._audit_log_filters(project_id=None, action=None, user_id=None, created_from=None, created_to=None) == []

    clauses = prj._audit_log_filters(
        project_id=5, action="project_archived", user_id=7, created_from=NOW, created_to=NOW
    )
    assert len(clauses) == 5

    with pytest.raises(HTTPException) as exc:
        prj._audit_log_filters(
            project_id=None, action=None, user_id=None, created_from=NOW, created_to=NOW.replace(year=2025)
        )
    assert exc.value.status_code == 422


def test_audit_log_csv_cell_escapes_formulas():
    assert prj._audit_log_csv_cell(None) == ""
    assert prj._audit_log_csv_cell(123) == "123"
    for prefix in ("=1+1", "+SUM", "-2", "@cmd"):
        assert prj._audit_log_csv_cell(prefix) == "'" + prefix


def test_list_audit_logs_with_and_without_filters():
    rows = [_audit_row(1), _audit_row(2, action="project_archived")]
    db = _FakeDB(results=[_Result(scalar=2), _Result(rows=rows)])
    page = asyncio.run(
        prj.list_audit_logs(
            project_id=None,
            action=None,
            user_id=None,
            created_from=None,
            created_to=None,
            page=1,
            page_size=50,
            db=db,
            _=None,
        )
    )
    assert page.total == 2 and [item.id for item in page.items] == [1, 2]
    assert page.page == 1 and page.page_size == 50

    db2 = _FakeDB(results=[_Result(scalar=0), _Result(rows=[])])
    filtered = asyncio.run(
        prj.list_audit_logs(
            project_id=5,
            action="project_archived",
            user_id=7,
            created_from=NOW,
            created_to=NOW,
            page=2,
            page_size=10,
            db=db2,
            _=None,
        )
    )
    assert filtered.total == 0 and filtered.items == [] and filtered.page == 2


def test_list_audit_logs_rejects_reversed_window():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            prj.list_audit_logs(
                project_id=None,
                action=None,
                user_id=None,
                created_from=NOW,
                created_to=NOW.replace(year=2025),
                page=1,
                page_size=50,
                db=_FakeDB(),
                _=None,
            )
        )
    assert exc.value.status_code == 422


def test_export_audit_logs_writes_bom_csv_and_records_export():
    rows = [_audit_row(1, action="=SUM(A1)", detail="note"), _audit_row(2, created_at=None)]
    db = _FakeDB(results=[_Result(rows=rows)])

    response = asyncio.run(
        prj.export_audit_logs(
            project_id=None,
            action=None,
            user_id=None,
            created_from=None,
            created_to=None,
            limit=10,
            db=db,
            current_user=_user(user_id=1),
        )
    )

    text = response.body.decode("utf-8")
    assert text.startswith("﻿")
    assert "id,created_at,action" in text
    assert "'=SUM(A1)" in text
    assert "2026-11-02T10:00:00" in text
    assert response.headers["content-disposition"] == 'attachment; filename="audit-logs.csv"'
    assert db.commits == 1
    audits = [item for item in db.added if item.__class__.__name__ == "AuditLog"]
    assert audits and audits[-1].action == "audit_log_export"

    db2 = _FakeDB(results=[_Result(rows=[])])
    filtered = asyncio.run(
        prj.export_audit_logs(
            project_id=5,
            action="project_archived",
            user_id=7,
            created_from=NOW,
            created_to=NOW,
            limit=100,
            db=db2,
            current_user=_user(user_id=1),
        )
    )
    assert filtered.body.decode("utf-8").startswith("﻿")
    assert db2.commits == 1


# ── 本地模式保护与项目列表 ───────────────────────────────────


def test_protect_last_local_project_branches(monkeypatch):
    monkeypatch.setattr(prj, "settings", SimpleNamespace(ATP_LOCAL_MODE=False))
    db = _FakeDB()
    asyncio.run(prj._protect_last_local_project(db, SimpleNamespace(id=1, status="active")))
    assert db.execute_calls == 0

    monkeypatch.setattr(prj, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    with pytest.raises(HTTPException) as last_one:
        asyncio.run(prj._protect_last_local_project(_FakeDB(scalars=[0]), SimpleNamespace(id=1, status="active")))
    assert last_one.value.status_code == 409
    assert "至少需要保留一个项目" in last_one.value.detail

    with pytest.raises(HTTPException) as last_active:
        asyncio.run(prj._protect_last_local_project(_FakeDB(scalars=[1, 0]), SimpleNamespace(id=1, status="active")))
    assert last_active.value.status_code == 409
    assert "至少需要保留一个活动项目" in last_active.value.detail

    asyncio.run(prj._protect_last_local_project(_FakeDB(scalars=[1, 1]), SimpleNamespace(id=1, status="active")))
    asyncio.run(prj._protect_last_local_project(_FakeDB(scalars=[1]), SimpleNamespace(id=2, status="archived")))


def test_list_projects_admin_sees_all_with_owner_role():
    row = _project_row(1)
    db = _FakeDB(results=[_Result(rows=[row])])

    result = asyncio.run(prj.list_projects(db=db, current_user=_user(role=UserRole.admin)))

    assert len(result) == 1 and result[0].id == 1
    assert result[0].current_user_role == ProjectRole.owner
