"""P3.B 数据集 CRUD + 上传单测：list / create / upload csv / upload json / size limit / delete。"""
import asyncio
import io
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

from fastapi import HTTPException, UploadFile

from app.api.v1 import datasets as ds_api
from app.models.bootstrap import load_all_models
from app.models.case import TestCase
from app.models.dataset import TestDataset, TestDatasetVersion
from app.models.plan import TestPlan
from app.models.suite import TestSuite
from app.schemas.dataset import DatasetValidateIn, TestDatasetCreate, TestDatasetUpdate

load_all_models()


class _FakeUser:
    id = 1


class _FakeDB:
    def __init__(self, store=None, *, cases=None, suites=None, plans=None):
        self.store: dict[int, TestDataset] = store or {}
        self.cases = cases or []
        self.suites = suites or []
        self.plans = plans or []
        self.versions: list[TestDatasetVersion] = []
        self._next_id = max(self.store) + 1 if self.store else 1
        self._next_version_id = 1
        self.commits = 0
        self.deleted: list[int] = []

    async def get(self, _cls, pk):
        return self.store.get(pk)

    def add(self, obj):
        if isinstance(obj, TestDatasetVersion):
            if not getattr(obj, "id", None):
                obj.id = self._next_version_id
                self._next_version_id += 1
            if not getattr(obj, "created_at", None):
                obj.created_at = datetime(2026, 5, 27, tzinfo=timezone.utc)
            self.versions.append(obj)
            return
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.store[obj.id] = obj

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None

    async def refresh(self, _obj):
        return None

    async def delete(self, obj):
        self.deleted.append(obj.id)
        self.store.pop(obj.id, None)

    async def execute(self, _stmt):
        db = self
        stmt_text = str(_stmt)
        is_version_query = "test_dataset_versions" in stmt_text
        is_case_query = "test_cases" in stmt_text
        is_suite_query = "test_suites" in stmt_text
        is_plan_query = "test_plans" in stmt_text

        class _R:
            def scalar_one(self):
                if is_version_query and db.versions:
                    return max(v.version for v in db.versions)
                return 0

            def scalar_one_or_none(self):
                if is_version_query and db.versions:
                    return db.versions[0]
                if is_case_query and db.cases:
                    return db.cases[0].id
                return None

            def scalars(self):
                return self

            def all(self):
                if is_version_query:
                    return list(db.versions)
                if is_case_query:
                    dataset_ids = set(db.store)
                    return [case for case in db.cases if case.dataset_id in dataset_ids]
                if is_suite_query:
                    return list(db.suites)
                if is_plan_query:
                    return list(db.plans)
                return list(_self_store.values())

        _self_store = self.store
        return _R()


def _make_dataset(id_=1, rows=None, fmt="json"):
    now = datetime(2026, 5, 27, tzinfo=timezone.utc)
    d = TestDataset(
        id=id_,
        name=f"ds-{id_}",
        description="d",
        project_id=10,
        format=fmt,
        rows=rows or [{"a": 1}],
        schema_fields=[],
        validation_policy="soft",
        creator_id=1,
        created_at=now,
        updated_at=now,
    )
    return d


def _make_case(case_id=100, dataset_id=1):
    return TestCase(
        id=case_id,
        name=f"case-{case_id}",
        case_code=f"C-{case_id}",
        summary="s",
        case_type="api",
        module_id=1,
        creator_id=1,
        dataset_id=dataset_id,
    )


def _make_suite(suite_id=200, case_ids=None, parameterization=None):
    return TestSuite(
        id=suite_id,
        name=f"suite-{suite_id}",
        project_id=10,
        creator_id=1,
        case_ids=case_ids or [],
        parameterization=parameterization or {},
    )


def _make_plan(plan_id=300, suite_ids=None):
    return TestPlan(
        id=plan_id,
        name=f"plan-{plan_id}",
        project_id=10,
        creator_id=1,
        suite_ids=suite_ids or [],
    )


