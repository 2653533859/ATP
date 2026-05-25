"""Q5 长尾 #3 — rollback_case 写审计日志测试。"""
import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_admin=_p3c_noop,
    require_engineer=lambda: None,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)
sys.modules["app.worker.tasks"] = types.SimpleNamespace(
    run_test_case=types.SimpleNamespace(delay=lambda *_a, **_k: None)
)


async def _noop_invalidate_stats_cache():
    return None


sys.modules["app.api.v1.statistics"] = types.SimpleNamespace(
    invalidate_stats_cache=_noop_invalidate_stats_cache
)

from app.api.v1 import cases  # noqa: E402
from app.api.v1.cases import workflow  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402
from app.models.case import CaseSnapshot, CaseStatus, CaseType, TestCase  # noqa: E402
from app.models.project import Module  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

load_all_models()


def _make_user() -> User:
    return User(
        id=11,
        username="auditor",
        email="auditor@example.com",
        hashed_password="x",
        role=UserRole.admin,
    )


def _make_case() -> TestCase:
    c = TestCase(
        id=100,
        name="case after rollback",
        case_code="ATP-API-0100",
        summary="s",
        case_type=CaseType.api,
        status=CaseStatus.active,
        priority="P2",
        case_level="regression",
        review_status="approved",
        automation_status="auto",
        tags=[],
        module_id=7,
        creator_id=11,
    )
    c.created_at = datetime.now(timezone.utc)
    c.updated_at = datetime.now(timezone.utc)
    return c


def _make_snapshot(case_id: int = 100) -> CaseSnapshot:
    snap = CaseSnapshot(
        id=55,
        case_id=case_id,
        version=3,
        name="历史名称",
        description="hist desc",
        tags=[],
        config={"url": "https://example.com"},
        snapshot_data={
            "name": "历史名称",
            "description": "hist desc",
            "case_type": "api",
            "status": "active",
            "config": {"url": "https://example.com"},
            "steps": [],
        },
        updated_by=11,
    )
    snap.created_at = datetime.now(timezone.utc)
    return snap


class _FakeDB:
    def __init__(self):
        self._objs = {
            (CaseSnapshot, 55): _make_snapshot(),
            (Module, 7): Module(id=7, name="m", module_code="MOD-007", project_id=9, parent_id=None, sort_order=0),
        }
        self.added = []
        self.commits = 0

    async def get(self, model, pk):
        return self._objs.get((model, pk))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def flush(self):
        return None


def test_rollback_case_writes_audit_log(monkeypatch):
    db = _FakeDB()
    user = _make_user()
    case = _make_case()

    async def fake_get_case_detail(_db, _case_id):
        return case

    async def fake_next_version(_db, _case_id):
        return 4

    def fake_build_snapshot(_case, _version, _user_id):
        return CaseSnapshot(
            id=999,
            case_id=_case.id,
            version=_version,
            name=_case.name,
            snapshot_data={},
            updated_by=_user_id,
        )

    async def fake_enforce_retention(_db, _case_id):
        return None

    async def fake_replace_steps(_db, _case, _steps):
        return None

    def fake_derive_steps(*_a, **_k):
        return []

    audit_calls: list[dict] = []

    async def spy_audit(_db, **kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_get_case_detail)
    monkeypatch.setattr(cases, "_next_snapshot_version", fake_next_version)
    monkeypatch.setattr(cases, "_build_snapshot", fake_build_snapshot)
    monkeypatch.setattr(cases, "_enforce_snapshot_retention", fake_enforce_retention)
    monkeypatch.setattr(cases, "_replace_case_steps", fake_replace_steps)
    monkeypatch.setattr(cases, "_derive_steps_from_config", fake_derive_steps)
    monkeypatch.setattr(cases, "_normalize_string_list", lambda x: list(x) if x else [])
    monkeypatch.setattr(cases, "write_audit_log", spy_audit)

    result = asyncio.run(
        workflow.rollback_case(case_id=100, snapshot_id=55, db=db, current_user=user)
    )

    assert result is case
    assert len(audit_calls) == 1
    payload = audit_calls[0]
    assert payload["action"] == "case.rollback"
    assert payload["resource_type"] == "test_case"
    assert payload["resource_id"] == 100
    assert payload["user_id"] == 11
    assert payload["username"] == "auditor"
    assert payload["project_id"] == 9
    assert "v3" in payload["detail"]
    assert "snapshot_id=55" in payload["detail"]
    # 至少经历两次 commit：业务回滚 + audit 写入
    assert db.commits >= 2


def test_rollback_case_404_when_snapshot_missing(monkeypatch):
    from fastapi import HTTPException

    db = _FakeDB()
    db._objs.pop((CaseSnapshot, 55))
    user = _make_user()
    case = _make_case()

    async def fake_get_case_detail(_db, _case_id):
        return case

    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_get_case_detail)

    raised = None
    try:
        asyncio.run(workflow.rollback_case(case_id=100, snapshot_id=55, db=db, current_user=user))
    except HTTPException as exc:
        raised = exc
    assert raised is not None
    assert raised.status_code == 404
