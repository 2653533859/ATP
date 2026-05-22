"""D.1 用例快照增强：手动创建 / 保留策略 / 搜索 / Diff / 导出 / 导入 / 克隆。"""
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
    get_current_user=lambda: None, require_engineer=lambda: None,
        require_admin=_p3c_noop,
        require_project_access=lambda *a, **kw: _p3c_noop,
        assert_project_access=_p3c_noop_async,
        ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
    )

async def _noop_invalidate_stats_cache():
    return None

sys.modules["app.api.v1.statistics"] = types.SimpleNamespace(
    invalidate_stats_cache=_noop_invalidate_stats_cache
)
sys.modules["app.worker.tasks"] = types.SimpleNamespace(
    run_test_case=types.SimpleNamespace(delay=lambda *_a, **_kw: None)
)

from app.api.v1 import cases
from app.api.v1.cases.workflow import (
    clone_case_from_snapshot,
    create_snapshot_manual,
    diff_snapshots,
    export_snapshot,
    import_snapshot,
)
from app.models.bootstrap import load_all_models
from app.models.case import CaseSnapshot, CaseStatus, CaseStep, CaseType, TestCase
from app.schemas.case import (
    CaseCloneFromSnapshotRequest,
    CaseSnapshotImport,
    CaseSnapshotManualCreate,
)


def _now():
    return datetime.now(timezone.utc)


def _case(case_id: int = 5) -> TestCase:
    case = TestCase(
        id=case_id,
        name="orig",
        description="desc",
        case_code="ATP-LOGIN-API-0001",
        summary="orig summary",
        case_type=CaseType.api,
        status=CaseStatus.active,
        priority="P1",
        case_level="core",
        review_status="approved",
        automation_status="auto",
        tags=["smoke"],
        module_id=2,
        creator_id=9,
        owner_id=9,
        preconditions=[],
        postconditions=[],
        config={"steps": [{"action": "request", "params": {"url": "/login"}}]},
    )
    case.created_at = _now()
    case.updated_at = _now()
    case.steps = [
        CaseStep(
            id=1,
            case_id=case_id,
            step_no=1,
            action="Send request",
            test_data="POST /login",
            expected_result="200 OK",
            is_key_step=True,
        )
    ]
    for step in case.steps:
        step.created_at = _now()
        step.updated_at = _now()
    return case


class _SimpleDB:
    """支持 add/flush/commit/get 的轻量伪库。"""

    def __init__(self):
        self.added = []
        self.deleted = []
        self._by_id = {}

    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, "id", None):
            self._by_id[(type(obj).__name__, obj.id)] = obj

    async def flush(self):
        for obj in self.added:
            if isinstance(obj, CaseSnapshot) and not obj.id:
                obj.id = 1000 + len(self.added)
                obj.created_at = _now()
                obj.updated_at = _now()
            if isinstance(obj, TestCase) and not obj.id:
                obj.id = 2000 + len(self.added)
                obj.created_at = _now()
                obj.updated_at = _now()

    async def commit(self):
        return None

    async def delete(self, obj):
        self.deleted.append(obj)


def test_manual_snapshot_create_writes_remark(monkeypatch):
    load_all_models()
    case_obj = _case()
    db = _SimpleDB()

    async def fake_detail(_db, cid):
        return case_obj

    async def fake_next_ver(_db, cid):
        return 7

    async def fake_retention(_db, cid, max_count=None):
        return 0

    async def fake_get(model, pk):
        for obj in db.added:
            if type(obj).__name__ == getattr(model, "__name__", "") and obj.id == pk:
                return obj
        return None

    db.get = fake_get

    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_detail)
    monkeypatch.setattr(cases, "_next_snapshot_version", fake_next_ver)
    monkeypatch.setattr(cases, "_enforce_snapshot_retention", fake_retention)

    result = asyncio.run(
        create_snapshot_manual(
            case_id=5,
            body=CaseSnapshotManualCreate(remark="release-tag"),
            db=db,
            current_user=types.SimpleNamespace(id=9, username="alice"),
        )
    )

    snap = db.added[0]
    assert snap.version == 7
    assert snap.snapshot_data["remark"] == "release-tag"
    assert result.version == 7


def test_enforce_snapshot_retention_deletes_oldest(monkeypatch):
    """retention helper：构造 5 个快照，cap=3 应删 2 个。"""
    from app.api.v1.cases.common import _enforce_snapshot_retention

    snaps = [
        types.SimpleNamespace(id=i, case_id=5, version=i) for i in range(1, 6)
    ]
    by_id = {s.id: s for s in snaps}

    class _RetentionDB:
        def __init__(self):
            self.deleted_ids = []

        async def scalar(self, _stmt):
            return len(by_id)

        async def execute(self, _stmt):
            # 模拟返回最旧的 2 个 id
            class _R:
                def scalars(self_inner):
                    class _S:
                        def all(s2):
                            return [1, 2]
                    return _S()
            return _R()

        async def get(self, model, sid):
            return by_id.get(sid)

        async def delete(self, obj):
            self.deleted_ids.append(obj.id)
            by_id.pop(obj.id, None)

        async def flush(self):
            return None

    db = _RetentionDB()
    removed = asyncio.run(_enforce_snapshot_retention(db, case_id=5, max_count=3))
    assert removed == 2
    assert db.deleted_ids == [1, 2]