def test_create_dataset_persists_and_returns():
    db = _FakeDB()
    body = TestDatasetCreate(
        name="ds1",
        project_id=10,
        format="json",
        rows=[{"a": 1}],
        schema_fields=[{"name": "a", "type": "integer", "required": True}],
        validation_policy="hard",
    )
    result = asyncio.run(ds_api.create_dataset(body=body, db=db, user=_FakeUser()))
    assert result.name == "ds1"
    assert result.rows == [{"a": 1}]
    assert result.schema_fields == [{"name": "a", "type": "integer", "required": True, "default": None}]
    assert result.validation_policy == "hard"
    assert result.creator_id == 1
    assert db.commits == 1
    assert db.versions[-1].change_type == "create"
    assert db.versions[-1].version == 1


def test_validate_dataset_endpoint_returns_preview_and_issues():
    body = DatasetValidateIn(
        schema_fields=[
            {"name": "username", "type": "string", "required": True},
            {"name": "age", "type": "integer", "required": True},
        ],
        rows=[{"username": "alice", "age": 18}, {"username": "bob", "age": "old"}],
    )
    result = asyncio.run(ds_api.validate_dataset(body=body, _=_FakeUser()))

    assert result.valid is False
    assert result.row_count == 2
    assert result.normalized_rows[0] == {"username": "alice", "age": 18}
    assert result.issues[0].row_index == 1
    assert result.issues[0].field == "age"
    assert result.can_upload is None


def test_list_datasets_uses_short_ttl_cache(monkeypatch):
    cached = [
        {
            "id": 1,
            "name": "cached",
            "description": None,
            "project_id": 10,
            "format": "json",
            "row_count": 2,
            "schema_field_count": 0,
            "creator_id": 1,
            "created_at": "2026-05-27T12:00:00Z",
            "updated_at": "2026-05-27T12:00:00Z",
        }
    ]

    async def fake_get_cache(key):
        assert key == "atp:datasets:list:project_id=10"
        return cached

    monkeypatch.setattr(ds_api, "get_json_cache", fake_get_cache)

    class NoDb:
        async def execute(self, _stmt):
            raise AssertionError("cache hit should skip db")

    result = asyncio.run(ds_api.list_datasets(project_id=10, db=NoDb(), _=None))

    assert result[0].name == "cached"
    assert ds_api._DATASET_LIST_CACHE_TTL == 60


def test_list_datasets_writes_json_serializable_cache(monkeypatch):
    written = {}

    async def fake_get_cache(_key):
        return None

    async def fake_set_cache(key, value, ttl_seconds):
        written["key"] = key
        written["value"] = value
        written["ttl"] = ttl_seconds

    monkeypatch.setattr(ds_api, "get_json_cache", fake_get_cache)
    monkeypatch.setattr(ds_api, "set_json_cache", fake_set_cache)

    db = _FakeDB({1: _make_dataset(1)})
    result = asyncio.run(ds_api.list_datasets(project_id=10, db=db, _=None))

    assert result[0].name == "ds-1"
    assert written["key"] == "atp:datasets:list:project_id=10"
    assert written["ttl"] == 60
    assert isinstance(written["value"][0]["created_at"], str)
    assert written["value"][0]["schema_field_count"] == 0
    assert written["value"][0]["validation_policy"] == "soft"


def test_create_dataset_rejects_oversize_rows():
    db = _FakeDB()
    big = [{"k": "x" * 1000} for _ in range(600)]  # > 500 rows
    body = TestDatasetCreate(name="bad", project_id=10, rows=big)
    try:
        asyncio.run(ds_api.create_dataset(body=body, db=db, user=_FakeUser()))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "500" in exc.detail or "上限" in exc.detail
    else:
        raise AssertionError("expected 400")


def test_upload_csv_parses_rows_and_skips_blank():
    db = _FakeDB({1: _make_dataset(1, rows=[], fmt="json")})
    raw = "name,value\nfoo,1\nbar,2\n,\n".encode("utf-8")
    file = UploadFile(filename="x.csv", file=io.BytesIO(raw))
    result = asyncio.run(ds_api.upload_dataset(dataset_id=1, file=file, db=db, user=_FakeUser()))
    assert result.format == "csv"
    assert result.rows == [{"name": "foo", "value": "1"}, {"name": "bar", "value": "2"}]


