"""Deleting a local case removes only artifacts owned by its runs."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core import local_object_store
from app.services import local_artifact_cleanup


class _ScalarResult:
    def all(self):
        return [5, 6]


class _Db:
    async def scalars(self, _query):
        return _ScalarResult()


@pytest.mark.asyncio
async def test_collect_run_ids_for_deleted_cases():
    assert await local_artifact_cleanup.case_run_ids(_Db(), []) == []
    assert await local_artifact_cleanup.case_run_ids(_Db(), [12]) == [5, 6]


def test_delete_only_owned_local_run_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(local_object_store, "settings", SimpleNamespace(LOCAL_DATA_PATH=tmp_path))
    owned = [
        "screenshots/runs/5/step_0.png",
        "traces/runs/5/trace.zip",
        "videos/runs/5/recording.webm",
        "reports/run-5/report.html",
    ]
    unrelated = "screenshots/runs/50/step_0.png"
    for name in [*owned, unrelated]:
        local_object_store.upload_bytes(name, b"artifact")

    local_artifact_cleanup.delete_run_artifacts([5, 5])

    assert all(not local_object_store.object_path(name).exists() for name in owned)
    assert local_object_store.object_path(unrelated).read_bytes() == b"artifact"


@pytest.mark.asyncio
async def test_single_case_delete_cleans_artifacts_after_commit(monkeypatch):
    from app.api.v1.cases import crud
    from app.models.case import TestCase

    events = []
    case = SimpleNamespace(id=12, module_id=2, name="temporary")
    module = SimpleNamespace(project_id=1)

    class Db:
        async def get(self, model, _id):
            return case if model is TestCase else module

        async def delete(self, _item):
            events.append("delete")

        async def commit(self):
            events.append("commit")

    monkeypatch.setattr(crud, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    monkeypatch.setattr(crud, "assert_project_access", AsyncMock())
    monkeypatch.setattr(crud, "case_run_ids", AsyncMock(return_value=[5]))
    monkeypatch.setattr(crud, "delete_run_artifacts", lambda ids: events.append(("artifacts", ids)))
    monkeypatch.setattr(crud._cases, "write_audit_log", AsyncMock())
    monkeypatch.setattr(crud._cases, "invalidate_stats_cache", AsyncMock())

    await crud.delete_case(12, Db(), SimpleNamespace(id=3, username="admin"))

    assert events == ["delete", "commit", ("artifacts", [5])]


@pytest.mark.asyncio
async def test_batch_case_delete_cleans_artifacts_after_commit(monkeypatch):
    from app.api.v1.cases import batch

    events = []
    case = SimpleNamespace(id=12)

    class Result:
        def scalars(self):
            return self

        def all(self):
            return [case]

    class Db:
        async def execute(self, _query):
            return Result()

        async def delete(self, _item):
            events.append("delete")

        async def commit(self):
            events.append("commit")

    monkeypatch.setattr(batch, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    monkeypatch.setattr(batch, "_assert_cases_access", AsyncMock())
    monkeypatch.setattr(batch, "case_run_ids", AsyncMock(return_value=[5]))
    monkeypatch.setattr(batch, "delete_run_artifacts", lambda ids: events.append(("artifacts", ids)))
    monkeypatch.setattr(batch._cases, "write_audit_log", AsyncMock())
    monkeypatch.setattr(batch._cases, "invalidate_stats_cache", AsyncMock())

    result = await batch.batch_delete_cases(
        SimpleNamespace(case_ids=[12]), Db(), SimpleNamespace(id=3, username="admin")
    )

    assert result.processed == 1
    assert events == ["delete", "commit", ("artifacts", [5])]
