"""针对补齐的新增/更新/删除接口及配套前端契约的回归测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.local_object_store import (
    delete_file as local_delete_file,
    ensure_store,
    list_objects as local_list_objects,
    read_bytes,
    upload_bytes,
)
from app.models.android_agent import AndroidAgentDraft, AndroidAgentReplay, AndroidAgentSession
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.case import CaseSnapshot, CaseStatus, CaseType, RunStatus, TestCase, TestRun
from app.models.dashboard_alert import (
    DashboardAlertEvent,
    DashboardAlertMetric,
    DashboardAlertOperator,
    DashboardAlertRule,
)
from app.models.defect import Defect
from app.models.hermes import HermesSession
from app.models.knowledge import KnowledgeEntry
from app.models.mobile_special import (
    DeviceScopeType,
    MobileSpecialRun,
    MobileSpecialTask,
    RunStatus as MobileRunStatus,
    TaskType,
)
from app.models.performance import PerformanceRun, PerformanceRunStatus, PerformanceTest
from app.models.project import Module, Project
from app.models.remote_node_grant import RemoteNodeGrant
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject

load_all_models()


class _AppEnv:
    """Isolated SQLite + FastAPI test environment."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.api.deps import get_current_user, require_admin, require_engineer
        from app.api.v1 import (
            ai_chat,
            android_agent,
            api_request_files,
            cases,
            dashboard_alerts,
            defects,
            hermes,
            mobile_special,
            performance,
            remote_nodes,
            users,
            web_files,
            web_recordings,
        )
        from app.core.database import get_db

        self.cases = cases
        self.performance = performance
        self.web_recordings = web_recordings
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'crud.sqlite3'}")

        @event.listens_for(self.engine.sync_engine, "connect")
        def _enable_fk(dbapi_conn, _record) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.actor: User | None = None
        self.app = FastAPI()
        for router_mod in (
            performance,
            defects,
            cases,
            mobile_special,
            users,
            hermes,
            android_agent,
            ai_chat,
            api_request_files,
            web_files,
            remote_nodes,
            dashboard_alerts,
            web_recordings,
        ):
            self.app.include_router(router_mod.router, prefix="/api/v1")

        async def _override_get_db():
            async with self.sessions() as session:
                yield session

        def _current() -> User:
            assert self.actor is not None
            return self.actor

        self.app.dependency_overrides[get_db] = _override_get_db
        self.app.dependency_overrides[get_current_user] = _current
        self.app.dependency_overrides[require_engineer] = _current
        self.app.dependency_overrides[require_admin] = _current

        def _bind_route_deps(dependant) -> None:
            for dep in getattr(dependant, "dependencies", []) or []:
                if dep.call is not None:
                    if dep.name == "db":
                        self.app.dependency_overrides[dep.call] = _override_get_db
                    elif dep.name in {"user", "current_user", "_user", "_"}:
                        self.app.dependency_overrides[dep.call] = _current
                _bind_route_deps(dep)

        def _walk_router_routes(router_obj) -> None:
            for r in getattr(router_obj, "routes", []) or []:
                dependant = getattr(r, "dependant", None)
                if dependant is not None:
                    _bind_route_deps(dependant)
                sub = getattr(r, "router", None) or getattr(r, "original_router", None)
                if sub is not None:
                    _walk_router_routes(sub)

        for router_mod in (
            performance,
            defects,
            cases,
            cases.crud,
            cases.workflow,
            cases.runs,
            mobile_special,
            users,
            hermes,
            android_agent,
            ai_chat,
            api_request_files,
            web_files,
            remote_nodes,
            dashboard_alerts,
            web_recordings,
        ):
            _walk_router_routes(router_mod.router)

        monkeypatch.setattr(users, "require_server_workspace", lambda *_a, **_k: None)
        monkeypatch.setattr(android_agent.settings, "ANDROID_AGENT_ENABLED", True)

    async def init(self) -> tuple[User, User, User, Project, Module]:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.sessions() as db:
            admin = User(username="admin", email="admin@t.local", hashed_password="x", role=UserRole.admin)
            eng = User(username="eng", email="eng@t.local", hashed_password="x", role=UserRole.engineer)
            viewer = User(username="viewer", email="viewer@t.local", hashed_password="x", role=UserRole.viewer)
            db.add_all([admin, eng, viewer])
            await db.flush()
            project = Project(name="Proj1", owner_id=admin.id)
            db.add(project)
            await db.flush()
            module = Module(name="Mod1", project_id=project.id)
            db.add(module)
            db.add_all(
                [
                    UserProject(user_id=eng.id, project_id=project.id, role=ProjectRole.editor),
                    UserProject(user_id=viewer.id, project_id=project.id, role=ProjectRole.viewer),
                ]
            )
            await db.commit()
            self.actor = admin
            return admin, eng, viewer, project, module

    def client(self) -> AsyncClient:
        return AsyncClient(transport=ASGITransport(app=self.app), base_url="http://testserver")

    async def close(self) -> None:
        await self.engine.dispose()