def test_upload_preview_parses_without_mutating_dataset():
    dataset = _make_dataset(1, rows=[{"old": 1}], fmt="json")
    db = _FakeDB({1: dataset})
    raw = "name,value\nfoo,1\nbar,2\n".encode("utf-8")
    file = UploadFile(filename="x.csv", file=io.BytesIO(raw))
    result = asyncio.run(ds_api.preview_upload_dataset(dataset_id=1, file=file, db=db, user=_FakeUser()))

    assert result.valid is True
    assert result.row_count == 2
    assert result.normalized_rows == [{"name": "foo", "value": "1"}, {"name": "bar", "value": "2"}]
    assert dataset.rows == [{"old": 1}]
    assert db.commits == 0


def test_upload_preview_uses_persisted_schema_fields():
    dataset = _make_dataset(1, rows=[{"age": 18}], fmt="json")
    dataset.schema_fields = [{"name": "age", "type": "integer", "required": True, "default": None}]
    db = _FakeDB({1: dataset})
    raw = b'[{"age": "old"}]'
    file = UploadFile(filename="x.json", file=io.BytesIO(raw))
    result = asyncio.run(ds_api.preview_upload_dataset(dataset_id=1, file=file, db=db, user=_FakeUser()))

    assert result.valid is False
    assert result.can_upload is True
    assert result.validation_policy == "soft"
    assert result.issues[0].field == "age"
    assert result.issues[0].message.startswith("expected integer")


def test_update_dataset_can_replace_schema_fields():
    dataset = _make_dataset(4, rows=[{"name": "alice"}], fmt="json")
    db = _FakeDB({4: dataset})
    body = TestDatasetUpdate(
        schema_fields=[{"name": "name", "type": "string", "required": True}],
        validation_policy="hard",
    )
    result = asyncio.run(ds_api.update_dataset(dataset_id=4, body=body, db=db, user=_FakeUser()))

    assert result.schema_fields == [{"name": "name", "type": "string", "required": True, "default": None}]
    assert result.validation_policy == "hard"
    assert db.commits == 1
    assert db.versions[-1].change_type == "update"


def test_upload_hard_policy_rejects_invalid_rows():
    dataset = _make_dataset(5, rows=[{"age": 18}], fmt="json")
    dataset.schema_fields = [{"name": "age", "type": "integer", "required": True, "default": None}]
    dataset.validation_policy = "hard"
    db = _FakeDB({5: dataset})
    file = UploadFile(filename="x.json", file=io.BytesIO(b'[{"age": "old"}]'))

    try:
        asyncio.run(ds_api.upload_dataset(dataset_id=5, file=file, db=db, user=_FakeUser()))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "hard-block" in exc.detail
    else:
        raise AssertionError("expected hard-block rejection")
    assert dataset.rows == [{"age": 18}]
    assert db.commits == 0


def test_upload_soft_policy_allows_invalid_rows():
    dataset = _make_dataset(6, rows=[{"age": 18}], fmt="json")
    dataset.schema_fields = [{"name": "age", "type": "integer", "required": True, "default": None}]
    dataset.validation_policy = "soft"
    db = _FakeDB({6: dataset})
    file = UploadFile(filename="x.json", file=io.BytesIO(b'[{"age": "old"}]'))

    result = asyncio.run(ds_api.upload_dataset(dataset_id=6, file=file, db=db, user=_FakeUser()))

    assert result.rows == [{"age": "old"}]
    assert db.commits == 1
    assert db.versions[-1].change_type == "upload"


def test_list_dataset_versions_returns_snapshot_metadata():
    dataset = _make_dataset(7)
    db = _FakeDB({7: dataset})
    db.add(
        TestDatasetVersion(
            dataset_id=7,
            version=1,
            format="json",
            rows=[{"a": 1}],
            schema_fields=[{"name": "a"}],
            validation_policy="soft",
            change_type="create",
            created_by=1,
        )
    )

    result = asyncio.run(ds_api.list_dataset_versions(dataset_id=7, db=db, user=_FakeUser()))

    assert result[0].version == 1
    assert result[0].row_count == 1
    assert result[0].schema_field_count == 1


