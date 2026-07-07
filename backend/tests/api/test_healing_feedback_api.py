"""P3.A iter3 healing 反馈端点测试：采纳/拒绝/幂等/边界。"""

import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_engineer=lambda: None,
    require_admin=_p3c_noop,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)


# stub 上游 import 链中触发真 celery 的两个模块（与 test_case_snapshots_d1.py 一致）
async def _noop_invalidate_stats_cache():
    return None


sys.modules["app.api.v1.statistics"] = types.SimpleNamespace(invalidate_stats_cache=_noop_invalidate_stats_cache)
sys.modules["app.worker.tasks"] = types.SimpleNamespace(
    run_test_case=types.SimpleNamespace(delay=lambda *_a, **_kw: None)
)

from fastapi import HTTPException

from app.api.v1.cases.runs import submit_healing_feedback
from app.models.bootstrap import load_all_models
from app.models.case import RunStatus, StepResult
from app.schemas.case import HealingFeedbackRequest

load_all_models()


class _FakeResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeDB:
    def __init__(self, step):
        self._step = step
        self.commits = 0

    async def execute(self, _stmt):
        return _FakeResult(self._step)

    async def commit(self):
        self.commits += 1


def _make_step(run_id=10, healing_status="done"):
    step = StepResult(id=1, run_id=run_id, step_index=0, name="s")
    step.status = RunStatus.failed
    step.healing_status = healing_status
    step.healing_suggestion = "try X"
    return step


def test_submit_feedback_adopted_writes_field():
    step = _make_step()
    db = _FakeDB(step)
    asyncio.run(
        submit_healing_feedback(run_id=10, step_id=1, body=HealingFeedbackRequest(action="adopted"), db=db, _=None)
    )
    assert step.healing_feedback == "adopted"
    assert step.healing_feedback_at is not None
    assert db.commits == 1


def test_submit_feedback_rejected_writes_field():
    step = _make_step()
    db = _FakeDB(step)
    asyncio.run(
        submit_healing_feedback(run_id=10, step_id=1, body=HealingFeedbackRequest(action="rejected"), db=db, _=None)
    )
    assert step.healing_feedback == "rejected"


def test_submit_feedback_404_when_step_missing():
    db = _FakeDB(None)
    try:
        asyncio.run(
            submit_healing_feedback(
                run_id=10, step_id=999, body=HealingFeedbackRequest(action="adopted"), db=db, _=None
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("expected 404")


def test_submit_feedback_400_when_healing_not_done():
    step = _make_step(healing_status="pending")
    db = _FakeDB(step)
    try:
        asyncio.run(
            submit_healing_feedback(run_id=10, step_id=1, body=HealingFeedbackRequest(action="adopted"), db=db, _=None)
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("expected 400")


def test_submit_feedback_is_idempotent_overwrite():
    """重复提交覆盖最新值。"""
    step = _make_step()
    db = _FakeDB(step)
    asyncio.run(
        submit_healing_feedback(run_id=10, step_id=1, body=HealingFeedbackRequest(action="adopted"), db=db, _=None)
    )
    assert step.healing_feedback == "adopted"
    asyncio.run(
        submit_healing_feedback(run_id=10, step_id=1, body=HealingFeedbackRequest(action="rejected"), db=db, _=None)
    )
    assert step.healing_feedback == "rejected"
    assert db.commits == 2
