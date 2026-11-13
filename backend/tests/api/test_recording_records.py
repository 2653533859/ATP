"""录制历史、草稿与 Web 证据持久化 API 及自动保存回归测试。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1 import recording_records, web_recordings
from app.models.base import Base
from app.models.case import CaseType, TestCase
from app.models.project import Module, Project
from app.models.recording_record import RecordingRecord
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject, role_satisfies
from app.schemas.recording_record import RecordingRecordCreate, RecordingRecordUpdate
from app.services import recording_records as record_service

from app.models.bootstrap import load_all_models

load_all_models()


async def _setup_db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'recording_records.sqlite3'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessions() as db:
        owner = User(username="owner", email="owner@example.test", hashed_password="x", role=UserRole.tester)
        editor = User(username="editor", email="editor@example.test", hashed_password="x", role=UserRole.tester)
        viewer = User(username="viewer", email="viewer@example.test", hashed_password="x", role=UserRole.tester)
        outsider = User(username="outsider", email="outsider@example.test", hashed_password="x", role=UserRole.tester)
        db.add_all([owner, editor, viewer, outsider])
        await db.flush()

        project_a = Project(name="Project A", project_code="PROJA", owner_id=owner.id, status="active")
        project_b = Project(name="Project B", project_code="PROJB", owner_id=owner.id, status="active")
        db.add_all([project_a, project_b])
        await db.flush()

        db.add_all(
            [
                UserProject(user_id=editor.id, project_id=project_a.id, role=ProjectRole.editor),
                UserProject(user_id=viewer.id, project_id=project_a.id, role=ProjectRole.viewer),
            ]
        )

        mod_a = Module(name="Root A", project_id=project_a.id)
        mod_b = Module(name="Root B", project_id=project_b.id)
        db.add_all([mod_a, mod_b])
        await db.flush()

        case_a = TestCase(
            name="App 登录",
            case_code="ATP-REC-0001",
            summary="App 登录用例",
            case_type=CaseType.android,
            module_id=mod_a.id,
            creator_id=owner.id,
            owner_id=owner.id,
            steps=[],
        )
        case_b = TestCase(
            name="他项目用例",
            case_code="ATP-REC-0002",
            summary="他项目用例",
            case_type=CaseType.android,
            module_id=mod_b.id,
            creator_id=owner.id,
            owner_id=owner.id,
            steps=[],
        )
        db.add_all([case_a, case_b])
        await db.commit()
        ids = {
            "owner": owner,
            "editor": editor,
            "viewer": viewer,
            "outsider": outsider,
            "project_a_id": project_a.id,
            "project_b_id": project_b.id,
            "case_a_id": case_a.id,
            "case_b_id": case_b.id,
        }
    return engine, sessions, ids


@pytest.mark.asyncio
async def test_recording_record_crud_redaction_and_upsert(tmp_path):
    engine, sessions, ctx = await _setup_db(tmp_path)
    try:
        async with sessions() as db:
            created = await recording_records.create_recording_record(
                RecordingRecordCreate(
                    project_id=ctx["project_a_id"],
                    kind="android",
                    source="mirror",
                    session_id="app-draft-1",
                    device_serial="172.16.101.11:5555",
                    target_url="https://example.test/login?token=secret123&tab=1",
                    steps=[
                        {
                            "action": "input_text",
                            "name": "输入敏感值",
                            "params": {"text": "p@ss", "value": "p@ss", "sensitive": True},
                        },
                        {"action": "assert_text_exists", "name": "断言登录成功", "params": {"text": "欢迎"}},
                    ],
                    summary={"device_name": "Pixel 8", "url": "https://example.test/cb?code=abc"},
                ),
                db=db,
                user=ctx["editor"],
            )
            assert created.kind == "android"
            assert created.status == "draft"
            assert created.steps_count == 2
            assert created.assertion_count == 1
            assert created.steps[0]["params"]["value"] == ""
            assert created.steps[0]["params"]["text"] == ""
            assert "secret123" not in (created.target_url or "")
            assert "code=abc" not in str(created.summary.get("url") or "")
            assert "Pixel 8" in created.title

            # Same (kind, session_id, project_id) performs idempotent upsert rather than duplicating rows.
            updated_upsert = await recording_records.create_recording_record(
                RecordingRecordCreate(
                    project_id=ctx["project_a_id"],
                    kind="android",
                    source="visual_editor",
                    session_id="app-draft-1",
                    device_serial="172.16.101.11:5555",
                    steps=[
                        {"action": "tap", "name": "点击登录", "params": {"x": 120, "y": 240}},
                    ],
                ),
                db=db,
                user=ctx["editor"],
            )
            assert updated_upsert.id == created.id
            assert updated_upsert.source == "visual_editor"
            assert updated_upsert.steps_count == 1

            patched = await recording_records.patch_recording_record(
                created.id,
                RecordingRecordUpdate(status="saved", case_id=ctx["case_a_id"], title="已保存登录草稿"),
                db=db,
                user=ctx["editor"],
            )
            assert patched.status == "saved"
            assert patched.case_id == ctx["case_a_id"]
            assert patched.title == "已保存登录草稿"

            listed = await recording_records.get_recording_records(
                project_id=ctx["project_a_id"],
                kind="android",
                status_filter="saved",
                limit=20,
                db=db,
                user=ctx["viewer"],
            )
            assert [item.id for item in listed] == [created.id]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recording_record_rbac_case_validation_and_artifact_refresh(tmp_path, monkeypatch):
    engine, sessions, ctx = await _setup_db(tmp_path)
    sign_calls: list[str] = []
    deleted_objects: list[str] = []

    def fake_presigned(object_name: str) -> str:
        sign_calls.append(object_name)
        return f"https://minio.local/{object_name}?sig={len(sign_calls)}"

    monkeypatch.setattr(record_service, "presigned_url", fake_presigned)
    monkeypatch.setattr(record_service, "delete_file", lambda object_name: deleted_objects.append(object_name))

    async def _db_project_access(db, user, project_id, min_role=ProjectRole.viewer):
        if user.role == UserRole.admin:
            return
        role = (
            await db.execute(
                select(UserProject.role).where(
                    UserProject.user_id == user.id,
                    UserProject.project_id == project_id,
                )
            )
        ).scalar_one_or_none()
        if role is None or not role_satisfies(role, min_role):
            raise HTTPException(status_code=403, detail="No access to this project")

    monkeypatch.setattr(recording_records, "assert_project_access", _db_project_access)

    try:
        async with sessions() as db:
            record = RecordingRecord(
                project_id=ctx["project_a_id"],
                owner_id=ctx["editor"].id,
                kind="web",
                source="workbench",
                session_id="sess-art-1",
                title="Web 录制 · demo.local",
                status="draft",
                steps=[{"action": "goto", "name": "打开页面", "params": {"url": "https://demo.local"}}],
                asset_ids=[],
                artifacts={
                    "trace": {
                        "kind": "trace",
                        "filename": "trace.zip",
                        "content_type": "application/zip",
                        "size": 1024,
                        "object_name": "traces/recordings/1/sess-art-1/trace.zip",
                    },
                    "har": {
                        "kind": "har",
                        "filename": "network.har",
                        "content_type": "application/json",
                        "size": 512,
                        "object_name": "reports/recordings/1/sess-art-1/network.har",
                    },
                },
                summary={},
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)

            # Viewer can read and gets freshly signed URLs on every read.
            first_read = await recording_records.get_recording_record(record.id, db=db, user=ctx["viewer"])
            second_read = await recording_records.get_recording_record(record.id, db=db, user=ctx["viewer"])
            assert first_read.artifacts["trace"].url != second_read.artifacts["trace"].url
            assert "trace.zip?sig=" in (first_read.artifacts["trace"].url or "")
            assert "network.har?sig=" in (second_read.artifacts["har"].url or "")

            # Viewer cannot create, patch, or delete.
            with pytest.raises(HTTPException) as exc_create:
                await recording_records.create_recording_record(
                    RecordingRecordCreate(project_id=ctx["project_a_id"], kind="android", steps=[]),
                    db=db,
                    user=ctx["viewer"],
                )
            assert exc_create.value.status_code == 403

            with pytest.raises(HTTPException) as exc_patch:
                await recording_records.patch_recording_record(
                    record.id,
                    RecordingRecordUpdate(title="denied"),
                    db=db,
                    user=ctx["viewer"],
                )
            assert exc_patch.value.status_code == 403

            with pytest.raises(HTTPException) as exc_del:
                await recording_records.remove_recording_record(record.id, db=db, user=ctx["viewer"])
            assert exc_del.value.status_code == 403

            # Outsider cannot read.
            with pytest.raises(HTTPException) as exc_outsider:
                await recording_records.get_recording_record(record.id, db=db, user=ctx["outsider"])
            assert exc_outsider.value.status_code == 403

            # Linking a case from another project returns 400.
            with pytest.raises(HTTPException) as exc_cross_case:
                await recording_records.patch_recording_record(
                    record.id,
                    RecordingRecordUpdate(case_id=ctx["case_b_id"]),
                    db=db,
                    user=ctx["editor"],
                )
            assert exc_cross_case.value.status_code == 400

            # Editor deletes record and artifacts are removed from storage.
            await recording_records.remove_recording_record(record.id, db=db, user=ctx["editor"])
            assert set(deleted_objects) == {
                "traces/recordings/1/sess-art-1/trace.zip",
                "reports/recordings/1/sess-art-1/network.har",
            }
            assert await db.get(RecordingRecord, record.id) is None

            with pytest.raises(HTTPException) as exc_missing:
                await recording_records.get_recording_record(record.id, db=db, user=ctx["editor"])
            assert exc_missing.value.status_code == 404
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_web_recording_stop_and_terminal_get_persist_record_idempotently(tmp_path, monkeypatch):
    engine, sessions, ctx = await _setup_db(tmp_path)
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_MODE", "local")
    monkeypatch.setattr(record_service, "presigned_url", lambda obj: f"https://minio.local/{obj}?fresh=1")

    local_session = web_recordings.WebRecordingSession(
        session_id="web-sess-auto-1",
        owner_id=ctx["editor"].id,
        start_url="https://app.example.test/login?secret=1",
        viewport_width=1280,
        viewport_height=720,
        project_id=ctx["project_a_id"],
        browser_name="chromium",
        source="workbench",
        status="recording",
        steps=[
            {"action": "goto", "name": "打开页面", "params": {"url": "https://app.example.test/login?secret=1"}},
            {"action": "assert_visible", "name": "断言可见 #login", "params": {"selector": "#login"}},
        ],
        artifacts={
            "trace": {
                "kind": "trace",
                "filename": "trace.zip",
                "content_type": "application/zip",
                "size": 2048,
                "object_name": "traces/recordings/1/web-sess-auto-1/trace.zip",
                "url": "https://minio.local/stale",
            },
            "har": {
                "kind": "har",
                "filename": "network.har",
                "content_type": "application/json",
                "size": 1024,
                "object_name": "reports/recordings/1/web-sess-auto-1/network.har",
                "url": "https://minio.local/stale",
            },
        },
    )

    async def fake_stop():
        local_session.status = "stopped"

    monkeypatch.setattr(local_session, "stop", fake_stop)
    web_recordings.manager.sessions[local_session.session_id] = local_session

    try:
        async with sessions() as db:
            # Simulates direct browser window close discovered by polling GET before /stop is called.
            local_session.status = "stopped"
            poll_snapshot = await web_recordings.get_recording(local_session.session_id, user=ctx["editor"], db=db)
            assert poll_snapshot["recording_record_id"] is not None

            # Subsequent poll does not duplicate elements or rows.
            second_poll = await web_recordings.get_recording(local_session.session_id, user=ctx["editor"], db=db)
            assert second_poll["recording_record_id"] == poll_snapshot["recording_record_id"]

            # Explicit stop keeps the same RecordingRecord id and updates cleanly.
            stop_snapshot = await web_recordings.stop_recording(local_session.session_id, db=db, user=ctx["editor"])
            assert stop_snapshot["recording_record_id"] == poll_snapshot["recording_record_id"]

            rows = (
                (
                    await db.execute(
                        select(RecordingRecord).where(RecordingRecord.session_id == local_session.session_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0].status == "draft"
            assert rows[0].artifacts["trace"]["object_name"] == "traces/recordings/1/web-sess-auto-1/trace.zip"
            assert "url" not in rows[0].artifacts["trace"]
            assert rows[0].asset_ids == stop_snapshot["asset_ids"]

            fetched = await recording_records.get_recording_record(rows[0].id, db=db, user=ctx["viewer"])
            assert (
                fetched.artifacts["trace"].url
                == "https://minio.local/traces/recordings/1/web-sess-auto-1/trace.zip?fresh=1"
            )
            assert fetched.assertion_count == 1

            rebuilt = web_recordings._session_from_snapshot(stop_snapshot, ctx["editor"].id)
            assert rebuilt.source == "workbench"
            assert rebuilt.recording_record_id == rows[0].id
    finally:
        web_recordings.manager.sessions.pop(local_session.session_id, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_recording_record_cross_project_session_isolation_and_conflict(tmp_path, monkeypatch):
    engine, sessions, ctx = await _setup_db(tmp_path)

    async def _allow_project_access(db, user, project_id, min_role=ProjectRole.viewer):
        return None

    monkeypatch.setattr(recording_records, "assert_project_access", _allow_project_access)

    try:
        async with sessions() as db:
            rec_a = await recording_records.create_recording_record(
                RecordingRecordCreate(
                    project_id=ctx["project_a_id"],
                    kind="android",
                    source="mirror",
                    session_id="shared-sess-01",
                    status="draft",
                    steps=[{"action": "tap", "name": "项目A点击", "params": {"x": 10, "y": 20}}],
                ),
                db=db,
                user=ctx["owner"],
            )
            rec_b = await recording_records.create_recording_record(
                RecordingRecordCreate(
                    project_id=ctx["project_b_id"],
                    kind="android",
                    source="mirror",
                    session_id="shared-sess-01",
                    status="draft",
                    steps=[{"action": "tap", "name": "项目B点击", "params": {"x": 30, "y": 40}}],
                ),
                db=db,
                user=ctx["owner"],
            )
            assert rec_a.id != rec_b.id
            assert rec_a.project_id == ctx["project_a_id"]
            assert rec_b.project_id == ctx["project_b_id"]

            rows = (await db.execute(select(RecordingRecord).order_by(RecordingRecord.id.asc()))).scalars().all()
            assert len(rows) == 2

            async def _miss_existing(*args, **kwargs):
                return None

            monkeypatch.setattr(record_service, "get_recording_record_by_session", _miss_existing)
            with pytest.raises(HTTPException) as exc_info:
                await recording_records.create_recording_record(
                    RecordingRecordCreate(
                        project_id=ctx["project_a_id"],
                        kind="android",
                        source="mirror",
                        session_id="shared-sess-01",
                        status="draft",
                        steps=[{"action": "tap", "name": "重复冲突", "params": {"x": 1, "y": 2}}],
                    ),
                    db=db,
                    user=ctx["owner"],
                )
            assert exc_info.value.status_code == 409
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_web_recording_assets_source_stops_cleanly_and_drops_unsafe_fallback_urls(tmp_path):
    engine, sessions, ctx = await _setup_db(tmp_path)
    try:
        async with sessions() as db:
            record = await record_service.upsert_web_recording_record(
                db,
                {
                    "id": "web-assets-only-1",
                    "project_id": ctx["project_a_id"],
                    "source": "assets",
                    "start_url": "https://example.test/login",
                    "browser": "chromium",
                    "status": "stopped",
                    "steps": [{"action": "goto", "name": "打开页面", "params": {"url": "https://example.test/login"}}],
                    "asset_ids": [77],
                    "artifacts": {
                        "trace": {
                            "kind": "trace",
                            "filename": "trace.zip",
                            "content_type": "application/zip",
                            "size": 100,
                            "object_name": "recordings/1/web-assets-only-1/trace.zip",
                        }
                    },
                },
                owner_id=ctx["editor"].id,
            )
            assert record is not None
            assert record.status == "stopped"

            reused = await record_service.upsert_web_recording_record(
                db,
                {
                    "id": "web-assets-only-1",
                    "project_id": ctx["project_a_id"],
                    "source": "assets",
                    "start_url": "https://example.test/login",
                    "browser": "chromium",
                    "status": "stopped",
                    "steps": [{"action": "goto", "name": "打开页面", "params": {"url": "https://example.test/login"}}],
                    "asset_ids": [],
                    "artifacts": {},
                },
                owner_id=ctx["editor"].id,
            )
            assert reused is not None
            assert reused.id == record.id
            assert reused.asset_ids == [77]

            reused.artifacts = {
                "trace": {
                    "kind": "trace",
                    "filename": "trace.zip",
                    "content_type": "application/zip",
                    "size": 100,
                    "url": "javascript:alert(1)",
                },
                "har": {
                    "kind": "har",
                    "filename": "har.json",
                    "content_type": "application/json",
                    "size": 80,
                    "url": "//evil.example/har.json",
                },
                "report": {
                    "kind": "report",
                    "filename": "report.html",
                    "content_type": "text/html",
                    "size": 120,
                    "url": "/api/v1/files/report.html",
                },
            }
            await db.commit()
            await db.refresh(reused)

            serialized = await record_service.serialize_recording_record(reused)
            assert serialized.artifacts["trace"].url is None
            assert serialized.artifacts["har"].url is None
            assert serialized.artifacts["report"].url == "/api/v1/files/report.html"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_web_recording_concurrent_get_and_stop_persists_once(tmp_path, monkeypatch):
    import asyncio

    engine, sessions, ctx = await _setup_db(tmp_path)
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_MODE", "local")
    monkeypatch.setattr(record_service, "presigned_url", lambda obj: f"https://minio.local/{obj}?sig=concurrent")

    local_session = web_recordings.WebRecordingSession(
        session_id="web-conc-1",
        owner_id=ctx["editor"].id,
        start_url="https://app.example.test/home",
        viewport_width=1280,
        viewport_height=720,
        project_id=ctx["project_a_id"],
        source="workbench",
    )
    local_session.status = "stopped"
    local_session.steps = [{"action": "goto", "name": "访问首页", "params": {"url": "https://app.example.test/home"}}]
    web_recordings.manager.sessions[local_session.session_id] = local_session

    async def _poll_terminal():
        async with sessions() as db1:
            return await web_recordings.get_recording(local_session.session_id, user=ctx["editor"], db=db1)

    async def _finalize_stop():
        async with sessions() as db2:
            return await web_recordings._persist_terminal_recording(
                db2, local_session, ctx["editor"].id, force_record_upsert=True
            )

    try:
        snap1, snap2 = await asyncio.gather(_poll_terminal(), _finalize_stop())
        assert snap1["recording_record_id"] is not None
        assert snap1["recording_record_id"] == snap2["recording_record_id"]

        async with sessions() as db:
            rows = (
                (await db.execute(select(RecordingRecord).where(RecordingRecord.session_id == "web-conc-1")))
                .scalars()
                .all()
            )
            assert len(rows) == 1
    finally:
        web_recordings.manager.sessions.pop(local_session.session_id, None)
        await engine.dispose()