@pytest.mark.asyncio
async def test_case_snapshots_and_execution_run_deletes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _AppEnv(tmp_path, monkeypatch)
    try:
        admin, _eng, _viewer, project, module = await env.init()
        async with env.sessions() as db:
            case = TestCase(
                module_id=module.id,
                name="Login Case",
                case_code="TC-001",
                summary="sum",
                case_type=CaseType.api,
                status=CaseStatus.active,
                creator_id=admin.id,
            )
            db.add(case)
            await db.flush()
            snap = CaseSnapshot(
                case_id=case.id,
                version=1,
                name="v1",
                description="orig",
                tags=[],
                config={},
                snapshot_data={"remark": "init"},
                updated_by=admin.id,
            )
            running_run = TestRun(case_id=case.id, triggered_by=admin.id, status=RunStatus.running)
            passed_run = TestRun(case_id=case.id, triggered_by=admin.id, status=RunStatus.passed)
            parent_run = TestRun(case_id=case.id, triggered_by=admin.id, status=RunStatus.passed)
            db.add_all([snap, running_run, passed_run, parent_run])
            await db.flush()
            active_child = TestRun(
                case_id=case.id,
                triggered_by=admin.id,
                status=RunStatus.running,
                parent_run_id=parent_run.id,
            )
            task = MobileSpecialTask(
                name="Perf Task",
                project_id=project.id,
                task_type=TaskType.performance,
                device_scope_type=DeviceScopeType.manual_pick,
                config_json={},
            )
            db.add_all([task, active_child])
            await db.flush()
            ms_running = MobileSpecialRun(
                task_id=task.id,
                task_type=TaskType.performance,
                status=MobileRunStatus.running,
                summary_json={},
                config_snapshot={},
            )
            ms_done = MobileSpecialRun(
                task_id=task.id,
                task_type=TaskType.performance,
                status=MobileRunStatus.completed,
                summary_json={},
                config_snapshot={},
            )
            db.add_all([ms_running, ms_done])
            await db.commit()
            ids = (case.id, snap.id, running_run.id, passed_run.id, parent_run.id, ms_running.id, ms_done.id)

        case_id, snap_id, run_active_id, run_done_id, parent_run_id, ms_active_id, ms_done_id = ids
        snapshot_routes = [
            r
            for r in env.cases.workflow.router.routes
            if getattr(r, "path", "") == "/cases/{case_id}/snapshots/{snapshot_id}"
        ]
        assert sum(len(getattr(r, "methods", set()) or set()) for r in snapshot_routes) == 3  # GET + PATCH + DELETE

        async with env.client() as client:
            bad = await client.patch(f"/api/v1/cases/{case_id}/snapshots/{snap_id}", json={"name": "   "})
            assert bad.status_code == 422
            bad_null = await client.patch(f"/api/v1/cases/{case_id}/snapshots/{snap_id}", json={"name": None})
            assert bad_null.status_code == 422

            upd = await client.patch(
                f"/api/v1/cases/{case_id}/snapshots/{snap_id}",
                json={"name": "v1-renamed", "description": "updated", "remark": "fixed"},
            )
            assert upd.status_code == 200
            assert upd.json()["name"] == "v1-renamed"
            assert upd.json()["snapshot_data"]["remark"] == "fixed"

            del_snap = await client.delete(f"/api/v1/cases/{case_id}/snapshots/{snap_id}")
            assert del_snap.status_code == 204
            assert (await client.delete(f"/api/v1/cases/{case_id}/snapshots/{snap_id}")).status_code == 404

            assert (await client.delete(f"/api/v1/runs/{run_active_id}")).status_code == 409
            assert (await client.delete(f"/api/v1/runs/{parent_run_id}")).status_code == 409
            assert (await client.delete(f"/api/v1/runs/{run_done_id}")).status_code == 204

            assert (await client.delete(f"/api/v1/mobile-special/runs/{ms_active_id}")).status_code == 409
            assert (await client.delete(f"/api/v1/mobile-special/runs/{ms_done_id}")).status_code == 204

        async with env.sessions() as db:
            logs = (await db.scalars(select(AuditLog.action))).all()
            assert "case.snapshot.delete" in logs
    finally:
        await env.close()


