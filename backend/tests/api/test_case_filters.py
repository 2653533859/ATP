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
sys.modules["app.worker.tasks"] = types.SimpleNamespace(
    run_test_case=types.SimpleNamespace(delay=lambda *_args, **_kwargs: None)
)

from app.api.v1 import cases
from app.models.bootstrap import load_all_models


class _FakeResult:
    def __init__(self, items):
        self.items = items

    def scalars(self):
        return self

    def all(self):
        return self.items


class _FakeDB:
    def __init__(self, items):
        self.items = items
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _FakeResult(self.items)


def test_list_cases_supports_project_filter():
    load_all_models()
    db = _FakeDB(items=[])

    result = asyncio.run(cases.list_cases(project_id=8, module_id=None, case_type=None, tag=None, db=db, user=None))

    assert result == []
    sql = str(db.statements[0])
    assert "JOIN modules" in sql
    assert "modules.project_id" in sql
