"""Automated tests for D3 Cloud Result Center API and D4 Sync Client."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import create_engine

from app.api.v1.cloud_sync import router as cloud_sync_router
from app.core.database import get_db
from app.core.local_schema import ensure_local_schema
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.cloud_sync import CloudRunSummaryModel
from app.schemas.cloud_sync import CloudRunSummary, CloudStepSummary
from app.services.cloud_sync_client import sync_pending_outbox
from app.services.sync_outbox import list_outbox_items, record_run_in_outbox
from fastapi import FastAPI

load_all_models()


@pytest.fixture
def sync_app():
    app = FastAPI()
    app.include_router(cloud_sync_router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_cloud_sync_receive_and_idempotent_deduplication(tmp_path, sync_app):
    """Test receiving summaries, deduplication by unique_key, and stat aggregation."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cloud_server.sqlite3'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with sessions() as s:
            yield s

    sync_app.dependency_overrides[get_db] = override_get_db
    from app.api.deps import get_current_user
    from app.models.user import User, UserRole

    admin = User(id=1, username="admin", email="admin@test.local", hashed_password="x", role=UserRole.admin)

    sample_summary = CloudRunSummary(
        schema_version=1,
        client_id="win-pc-alpha",
        machine_name="DESKTOP-ALPHA",
        unique_key="win-pc-alpha:case:1001",
        run_type="case",
        run_id=1001,
        project_name="E-Commerce",
        project_code="ECOM",
        title="Checkout Flow",
        status="passed",
        duration_ms=450,
        triggered_by="admin",
        metrics={"total_steps": 2, "passed_steps": 2},
        steps=[
            CloudStepSummary(step_index=0, name="Login", status="passed", duration_ms=150),
            CloudStepSummary(step_index=1, name="Pay", status="passed", duration_ms=300),
        ],
    )

    transport = ASGITransport(app=sync_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/v1/cloud-sync/stats")).status_code == 401
        assert (
            await client.post("/api/v1/cloud-sync/runs", json=sample_summary.model_dump(mode="json"))
        ).status_code == 401
        viewer = User(id=2, username="viewer", email="viewer@test.local", hashed_password="x", role=UserRole.viewer)
        sync_app.dependency_overrides[get_current_user] = lambda: viewer
        assert (await client.get("/api/v1/cloud-sync/runs")).status_code == 403
        assert (
            await client.post("/api/v1/cloud-sync/runs", json=sample_summary.model_dump(mode="json"))
        ).status_code == 403
        sync_app.dependency_overrides[get_current_user] = lambda: admin
        # 1. Post initial summary -> created
        res1 = await client.post("/api/v1/cloud-sync/runs", json=sample_summary.model_dump(mode="json"))
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "ok"
        assert data1["acknowledged"] is True
        assert data1["action"] == "created"
        assert data1["unique_key"] == "win-pc-alpha:case:1001"

        # 2. Post identical summary again -> updated (deduplication)
        updated_summary = sample_summary.model_copy(update={"duration_ms": 480})
        res2 = await client.post("/api/v1/cloud-sync/runs", json=updated_summary.model_dump(mode="json"))
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["action"] == "updated"

        # 3. Query list
        res_list = await client.get("/api/v1/cloud-sync/runs?client_id=win-pc-alpha")
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert list_data["total"] == 1
        assert list_data["items"][0]["duration_ms"] == 480
        assert list_data["items"][0]["project_code"] == "ECOM"

        # 4. Query detail
        res_detail = await client.get("/api/v1/cloud-sync/runs/win-pc-alpha:case:1001")
        assert res_detail.status_code == 200
        detail_data = res_detail.json()
        assert len(detail_data["steps"]) == 2
        assert detail_data["steps"][0]["name"] == "Login"

        # 5. Query stats
        res_stats = await client.get("/api/v1/cloud-sync/stats")
        assert res_stats.status_code == 200
        stats_data = res_stats.json()
        assert stats_data["total_runs"] == 1
        assert stats_data["status_distribution"].get("passed") == 1
        assert len(stats_data["connected_clients"]) == 1
        assert stats_data["connected_clients"][0]["client_id"] == "win-pc-alpha"

    sync_app.dependency_overrides.clear()
    await engine.dispose()


def test_cloud_sync_client_sweeps_outbox_to_server(tmp_path, sync_app, monkeypatch):
    """Test D4 sync client reading outbox, posting to cloud, and transitioning to synced."""
    # 1. Setup local sqlite database with Schema v15
    local_db_path = tmp_path / "local.sqlite3"
    local_engine = create_engine(f"sqlite:///{local_db_path}")
    ensure_local_schema(local_engine)

    # 2. Setup cloud server database
    cloud_db_path = tmp_path / "cloud_srv.sqlite3"
    cloud_engine = create_async_engine(f"sqlite+aiosqlite:///{cloud_db_path}")
    cloud_sessions = async_sessionmaker(cloud_engine, expire_on_commit=False)

    import asyncio

    async def init_cloud_db():
        async with cloud_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_cloud_db())

    async def override_get_db():
        async with cloud_sessions() as s:
            yield s

    sync_app.dependency_overrides[get_db] = override_get_db
    from app.api.deps import get_current_user
    from app.models.user import User, UserRole

    cloud_admin = User(id=9, username="cloud-admin", email="cloud@test.local", hashed_password="x", role=UserRole.admin)
    sync_app.dependency_overrides[get_current_user] = lambda: cloud_admin

    from sqlalchemy.orm import Session
    from app.models.user import User, UserRole
    from app.models.project import Project, Module
    from app.models.case import TestCase, TestRun, CaseType, CaseStatus, RunStatus

    with Session(local_engine) as session:
        user = User(id=1, username="u", email="u@local", hashed_password="p", role=UserRole.admin, is_active=True)
        proj = Project(id=1, name="Proj1", project_code="PR1", owner_id=1, status="active")
        mod = Module(id=1, name="Mod1", module_code="MOD1", project_id=1, sort_order=0)
        case = TestCase(
            id=1,
            name="Case1",
            summary="sum",
            case_code="C01",
            module_id=1,
            case_type=CaseType.api,
            status=CaseStatus.active,
            creator_id=1,
        )
        run = TestRun(
            id=50,
            case_id=1,
            triggered_by=1,
            status=RunStatus.passed,
            duration_ms=120,
        )
        session.add_all([user, proj, mod, case, run])
        session.commit()

    with local_engine.begin() as conn:
        key = record_run_in_outbox(conn, "run_test_case", 50)
        assert key is not None
    with local_engine.connect() as conn:
        items = list_outbox_items(conn, status="pending")
        assert len(items) == 1
        assert items[0]["status"] == "pending"

    from starlette.testclient import TestClient

    client = TestClient(sync_app, base_url="http://mock-cloud-server")

    # Execute sync_pending_outbox
    res = sync_pending_outbox(
        sync_url="http://mock-cloud-server",
        engine=local_engine,
        http_client=client,
    )

    assert res["status"] == "ok"
    assert res["synced"] == 1
    assert res["failed"] == 0

    # Verify local outbox record is now synced
    with local_engine.connect() as conn:
        items_after = list_outbox_items(conn)
        assert len(items_after) == 1
        assert items_after[0]["status"] == "synced"
        assert items_after[0]["synced_at"] is not None

    sync_app.dependency_overrides.clear()
    asyncio.run(cloud_engine.dispose())