@pytest.mark.asyncio
async def test_performance_and_defect_and_user_deletes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _AppEnv(tmp_path, monkeypatch)
    deleted_objects: list[str] = []
    try:
        admin, eng, _viewer, project, module = await env.init()
        async with env.sessions() as db:
            perf_test = PerformanceTest(
                project_id=project.id,
                name="Load1",
                executor="k6",
                script_object_name=f"performance/scripts/{project.id}/abc-script.js",
                default_options={},
                creator_id=admin.id,
            )
            db.add(perf_test)
            await db.flush()
            base_run = PerformanceRun(
                performance_test_id=perf_test.id,
                project_id=project.id,
                status=PerformanceRunStatus.success.value,
                options_snapshot={},
                summary={},
            )
            parent_perf_run = PerformanceRun(
                performance_test_id=perf_test.id,
                project_id=project.id,
                status=PerformanceRunStatus.failed.value,
                options_snapshot={},
                summary={},
            )
            active_run = PerformanceRun(
                performance_test_id=perf_test.id,
                project_id=project.id,
                status=PerformanceRunStatus.running.value,
                options_snapshot={},
                summary={},
            )
            db.add_all([base_run, parent_perf_run, active_run])
            await db.flush()
            active_shard = PerformanceRun(
                performance_test_id=perf_test.id,
                project_id=project.id,
                parent_run_id=parent_perf_run.id,
                status=PerformanceRunStatus.running.value,
                options_snapshot={},
                summary={},
            )
            db.add(active_shard)
            await db.flush()
            perf_test.baseline_run_id = base_run.id

            defect = Defect(project_id=project.id, title="Bug1", creator_id=admin.id)
            db.add(defect)

            standalone_user = User(
                username="tempuser",
                email="temp@t.local",
                hashed_password="x",
                role=UserRole.tester,
            )
            # Case owned by eng triggers FK Restrict when deleting eng
            case = TestCase(
                module_id=module.id,
                name="EngCase",
                case_code="TC-002",
                summary="s",
                case_type=CaseType.api,
                status=CaseStatus.draft,
                creator_id=eng.id,
            )
            db.add_all([standalone_user, case])
            await db.commit()
            test_id, base_run_id, parent_perf_id, active_shard_id, active_run_id = (
                perf_test.id,
                base_run.id,
                parent_perf_run.id,
                active_shard.id,
                active_run.id,
            )
            defect_id, standalone_id = defect.id, standalone_user.id

        monkeypatch.setattr(
            env.performance.minio_client,
            "list_objects",
            lambda _prefix: [
                SimpleNamespace(
                    object_name=f"performance/scripts/{project.id}/abc-script.js",
                    size=42,
                    last_modified=datetime.now(timezone.utc),
                )
            ],
        )
        monkeypatch.setattr(env.performance.minio_client, "delete_file", lambda obj: deleted_objects.append(obj))

        async with env.client() as client:
            scripts = await client.get(f"/api/v1/projects/{project.id}/performance/scripts")
            assert scripts.status_code == 200
            assert scripts.json()[0]["filename"] == "script.js"

            # Referenced script cannot be deleted
            ref_del = await client.delete(
                f"/api/v1/projects/{project.id}/performance/scripts",
                params={"object_name": f"performance/scripts/{project.id}/abc-script.js"},
            )
            assert ref_del.status_code == 409

            # Active run or active child shard blocks deleting test & run
            assert (await client.delete(f"/api/v1/performance/tests/{test_id}")).status_code == 409
            assert (await client.delete(f"/api/v1/performance/runs/{active_run_id}")).status_code == 409
            assert (await client.delete(f"/api/v1/performance/runs/{parent_perf_id}")).status_code == 409

            # Deleting baseline run clears baseline_run_id FK cleanly
            assert (await client.delete(f"/api/v1/performance/runs/{base_run_id}")).status_code == 204
            async with env.sessions() as db:
                for run_pk in (active_run_id, active_shard_id):
                    row = await db.get(PerformanceRun, run_pk)
                    assert row is not None
                    row.status = PerformanceRunStatus.cancelled.value
                await db.commit()

            # Now test can be deleted and then script can be deleted
            assert (await client.delete(f"/api/v1/performance/tests/{test_id}")).status_code == 204
            assert (
                await client.delete(
                    f"/api/v1/projects/{project.id}/performance/scripts",
                    params={"object_name": f"performance/scripts/{project.id}/abc-script.js"},
                )
            ).status_code == 204
            assert deleted_objects == [f"performance/scripts/{project.id}/abc-script.js"]
            assert (
                await client.delete(
                    f"/api/v1/projects/{project.id}/performance/scripts",
                    params={"object_name": f"performance/scripts/{project.id}/missing.js"},
                )
            ).status_code == 404
            assert (
                await client.delete(
                    f"/api/v1/projects/{project.id}/performance/scripts",
                    params={"object_name": f"performance/scripts/{project.id}/bad\\script.js"},
                )
            ).status_code == 400

            # Defect delete + audit log
            assert (await client.delete(f"/api/v1/defects/{defect_id}")).status_code == 204

            # User deletion guards: self (400), FK-referenced eng (409), unreferenced (204)
            assert (await client.delete(f"/api/v1/users/{admin.id}")).status_code == 400
            assert (await client.delete(f"/api/v1/users/{eng.id}")).status_code == 409
            assert (await client.delete(f"/api/v1/users/{standalone_id}")).status_code == 204

        async with env.sessions() as db:
            actions = set((await db.scalars(select(AuditLog.action))).all())
            assert {"defect_delete", "delete_user"}.issubset(actions)
    finally:
        await env.close()