def test_rollback_dataset_restores_snapshot_and_creates_new_version():
    dataset = _make_dataset(8, rows=[{"age": "old"}])
    db = _FakeDB({8: dataset})
    db.add(
        TestDatasetVersion(
            dataset_id=8,
            version=1,
            format="json",
            rows=[{"age": 18}],
            schema_fields=[{"name": "age", "type": "integer"}],
            validation_policy="hard",
            change_type="upload",
            created_by=1,
        )
    )

    result = asyncio.run(ds_api.rollback_dataset(dataset_id=8, version=1, db=db, user=_FakeUser()))

    assert result.rows == [{"age": 18}]
    assert result.schema_fields == [{"name": "age", "type": "integer"}]
    assert result.validation_policy == "hard"
    assert db.versions[-1].change_type == "rollback:1"


def test_get_dataset_impact_collects_case_suite_and_plan_refs():
    dataset = _make_dataset(9)
    case = _make_case(101, dataset_id=9)
    suite_from_case = _make_suite(201, case_ids=[{"case_id": 101, "sort": 0}])
    suite_from_param = _make_suite(202, parameterization={"dataset_id": 9})
    plan = _make_plan(301, suite_ids=[{"suite_id": 201, "sort": 0}, {"suite_id": 202, "sort": 1}])
    db = _FakeDB({9: dataset}, cases=[case], suites=[suite_from_case, suite_from_param], plans=[plan])

    result = asyncio.run(ds_api.get_dataset_impact(dataset_id=9, db=db, user=_FakeUser()))

    assert result.total_count == 4
    assert result.cases[0].reason == "case_dataset_binding"
    assert {item.id for item in result.suites} == {201, 202}
    assert result.plans[0].id == 301


def test_get_dataset_impact_ignores_unrelated_refs():
    dataset = _make_dataset(10)
    db = _FakeDB(
        {10: dataset},
        cases=[_make_case(102, dataset_id=99)],
        suites=[_make_suite(203, case_ids=[{"case_id": 102, "sort": 0}], parameterization={"dataset_id": 99})],
        plans=[_make_plan(302, suite_ids=[{"suite_id": 203, "sort": 0}])],
    )

    result = asyncio.run(ds_api.get_dataset_impact(dataset_id=10, db=db, user=_FakeUser()))

    assert result.total_count == 0
    assert result.cases == []
    assert result.suites == []
    assert result.plans == []


def test_upload_json_requires_array_of_objects():
    db = _FakeDB({2: _make_dataset(2, rows=[], fmt="json")})
    raw = b'{"not": "array"}'
    file = UploadFile(filename="x.json", file=io.BytesIO(raw))
    try:
        asyncio.run(ds_api.upload_dataset(dataset_id=2, file=file, db=db, user=_FakeUser()))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "数组" in exc.detail
    else:
        raise AssertionError("expected 400")


def test_upload_json_ok():
    db = _FakeDB({3: _make_dataset(3, rows=[], fmt="json")})
    raw = b'[{"k": 1}, {"k": 2}]'
    file = UploadFile(filename="x.json", file=io.BytesIO(raw))
    result = asyncio.run(ds_api.upload_dataset(dataset_id=3, file=file, db=db, user=_FakeUser()))
    assert result.format == "json"
    assert result.rows == [{"k": 1}, {"k": 2}]


def test_get_dataset_404_when_missing():
    db = _FakeDB()
    try:
        asyncio.run(ds_api.get_dataset(dataset_id=999, db=db, user=_FakeUser()))
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("expected 404")


def test_delete_dataset_succeeds_when_no_refs():
    db = _FakeDB({5: _make_dataset(5)})
    asyncio.run(ds_api.delete_dataset(dataset_id=5, db=db, user=_FakeUser()))
    assert 5 in db.deleted