def test_cloud_sync_client_retries_failed_and_abandoned_records(tmp_path):
    """A manual retry recovers failures, and an abandoned claim resumes safely."""
    from sqlalchemy import text

    engine = create_engine(f"sqlite:///{tmp_path / 'retry.sqlite3'}")
    ensure_local_schema(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO local_sync_outbox "
                "(client_id, run_type, run_id, unique_key, payload_json, status) "
                "VALUES ('pc', 'case', 1, 'pc:case:1', :payload, 'pending')"
            ),
            {"payload": '{"error_summary":"token secret_token_xyz","steps":[{"error_summary":"secret_token_xyz"}]}'},
        )

    class Response:
        def __init__(self, code):
            self.status_code = code
            self.text = "unavailable"

        def json(self):
            return {"acknowledged": True}

    class Client:
        def __init__(self, code):
            self.code = code

        def post(self, *_args, **kwargs):
            assert "secret_token_xyz" not in str(kwargs["json"])
            return Response(self.code)

    first = sync_pending_outbox(sync_url="http://test", engine=engine, http_client=Client(503))
    assert first["failed"] == 1
    with engine.connect() as conn:
        assert list_outbox_items(conn)[0]["status"] == "failed"

    assert sync_pending_outbox(sync_url="http://test", engine=engine, http_client=Client(200))["processed"] == 0
    second = sync_pending_outbox(sync_url="http://test", engine=engine, http_client=Client(200), force_retry=True)
    assert second["synced"] == 1

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE local_sync_outbox SET status = 'syncing', synced_at = NULL, "
                "updated_at = datetime('now', '-61 seconds') WHERE unique_key = 'pc:case:1'"
            )
        )
    recovered = sync_pending_outbox(sync_url="http://test", engine=engine, http_client=Client(200))
    assert recovered["synced"] == 1
    with engine.connect() as conn:
        assert list_outbox_items(conn)[0]["status"] == "synced"


@pytest.mark.asyncio
async def test_local_outbox_endpoints(tmp_path, sync_app, monkeypatch):
    """Test /api/v1/cloud-sync/local/* endpoints in local mode."""
    from app.api.deps import get_current_user
    from app.models.user import User, UserRole
    import app.core.database as db_mod
    from app.core.config import settings

    fake_admin = User(
        id=1, username="admin", email="a@test.local", hashed_password="pw", role=UserRole.admin, is_active=True
    )
    sync_app.dependency_overrides[get_current_user] = lambda: fake_admin

    local_db_path = tmp_path / "local_test.sqlite3"
    local_engine = create_engine(f"sqlite:///{local_db_path}")
    ensure_local_schema(local_engine)

    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", True)
    monkeypatch.setattr(settings, "CLOUD_SYNC_URL", "http://192.168.3.196:8000")
    monkeypatch.setattr(db_mod, "sync_engine", local_engine)
    transport = ASGITransport(app=sync_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_status = await client.get("/api/v1/cloud-sync/local/status")
        assert res_status.status_code == 200
        st_data = res_status.json()
        assert st_data["local_mode"] is True
        assert st_data["cloud_sync_url"] == "http://192.168.3.196:8000"
        assert st_data["stats"]["total"] == 0

        res_run = await client.get("/api/v1/cloud-sync/local/runs/case/999")
        assert res_run.status_code == 200
        assert res_run.json()["sync_status"] == "not_queued"

    sync_app.dependency_overrides.clear()
