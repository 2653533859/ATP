import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(get_current_user=lambda: None)


async def _noop_invalidate_stats_cache():
    return None


sys.modules["app.api.v1.statistics"] = types.SimpleNamespace(invalidate_stats_cache=_noop_invalidate_stats_cache)

from app.api.v1 import projects
from app.models.bootstrap import load_all_models


class _ModuleLike:
    def __init__(self, module_id: int, name: str, project_id: int, parent_id: int | None, sort_order: int):
        self.id = module_id
        self.name = name
        self.project_id = project_id
        self.parent_id = parent_id
        self.sort_order = sort_order
        self.created_at = datetime.now(timezone.utc)

    @property
    def children(self):
        raise AssertionError("tree builder should not touch ORM children relationship")


class _CreateDB:
    def __init__(self):
        self.added = []
        self.refresh_calls = []
        self.commit_calls = 0

    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = len(self.added)

    async def commit(self):
        self.commit_calls += 1

    async def flush(self):
        return None

    async def refresh(self, obj):
        self.refresh_calls.append(obj)


class _DeleteDB:
    def __init__(self, obj):
        self.obj = obj
        self.deleted = []
        self.commit_calls = 0

    async def get(self, _model, obj_id):
        assert obj_id == self.obj.id
        return self.obj

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commit_calls += 1


def test_build_tree_does_not_access_lazy_children_relationship():
    root = _ModuleLike(module_id=1, name="Root", project_id=8, parent_id=None, sort_order=0)
    child = _ModuleLike(module_id=2, name="Child", project_id=8, parent_id=1, sort_order=1)

    tree = projects._build_tree([root, child])

    assert len(tree) == 1
    assert tree[0].id == 1
    assert len(tree[0].children) == 1
    assert tree[0].children[0].id == 2


def test_create_project_invalidates_stats_cache(monkeypatch):
    load_all_models()
    db = _CreateDB()
    invalidated = []

    async def fake_invalidate_stats_cache():
        invalidated.append(True)

    monkeypatch.setattr(projects, "invalidate_stats_cache", fake_invalidate_stats_cache)

    result = asyncio.run(
        projects.create_project(
            body=types.SimpleNamespace(model_dump=lambda: {"name": "ATP", "project_code": None}, name="ATP"),
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    assert result.id == 1
    assert db.commit_calls == 1
    assert len(db.refresh_calls) == 1
    assert invalidated == [True]


def test_create_module_invalidates_stats_cache(monkeypatch):
    load_all_models()
    db = _CreateDB()
    invalidated = []

    async def fake_invalidate_stats_cache():
        invalidated.append(True)

    monkeypatch.setattr(projects, "invalidate_stats_cache", fake_invalidate_stats_cache)

    result = asyncio.run(
        projects.create_module(
            body=types.SimpleNamespace(model_dump=lambda: {"name": "Login", "module_code": None, "project_id": 1}, name="Login"),
            db=db,
            _=None,
        )
    )

    assert result.id == 1
    assert db.commit_calls == 1
    assert len(db.refresh_calls) == 1
    assert invalidated == [True]


def test_delete_project_invalidates_stats_cache(monkeypatch):
    project = types.SimpleNamespace(id=3, name="ATP")
    db = _DeleteDB(project)
    invalidated = []

    async def fake_invalidate_stats_cache():
        invalidated.append(True)

    monkeypatch.setattr(projects, "invalidate_stats_cache", fake_invalidate_stats_cache)

    asyncio.run(projects.delete_project(project_id=3, db=db, _=None))

    assert db.deleted == [project]
    assert db.commit_calls == 1
    assert invalidated == [True]


def test_delete_module_invalidates_stats_cache(monkeypatch):
    module = types.SimpleNamespace(id=5, name="Login")
    db = _DeleteDB(module)
    invalidated = []

    async def fake_invalidate_stats_cache():
        invalidated.append(True)

    monkeypatch.setattr(projects, "invalidate_stats_cache", fake_invalidate_stats_cache)

    asyncio.run(projects.delete_module(module_id=5, db=db, _=None))

    assert db.deleted == [module]
    assert db.commit_calls == 1
    assert invalidated == [True]