@pytest.mark.asyncio
async def test_hermes_android_agent_and_ai_chat_crud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _AppEnv(tmp_path, monkeypatch)
    try:
        admin, _eng, _viewer, project, module = await env.init()
        async with env.sessions() as db:
            h_sess = HermesSession(project_id=project.id, user_id=admin.id, title="Initial", drafts=[])
            ag_idle = AndroidAgentSession(
                project_id=project.id,
                created_by=admin.id,
                title="Agent1",
                goal="open app",
                expected_outcome="home",
                package_name="com.demo",
                status="created",
            )
            ag_run = AndroidAgentSession(
                project_id=project.id,
                created_by=admin.id,
                title="AgentBusy",
                goal="busy",
                expected_outcome="ok",
                package_name="com.demo",
                status="running",
                lease_token="lease-1",
            )
            case = TestCase(
                module_id=module.id,
                name="ChatCase",
                case_code="TC-CHAT",
                summary="s",
                case_type=CaseType.api,
                status=CaseStatus.draft,
                creator_id=admin.id,
            )
            defect = Defect(project_id=project.id, title="ChatDefect", creator_id=admin.id)
            db.add_all([h_sess, ag_idle, ag_run, case, defect])
            await db.flush()
            draft = AndroidAgentDraft(
                project_id=project.id,
                session_id=ag_idle.id,
                version=1,
                status="replayable",
                content_hash="h" * 64,
                steps=[],
                assertions=[],
                variables=[],
                preconditions=[],
                blocking_issues=[],
                source_map={},
                environment_snapshot={},
            )
            db.add(draft)
            await db.flush()
            active_replay = AndroidAgentReplay(
                project_id=project.id,
                session_id=ag_idle.id,
                draft_id=draft.id,
                draft_version=1,
                content_hash="h" * 64,
                idempotency_key="rep-1",
                status="running",
            )
            db.add(active_replay)
            await db.commit()
            ids = (h_sess.id, ag_idle.id, ag_run.id, draft.id, active_replay.id, case.id, defect.id)

        hs_id, ag_idle_id, ag_run_id, draft_id, replay_id, case_id, defect_id = ids
        async with env.client() as client:
            # Hermes session & draft update/delete
            r_hs = await client.patch(
                f"/api/v1/hermes/sessions/{hs_id}",
                json={"project_id": project.id, "title": "Renamed Session"},
            )
            assert r_hs.status_code == 200
            assert r_hs.json()["title"] == "Renamed Session"

            created_draft = await client.post(
                f"/api/v1/hermes/sessions/{hs_id}/drafts",
                json={"project_id": project.id, "draft_type": "defect", "payload": {"title": "D1"}},
            )
            assert created_draft.status_code == 200
            hd_id = created_draft.json()["id"]

            upd_draft = await client.patch(
                f"/api/v1/hermes/sessions/{hs_id}/drafts/{hd_id}",
                json={"project_id": project.id, "payload": {"title": "D1-updated"}},
            )
            assert upd_draft.status_code == 200
            assert upd_draft.json()["payload"]["title"] == "D1-updated"

            assert (
                await client.delete(
                    f"/api/v1/hermes/sessions/{hs_id}/drafts/{hd_id}", params={"project_id": project.id}
                )
            ).status_code == 204
            assert (
                await client.delete(f"/api/v1/hermes/sessions/{hs_id}", params={"project_id": project.id})
            ).status_code == 204

            # Android agent session & draft
            assert (
                await client.patch(
                    f"/api/v1/projects/{project.id}/android-agent/sessions/{ag_run_id}",
                    json={"title": "Nope"},
                )
            ).status_code == 409
            assert (
                await client.delete(f"/api/v1/projects/{project.id}/android-agent/sessions/{ag_run_id}")
            ).status_code == 409

            upd_ag = await client.patch(
                f"/api/v1/projects/{project.id}/android-agent/sessions/{ag_idle_id}",
                json={"title": "AgentUpdated"},
            )
            assert upd_ag.status_code == 200
            assert upd_ag.json()["title"] == "AgentUpdated"
            assert upd_ag.json()["version"] == 2

            assert (
                await client.patch(
                    f"/api/v1/projects/{project.id}/android-agent/sessions/{ag_idle_id}",
                    json={"title": "   "},
                )
            ).status_code == 422

            noop_ag = await client.patch(
                f"/api/v1/projects/{project.id}/android-agent/sessions/{ag_idle_id}",
                json={"title": "AgentUpdated"},
            )
            assert noop_ag.status_code == 200
            assert noop_ag.json()["version"] == 2

            assert (
                await client.delete(f"/api/v1/projects/{project.id}/android-agent/drafts/{draft_id}")
            ).status_code == 409
            assert (
                await client.delete(f"/api/v1/projects/{project.id}/android-agent/sessions/{ag_idle_id}")
            ).status_code == 409

            async with env.sessions() as db:
                replay_row = await db.get(AndroidAgentReplay, replay_id)
                assert replay_row is not None
                replay_row.status = "passed"
                await db.commit()

            assert (
                await client.delete(f"/api/v1/projects/{project.id}/android-agent/drafts/{draft_id}")
            ).status_code == 204
            assert (
                await client.delete(f"/api/v1/projects/{project.id}/android-agent/sessions/{ag_idle_id}")
            ).status_code == 204

            # Bool rejection on AI chat integer ID params
            assert (
                await client.post(
                    "/api/v1/ai/chat/execute-action",
                    json={"project_id": project.id, "action": "delete_case", "params": {"case_id": True}},
                )
            ).status_code == 400
            assert (
                await client.post(
                    "/api/v1/ai/chat/execute-action",
                    json={"project_id": project.id, "action": "delete_defect", "params": {"defect_id": True}},
                )
            ).status_code == 400
            assert (
                await client.post(
                    "/api/v1/ai/chat/execute-action",
                    json={"project_id": project.id, "action": "delete_knowledge", "params": {"knowledge_id": True}},
                )
            ).status_code == 400

            # Hermes chat actions (create/update/delete knowledge + delete case/defect)
            ck = await client.post(
                "/api/v1/ai/chat/execute-action",
                json={
                    "project_id": project.id,
                    "action": "create_knowledge",
                    "params": {"title": "Tip", "content": "Details", "source_type": "runbook"},
                },
            )
            assert ck.status_code == 200
            k_id = ck.json()["resource_id"]

            uk = await client.post(
                "/api/v1/ai/chat/execute-action",
                json={
                    "project_id": project.id,
                    "action": "update_knowledge",
                    "params": {"knowledge_id": k_id, "title": "TipV2", "status": "published"},
                },
            )
            assert uk.status_code == 200

            assert (
                await client.post(
                    "/api/v1/ai/chat/execute-action",
                    json={"project_id": project.id, "action": "update_knowledge", "params": {"knowledge_id": k_id}},
                )
            ).status_code == 400
            assert (
                await client.post(
                    "/api/v1/ai/chat/execute-action",
                    json={
                        "project_id": project.id,
                        "action": "update_knowledge",
                        "params": {"knowledge_id": k_id, "status": "bogus"},
                    },
                )
            ).status_code == 400
            assert (
                await client.post(
                    "/api/v1/ai/chat/execute-action",
                    json={
                        "project_id": project.id,
                        "action": "update_knowledge",
                        "params": {"knowledge_id": k_id, "title": "   "},
                    },
                )
            ).status_code == 400

            async with env.sessions() as db:
                entry = await db.get(KnowledgeEntry, k_id)
                assert entry is not None
                assert entry.title == "TipV2"
                assert entry.status == "published"
                assert entry.version == 2

            assert (
                await client.post(
                    "/api/v1/ai/chat/execute-action",
                    json={"project_id": project.id, "action": "delete_knowledge", "params": {"knowledge_id": k_id}},
                )
            ).status_code == 200
            assert (
                await client.post(
                    "/api/v1/ai/chat/execute-action",
                    json={"project_id": project.id, "action": "delete_case", "params": {"case_id": case_id}},
                )
            ).status_code == 200
            assert (
                await client.post(
                    "/api/v1/ai/chat/execute-action",
                    json={"project_id": project.id, "action": "delete_defect", "params": {"defect_id": defect_id}},
                )
            ).status_code == 200
    finally:
        await env.close()


