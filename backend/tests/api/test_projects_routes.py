"""projects API 路由单元测试（Q13 补覆盖：此前 41%）。

聚焦项目/模块 CRUD 与成员管理的安全关键逻辑：创建者自动 owner、模块树构建、
成员增删改的 404/409、以及"不能移除最后一个 owner"不变量。
FakeDB 承载对象与脚本化查询；assert_project_access / 缓存失效按测试注入。
"""

import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _noop_async(*_a, **_kw):
    return None


_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())
for _name, _value in (
    ("get_current_user", lambda: None),
    ("require_admin", lambda: None),
    ("require_engineer", lambda: None),
    ("assert_project_access", _noop_async),
    ("require_project_access", lambda role: _noop_async),
    ("require_project_writable_access", lambda role: _noop_async),
):
    if not hasattr(_deps, _name):
        setattr(_deps, _name, _value)

from fastapi import HTTPException  # noqa: E402

from app.api.v1 import projects as prj  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402

load_all_models()

from app.models.user import UserRole  # noqa: E402
from app.models.user_project import ProjectRole  # noqa: E402
from app.schemas.project import (  # noqa: E402
    ModuleCreate,
    ModuleUpdate,
    ProjectCopyIn,
    ProjectCreate,
    ProjectExportPayload,
    ProjectImportIn,
    ProjectTransferEnvironment,
    ProjectTransferDataset,
    ProjectTransferModule,
    ProjectTransferProject,
    ProjectTransferVariable,
    ProjectUpdate,
)
from app.schemas.user_project import ProjectMemberAddIn, ProjectMemberUpdateIn  # noqa: E402


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar


class _FakeDB:
    def __init__(self, objects=None, execute_results=None):
        self.objects = dict(objects or {})
        self.execute_results = list(execute_results or [])
        self.added = []
        self.deleted = []
        self.commits = 0
        self.flushes = 0
        self._next_id = 700

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def flush(self):
        self.flushes += 1
        for obj in self.added:
            if not getattr(obj, "id", None):
                obj.id = self._next_id
                self._next_id += 1

    async def refresh(self, obj):
        if getattr(obj, "created_at", None) is None:
            obj.created_at = _now()
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = _now()

    async def execute(self, _query):
        return self.execute_results.pop(0) if self.execute_results else _FakeResult()


def _now():
    return datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def stub_cache(monkeypatch):
    monkeypatch.setattr(prj, "invalidate_stats_cache", _noop_async)


def _user(uid=9, role=UserRole.engineer):
    return _Obj(id=uid, role=role, username="amy", email="amy@x.com")


# ── 项目 CRUD ───────────────────────────────────────────────


def test_list_projects_scopes_non_admin_to_memberships():
    project = _Obj(
        id=1,
        name="P1",
        project_code="P1",
        description=None,
        owner_id=9,
        ai_llm_config_id=None,
        status="active",
        run_retention_days_override=None,
        created_at=_now(),
        updated_at=_now(),
    )
    db = _FakeDB(execute_results=[_FakeResult(rows=[(project, ProjectRole.editor)])])
    result = asyncio.run(prj.list_projects(db=db, current_user=_user(role=UserRole.engineer)))
    assert [p.id for p in result] == [1]
    assert result[0].current_user_role is ProjectRole.editor


def test_create_project_auto_assigns_owner_and_code():
    db = _FakeDB()
    body = ProjectCreate(name="Acme Platform")

    project = asyncio.run(prj.create_project(body=body, db=db, current_user=_user(21)))

    assert project.owner_id == 21
    assert project.project_code  # 自动生成
    # 创建者的 owner UserProject 也被添加
    memberships = [o for o in db.added if o.__class__.__name__ == "UserProject"]
    assert memberships and memberships[0].role is ProjectRole.owner


def test_create_project_template_seeds_modules_environment_and_dataset():
    db = _FakeDB()
    project = asyncio.run(
        prj.create_project(body=ProjectCreate(name="Full", template="full"), db=db, current_user=_user(21))
    )

    assert project.id
    modules = [item for item in db.added if item.__class__.__name__ == "Module"]
    environments = [item for item in db.added if item.__class__.__name__ == "Environment"]
    datasets = [item for item in db.added if item.__class__.__name__ == "TestDataset"]
    assert [item.name for item in modules] == ["接口测试", "Web UI 测试", "Android 测试"]
    assert environments[0].project_id == project.id
    assert datasets[0].rows and datasets[0].creator_id == 21


