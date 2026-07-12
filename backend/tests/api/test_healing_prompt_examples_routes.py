import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.v1 import healing_prompt_examples
from app.models.healing_prompt_example import HealingPromptExample
from app.schemas.healing_prompt_example import HealingPromptExampleUpdateIn


class _DB:
    def __init__(self, example=None):
        self.example = example
        self.deleted = []
        self.commits = 0
        self.refreshes = 0

    async def get(self, model, pk):
        if model is HealingPromptExample and self.example and self.example.id == pk:
            return self.example
        return None

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshes += 1

    async def delete(self, obj):
        self.deleted.append(obj)


def _user(user_id=42):
    return SimpleNamespace(id=user_id)


def _example(example_id=1):
    now = datetime(2026, 7, 11, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=example_id,
        error_fingerprint="assertion:text",
        case_type="web",
        step_context_json={"selector": "#submit"},
        suggestion_text="Wait for submit button before clicking.",
        source_step_result_id=9,
        marked_high_quality=False,
        marked_by=None,
        marked_at=None,
        created_at=now,
        updated_at=now,
    )


def test_list_examples_forwards_filters_to_service(monkeypatch):
    calls = {}
    rows = [_example()]

    async def fake_list(db, **filters):
        calls["db"] = db
        calls["filters"] = filters
        return rows

    monkeypatch.setattr(healing_prompt_examples, "list_prompt_examples", fake_list)

    result = asyncio.run(
        healing_prompt_examples.list_examples(
            error_fingerprint="assertion:text",
            case_type="web",
            high_quality=True,
            limit=25,
            db="db",
            _=None,
        )
    )

    assert result == rows
    assert calls == {
        "db": "db",
        "filters": {
            "error_fingerprint": "assertion:text",
            "case_type": "web",
            "high_quality": True,
            "limit": 25,
        },
    }


@pytest.mark.parametrize(
    ("service_error", "status_code", "detail"),
    [
        ("step_not_found", 404, "步骤结果不存在"),
        ("step_feedback_not_adopted", 400, "仅能从已采纳的自愈反馈创建示例"),
        ("step_suggestion_empty", 400, "自愈建议为空，无法创建示例"),
        ("run_not_found", 404, "执行记录不存在"),
        ("case_not_found", 404, "用例不存在"),
        ("unexpected", 400, "创建示例失败"),
    ],
)
def test_create_from_step_maps_service_errors(monkeypatch, service_error, status_code, detail):
    async def fake_create(_db, *, step_result_id, marked_by):
        assert step_result_id == 7
        assert marked_by == 42
        raise ValueError(service_error)

    monkeypatch.setattr(healing_prompt_examples, "create_example_from_step", fake_create)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(healing_prompt_examples.create_from_step(step_result_id=7, db="db", user=_user()))

    assert exc.value.status_code == status_code
    assert exc.value.detail == detail


def test_create_from_step_returns_created_example(monkeypatch):
    example = _example()

    async def fake_create(_db, *, step_result_id, marked_by):
        assert (step_result_id, marked_by) == (7, 42)
        return example

    monkeypatch.setattr(healing_prompt_examples, "create_example_from_step", fake_create)

    result = asyncio.run(healing_prompt_examples.create_from_step(step_result_id=7, db="db", user=_user()))

    assert result is example


def test_update_example_updates_text_and_quality_marker():
    example = _example()
    db = _DB(example=example)
    body = HealingPromptExampleUpdateIn(
        suggestion_text="Use an explicit visible assertion.",
        marked_high_quality=True,
    )

    result = asyncio.run(healing_prompt_examples.update_example(example_id=1, body=body, db=db, user=_user()))

    assert result is example
    assert example.suggestion_text == "Use an explicit visible assertion."
    assert example.marked_high_quality is True
    assert example.marked_by == 42
    assert example.marked_at is not None
    assert db.commits == 1 and db.refreshes == 1


def test_update_example_404_for_missing_example():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            healing_prompt_examples.update_example(
                example_id=404,
                body=HealingPromptExampleUpdateIn(suggestion_text="x"),
                db=_DB(),
                user=_user(),
            )
        )

    assert exc.value.status_code == 404


def test_delete_example_removes_existing_example():
    example = _example()
    db = _DB(example=example)

    asyncio.run(healing_prompt_examples.delete_example(example_id=1, db=db, _=None))

    assert db.deleted == [example]
    assert db.commits == 1


def test_delete_example_404_for_missing_example():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(healing_prompt_examples.delete_example(example_id=404, db=_DB(), _=None))

    assert exc.value.status_code == 404