@pytest.mark.asyncio
async def test_files_grants_alerts_and_web_recordings_crud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import project_file_assets

    env = _AppEnv(tmp_path, monkeypatch)
    monkeypatch.setattr("app.core.config.settings.ATP_LOCAL_MODE", True)
    monkeypatch.setattr("app.core.config.settings.ATP_LOCAL_DATA_DIR", str(tmp_path / "local-store"))
    monkeypatch.setattr(project_file_assets, "ensure_bucket", ensure_store)
    monkeypatch.setattr(project_file_assets, "list_objects", local_list_objects)
    monkeypatch.setattr(project_file_assets, "read_bytes", read_bytes)
    monkeypatch.setattr(project_file_assets, "upload_bytes", upload_bytes)
    monkeypatch.setattr(project_file_assets, "delete_file", local_delete_file)
    ensure_store()

    try:
        _admin, _eng, viewer, project, _module = await env.init()
        api_obj = f"api-files/projects/{project.id}/{'a' * 32}_payload.json"
        web_obj = f"web-files/projects/{project.id}/{'b' * 32}_sample.csv"
        upload_bytes(api_obj, b'{"hello":1}', "application/json")
        upload_bytes(web_obj, b"a,b\n1,2\n", "text/csv")

        async with env.sessions() as db:
            rule = DashboardAlertRule(
                name="FailRate",
                project_id=project.id,
                metric=DashboardAlertMetric.pass_rate,
                op=DashboardAlertOperator.lt,
                threshold=0.9,
            )
            db.add(rule)
            await db.flush()
            event_row = DashboardAlertEvent(
                rule_id=rule.id,
                triggered_at=datetime.now(timezone.utc),
                actual_value=0.5,
            )
            viewer_grant = RemoteNodeGrant(node_client_id="pc-1", user_id=viewer.id, access_level="read_only")
            inactive_user = User(
                username="disabled_u",
                email="disabled@t.local",
                hashed_password="x",
                role=UserRole.engineer,
                is_active=False,
            )
            db.add(inactive_user)
            await db.flush()
            inactive_grant = RemoteNodeGrant(node_client_id="pc-1", user_id=inactive_user.id, access_level="read_only")
            proj_grant = RemoteNodeGrant(node_client_id="pc-1", project_id=project.id, access_level="read_only")
            revoked_grant = RemoteNodeGrant(
                node_client_id="pc-1",
                project_id=project.id,
                access_level="read_only",
                revoked_at=datetime.now(timezone.utc),
            )
            db.add_all([event_row, viewer_grant, inactive_grant, proj_grant, revoked_grant])
            await db.commit()
            event_id, vg_id, ig_id, pg_id, rg_id = (
                event_row.id,
                viewer_grant.id,
                inactive_grant.id,
                proj_grant.id,
                revoked_grant.id,
            )

        # Fake local & remote web recording sessions
        stopped_flags: list[str] = []

        class _FakeSession:
            owner_id = _admin.id
            session_id = "rec-local-1"
            status = "recording"
            finished_at = None

            async def stop(self) -> None:
                stopped_flags.append(self.session_id)

        env.web_recordings.manager.sessions["rec-local-1"] = _FakeSession()  # type: ignore[assignment]
        deleted_remote: list[tuple[str, int]] = []

        async def _fake_remote_delete(session_id: str, owner_id: int) -> None:
            deleted_remote.append((session_id, owner_id))

        monkeypatch.setattr(env.web_recordings.remote_manager, "delete", _fake_remote_delete)

        async with env.client() as client:
            # Project-scoped uploaded request & web files
            for ns_url, orig_obj, new_name, expected_bytes in (
                ("api-request-files", api_obj, "中文报告 renamed?.json", b'{"hello":1}'),
                ("web-files", web_obj, "renamed.csv", b"a,b\n1,2\n"),
            ):
                listed = await client.get(f"/api/v1/projects/{project.id}/{ns_url}")
                assert listed.status_code == 200
                assert any(item["object_name"] == orig_obj for item in listed.json())

                renamed = await client.patch(
                    f"/api/v1/projects/{project.id}/{ns_url}",
                    json={"object_name": orig_obj, "filename": new_name},
                )
                assert renamed.status_code == 200
                new_obj = renamed.json()["object_name"]
                assert read_bytes(new_obj) == expected_bytes
                listed_after = await client.get(f"/api/v1/projects/{project.id}/{ns_url}")
                matched_after = next(item for item in listed_after.json() if item["object_name"] == new_obj)
                assert renamed.json()["filename"] == matched_after["filename"]

                bad_path = await client.delete(
                    f"/api/v1/projects/{project.id}/{ns_url}",
                    params={"object_name": "api-files/projects/999/../secret"},
                )
                assert bad_path.status_code == 400

                assert (
                    await client.delete(f"/api/v1/projects/{project.id}/{ns_url}", params={"object_name": new_obj})
                ).status_code == 204
                assert (
                    await client.delete(f"/api/v1/projects/{project.id}/{ns_url}", params={"object_name": new_obj})
                ).status_code == 404

            # Remote node grants update
            assert (
                await client.patch(
                    f"/api/v1/remote-nodes/pc-1/grants/{vg_id}",
                    json={"access_level": "read_write"},
                )
            ).status_code == 400
            assert (
                await client.patch(
                    f"/api/v1/remote-nodes/pc-1/grants/{ig_id}",
                    json={"access_level": "read_write"},
                )
            ).status_code == 400
            assert (
                await client.patch(
                    f"/api/v1/remote-nodes/pc-1/grants/{rg_id}",
                    json={"access_level": "read_write"},
                )
            ).status_code == 409
            ok_grant = await client.patch(
                f"/api/v1/remote-nodes/pc-1/grants/{pg_id}",
                json={"access_level": "read_write"},
            )
            assert ok_grant.status_code == 200
            assert ok_grant.json()["access_level"] == "read_write"

            # Dashboard alert event update & delete
            snooze_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            upd_evt = await client.patch(
                f"/api/v1/dashboard-alert-events/{event_id}",
                json={"actual_value": 0.42, "snoozed_until": snooze_ts},
            )
            assert upd_evt.status_code == 200
            assert upd_evt.json()["actual_value"] == pytest.approx(0.42)
            assert upd_evt.json()["snoozed_until"] is not None

            unsnooze_evt = await client.patch(
                f"/api/v1/dashboard-alert-events/{event_id}",
                json={"snoozed_until": None},
            )
            assert unsnooze_evt.status_code == 200
            assert unsnooze_evt.json()["snoozed_until"] is None
            assert (await client.delete(f"/api/v1/dashboard-alert-events/{event_id}")).status_code == 204

            # Web recordings local & worker delete
            monkeypatch.setattr(env.web_recordings.settings, "WEB_RECORDER_MODE", "local")
            assert (await client.delete("/api/v1/web-recordings/rec-local-1")).status_code == 204
            assert stopped_flags == ["rec-local-1"]
            assert "rec-local-1" not in env.web_recordings.manager.sessions

            monkeypatch.setattr(env.web_recordings.settings, "WEB_RECORDER_MODE", "worker")
            assert (await client.delete("/api/v1/web-recordings/rec-worker-1")).status_code == 204
            assert deleted_remote == [("rec-worker-1", 1)]
    finally:
        env.web_recordings.manager.sessions.pop("rec-local-1", None)
        await env.close()


@pytest.mark.asyncio
async def test_remote_web_recording_manager_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import web_recording_transport as transport

    mgr = transport.RemoteWebRecordingManager()
    calls: list[tuple] = []
    deleted_ids: list[str] = []

    async def _fake_load(session_id: str):
        if session_id == "s-active":
            return {"owner_id": 7, "project_id": 1, "worker_id": "w-1"}
        return None

    async def _fake_touch(_session_id: str) -> None:
        return None

    async def _fake_send(worker_id: str, action: str, **payload):
        calls.append((worker_id, action, payload))
        return {"ok": True}

    async def _fake_del(session_id: str) -> None:
        deleted_ids.append(session_id)

    monkeypatch.setattr(transport, "load_session_metadata", _fake_load)
    monkeypatch.setattr(transport, "touch_session_metadata", _fake_touch)
    monkeypatch.setattr(transport, "send_recording_command", _fake_send)
    monkeypatch.setattr(transport, "delete_session_metadata", _fake_del)

    await mgr.delete("s-active", owner_id=7)
    assert calls == [("w-1", "stop", {"session_id": "s-active"})]
    assert deleted_ids == ["s-active"]

    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        await mgr.delete("missing", owner_id=7)
    assert excinfo.value.status_code == 404
