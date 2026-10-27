"""D2 Automated Verification: Machine Identity, Summary Sanitization, Outbox Idempotency and Recovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.local_machine_identity import get_machine_id, get_machine_info, get_machine_name
from app.core.local_schema import ensure_local_schema
from app.models.bootstrap import load_all_models
from app.models.case import CaseStatus, CaseType, StepResult, TestCase, TestRun, RunStatus
from app.models.project import Module, Project
from app.models.user import User, UserRole
from app.services.cloud_result_sanitizer import build_cloud_run_summary
from app.services.local_jobs import recover_interrupted_jobs
from app.services import sync_outbox

load_all_models()


def test_machine_identity_persistent_and_stable(tmp_path: Path) -> None:
    """Verify machine identity generates once and remains consistent on repeated reads."""
    info1 = get_machine_info(tmp_path)
    mid1 = info1["machine_id"]
    assert mid1.startswith("win-")
    assert len(mid1) >= 16

    mid2 = get_machine_id(tmp_path)
    assert mid1 == mid2

    # Verify persistent file content
    id_file = tmp_path / ".machine_identity.json"
    assert id_file.is_file()
    saved = json.loads(id_file.read_text(encoding="utf-8"))
    assert saved["machine_id"] == mid1
    assert saved["machine_name"] == get_machine_name()

    # Re-read in another call
    info3 = get_machine_info(tmp_path)
    assert info3["machine_id"] == mid1


def _setup_test_db(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'd2_test.sqlite3'}")
    ensure_local_schema(engine)
    return engine


def test_cloud_result_sanitizer_removes_pii_and_raw_payloads(tmp_path: Path) -> None:
    """Verify summaries redact PII (phone, email) and strip all raw request/response/screenshot data."""
    engine = _setup_test_db(tmp_path)

    raw_error = "Connection failed for user 13800138000 with email secret@company.com and token secret_token_xyz"

    with Session(engine) as session:
        user = User(
            id=1, username="alice", email="alice@test.local", hashed_password="h", role=UserRole.admin, is_active=True
        )
        proj = Project(id=1, name="Safety Project", project_code="SAFE", owner_id=1, status="active")
        mod = Module(id=1, name="Core", module_code="CORE", project_id=1, sort_order=0)
        case = TestCase(
            id=101,
            name="User Login Test",
            summary="Test login",
            case_code="TC_LOGIN_01",
            module_id=1,
            case_type=CaseType.api,
            status=CaseStatus.active,
            creator_id=1,
        )
        run = TestRun(
            id=501,
            case_id=101,
            triggered_by=1,
            status=RunStatus.failed,
            duration_ms=1234,
            error_message=raw_error,
        )
        step = StepResult(
            id=1,
            run_id=501,
            step_index=0,
            name="POST /login",
            status=RunStatus.failed,
            duration_ms=200,
            request_data={"password": "secret123", "body": "large payload"},
            response_data={"token": "eyJ..."},
            screenshot_url="C:\\data\\secret_screen.png",
            error_message="Invalid auth credentials for 13911112222",
        )
        session.add_all([user, proj, mod, case, run, step])
        session.commit()

    with engine.connect() as conn:
        summary = build_cloud_run_summary(
            conn,
            task_name="run_test_case",
            run_id=501,
            client_id="win-client-001",
            machine_name="desktop-box",
        )

        assert summary.client_id == "win-client-001"
        assert summary.unique_key == "win-client-001:case:501"
        assert summary.run_type == "case"
        assert summary.run_id == 501
        assert summary.title == "User Login Test"
        assert summary.status == "failed"
        assert summary.duration_ms == 1234

        # Free-form errors may contain credentials and request bodies: never export them.
        assert summary.error_summary is not None
        assert summary.error_summary == "执行失败；详细错误仅保存在本机报告"
        assert "13800138000" not in summary.error_summary
        assert "secret@company.com" not in summary.error_summary
        assert "secret_token_xyz" not in summary.error_summary

        # Verify steps do NOT expose payloads or screenshot URLs
        assert len(summary.steps) == 1
        st = summary.steps[0]
        assert st.step_index == 0
        assert st.name == "POST /login"
        assert st.status == "failed"
        assert st.error_summary is not None
        assert st.error_summary == "执行失败；详细错误仅保存在本机报告"
        assert "13911112222" not in st.error_summary

        # Check dump json contains no leaked raw payloads or local file paths
        dumped = summary.model_dump_json()
        assert "secret123" not in dumped
        assert "secret_screen.png" not in dumped
        assert "eyJ..." not in dumped


def test_sync_outbox_enqueue_idempotency_and_state_transitions(tmp_path: Path) -> None:
    """Verify outbox deduplication by unique_key, state updates, and retry transitions."""
    engine = _setup_test_db(tmp_path)

    with Session(engine) as session:
        user = User(
            id=1, username="tester", email="t@test.local", hashed_password="h", role=UserRole.admin, is_active=True
        )
        proj = Project(id=1, name="P1", project_code="P1", owner_id=1, status="active")
        mod = Module(id=1, name="M1", module_code="M1", project_id=1, sort_order=0)
        case = TestCase(
            id=10,
            name="TC1",
            summary="sum",
            case_code="TC_001",
            module_id=1,
            case_type=CaseType.api,
            status=CaseStatus.active,
            creator_id=1,
        )
        run = TestRun(
            id=100,
            case_id=10,
            triggered_by=1,
            status=RunStatus.passed,
            duration_ms=50,
        )
        session.add_all([user, proj, mod, case, run])
        session.commit()

    # 1. Record run into outbox
    with engine.begin() as conn:
        key = sync_outbox.record_run_in_outbox(conn, "run_test_case", 100)
        assert key is not None

    # Verify exactly 1 pending record
    with engine.connect() as conn:
        items = sync_outbox.list_outbox_items(conn, status="pending")
        assert len(items) == 1
        assert items[0]["unique_key"] == key
        assert items[0]["status"] == "pending"
        assert items[0]["run_id"] == 100
        stats = sync_outbox.get_outbox_stats(conn)
        assert stats["pending"] == 1
        assert stats["total"] == 1

    # 2. Re-recording the same run is idempotent (deduplication)
    with engine.begin() as conn:
        key2 = sync_outbox.record_run_in_outbox(conn, "run_test_case", 100)
        assert key2 == key

    with engine.connect() as conn:
        items = sync_outbox.list_outbox_items(conn)
        assert len(items) == 1  # No duplicate record created

    # 3. Simulate failure with retry backoff recording
    with engine.begin() as conn:
        failed_ok = sync_outbox.mark_outbox_failed(conn, key, "HTTP 503 Service Unavailable")
        assert failed_ok

    with engine.connect() as conn:
        failed_items = sync_outbox.list_outbox_items(conn, status="failed")
        assert len(failed_items) == 1
        assert failed_items[0]["attempts"] == 1
        assert failed_items[0]["last_error"] == "HTTP 503 Service Unavailable"

    # 4. Reset failed outbox items
    with engine.begin() as conn:
        reset_count = sync_outbox.reset_failed_outbox(conn)
        assert reset_count == 1

    with engine.connect() as conn:
        pending_items = sync_outbox.list_outbox_items(conn, status="pending")
        assert len(pending_items) == 1

    # 5. Mark synced
    with engine.begin() as conn:
        synced_ok = sync_outbox.mark_outbox_synced(conn, key)
        assert synced_ok

    with engine.connect() as conn:
        synced_items = sync_outbox.list_outbox_items(conn, status="synced")
        assert len(synced_items) == 1
        assert synced_items[0]["status"] == "synced"
        assert synced_items[0]["synced_at"] is not None

    # 6. Re-recording an already synced run does not overwrite synced status
    with engine.begin() as conn:
        sync_outbox.record_run_in_outbox(conn, "run_test_case", 100)

    with engine.connect() as conn:
        items = sync_outbox.list_outbox_items(conn)
        assert len(items) == 1
        assert items[0]["status"] == "synced"


def test_local_jobs_recovery_creates_outbox_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify interrupted runs during local ATP crash are converted to terminal state and recorded in outbox."""
    engine = _setup_test_db(tmp_path)
    monkeypatch.setattr("app.services.local_jobs._engine", lambda: engine)

    with Session(engine) as session:
        user = User(id=1, username="u", email="u@test.local", hashed_password="h", role=UserRole.admin, is_active=True)
        proj = Project(id=1, name="P", project_code="P", owner_id=1, status="active")
        mod = Module(id=1, name="M", module_code="M", project_id=1, sort_order=0)
        case = TestCase(
            id=1,
            name="C1",
            summary="S",
            case_code="TC_CRASH_1",
            module_id=1,
            case_type=CaseType.api,
            status=CaseStatus.active,
            creator_id=1,
        )
        run = TestRun(
            id=999,
            case_id=1,
            triggered_by=1,
            status=RunStatus.pending,
            duration_ms=None,
        )
        session.add_all([user, proj, mod, case, run])
        session.commit()

    with engine.begin() as conn:
        run_created_at = conn.exec_driver_sql("SELECT created_at FROM test_runs WHERE id=999").scalar_one()
        # Create a job in 'running' state simulating a crash while running
        conn.exec_driver_sql(
            "INSERT INTO local_jobs (id, task_name, run_id, run_created_at, args_json, status, created_at, started_at) "
            "VALUES (1, 'run_test_case', 999, ?, 'cipher', 'running', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (str(run_created_at),),
        )
    # Trigger recovery on restart
    recovered = recover_interrupted_jobs()
    assert recovered == 1

    with engine.connect() as conn:
        # Verify job is marked interrupted
        job_status = conn.exec_driver_sql("SELECT status FROM local_jobs WHERE id=1").scalar_one()
        assert job_status == "interrupted"

        # Verify run is marked error
        run_status = conn.exec_driver_sql("SELECT status FROM test_runs WHERE id=999").scalar_one()
        assert run_status == "error"

        # Verify outbox has recorded this interrupted run
        outbox_items = sync_outbox.list_outbox_items(conn)
        assert len(outbox_items) == 1
        assert outbox_items[0]["run_id"] == 999
        assert outbox_items[0]["payload"]["status"] == "error"
        assert outbox_items[0]["payload"]["error_summary"] == "执行失败；详细错误仅保存在本机报告"
