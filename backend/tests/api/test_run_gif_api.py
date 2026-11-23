from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from app.api.v1.cases import runs
from app.models.case import RunStatus


class _FakeDB:
    def __init__(self):
        self.commits = 0
        self.refreshes = 0

    async def commit(self):
        self.commits += 1

    async def refresh(self, _run):
        self.refreshes += 1


def test_generate_run_gif_success(monkeypatch):
    run = SimpleNamespace(
        id=77,
        status=RunStatus.passed,
        result_summary={"network_events": []},
        steps=[
            SimpleNamespace(step_index=1, name="打开首页", status=SimpleNamespace(value="passed")),
            SimpleNamespace(step_index=2, name="点击搜索", status=SimpleNamespace(value="passed")),
        ],
    )

    async def fake_get_run(*_args, **_kwargs):
        return run

    monkeypatch.setattr(runs, "_get_run_with_access", fake_get_run)
    monkeypatch.setattr(
        "app.services.gif_recorder.generate_gif_from_run_step_records",
        lambda run_id, steps: "http://minio/gifs/runs/77/recording.gif",
    )

    db = _FakeDB()
    user = SimpleNamespace(id=1)

    result = asyncio.run(runs.generate_run_gif(77, db, user))

    assert result is run
    assert db.commits == 1
    assert db.refreshes == 1
    assert run.result_summary["gif_url"] == "http://minio/gifs/runs/77/recording.gif"


def test_generate_run_gif_rejects_when_no_screenshots(monkeypatch):
    run = SimpleNamespace(
        id=88,
        status=RunStatus.passed,
        result_summary={},
        steps=[],
    )

    async def fake_get_run(*_args, **_kwargs):
        return run

    monkeypatch.setattr(runs, "_get_run_with_access", fake_get_run)
    monkeypatch.setattr(
        "app.services.gif_recorder.generate_gif_from_run_step_records",
        lambda run_id, steps: None,
    )

    db = _FakeDB()
    user = SimpleNamespace(id=1)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(runs.generate_run_gif(88, db, user))

    assert exc.value.status_code == 400
    assert "没有可用的步骤截图" in str(exc.value.detail)