def test_copy_project_copies_metadata_and_module_tree():
    source = _Obj(
        id=1,
        name="Source",
        description="source description",
        ai_llm_config_id=8,
        run_retention_days_override=14,
    )
    modules = [
        _Obj(id=11, name="API", module_code="API", parent_id=None, sort_order=0),
        _Obj(id=12, name="Auth", module_code="AUTH", parent_id=11, sort_order=1),
    ]
    db = _FakeDB({("Project", 1): source}, execute_results=[_FakeResult(rows=modules)])

    copied = asyncio.run(
        prj.copy_project(project_id=1, body=ProjectCopyIn(name="Copied"), db=db, current_user=_user(21))
    )

    copied_modules = [item for item in db.added if item.__class__.__name__ == "Module"]
    assert copied.name == "Copied" and copied.status == "active"
    assert copied.description == source.description and copied.owner_id == 21
    assert copied_modules[0].parent_id is None
    assert copied_modules[1].parent_id == copied_modules[0].id
    assert any(item.__class__.__name__ == "UserProject" and item.project_id == copied.id for item in db.added)


def test_export_project_masks_secrets_and_dataset_sensitive_fields():
    project = _Obj(id=1, name="Source", project_code="SOURCE", description="desc", ai_llm_config_id=None)
    module = _Obj(id=11, name="API", module_code="API", parent_id=None, sort_order=0)
    environment = _Obj(id=21, name="dev", description=None)
    variables = [
        _Obj(env_id=21, key="BASE_URL", value="https://example.test", is_secret=False),
        _Obj(env_id=21, key="API_TOKEN", value="do-not-export", is_secret=True),
    ]
    dataset = _Obj(
        id=31,
        name="users",
        description=None,
        format="json",
        rows=[{"username": "demo", "password": "do-not-export"}],
        schema_fields=[],
        validation_policy="soft",
    )
    db = _FakeDB(
        {("Project", 1): project},
        execute_results=[
            _FakeResult(rows=[module]),
            _FakeResult(rows=[environment]),
            _FakeResult(rows=variables),
            _FakeResult(rows=[dataset]),
        ],
    )

    exported = asyncio.run(prj.export_project(project_id=1, db=db))

    exported_variables = exported.environments[0].variables
    assert exported_variables[0].value == "https://example.test"
    assert exported_variables[1].value is None and exported_variables[1].redacted is True
    assert exported.datasets[0].rows[0]["password"] == "[REDACTED]"
    assert exported.warnings


def test_import_project_preview_and_import_skip_redacted_variables():
    payload = ProjectExportPayload(
        exported_at=_now(),
        project=ProjectTransferProject(name="Imported", project_code="IMPORTED"),
        modules=[ProjectTransferModule(id=11, name="API")],
        environments=[
            ProjectTransferEnvironment(
                name="dev",
                variables=[
                    ProjectTransferVariable(key="BASE_URL", value="https://example.test"),
                    ProjectTransferVariable(key="API_TOKEN", value=None, is_secret=True, redacted=True),
                ],
            )
        ],
    )
    preview_db = _FakeDB(execute_results=[_FakeResult(scalar=None)])
    preview = asyncio.run(
        prj.preview_project_import(
            body=ProjectImportIn(payload=payload),
            db=preview_db,
        )
    )
    assert preview.valid is True and preview.summary["variables"] == 2

    conflict_preview = asyncio.run(
        prj.preview_project_import(
            body=ProjectImportIn(payload=payload, conflict_policy="fail"),
            db=_FakeDB(execute_results=[_FakeResult(scalar=_Obj(id=99))]),
        )
    )
    rename_preview = asyncio.run(
        prj.preview_project_import(
            body=ProjectImportIn(payload=payload, conflict_policy="rename"),
            db=_FakeDB(execute_results=[_FakeResult(scalar=_Obj(id=99))]),
        )
    )
    assert conflict_preview.valid is False and conflict_preview.conflicts
    assert rename_preview.valid is True

    import_db = _FakeDB(execute_results=[_FakeResult(scalar=None)])
    imported = asyncio.run(
        prj.import_project(
            body=ProjectImportIn(payload=payload),
            db=import_db,
            current_user=_user(21),
        )
    )
    variables = [item for item in import_db.added if item.__class__.__name__ == "EnvVariable"]
    assert imported.imported["modules"] == 1
    assert imported.imported["variables"] == 1
    assert len(variables) == 1 and variables[0].key == "BASE_URL"


