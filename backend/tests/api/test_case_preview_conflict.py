"""A case preview must still match after the case row is locked."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.cases import crud
from app.models.project import Module
from app.schemas.case import TestCaseUpdate


@pytest.mark.parametrize("changed_field", ["updated_at", "config"])
def test_preview_update_rechecks_case_after_lock(monkeypatch, changed_field):
    original_time = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    case = SimpleNamespace(id=7, module_id=2, updated_at=original_time, config={"url": "/old"})
    locked = []

    class DB:
        async def get(self, model, pk):
            assert model is Module and pk == 2
            return SimpleNamespace(project_id=3)

        async def execute(self, _statement):
            locked.append(True)

        async def refresh(self, _case, attribute_names):
            assert locked and attribute_names
            if changed_field == "updated_at":
                case.updated_at = original_time + timedelta(milliseconds=500)
            else:
                case.config = {"url": "/changed"}

    async def load_case(_db, _case_id):
        return case

    async def allow_access(_db, _user, _project_id, _role):
        return None

    monkeypatch.setattr(crud._cases, "_get_case_detail_or_404", load_case)
    monkeypatch.setattr(crud, "assert_project_access", allow_access)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            crud.update_case(
                case_id=7,
                body=TestCaseUpdate(
                    config={"url": "/new"},
                    expected_updated_at=original_time,
                    expected_config={"url": "/old"},
                ),
                db=DB(),
                current_user=SimpleNamespace(id=5),
            )
        )

    assert locked
    assert exc_info.value.status_code == 409
