"""P3.A ai_healing 单测：prompt 构造 + apply_healing_hook 决策 + run_diagnosis 三态。"""
import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.bootstrap import load_all_models

load_all_models()

from app.services import ai_healing
from app.models.case import RunStatus


# ── apply_healing_hook ─────────────────────────────────────────
class _StepStub:
    def __init__(self, status):
        self.status = status
        self.healing_status = None


def test_apply_healing_hook_skips_when_step_passed():
    step = _StepStub(RunStatus.passed)
    assert ai_healing.apply_healing_hook(step) is False
    assert step.healing_status is None


def test_apply_healing_hook_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_ENABLED", False)
    step = _StepStub(RunStatus.failed)
    assert ai_healing.apply_healing_hook(step) is False
    assert step.healing_status == "skipped"


def test_apply_healing_hook_marks_pending_when_enabled(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_ENABLED", True)
    step = _StepStub(RunStatus.error)
    assert ai_healing.apply_healing_hook(step) is True
    assert step.healing_status == "pending"


# ── build_healing_prompt ───────────────────────────────────────
def test_build_healing_prompt_includes_all_sections():
    prompt = ai_healing.build_healing_prompt(
        case_type="api",
        case_name="login flow",
        step_name="POST /login",
        error_message="status_code expected 200 got 401",
        request_data={"method": "POST", "url": "/login"},
        response_data={"status_code": 401, "body": "unauthorized"},
        run_summary={"passed": 0, "failed": 1},
    )
    assert "用例类型: api" in prompt
    assert "login flow" in prompt
    assert "POST /login" in prompt
    assert "401" in prompt
    assert "运行摘要" in prompt
    assert "200 字以内" in prompt


def test_build_healing_prompt_truncates_long_fields():
    big = "x" * 5000
    prompt = ai_healing.build_healing_prompt(
        case_type="web",
        case_name="huge",
        step_name="step",
        error_message=big,
        request_data=None,
        response_data=None,
    )
    assert "truncated" in prompt
    assert len(prompt) < 6000


# ── run_diagnosis: skipped 路径（无 ai_llm_config）──────────────
def _make_async_db(objects: dict[type, dict[int, object]]):
    """轻量假 db：get 按 (cls, id) 查 dict。"""

    class FakeDB:
        async def get(self, cls, pk):
            return objects.get(cls, {}).get(pk)

        async def commit(self):
            pass

    return FakeDB()


def test_run_diagnosis_marks_skipped_when_project_lacks_llm_config(monkeypatch):
    from app.models.case import StepResult, TestRun, TestCase
    from app.models.project import Module, Project

    step = StepResult(
        id=1, run_id=10, step_index=0, name="step",
        status=RunStatus.failed, error_message="boom",
    )
    run = TestRun(id=10, case_id=100)
    case = TestCase(id=100, name="case", module_id=200)
    case.case_type = types.SimpleNamespace(value="api")
    module = Module(id=200, name="m", project_id=300)
    project = Project(id=300, name="p")
    project.ai_llm_config_id = None

    db = _make_async_db({StepResult: {1: step}, TestRun: {10: run},
                         TestCase: {100: case}, Module: {200: module}, Project: {300: project}})

    published = []

    async def fake_publish(rid, payload):
        published.append((rid, payload))

    import app.core.redis_client as redis_mod
    monkeypatch.setattr(redis_mod, "publish_run_event", fake_publish)

    asyncio.run(ai_healing.run_diagnosis(db, 1))

    assert step.healing_status == "skipped"
    assert step.healing_at is not None
    assert published and published[0][1]["status"] == "skipped"


def test_run_diagnosis_is_idempotent_on_done(monkeypatch):
    from app.models.case import StepResult

    step = StepResult(id=2)
    step.healing_status = "done"
    step.healing_suggestion = "already analysed"

    db = _make_async_db({StepResult: {2: step}})

    # 任何 LLM 调用都不应发生
    def boom(*_a, **_kw):
        raise AssertionError("LLM should not be called")

    import app.services.ai_case.llm_client as llm_mod
    monkeypatch.setattr(llm_mod, "call_llm", boom)

    asyncio.run(ai_healing.run_diagnosis(db, 2))
    assert step.healing_suggestion == "already analysed"  # 未被覆盖