def test_import_project_rejects_oversized_dataset_before_creating_project():
    payload = ProjectExportPayload(
        exported_at=_now(),
        project=ProjectTransferProject(name="Too Large"),
        datasets=[ProjectTransferDataset(name="large", rows=[{"value": "x" * (256 * 1024)}])],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            prj.import_project(
                body=ProjectImportIn(payload=payload),
                db=_FakeDB(execute_results=[_FakeResult(scalar=None)]),
                current_user=_user(21),
            )
        )

    assert exc.value.status_code == 400


def test_get_project_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(prj.get_project(project_id=404, db=_FakeDB()))
    assert exc.value.status_code == 404


def test_update_project_applies_fields_and_backfills_code():
    project = _Obj(id=1, name="old", project_code=None)
    db = _FakeDB({("Project", 1): project})

    updated = asyncio.run(prj.update_project(project_id=1, body=ProjectUpdate(name="new"), db=db))

    assert updated.name == "new"
    assert updated.project_code  # 无 code 时按新名回填


def test_update_project_uses_writable_dependency_for_archived_read_only_boundary():
    source = (Path(__file__).resolve().parents[2] / "app/api/v1/projects.py").read_text(encoding="utf-8")
    start = source.index('@router.patch("/projects/{project_id}"')
    end = source.index('@router.delete("/projects/{project_id}"', start)
    route = source[start:end]
    assert "require_project_writable_access(ProjectRole.owner)" in route


def test_delete_project_removes_and_404():
    project = _Obj(id=1)
    db = _FakeDB({("Project", 1): project})
    asyncio.run(prj.delete_project(project_id=1, db=db))
    assert db.deleted == [project]

    with pytest.raises(HTTPException):
        asyncio.run(prj.delete_project(project_id=404, db=_FakeDB()))


def test_archive_and_restore_project_are_reversible():
    project = _Obj(id=1, status="active")
    db = _FakeDB({("Project", 1): project})

    archived = asyncio.run(prj.archive_project(project_id=1, db=db, current_user=_user(21)))
    assert archived.status == "archived"
    restored = asyncio.run(prj.restore_project(project_id=1, db=db, current_user=_user(21)))
    assert restored.status == "active"
    assert db.commits == 2
    assert [item.action for item in db.added if item.__class__.__name__ == "AuditLog"] == [
        "project_archived",
        "project_restored",
    ]


# ── 模块树与 CRUD ───────────────────────────────────────────


def test_build_tree_nests_children_and_sorts_roots():
    modules = [
        _Obj(id=1, name="根B", module_code=None, project_id=1, parent_id=None, sort_order=2, created_at=_now()),
        _Obj(id=2, name="根A", module_code=None, project_id=1, parent_id=None, sort_order=1, created_at=_now()),
        _Obj(id=3, name="子", module_code=None, project_id=1, parent_id=2, sort_order=0, created_at=_now()),
    ]

    tree = prj._build_tree(modules)

    assert [r.id for r in tree] == [2, 1]  # 按 sort_order 排根
    assert [c.id for c in tree[0].children] == [3]


def test_list_modules_builds_tree():
    modules = [_Obj(id=1, name="m", module_code=None, project_id=5, parent_id=None, sort_order=0, created_at=_now())]
    db = _FakeDB(execute_results=[_FakeResult(rows=modules)])
    result = asyncio.run(prj.list_modules(project_id=5, db=db))
    assert [m.id for m in result] == [1]


def test_create_module_checks_access_and_generates_code(monkeypatch):
    calls = []

    async def assert_access(_db, _user, project_id, role):
        calls.append((project_id, role))

    monkeypatch.setattr(prj, "assert_project_access", assert_access)
    db = _FakeDB()

    module = asyncio.run(
        prj.create_module(body=ModuleCreate(name="登录模块", project_id=5), db=db, current_user=_user())
    )

    assert module.module_code and calls == [(5, ProjectRole.editor)]


