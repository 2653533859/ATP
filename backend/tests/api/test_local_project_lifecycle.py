"""Local project lifecycle keeps a usable project after archive and delete."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1 import projects
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.project import Project
from app.models.user import User, UserRole

load_all_models()


async def _noop(*_args, **_kwargs):
    return None


@pytest.mark.asyncio
async def test_local_archive_and_delete_keep_one_active_project(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'projects.sqlite3'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(projects, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    monkeypatch.setattr(projects, "invalidate_stats_cache", _noop)
    monkeypatch.setattr(projects, "delete_project_api_session", _noop)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            admin = User(username="admin", email="admin@example.test", hashed_password="test", role=UserRole.admin)
            db.add(admin)
            await db.flush()
            first = Project(name="first", project_code="FIRST", owner_id=admin.id, status="active")
            second = Project(name="second", project_code="SECOND", owner_id=admin.id, status="active")
            db.add_all([first, second])
            await db.commit()
            ids = (first.id, second.id)

        async with sessions() as db:
            await projects.archive_project(ids[0], db=db, current_user=admin)
        async with sessions() as db:
            with pytest.raises(HTTPException) as exc:
                await projects.archive_project(ids[1], db=db, current_user=admin)
            assert exc.value.status_code == 409
        async with sessions() as db:
            await projects.restore_project(ids[0], db=db, current_user=admin)
        async with sessions() as db:
            await projects.delete_project(ids[1], db=db)
        async with sessions() as db:
            with pytest.raises(HTTPException) as exc:
                await projects.delete_project(ids[0], db=db)
            assert exc.value.status_code == 409
        async with sessions() as db:
            assert (await db.scalar(select(func.count(Project.id)))) == 1
            assert (await db.get(Project, ids[0])).status == "active"
    finally:
        await engine.dispose()
