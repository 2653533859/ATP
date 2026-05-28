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
from app.models.dataset import TestDataset
from app.schemas.dataset import TestDatasetCreate, TestDatasetUpdate

load_all_models()


class _FakeUser:
    id = 1


class _FakeDB:
    def __init__(self, store=None):
        self.store: dict[int, TestDataset] = store or {}
        self._next_id = max(self.store) + 1 if self.store else 1
        self.commits = 0
        self.deleted: list[int] = []

    async def get(self, _cls, pk):
        return self.store.get(pk)

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.store[obj.id] = obj

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
        # delete dataset 时 query TestCase.id (引用检查)；测试默认空
        class _R:
            def scalar_one_or_none(self):
                return None

            def scalars(self):
                return self

            def all(self):
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
        creator_id=1,
        created_at=now,
        updated_at=now,
    )
    return d


def test_create_dataset_persists_and_returns():
    db = _FakeDB()
    body = TestDatasetCreate(name="ds1", project_id=10, format="json", rows=[{"a": 1}])
    result = asyncio.run(ds_api.create_dataset(body=body, db=db, user=_FakeUser()))
    assert result.name == "ds1"
    assert result.rows == [{"a": 1}]
    assert result.creator_id == 1
    assert db.commits == 1


def test_list_datasets_uses_short_ttl_cache(monkeypatch):
    cached = [
        {
            "id": 1,
            "name": "cached",
            "description": None,
            "project_id": 10,
            "format": "json",
            "row_count": 2,
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