def test_diff_snapshots_emits_field_changes(monkeypatch):
    case_obj = _case()
    from_snap = types.SimpleNamespace(
        id=10, case_id=5, version=1,
        snapshot_data={"name": "old", "priority": "P2", "tags": ["a"]},
    )
    to_snap = types.SimpleNamespace(
        id=11, case_id=5, version=2,
        snapshot_data={"name": "new", "priority": "P2", "tags": ["a", "b"]},
    )

    class _DiffDB:
        async def execute(self, stmt):
            class _R:
                def __init__(self, obj):
                    self._obj = obj

                def scalar_one_or_none(self_inner):
                    return self_inner._obj

            sql = str(stmt)
            return _R(from_snap) if "version = :version_1" in sql.lower() or "version = 1" in sql.lower() else _R(to_snap)

    # 我们用 monkeypatch 替代 db.execute 行为：交替返回 from / to
    queue = [from_snap, to_snap]

    class _DiffDB2:
        async def execute(self, _stmt):
            obj = queue.pop(0)

            class _R:
                def scalar_one_or_none(self_inner):
                    return obj

            return _R()

    async def fake_detail(_db, cid):
        return case_obj

    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_detail)
    db = _DiffDB2()
    result = asyncio.run(
        diff_snapshots(case_id=5, from_version=1, to_version=2, db=db)
    )
    assert result.from_version == 1
    assert result.to_version == 2
    assert "name" in result.changes
    assert result.changes["name"] == {"from": "old", "to": "new"}
    assert "tags" in result.changes
    assert "priority" not in result.changes  # 未变化字段不出现


def test_export_snapshot_returns_attachment_payload():
    snap = types.SimpleNamespace(
        id=42, case_id=5, version=3,
        name="snap-3", description="d", tags=["x"], config={"k": 1},
        snapshot_data={"name": "snap-3"},
    )

    class _DB:
        async def get(self, model, pk):
            return snap

    response = asyncio.run(export_snapshot(case_id=5, snapshot_id=42, db=_DB()))
    assert "attachment" in response.headers["content-disposition"]
    assert "case-5-snapshot-v3" in response.headers["content-disposition"]


def test_import_snapshot_creates_new_version(monkeypatch):
    load_all_models()
    case_obj = _case()
    db = _SimpleDB()

    async def fake_detail(_db, cid):
        return case_obj

    async def fake_next_ver(_db, cid):
        return 99

    async def fake_retention(_db, cid, max_count=None):
        return 0

    async def fake_get(model, pk):
        for obj in db.added:
            if type(obj).__name__ == getattr(model, "__name__", "") and obj.id == pk:
                return obj
        return None

    db.get = fake_get
    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_detail)
    monkeypatch.setattr(cases, "_next_snapshot_version", fake_next_ver)
    monkeypatch.setattr(cases, "_enforce_snapshot_retention", fake_retention)

    payload = CaseSnapshotImport(
        snapshot_data={"name": "imported", "config": {"a": 1}},
        name="imported",
        tags=["import"],
        config={"a": 1},
    )
    result = asyncio.run(
        import_snapshot(
            case_id=5,
            body=payload,
            db=db,
            current_user=types.SimpleNamespace(id=9, username="bob"),
        )
    )
    assert db.added[0].version == 99
    assert db.added[0].name == "imported"
    assert db.added[0].snapshot_data["name"] == "imported"
    assert result.version == 99


def test_clone_case_from_snapshot_creates_new_case(monkeypatch):
    load_all_models()
    case_obj = _case()
    snap = types.SimpleNamespace(
        id=77, case_id=5, version=4,
        snapshot_data={
            "name": "orig", "case_type": "api", "priority": "P1",
            "case_level": "core", "automation_status": "auto",
            "preconditions": [], "postconditions": [], "tags": ["x"],
            "config": {"steps": [{"action": "noop"}]},
        },
    )
    db = _SimpleDB()

    async def fake_get(model, pk):
        name = getattr(model, "__name__", "")
        if name == "CaseSnapshot" and pk == 77:
            return snap
        for obj in db.added:
            if type(obj).__name__ == name and getattr(obj, "id", None) == pk:
                return obj
        return None

    db.get = fake_get

    fake_module = types.SimpleNamespace(
        id=2, project=types.SimpleNamespace(project_code="ATP"),
        module_code="LOGIN",
    )

    detail_calls = {"count": 0}

    async def fake_detail(_db, cid):
        detail_calls["count"] += 1
        if detail_calls["count"] == 1:
            return case_obj
        # 第二次：返回新创建的用例
        for obj in db.added:
            if isinstance(obj, TestCase):
                return obj
        return case_obj

    async def fake_module_loader(_db, mid):
        return fake_module

    async def fake_generate_code(_db, _module, _ctype):
        return "ATP-LOGIN-API-9999"

    async def fake_replace_steps(_db, case, payload):
        return None

    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_detail)
    monkeypatch.setattr(cases, "_get_module_for_case_code", fake_module_loader)
    monkeypatch.setattr(cases, "_generate_case_code", fake_generate_code)
    monkeypatch.setattr(cases, "_replace_case_steps", fake_replace_steps)

    result = asyncio.run(
        clone_case_from_snapshot(
            case_id=5,
            snapshot_id=77,
            body=CaseCloneFromSnapshotRequest(name="clone-name"),
            db=db,
            current_user=types.SimpleNamespace(id=9, username="carol"),
        )
    )

    new_case = next(o for o in db.added if isinstance(o, TestCase))
    assert new_case.name == "clone-name"
    assert new_case.case_code == "ATP-LOGIN-API-9999"
    assert new_case.status == CaseStatus.draft
    assert new_case.creator_id == 9
    assert result.name == "clone-name"
