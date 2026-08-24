import asyncio
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _fake_get_current_user():
    return None


def _fake_require_engineer():
    return None


sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=_fake_get_current_user,
    require_engineer=_fake_require_engineer,
    require_admin=_p3c_noop,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)
_minio = sys.modules.setdefault("app.core.minio_client", types.SimpleNamespace())
_minio.read_bytes = lambda _name: b"img"

from app.api.v1 import bug_trackers
from app.models.bug_tracker import TrackerType


class _FakeDB:
    def __init__(self, *, run, tracker, case, module, step=None):
        self._run = run
        self._tracker = tracker
        self._case = case
        self._module = module
        self._step = step
        self.committed = False
        self.execute_calls = 0

    async def get(self, model, _pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "TestRun":
            return self._run
        if model_name == "BugTracker":
            return self._tracker
        if model_name == "TestCase":
            return self._case
        if model_name == "Module":
            return self._module
        return None

    async def execute(self, _stmt):
        self.execute_calls += 1
        return types.SimpleNamespace(
            scalar_one_or_none=lambda: self._step,
            scalars=lambda: types.SimpleNamespace(first=lambda: self._step),
            first=lambda: (self._tracker, self._module),
        )

    async def commit(self):
        self.committed = True


def test_create_bug_from_run_rejects_tracker_from_other_project(monkeypatch):
    async def fake_create_bug(**_kwargs):
        raise AssertionError("should not create bug for cross-project tracker")

    monkeypatch.setattr(bug_trackers, "create_bug", fake_create_bug)

    db = _FakeDB(
        run=types.SimpleNamespace(id=5, case_id=9, environment="test", error_message="boom", result_summary={}),
        tracker=types.SimpleNamespace(
            id=3,
            project_id=2,
            tracker_type=types.SimpleNamespace(value="jira"),
            config={},
            field_mapping={},
            is_enabled=True,
        ),
        case=types.SimpleNamespace(id=9, module_id=7, name="支付失败"),
        module=types.SimpleNamespace(id=7, project_id=1),
    )
    body = bug_trackers.CreateBugRequest(tracker_id=3)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(bug_trackers.create_bug_from_run(run_id=5, body=body, db=db, _=None))

    assert exc.value.status_code == 400
    assert db.committed is False


def test_test_bug_tracker_connection_returns_false_on_error(monkeypatch):
    async def fake_test_connection(*_args, **_kwargs):
        raise RuntimeError("auth failed: token=raw-secret")

    monkeypatch.setattr(bug_trackers, "test_connection", fake_test_connection)
    body = bug_trackers.BugTrackerConnectionTestRequest(tracker_type=TrackerType.jira, config={})

    result = asyncio.run(bug_trackers.test_bug_tracker_connection(body=body, _=None))

    assert result.ok is False
    assert "auth failed" in result.message
    assert "raw-secret" not in result.message
    assert "token=[REDACTED]" in result.message


def test_create_bug_from_run_redacts_provider_error(monkeypatch):
    async def fake_find_duplicate_bug(**_kwargs):
        return None

    async def fake_create_bug(**_kwargs):
        raise RuntimeError("provider rejected https://user:password@example.com/hook?token=raw-secret")

    monkeypatch.setattr(bug_trackers, "find_duplicate_bug", fake_find_duplicate_bug)
    monkeypatch.setattr(bug_trackers, "create_bug", fake_create_bug)

    db = _FakeDB(
        run=types.SimpleNamespace(id=5, case_id=9, environment="test", error_message="boom", result_summary={}),
        tracker=types.SimpleNamespace(
            id=3,
            project_id=1,
            tracker_type=types.SimpleNamespace(value="jira"),
            config={},
            field_mapping={},
            is_enabled=True,
        ),
        case=types.SimpleNamespace(id=9, module_id=7, name="支付失败"),
        module=types.SimpleNamespace(id=7, project_id=1),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            bug_trackers.create_bug_from_run(
                run_id=5,
                body=bug_trackers.CreateBugRequest(tracker_id=3),
                db=db,
                _=None,
            )
        )

    assert exc.value.status_code == 502
    assert "raw-secret" not in str(exc.value.detail)
    assert "password" not in str(exc.value.detail)


def test_get_run_bug_status_redacts_provider_error(monkeypatch):
    async def fake_get_bug_status(**_kwargs):
        raise RuntimeError("status failed: api_key=raw-secret")

    monkeypatch.setattr(bug_trackers, "get_bug_status", fake_get_bug_status)
    run = types.SimpleNamespace(
        id=5,
        case_id=9,
        result_summary={"bug": {"bug_id": "99", "bug_url": "https://jira/browse/99", "title": "bug"}},
    )
    tracker = types.SimpleNamespace(
        id=3,
        project_id=1,
        tracker_type=types.SimpleNamespace(value="jira"),
        config={},
        field_mapping={},
        is_enabled=True,
    )
    db = _FakeDB(
        run=run,
        tracker=tracker,
        case=types.SimpleNamespace(id=9, module_id=7, name="支付失败"),
        module=types.SimpleNamespace(id=7, project_id=1),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(bug_trackers.get_run_bug_status(run_id=5, db=db, _=None))

    assert exc.value.status_code == 502
    assert "raw-secret" not in str(exc.value.detail)
    assert "api_key=[REDACTED]" in str(exc.value.detail)


def test_test_bug_tracker_connection_uses_decrypted_saved_config(monkeypatch):
    captured = {}

    async def fake_test_connection(tracker_type, config):
        captured["tracker_type"] = tracker_type
        captured["config"] = config
        return {"ok": True, "message": "ok"}

    monkeypatch.setattr(bug_trackers, "test_connection", fake_test_connection)

    tracker = types.SimpleNamespace(
        id=3,
        project_id=1,
        tracker_type=TrackerType.jira,
        config=bug_trackers.encrypt_config(
            {
                "base_url": "https://jira.example.com",
                "email": "qa@example.com",
                "api_token": "plain-token",
                "project_key": "ATP",
            }
        ),
        field_mapping={},
        is_enabled=True,
    )
    db = _FakeDB(run=None, tracker=tracker, case=None, module=None)
    body = bug_trackers.BugTrackerConnectionTestRequest(
        tracker_id=3,
        tracker_type=TrackerType.jira,
        config={},
    )

    result = asyncio.run(bug_trackers.test_bug_tracker_connection(body=body, db=db, _=None))

    assert result.ok is True
    assert captured["tracker_type"] == "jira"
    assert captured["config"]["api_token"] == "plain-token"
    assert captured["config"]["base_url"] == "https://jira.example.com"


def test_create_bug_from_run_returns_duplicate_without_creating(monkeypatch):
    async def fake_find_duplicate_bug(**_kwargs):
        return {"bug_id": "ATP-12", "bug_url": "https://jira/browse/ATP-12", "title": "[ATP] 支付失败 执行失败"}

    async def fake_create_bug(**_kwargs):
        raise AssertionError("duplicate should short-circuit create")

    monkeypatch.setattr(bug_trackers, "find_duplicate_bug", fake_find_duplicate_bug)
    monkeypatch.setattr(bug_trackers, "create_bug", fake_create_bug)

    run = types.SimpleNamespace(id=5, case_id=9, environment="test", error_message="boom", result_summary={})
    db = _FakeDB(
        run=run,
        tracker=types.SimpleNamespace(
            id=3,
            project_id=1,
            tracker_type=types.SimpleNamespace(value="jira"),
            config={},
            field_mapping={},
            is_enabled=True,
        ),
        case=types.SimpleNamespace(id=9, module_id=7, name="支付失败"),
        module=types.SimpleNamespace(id=7, project_id=1),
    )
    body = bug_trackers.CreateBugRequest(tracker_id=3)

    result = asyncio.run(bug_trackers.create_bug_from_run(run_id=5, body=body, db=db, _=None))

    assert result.duplicate_of == "ATP-12"
    assert result.attachment_uploaded is False
    assert run.result_summary["bug"]["bug_id"] == "ATP-12"
    assert run.result_summary["bug"]["duplicate_of"] == "ATP-12"
    assert run.result_summary["bug"]["tracker_id"] == 3
    assert db.committed is True


def test_get_run_bug_status_updates_result_summary(monkeypatch):
    async def fake_get_bug_status(**_kwargs):
        return {"bug_id": "99", "status": "closed", "bug_url": "https://jira/browse/99"}

    monkeypatch.setattr(bug_trackers, "get_bug_status", fake_get_bug_status)

    run = types.SimpleNamespace(
        id=5, case_id=9, result_summary={"bug": {"bug_id": "99", "bug_url": "https://jira/browse/99", "title": "bug"}}
    )
    tracker = types.SimpleNamespace(
        id=3,
        project_id=1,
        tracker_type=types.SimpleNamespace(value="jira"),
        config={},
        field_mapping={},
        is_enabled=True,
    )
    db = _FakeDB(
        run=run,
        tracker=tracker,
        case=types.SimpleNamespace(id=9, module_id=7, name="支付失败"),
        module=types.SimpleNamespace(id=7, project_id=1),
    )

    result = asyncio.run(bug_trackers.get_run_bug_status(run_id=5, db=db, _=None))

    assert result.status == "closed"
    assert run.result_summary["bug"]["status"] == "closed"
    assert db.committed is True


def test_get_run_bug_status_prefers_persisted_tracker_id(monkeypatch):
    captured = {}

    async def fake_get_bug_status(**kwargs):
        captured.update(kwargs)
        return {"bug_id": "99", "status": "open", "bug_url": "https://github/issues/99"}

    monkeypatch.setattr(bug_trackers, "get_bug_status", fake_get_bug_status)

    run = types.SimpleNamespace(
        id=5,
        case_id=9,
        result_summary={
            "bug": {
                "bug_id": "99",
                "bug_url": "https://github/issues/99",
                "title": "bug",
                "tracker_id": 3,
            }
        },
    )
    tracker = types.SimpleNamespace(
        id=3,
        project_id=1,
        tracker_type=TrackerType.github,
        config=bug_trackers.encrypt_config(
            {
                "base_url": "https://api.github.com",
                "owner": "octo-org",
                "repo": "atp",
                "token": "ghp_secret",
            }
        ),
        field_mapping={},
        is_enabled=True,
    )
    db = _FakeDB(
        run=run,
        tracker=tracker,
        case=types.SimpleNamespace(id=9, module_id=7, name="支付失败"),
        module=types.SimpleNamespace(id=7, project_id=1),
    )

    result = asyncio.run(bug_trackers.get_run_bug_status(run_id=5, db=db, _=None))

    assert result.status == "open"
    assert captured["tracker_type"] == "github"
    assert captured["config"]["token"] == "ghp_secret"
    assert db.execute_calls == 0


def test_create_bug_from_run_uploads_attachment_from_presigned_screenshot(monkeypatch):
    captured = {}

    async def fake_find_duplicate_bug(**_kwargs):
        return None

    async def fake_create_bug(**kwargs):
        captured["create_bug"] = kwargs
        return {"bug_id": "ATP-99", "bug_url": "https://jira/browse/ATP-99", "title": kwargs["title"]}

    async def fake_upload_attachment(**kwargs):
        captured["upload_attachment"] = kwargs
        return True

    monkeypatch.setattr(bug_trackers, "find_duplicate_bug", fake_find_duplicate_bug)
    monkeypatch.setattr(bug_trackers, "create_bug", fake_create_bug)
    monkeypatch.setattr(bug_trackers, "upload_attachment", fake_upload_attachment)
    monkeypatch.setattr(bug_trackers, "decrypt_config", lambda value: value)
    monkeypatch.setattr(bug_trackers, "read_bytes", lambda object_name: f"bytes:{object_name}".encode())

    run = types.SimpleNamespace(id=5, case_id=9, environment="test", error_message="boom", result_summary={})
    step = types.SimpleNamespace(
        screenshot_url="http://minio:9000/atp/screenshots/runs/5/step_0.png?X-Amz-Signature=abc"
    )
    db = _FakeDB(
        run=run,
        tracker=types.SimpleNamespace(
            id=3,
            project_id=1,
            tracker_type=types.SimpleNamespace(value="jira"),
            config={"base_url": "https://jira.example.com"},
            field_mapping={},
            is_enabled=True,
        ),
        case=types.SimpleNamespace(id=9, module_id=7, name="支付失败"),
        module=types.SimpleNamespace(id=7, project_id=1),
        step=step,
    )

    result = asyncio.run(
        bug_trackers.create_bug_from_run(run_id=5, body=bug_trackers.CreateBugRequest(tracker_id=3), db=db, _=None)
    )

    assert result.bug_id == "ATP-99"
    assert result.attachment_uploaded is True
    assert captured["upload_attachment"] == {
        "tracker_type": "jira",
        "config": {"base_url": "https://jira.example.com"},
        "bug_id": "ATP-99",
        "filename": "run-5-screenshot.png",
        "content": b"bytes:screenshots/runs/5/step_0.png",
    }
    assert run.result_summary["bug"]["attachment_uploaded"] is True
    assert db.committed is True
