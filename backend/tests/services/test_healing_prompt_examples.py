import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.bootstrap import load_all_models

load_all_models()

from app.models.case import CaseType, RunStatus, StepResult, TestCase as CaseModel, TestRun as RunModel
from app.models.healing_prompt_example import HealingPromptExample
from app.services.healing_prompt_examples import (
    build_few_shot_block,
    build_step_context,
    create_example_from_step,
)


def test_build_step_context_captures_failure_fields():
    step = StepResult(
        id=1,
        step_index=2,
        name="POST /login",
        status=RunStatus.failed,
        error_message="401",
        request_data={"method": "POST"},
        response_data={"status_code": 401},
        screenshot_url="s3://shot",
    )

    context = build_step_context(step)

    assert context["step_id"] == 1
    assert context["step_name"] == "POST /login"
    assert context["status"] == "failed"
    assert context["response_data"] == {"status_code": 401}


def test_build_few_shot_block_formats_examples():
    block = build_few_shot_block(
        [
            HealingPromptExample(
                error_fingerprint="abc",
                case_type="api",
                step_context_json={"step_name": "login", "error_message": "401"},
                suggestion_text="检查 token",
                marked_high_quality=True,
            )
        ]
    )

    assert "历史高质量修复示例" in block
    assert "login" in block
    assert "检查 token" in block


class _FakeDb:
    def __init__(self, objects):
        self.objects = objects
        self.added = []
        self.commits = 0

    async def get(self, cls, pk):
        return self.objects.get(cls, {}).get(pk)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        return None


def test_create_example_from_adopted_step():
    step = StepResult(
        id=1,
        run_id=10,
        step_index=0,
        name="login",
        status=RunStatus.failed,
        error_message="401",
        response_data={"status_code": 401},
    )
    step.healing_feedback = "adopted"
    step.healing_suggestion = "刷新 token"
    run = RunModel(id=10, case_id=100)
    case = CaseModel(id=100, name="case", module_id=1)
    case.case_type = CaseType.api
    db = _FakeDb({StepResult: {1: step}, RunModel: {10: run}, CaseModel: {100: case}})

    example = asyncio.run(create_example_from_step(db, step_result_id=1, marked_by=7))

    assert db.commits == 1
    assert db.added == [example]
    assert example.case_type == "api"
    assert example.suggestion_text == "刷新 token"
    assert example.marked_high_quality is True
    assert example.marked_by == 7


def test_create_example_rejects_non_adopted_step():
    step = types.SimpleNamespace(id=1, healing_feedback="rejected")
    db = _FakeDb({StepResult: {1: step}})

    try:
        asyncio.run(create_example_from_step(db, step_result_id=1))
    except ValueError as exc:
        assert str(exc) == "step_feedback_not_adopted"
    else:
        raise AssertionError("expected ValueError")
