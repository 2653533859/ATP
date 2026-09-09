from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from app.api.v1.cases import runs
from app.models.case import CaseType, RunStatus


class _DB:
    def __init__(self, case):
        self.case = case
        self.commits = 0
        self.refreshes = 0

    async def get(self, model, _pk):
        return self.case if getattr(model, "__name__", "") == "TestCase" else None

    async def commit(self):
        self.commits += 1

    async def refresh(self, _run):
        self.refreshes += 1


@pytest.mark.parametrize("initial_status", [RunStatus.pending, RunStatus.running])
def test_stop_web_run_sends_signal_and_transitions_pending(monkeypatch, initial_status):
    run = SimpleNamespace(id=9, case_id=4, status=initial_status, error_message=None)

    async def get_run(*_args, **_kwargs):
        return run

    monkeypatch.setattr(runs, "_get_run_with_access", get_run)
    requested = []
    monkeypatch.setattr(runs, "request_cancel", requested.append)
    db = _DB(SimpleNamespace(case_type=CaseType.web))

    result = asyncio.run(runs.stop_web_run(9, db, SimpleNamespace(id=3)))

    assert result is run and requested == [9] and db.refreshes == 1
    if initial_status == RunStatus.pending:
        assert run.status == RunStatus.cancelled and db.commits == 1
    else:
        assert run.status == RunStatus.running and db.commits == 0


def test_stop_web_run_rejects_terminal_run_without_signal(monkeypatch):
    run = SimpleNamespace(id=9, case_id=4, status=RunStatus.passed, error_message=None)

    async def get_run(*_args, **_kwargs):
        return run

    monkeypatch.setattr(runs, "_get_run_with_access", get_run)
    monkeypatch.setattr(runs, "request_cancel", lambda _run_id: pytest.fail("must not send a signal"))
    db = _DB(SimpleNamespace(case_type=CaseType.web))

    with pytest.raises(HTTPException) as caught:
        asyncio.run(runs.stop_web_run(9, db, SimpleNamespace(id=3)))

    assert caught.value.status_code == 409