def test_update_and_delete_module_404(monkeypatch):
    monkeypatch.setattr(prj, "assert_project_access", _noop_async)
    with pytest.raises(HTTPException):
        asyncio.run(prj.update_module(module_id=404, body=ModuleUpdate(name="x"), db=_FakeDB(), current_user=_user()))
    with pytest.raises(HTTPException):
        asyncio.run(prj.delete_module(module_id=404, db=_FakeDB(), current_user=_user()))


# ── 成员管理（安全关键）────────────────────────────────────


def test_list_project_members_maps_role_and_user():
    up = _Obj(id=1, user_id=9, role=ProjectRole.editor, created_at=_now())
    user = _Obj(id=9, username="amy", email="amy@x.com")
    db = _FakeDB(execute_results=[_FakeResult(rows=[(up, user)])])

    members = asyncio.run(prj.list_project_members(project_id=5, db=db))

    assert members[0].username == "amy" and members[0].role == "editor"


def test_add_project_member_creates_and_guards_dupes():
    user = _Obj(id=7, username="bob", email="bob@x.com")
    # 首次：用户存在、无既有成员
    db = _FakeDB({("User", 7): user}, execute_results=[_FakeResult(scalar=None)])

    out = asyncio.run(prj.add_project_member(project_id=5, body=ProjectMemberAddIn(user_id=7, role="editor"), db=db))

    assert out.user_id == 7 and out.role == "editor"

    # 用户不存在 → 404
    with pytest.raises(HTTPException) as exc:
        asyncio.run(prj.add_project_member(project_id=5, body=ProjectMemberAddIn(user_id=404), db=_FakeDB()))
    assert exc.value.status_code == 404

    # 已是成员 → 409
    dup_db = _FakeDB({("User", 7): user}, execute_results=[_FakeResult(scalar=_Obj(id=1))])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(prj.add_project_member(project_id=5, body=ProjectMemberAddIn(user_id=7), db=dup_db))
    assert exc.value.status_code == 409


def test_update_project_member_changes_role_and_404():
    up = _Obj(id=1, user_id=7, role=ProjectRole.viewer, created_at=_now())
    user = _Obj(id=7, username="bob", email="bob@x.com")
    db = _FakeDB({("User", 7): user}, execute_results=[_FakeResult(scalar=up)])

    out = asyncio.run(
        prj.update_project_member(project_id=5, user_id=7, body=ProjectMemberUpdateIn(role="owner"), db=db)
    )

    assert out.role == "owner" and up.role is ProjectRole.owner

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            prj.update_project_member(
                project_id=5,
                user_id=404,
                body=ProjectMemberUpdateIn(role="viewer"),
                db=_FakeDB(execute_results=[_FakeResult(scalar=None)]),
            )
        )
    assert exc.value.status_code == 404


def test_remove_member_blocks_last_owner():
    owner_up = _Obj(id=1, user_id=7, role=ProjectRole.owner)
    # 查成员命中 owner，再查 owner 计数 = 1 → 拒绝
    db = _FakeDB(execute_results=[_FakeResult(scalar=owner_up), _FakeResult(scalar=1)])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(prj.remove_project_member(project_id=5, user_id=7, db=db))

    assert exc.value.status_code == 400 and "最后一个 owner" in exc.value.detail
    assert db.deleted == []


def test_remove_member_allows_non_last_owner_and_regular_member():
    # 有多个 owner → 允许移除
    owner_up = _Obj(id=1, user_id=7, role=ProjectRole.owner)
    db = _FakeDB(execute_results=[_FakeResult(scalar=owner_up), _FakeResult(scalar=2)])
    asyncio.run(prj.remove_project_member(project_id=5, user_id=7, db=db))
    assert db.deleted == [owner_up]

    # 普通成员（非 owner）直接移除，不查 owner 计数
    member_up = _Obj(id=2, user_id=8, role=ProjectRole.viewer)
    db2 = _FakeDB(execute_results=[_FakeResult(scalar=member_up)])
    asyncio.run(prj.remove_project_member(project_id=5, user_id=8, db=db2))
    assert db2.deleted == [member_up]


def test_remove_member_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            prj.remove_project_member(project_id=5, user_id=404, db=_FakeDB(execute_results=[_FakeResult(scalar=None)]))
        )
    assert exc.value.status_code == 404
