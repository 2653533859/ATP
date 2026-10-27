"""The Windows profile keeps one administrator with independent local projects."""

from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import local_workspace
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.project import Module, Project
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject

load_all_models()


class _Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _Session:
    def __init__(self, scalar_values, projects):
        self.scalar_values = iter(scalar_values)
        self.projects = projects
        self.added = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def scalar(self, _query):
        return next(self.scalar_values)

    async def scalars(self, _query):
        return _Scalars(self.projects)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        for item in self.added:
            if isinstance(item, Project) and item.id is None:
                item.id = 12

    async def commit(self):
        self.committed = True


def _set_session(monkeypatch, session):
    monkeypatch.setattr(local_workspace, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    monkeypatch.setattr(local_workspace, "AsyncSessionLocal", lambda: session)


@pytest.mark.asyncio
async def test_local_workspace_creates_project_membership_and_module(monkeypatch):
    admin = SimpleNamespace(id=3, role=UserRole.admin, is_active=True)
    session = _Session([1, admin, None, None], [])
    _set_session(monkeypatch, session)

    assert await local_workspace.ensure_local_workspace() == 12
    assert session.committed
    assert [type(item).__name__ for item in session.added] == ["Project", "UserProject", "Module"]
    assert session.added[1].role.value == "owner"


@pytest.mark.asyncio
async def test_local_workspace_keeps_existing_project(monkeypatch):
    admin = SimpleNamespace(id=3, role=UserRole.admin, is_active=True)
    project = Project(id=12, name="existing", project_code="EXIST", owner_id=3)
    session = _Session([1, admin, UserProject(user_id=3, project_id=12), 7], [project])
    _set_session(monkeypatch, session)

    assert await local_workspace.ensure_local_workspace() == 12
    assert session.added == []
    assert session.committed


@pytest.mark.asyncio
async def test_local_workspace_preserves_multiple_projects_and_repairs_membership(monkeypatch):
    admin = SimpleNamespace(id=3, role=UserRole.admin, is_active=True)
    first = Project(id=12, name="first", project_code="FIRST", owner_id=3)
    second = Project(id=13, name="second", project_code="SECOND", owner_id=3)
    session = _Session([1, admin, UserProject(user_id=3, project_id=12), None], [first, second])
    _set_session(monkeypatch, session)

    assert await local_workspace.ensure_local_workspace() == 12
    assert session.committed
    assert [(item.user_id, item.project_id, item.role) for item in session.added] == [(3, 13, ProjectRole.owner)]
    assert (first.name, second.name) == ("first", "second")


@pytest.mark.asyncio
async def test_local_workspace_multiple_projects_survive_real_sqlite_restart(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'local.sqlite3'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            admin = User(username="admin", email="admin@example.test", hashed_password="test", role=UserRole.admin)
            db.add(admin)
            await db.flush()
            first = Project(name="first", project_code="FIRST", owner_id=admin.id)
            second = Project(name="second", project_code="SECOND", owner_id=admin.id)
            db.add_all([first, second])
            await db.flush()
            db.add(Module(name="custom", module_code="CUSTOM", project_id=first.id))
            await db.commit()
            ids = (first.id, second.id)

        monkeypatch.setattr(local_workspace, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
        monkeypatch.setattr(local_workspace, "AsyncSessionLocal", sessions)
        assert await local_workspace.ensure_local_workspace() == ids[0]
        assert await local_workspace.ensure_local_workspace() == ids[0]

        async with sessions() as db:
            assert (await db.scalar(select(func.count(Project.id)))) == 2
            assert (await db.scalar(select(func.count(Module.id)))) == 1
            memberships = (await db.scalars(select(UserProject).order_by(UserProject.project_id))).all()
            assert [(row.user_id, row.project_id, row.role) for row in memberships] == [
                (admin.id, ids[0], ProjectRole.owner),
                (admin.id, ids[1], ProjectRole.owner),
            ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scalar_values", "projects", "error"),
    [
        ([0], [], "exactly one user"),
        ([1, None], [], "active administrator"),
        ([1, SimpleNamespace(id=3, role=UserRole.admin, is_active=False)], [], "active administrator"),
        (
            [1, SimpleNamespace(id=3, role=UserRole.admin, is_active=True)],
            [Project(id=12, owner_id=4)],
            "owner differs",
        ),
        (
            [1, SimpleNamespace(id=3, role=UserRole.admin, is_active=True), SimpleNamespace(id=1)],
            [Project(id=12, owner_id=3), Project(id=13, owner_id=4)],
            "owner differs",
        ),
    ],
)
async def test_local_workspace_rejects_invalid_profile(monkeypatch, scalar_values, projects, error):
    _set_session(monkeypatch, _Session(scalar_values, projects))
    with pytest.raises(RuntimeError, match=error):
        await local_workspace.ensure_local_workspace()


@pytest.mark.asyncio
async def test_local_workspace_rejects_server_mode(monkeypatch):
    monkeypatch.setattr(local_workspace, "settings", SimpleNamespace(ATP_LOCAL_MODE=False))
    with pytest.raises(RuntimeError, match="Windows local mode"):
        await local_workspace.ensure_local_workspace()
