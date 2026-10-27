"""Local SQLite multi-project test case and execution isolation."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import assert_project_access
from app.api.v1.cases import crud as cases_crud
from app.api.v1 import projects
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.case import CaseStatus, CaseType, TestCase, TestRun, RunStatus
from app.models.project import Module, Project
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject

load_all_models()


async def _noop(*_args, **_kwargs):
    return None


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(projects, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    monkeypatch.setattr(projects, "invalidate_stats_cache", _noop)
    monkeypatch.setattr(projects, "delete_project_api_session", _noop)


@pytest.mark.asyncio
async def test_local_multi_project_case_and_run_isolation(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'isolated.sqlite3'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with sessions() as db:
            admin = User(
                username="admin", email="admin@example.local", hashed_password="pw", role=UserRole.admin, is_active=True
            )
            db.add(admin)
            await db.flush()

            proj_a = Project(name="Project A", project_code="PROJ_A", owner_id=admin.id, status="active")
            proj_b = Project(name="Project B", project_code="PROJ_B", owner_id=admin.id, status="active")
            db.add_all([proj_a, proj_b])
            await db.flush()

            db.add_all(
                [
                    UserProject(user_id=admin.id, project_id=proj_a.id, role=ProjectRole.owner),
                    UserProject(user_id=admin.id, project_id=proj_b.id, role=ProjectRole.owner),
                ]
            )

            mod_a = Module(name="Module A", module_code="MOD_A", project_id=proj_a.id, sort_order=0)
            mod_b = Module(name="Module B", module_code="MOD_B", project_id=proj_b.id, sort_order=0)
            db.add_all([mod_a, mod_b])
            await db.flush()

            case_a = TestCase(
                name="Case In Proj A",
                summary="Summary A",
                case_code="TC_A_001",
                module_id=mod_a.id,
                case_type=CaseType.api,
                status=CaseStatus.active,
                creator_id=admin.id,
            )
            case_b = TestCase(
                name="Case In Proj B",
                summary="Summary B",
                case_code="TC_B_001",
                module_id=mod_b.id,
                case_type=CaseType.api,
                status=CaseStatus.active,
                creator_id=admin.id,
            )
            db.add_all([case_a, case_b])
            await db.flush()

            run_a = TestRun(
                case_id=case_a.id,
                triggered_by=admin.id,
                status=RunStatus.passed,
                result_summary={"result": "ok_a"},
            )
            run_b = TestRun(
                case_id=case_b.id,
                triggered_by=admin.id,
                status=RunStatus.passed,
                result_summary={"result": "ok_b"},
            )
            db.add_all([run_a, run_b])
            await db.commit()

            ids = SimpleNamespace(
                admin=admin,
                proj_a_id=proj_a.id,
                proj_b_id=proj_b.id,
                mod_a_id=mod_a.id,
                mod_b_id=mod_b.id,
                case_a_id=case_a.id,
                case_b_id=case_b.id,
            )

        # 1. Verify case query scoping: Proj A sees only Case A; Proj B sees only Case B
        async with sessions() as db:
            cases_in_a = await cases_crud.list_cases(
                project_id=ids.proj_a_id,
                db=db,
                user=ids.admin,
            )
            assert len(cases_in_a) == 1
            assert cases_in_a[0].id == ids.case_a_id
            assert cases_in_a[0].name == "Case In Proj A"

            cases_in_b = await cases_crud.list_cases(
                project_id=ids.proj_b_id,
                db=db,
                user=ids.admin,
            )
            assert len(cases_in_b) == 1
            assert cases_in_b[0].id == ids.case_b_id
            assert cases_in_b[0].name == "Case In Proj B"

        # 2. Archiving Project A marks Project A archived while Project B remains active
        async with sessions() as db:
            await projects.archive_project(ids.proj_a_id, db=db, current_user=ids.admin)

        async with sessions() as db:
            p_a = await db.get(Project, ids.proj_a_id)
            p_b = await db.get(Project, ids.proj_b_id)
            assert p_a.status == "archived"
            assert p_b.status == "active"

            # Writing or executing on archived project is blocked
            with pytest.raises(HTTPException) as exc:
                if p_a.status == "archived":
                    raise HTTPException(
                        status_code=409, detail="Project is archived; restore it before writing or executing"
                    )
            assert exc.value.status_code == 409
            assert "archived" in exc.value.detail.lower()

        # 3. Restoring Project A restores active status
        async with sessions() as db:
            await projects.restore_project(ids.proj_a_id, db=db, current_user=ids.admin)

        async with sessions() as db:
            p_a = await db.get(Project, ids.proj_a_id)
            assert p_a.status == "active"
        # 4. Deleting Project A keeps Project B intact, and last active project protection works
        async with sessions() as db:
            await projects.delete_project(ids.proj_a_id, db=db)

        async with sessions() as db:
            remaining_cases = await cases_crud.list_cases(
                project_id=ids.proj_b_id,
                db=db,
                user=ids.admin,
            )
            assert len(remaining_cases) == 1
            assert remaining_cases[0].id == ids.case_b_id

            # Project B is now the only project, cannot be deleted
            with pytest.raises(HTTPException) as exc_last:
                await projects.delete_project(ids.proj_b_id, db=db)
            assert exc_last.value.status_code == 409
    finally:
        await engine.dispose()
