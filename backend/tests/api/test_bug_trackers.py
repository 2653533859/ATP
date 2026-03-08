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
sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=_fake_get_current_user,
    require_engineer=_fake_require_engineer,
)

from app.api.v1 import bug_trackers


class _FakeDB:
    def __init__(self, *, run, tracker, case, module):
        self._run = run
        self._tracker = tracker
        self._case = case
        self._module = module
        self.committed = False

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

    async def commit(self):
        self.committed = True


def test_create_bug_from_run_rejects_tracker_from_other_project(monkeypatch):
    async def fake_create_bug(**_kwargs):
        raise AssertionError("should not create bug for cross-project tracker")

    monkeypatch.setattr(bug_trackers, "create_bug", fake_create_bug)

    db = _FakeDB(
        run=types.SimpleNamespace(id=5, case_id=9, environment="test", error_message="boom", result_summary={}),
        tracker=types.SimpleNamespace(id=3, project_id=2, tracker_type=types.SimpleNamespace(value="jira"), config={}, is_enabled=True),
        case=types.SimpleNamespace(id=9, module_id=7, name="支付失败"),
        module=types.SimpleNamespace(id=7, project_id=1),
    )
    body = bug_trackers.CreateBugRequest(tracker_id=3)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(bug_trackers.create_bug_from_run(run_id=5, body=body, db=db, _=None))

    assert exc.value.status_code == 400
    assert db.committed is False

