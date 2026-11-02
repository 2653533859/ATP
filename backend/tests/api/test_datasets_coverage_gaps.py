"""补齐 datasets.py 端点的未覆盖分支：缓存降级、上传解析错误、AI 生成异常映射、
存储失败回滚与清理、MinIO 对象换名删除、版本回滚与影响面边界。

风格对齐 test_defects_endpoint_gaps.py：同步测试函数 + asyncio.run 直调端点 +
hand-rolled fake DB/Result + monkeypatch 模块属性。所有 Query/Form 参数均显式传值。
"""

import asyncio
import io
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException, UploadFile

from app.api.v1 import datasets as ds_api
from app.models.bootstrap import load_all_models
from app.models.case import TestCase
from app.models.dataset import TestDataset, TestDatasetVersion
from app.schemas.dataset import (
    DatasetAIGenerateIn,
    DatasetStorageReconcileIn,
    DatasetValidateIn,
    TestDatasetCreate,
    TestDatasetUpdate,
)
from app.services.dataset_storage import DatasetStorageError

load_all_models()

NOW = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows if rows is not None else []

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDBBase:
    """极简异步会话：get 走预置映射，execute 按队列返回，写操作只记录调用。"""

    def __init__(self, objects=None, results=None):
        self.objects = dict(objects or {})
        self.results = list(results or [])
        self.added = []
        self.deleted = []
        self.commits = 0
        self.rollbacks = 0
        self.execute_calls = 0
        self.commit_error = None

    async def get(self, model, ident):
        value = self.objects.get(model)
        return value(ident) if callable(value) else value

    async def execute(self, _statement):
        self.execute_calls += 1
        if self.results:
            return self.results.pop(0)
        return _Result()

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def commit(self):
        if self.commit_error is not None:
            raise self.commit_error
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, _value):
        return None


class _FakeDB(_FakeDBBase):
    async def flush(self):
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = 11


class _FakeDBNoFlush(_FakeDBBase):
    """不带 flush 的会话，覆盖 create_dataset 的 hasattr 兜底分支。"""


def _user(user_id: int = 7):
    return SimpleNamespace(id=user_id, username="engineer")


def _dataset(
    dataset_id=1,
    *,
    rows=None,
    project_id=10,
    storage_mode="database",
    object_name=None,
    row_count=None,
    schema_fields=None,
    validation_policy="soft",
):
    return TestDataset(
        id=dataset_id,
        name=f"ds-{dataset_id}",
        description="d",
        project_id=project_id,
        format="json",
        rows=rows if rows is not None else [{"a": 1}],
        storage_mode=storage_mode,
        object_name=object_name,
        row_count=row_count,
        schema_fields=schema_fields or [],
        validation_policy=validation_policy,
        creator_id=7,
        created_at=NOW,
        updated_at=NOW,
    )


def _version(
    version_id=21,
    *,
    dataset_id=1,
    version=1,
    rows=None,
    storage_mode="database",
    object_name=None,
    schema_fields=None,
    validation_policy="soft",
    change_type="create",
):
    return TestDatasetVersion(
        id=version_id,
        dataset_id=dataset_id,
        version=version,
        format="json",
        rows=rows if rows is not None else [{"a": 1}],
        storage_mode=storage_mode,
        object_name=object_name,
        schema_fields=schema_fields or [],
        validation_policy=validation_policy,
        change_type=change_type,
        created_by=7,
        created_at=NOW,
        updated_at=NOW,
    )


def _patch_uploads(monkeypatch, *, fail_on_version=False):
    uploaded = []

    def fake_upload(*, project_id, dataset_id, rows, version=None, object_name=None):
        if fail_on_version and version is not None:
            raise DatasetStorageError("MinIO version write failed")
        if object_name:
            name = object_name
        elif version is not None:
            name = f"datasets/{project_id}/{dataset_id}/version-{version}.json"
        else:
            name = f"datasets/{project_id}/{dataset_id}/current.json"
        uploaded.append(name)
        return name

    monkeypatch.setattr(ds_api, "upload_dataset_rows", fake_upload)
    return uploaded


def _patch_cleanup(monkeypatch):
    cleaned = []

    def fake_cleanup(project_id, dataset_id, object_names):
        cleaned.append((project_id, dataset_id, list(object_names)))
        return []

    monkeypatch.setattr(ds_api, "cleanup_dataset_object_names", fake_cleanup)
    return cleaned


def _patch_delete_file(monkeypatch, *, error=None):
    calls = []
    module = sys.modules["app.core.minio_client"]

    def fake_delete(object_name):
        calls.append(object_name)
        if error is not None:
            raise error

    monkeypatch.setattr(module, "delete_file", fake_delete)
    return calls


def _patch_audit(monkeypatch):
    calls = []

    async def fake_audit(_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(ds_api, "write_audit_log", fake_audit)
    return calls


def test_cache_helpers_swallow_redis_failures(monkeypatch):
    """Redis 读写异常时缓存 helper 静默降级；失效路径正常发出删除模式。"""

    async def failing_get(_key):
        raise RuntimeError("redis down")

    async def failing_set(_key, _value, _ttl):
        raise RuntimeError("redis down")

    monkeypatch.setattr(ds_api, "get_json_cache", failing_get)
    monkeypatch.setattr(ds_api, "set_json_cache", failing_set)
    assert asyncio.run(ds_api._safe_get_dataset_cache("atp:datasets:list:project_id=10")) is None
    assert asyncio.run(ds_api._safe_set_dataset_cache("k", [{"a": 1}])) is None

    patterns = []

    async def record_delete(pattern):
        patterns.append(pattern)

    monkeypatch.setattr(ds_api, "delete_json_cache_pattern", record_delete)
    assert asyncio.run(ds_api._invalidate_dataset_list_cache(10)) is None
    assert patterns == ["atp:datasets:list:project_id=10"]


def test_cleanup_uploaded_objects_skips_empty_and_schedules_prefix_cleanup(monkeypatch):
    """空列表不触发清理；非空列表按数据集前缀调度 MinIO 清理。"""
    cleaned = _patch_cleanup(monkeypatch)
    dataset = _dataset(3)
    ds_api._cleanup_uploaded_objects(dataset, [])
    assert cleaned == []
    ds_api._cleanup_uploaded_objects(dataset, ["datasets/10/3/current.json"])
    assert cleaned == [(10, 3, ["datasets/10/3/current.json"])]


def test_parse_dataset_file_rejects_empty_bad_encoding_and_bad_json():
    """空文件 / 非 UTF-8 的 CSV / 非法 JSON 均返回 400。"""
    with pytest.raises(HTTPException) as empty:
        ds_api._parse_dataset_file(b"", "x.csv", "csv")
    assert empty.value.status_code == 400
    assert "为空" in empty.value.detail

    with pytest.raises(HTTPException) as bad_csv:
        ds_api._parse_dataset_file(b"\xd6\xd0\xce\xc4", "x.csv", "json")
    assert bad_csv.value.status_code == 400
    assert "UTF-8" in bad_csv.value.detail

    with pytest.raises(HTTPException) as bad_json:
        ds_api._parse_dataset_file(b"{not json", "x.json", "json")
    assert bad_json.value.status_code == 400
    assert "JSON 解析失败" in bad_json.value.detail


def test_parse_dataset_file_csv_by_dataset_format_and_blank_rows():
    """文件名不是 .csv 但数据集格式为 csv 时仍按 CSV 解析；多余列与全空白行被过滤。"""
    raw = "a,b\n1,2,3\n\n , \n".encode("utf-8")
    rows, fmt = ds_api._parse_dataset_file(raw, "data.txt", "csv")
    assert rows == [{"a": "1", "b": "2"}]
    assert fmt == "csv"


def test_json_references_dataset_covers_nested_and_invalid_values():
    """dataset_id 递归匹配：字符串数字命中、非法值跳过、嵌套 dict/list 命中。"""
    assert ds_api._json_references_dataset({"dataset_id": "9"}, 9) is True
    assert ds_api._json_references_dataset({"dataset_id": "abc"}, 9) is False
    assert ds_api._json_references_dataset({"dataset_id": None}, 9) is False
    assert ds_api._json_references_dataset({"key": "x"}, 9) is False
    assert ds_api._json_references_dataset({"outer": {"dataset_id": 9}}, 9) is True
    assert ds_api._json_references_dataset([{"a": 1}, {"dataset_id": 9}], 9) is True
    assert ds_api._json_references_dataset("plain", 9) is False


def test_suite_and_plan_id_extraction_ignores_invalid_items():
    """非 dict 项、缺失/非法 id 项被跳过；合法字符串数字被转换收录。"""
    suite = SimpleNamespace(case_ids=["not-a-dict", {"case_id": "7"}, {"case_id": None}, {"case_id": 3}])
    assert ds_api._case_ids_from_suite(suite) == {7, 3}
    assert ds_api._case_ids_from_suite(SimpleNamespace(case_ids=None)) == set()

    plan = SimpleNamespace(suite_ids=[{"suite_id": "8"}, "x", {"suite_id": None}, {"suite_id": 4}])
    assert ds_api._suite_ids_from_plan(plan) == {8, 4}


def test_dataset_row_helpers_fall_back_to_defaults():
    """row_count/storage_mode/validation_policy 缺失时回退默认值；rows 为空时输出 []。"""
    bare = SimpleNamespace(rows=None)
    assert ds_api._dataset_row_count(bare) == 0
    assert ds_api._storage_mode(bare) == "database"
    assert ds_api._validation_policy(bare) == "soft"

    counted = SimpleNamespace(row_count=4, rows=[{"a": 1}], storage_mode="minio", validation_policy=None)
    assert ds_api._dataset_row_count(counted) == 4
    assert ds_api._storage_mode(counted) == "minio"
    assert ds_api._validation_policy(counted) == "soft"

    empty = TestDataset(
        name="e",
        description=None,
        project_id=1,
        format="json",
        rows=None,
        schema_fields=[],
        creator_id=1,
        created_at=NOW,
        updated_at=NOW,
    )
    out = ds_api._dataset_output(empty)
    assert out.rows == []
    assert out.row_count == 0
    assert out.storage_mode == "database"
    assert out.validation_policy == "soft"


def test_store_current_rows_with_and_without_tracking(monkeypatch):
    """MinIO 模式换用唯一 current 对象名并可跟踪；database 模式清空对象引用。"""
    dataset = _dataset(5, rows=[{"a": 1}], storage_mode="minio", object_name="datasets/10/5/current.json")
    uploaded = _patch_uploads(monkeypatch)
    tracked: list[str] = []
    object_name = ds_api._store_current_rows(dataset, [{"b": 2}], "minio", uploaded_object_names=tracked)
    assert object_name == dataset.object_name
    assert object_name.startswith("datasets/10/5/current-")
    assert uploaded == [object_name]
    assert tracked == [object_name]
    assert dataset.rows == []
    assert dataset.row_count == 1

    untracked = _dataset(6, rows=[{"a": 1}], storage_mode="minio", object_name="datasets/10/6/current.json")
    assert ds_api._store_current_rows(untracked, [{"c": 3}], "database", uploaded_object_names=None) is None
    assert untracked.object_name is None
    assert untracked.rows == [{"c": 3}]
    assert untracked.storage_mode == "database"

    # MinIO 模式且不跟踪上传对象：覆盖 uploaded_object_names 为 None 时的跳过分支
    plain = _dataset(7, rows=[{"a": 1}], storage_mode="minio")
    assert (
        ds_api._store_current_rows(plain, [{"d": 4}], "minio", uploaded_object_names=None)
        == "datasets/10/7/current.json"
    )
    assert plain.object_name == "datasets/10/7/current.json"


def test_snapshot_dataset_minio_without_tracking_list(monkeypatch):
    """MinIO 快照在未传跟踪列表时跳过 append，仅上传不可变版本对象。"""
    dataset = _dataset(5, rows=[{"a": 1}], storage_mode="minio", object_name="datasets/10/5/current.json")
    uploaded = _patch_uploads(monkeypatch)
    db = _FakeDB(results=[_Result(scalar=3)])
    version = asyncio.run(ds_api._snapshot_dataset(db, dataset, created_by=7, change_type="manual", rows=[{"x": 1}]))
    assert version.version == 4
    assert version.storage_mode == "minio"
    assert version.rows == []
    assert version.row_count == 1
    assert uploaded == ["datasets/10/5/version-4.json"]
    assert version.object_name == "datasets/10/5/version-4.json"


def test_ai_generate_guards_missing_project_config_and_dataset():
    """AI 生成的数据集/项目/AI 配置守卫：404 与 400 分支。"""
    with pytest.raises(HTTPException) as missing_project:
        asyncio.run(
            ds_api.generate_dataset_with_ai(body=DatasetAIGenerateIn(project_id=10), db=_FakeDB(), user=_user())
        )
    assert missing_project.value.status_code == 404

    no_ai = SimpleNamespace(id=10, ai_llm_config_id=None)
    with pytest.raises(HTTPException) as without_ai:
        asyncio.run(
            ds_api.generate_dataset_with_ai(
                body=DatasetAIGenerateIn(project_id=10),
                db=_FakeDB(objects={ds_api.Project: no_ai}),
                user=_user(),
            )
        )
    assert without_ai.value.status_code == 400

    project = SimpleNamespace(id=10, ai_llm_config_id=7)
    with pytest.raises(HTTPException) as missing_dataset:
        asyncio.run(
            ds_api.generate_dataset_with_ai(
                body=DatasetAIGenerateIn(project_id=10, dataset_id=3),
                db=_FakeDB(objects={ds_api.Project: project}),
                user=_user(),
            )
        )
    assert missing_dataset.value.status_code == 404

    with pytest.raises(HTTPException) as foreign_dataset:
        asyncio.run(
            ds_api.generate_dataset_with_ai(
                body=DatasetAIGenerateIn(project_id=10, dataset_id=3),
                db=_FakeDB(objects={ds_api.Project: project, TestDataset: _dataset(3, project_id=99)}),
                user=_user(),
            )
        )
    assert foreign_dataset.value.status_code == 400

    with pytest.raises(HTTPException) as missing_config:
        asyncio.run(
            ds_api.generate_dataset_with_ai(
                body=DatasetAIGenerateIn(project_id=10),
                db=_FakeDB(objects={ds_api.Project: project}),
                user=_user(),
            )
        )
    assert missing_config.value.status_code == 400


def test_ai_generate_maps_llm_failures(monkeypatch):
    """LLM 超时/HTTP 状态错误/网络错误/值错误分别映射为 504/502/502/400。"""
    project = SimpleNamespace(id=10, ai_llm_config_id=7)
    config = SimpleNamespace(id=7, enabled=True)
    db = _FakeDB(objects={ds_api.Project: project, ds_api.AILLMConfig: config})

    async def timeout(*_args, **_kwargs):
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr(ds_api, "generate_dataset_rows", timeout)
    with pytest.raises(HTTPException) as timed_out:
        asyncio.run(ds_api.generate_dataset_with_ai(body=DatasetAIGenerateIn(project_id=10), db=db, user=_user()))
    assert timed_out.value.status_code == 504

    request = httpx.Request("POST", "http://llm.example/v1/chat")

    async def status_error(*_args, **_kwargs):
        raise httpx.HTTPStatusError("boom", request=request, response=httpx.Response(429, request=request))

    monkeypatch.setattr(ds_api, "generate_dataset_rows", status_error)
    with pytest.raises(HTTPException) as bad_status:
        asyncio.run(ds_api.generate_dataset_with_ai(body=DatasetAIGenerateIn(project_id=10), db=db, user=_user()))
    assert bad_status.value.status_code == 502
    assert "429" in bad_status.value.detail

    async def transport_error(*_args, **_kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(ds_api, "generate_dataset_rows", transport_error)
    with pytest.raises(HTTPException) as network:
        asyncio.run(ds_api.generate_dataset_with_ai(body=DatasetAIGenerateIn(project_id=10), db=db, user=_user()))
    assert network.value.status_code == 502
    assert "网络" in network.value.detail

    async def invalid_rows(*_args, **_kwargs):
        raise ValueError("bad rows")

    monkeypatch.setattr(ds_api, "generate_dataset_rows", invalid_rows)
    with pytest.raises(HTTPException) as value_error:
        asyncio.run(ds_api.generate_dataset_with_ai(body=DatasetAIGenerateIn(project_id=10), db=db, user=_user()))
    assert value_error.value.status_code == 400
    assert "bad rows" in value_error.value.detail


def test_preview_upload_dataset_404_and_hard_policy_block():
    """上传预览：数据集缺失 404；hard 策略下校验失败不允许上传。"""
    file = UploadFile(filename="x.json", file=io.BytesIO(b'[{"k": 1}]'))
    with pytest.raises(HTTPException) as missing:
        asyncio.run(ds_api.preview_upload_dataset(dataset_id=999, file=file, db=_FakeDB(), user=_user()))
    assert missing.value.status_code == 404

    dataset = _dataset(
        5,
        rows=[{"age": 18}],
        schema_fields=[{"name": "age", "type": "integer", "required": True}],
        validation_policy="hard",
    )
    file = UploadFile(filename="x.json", file=io.BytesIO(b'[{"age": "old"}]'))
    result = asyncio.run(
        ds_api.preview_upload_dataset(dataset_id=5, file=file, db=_FakeDB(objects={TestDataset: dataset}), user=_user())
    )
    assert result.valid is False
    assert result.validation_policy == "hard"
    assert result.can_upload is False


def test_reconcile_project_dataset_storage_guards_and_purge(monkeypatch):
    """存储核对：项目缺失 404、MinIO 失败 503、purge 模式写入审计明细。"""
    with pytest.raises(HTTPException) as missing:
        asyncio.run(
            ds_api.reconcile_project_dataset_storage(
                project_id=10, body=DatasetStorageReconcileIn(), db=_FakeDB(), user=_user()
            )
        )
    assert missing.value.status_code == 404

    project = SimpleNamespace(id=10)
    audit = _patch_audit(monkeypatch)

    def failing_reconcile(*_args, **_kwargs):
        raise DatasetStorageError("minio down")

    monkeypatch.setattr(ds_api, "reconcile_dataset_objects", failing_reconcile)
    with pytest.raises(HTTPException) as unavailable:
        asyncio.run(
            ds_api.reconcile_project_dataset_storage(
                project_id=10,
                body=DatasetStorageReconcileIn(),
                db=_FakeDB(objects={ds_api.Project: project}),
                user=_user(),
            )
        )
    assert unavailable.value.status_code == 503

    captured = {}

    def ok_reconcile(project_id, referenced_object_names, *, purge=False):
        captured.update(project_id=project_id, refs=referenced_object_names, purge=purge)
        return {
            "project_id": project_id,
            "dry_run": not purge,
            "scanned_count": 2,
            "referenced_count": len(referenced_object_names),
            "orphan_count": 1,
            "orphaned_objects": ["datasets/10/9/current.json"],
            "truncated": False,
            "deleted_count": 1,
            "errors": [],
        }

    monkeypatch.setattr(ds_api, "reconcile_dataset_objects", ok_reconcile)
    db = _FakeDB(
        objects={ds_api.Project: project},
        results=[_Result(rows=["datasets/10/1/current.json", None]), _Result(rows=[])],
    )
    result = asyncio.run(
        ds_api.reconcile_project_dataset_storage(
            project_id=10, body=DatasetStorageReconcileIn(purge=True), db=db, user=_user()
        )
    )
    assert captured == {"project_id": 10, "refs": {"datasets/10/1/current.json"}, "purge": True}
    assert result.deleted_count == 1
    assert db.commits == 1
    assert "purge=True" in audit[0]["detail"]


def test_create_dataset_without_flush_support():
    """会话没有 flush 方法时跳过预取主键，仍能完成库内存储。"""
    db = _FakeDBNoFlush()
    body = TestDatasetCreate(name="nf", project_id=10, rows=[{"a": 1}])
    result = asyncio.run(ds_api.create_dataset(body=body, db=db, user=_user()))
    assert result.name == "nf"
    assert result.rows == [{"a": 1}]
    assert db.commits == 1
    assert db.execute_calls == 1


def test_create_dataset_storage_failure_cleans_up_uploaded_objects(monkeypatch):
    """创建时版本对象上传失败：回滚事务并清理已上传的 current 对象。"""
    uploaded = _patch_uploads(monkeypatch, fail_on_version=True)
    cleaned = _patch_cleanup(monkeypatch)
    db = _FakeDB()
    body = TestDatasetCreate(name="m", project_id=10, storage_mode="minio", rows=[{"a": 1}])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ds_api.create_dataset(body=body, db=db, user=_user()))
    assert exc.value.status_code == 503
    assert db.rollbacks == 1
    assert uploaded == ["datasets/10/11/current.json"]
    assert cleaned == [(10, 11, ["datasets/10/11/current.json"])]


def test_create_dataset_commit_failure_returns_conflict():
    """提交失败（如名称唯一约束）映射为 409。"""
    db = _FakeDB()
    db.commit_error = RuntimeError("duplicate name")
    body = TestDatasetCreate(name="dup", project_id=10, rows=[{"a": 1}])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ds_api.create_dataset(body=body, db=db, user=_user()))
    assert exc.value.status_code == 409
    assert db.rollbacks == 1


def test_get_dataset_returns_rows_and_maps_storage_failure(monkeypatch):
    """读取数据集：库内模式正常返回；MinIO 读取失败映射 503。"""
    dataset = _dataset(3, rows=[{"a": 1}])
    result = asyncio.run(ds_api.get_dataset(dataset_id=3, db=_FakeDB(objects={TestDataset: dataset}), user=_user()))
    assert result.rows == [{"a": 1}]
    assert result.storage_mode == "database"

    def failing_rows(_source):
        raise DatasetStorageError("minio down")

    monkeypatch.setattr(ds_api, "rows_from_source", failing_rows)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ds_api.get_dataset(dataset_id=3, db=_FakeDB(objects={TestDataset: dataset}), user=_user()))
    assert exc.value.status_code == 503


def test_update_dataset_missing_and_applies_description_and_rows():
    """更新：缺失 404；description 与 rows 替换生效且提交一次。"""
    with pytest.raises(HTTPException) as missing:
        asyncio.run(ds_api.update_dataset(dataset_id=999, body=TestDatasetUpdate(name="x"), db=_FakeDB(), user=_user()))
    assert missing.value.status_code == 404

    dataset = _dataset(4, rows=[{"a": 1}])
    db = _FakeDB(objects={TestDataset: dataset})
    result = asyncio.run(
        ds_api.update_dataset(
            dataset_id=4, body=TestDatasetUpdate(description="新说明", rows=[{"b": 2}]), db=db, user=_user()
        )
    )
    assert result.description == "新说明"
    assert result.rows == [{"b": 2}]
    assert db.commits == 1


def test_update_dataset_switches_storage_mode_and_maps_read_failure(monkeypatch):
    """存储模式切换时读取当前 rows 迁移；读取失败映射 503。"""
    dataset = _dataset(6, rows=[{"a": 1}])
    uploaded = _patch_uploads(monkeypatch)
    db = _FakeDB(objects={TestDataset: dataset})
    result = asyncio.run(
        ds_api.update_dataset(dataset_id=6, body=TestDatasetUpdate(storage_mode="minio"), db=db, user=_user())
    )
    assert result.storage_mode == "minio"
    assert result.rows == [{"a": 1}]
    assert dataset.rows == []
    assert uploaded == ["datasets/10/6/current.json", "datasets/10/6/version-1.json"]

    def failing_rows(_source):
        raise DatasetStorageError("minio down")

    monkeypatch.setattr(ds_api, "rows_from_source", failing_rows)
    other = _dataset(16, rows=[{"a": 1}])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ds_api.update_dataset(
                dataset_id=16,
                body=TestDatasetUpdate(storage_mode="minio"),
                db=_FakeDB(objects={TestDataset: other}),
                user=_user(),
            )
        )
    assert exc.value.status_code == 503


def test_update_dataset_storage_failure_and_previous_object_cleanup(monkeypatch):
    """更新：版本写入失败回滚并清理；换名成功后删除旧对象（删除异常被吞掉）。"""
    dataset = _dataset(8, rows=[{"a": 1}])
    _patch_uploads(monkeypatch, fail_on_version=True)
    cleaned = _patch_cleanup(monkeypatch)
    db = _FakeDB(objects={TestDataset: dataset})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ds_api.update_dataset(
                dataset_id=8,
                body=TestDatasetUpdate(storage_mode="minio", rows=[{"b": 2}]),
                db=db,
                user=_user(),
            )
        )
    assert exc.value.status_code == 503
    assert db.rollbacks == 1
    assert cleaned == [(10, 8, ["datasets/10/8/current.json"])]

    swapped = _dataset(9, rows=[], storage_mode="minio", object_name="datasets/10/9/current-old.json")
    _patch_uploads(monkeypatch)
    deleted = _patch_delete_file(monkeypatch, error=RuntimeError("minio down"))
    result = asyncio.run(
        ds_api.update_dataset(
            dataset_id=9,
            body=TestDatasetUpdate(rows=[{"b": 2}]),
            db=_FakeDB(objects={TestDataset: swapped}),
            user=_user(),
        )
    )
    assert result.storage_mode == "minio"
    assert deleted == ["datasets/10/9/current-old.json"]


def test_update_dataset_minio_reread_failure_returns_503(monkeypatch):
    """元数据更新后按 current 引用回读 rows 失败时返回 503。"""
    dataset = _dataset(13, rows=[], storage_mode="minio", object_name="datasets/10/13/current.json")
    _patch_uploads(monkeypatch)
    calls = {"count": 0}

    def flaky_rows(_source):
        calls["count"] += 1
        if calls["count"] >= 2:
            raise DatasetStorageError("minio down")
        return [{"a": 1}]

    monkeypatch.setattr(ds_api, "rows_from_source", flaky_rows)
    db = _FakeDB(objects={TestDataset: dataset})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ds_api.update_dataset(dataset_id=13, body=TestDatasetUpdate(name="x"), db=db, user=_user()))
    assert exc.value.status_code == 503
    assert db.commits == 1


def test_delete_dataset_missing_referenced_and_columnless(monkeypatch):
    """删除：缺失 404；被用例引用 409；模型缺少引用列时跳过检查直接删除。"""
    with pytest.raises(HTTPException) as missing:
        asyncio.run(ds_api.delete_dataset(dataset_id=9, db=_FakeDB(), user=_user()))
    assert missing.value.status_code == 404

    dataset = _dataset(9)
    db = _FakeDB(objects={TestDataset: dataset}, results=[_Result(scalar=5)])
    with pytest.raises(HTTPException) as referenced:
        asyncio.run(ds_api.delete_dataset(dataset_id=9, db=db, user=_user()))
    assert referenced.value.status_code == 409

    # 真实模型带 dataset_id 列；替换 app.models.case 中的引用以模拟"缺列"阶段
    assert hasattr(TestCase, "dataset_id")
    columnless = _dataset(10)
    columnless_db = _FakeDB(objects={TestDataset: columnless})
    monkeypatch.setattr("app.models.case.TestCase", SimpleNamespace())
    asyncio.run(ds_api.delete_dataset(dataset_id=10, db=columnless_db, user=_user()))
    assert columnless_db.execute_calls == 0
    assert columnless_db.deleted == [columnless]


def test_delete_dataset_swallows_object_cleanup_failure(monkeypatch):
    """删除后 MinIO 对象清理失败不阻断响应。"""
    dataset = _dataset(11)
    db = _FakeDB(objects={TestDataset: dataset}, results=[_Result()])

    def failing_delete(_project_id, _dataset_id):
        raise RuntimeError("minio down")

    monkeypatch.setattr(ds_api, "delete_dataset_objects", failing_delete)
    asyncio.run(ds_api.delete_dataset(dataset_id=11, db=db, user=_user()))
    assert db.commits == 1
    assert db.deleted == [dataset]


def test_get_dataset_impact_404_and_null_parameterization():
    """影响面：数据集缺失 404；参数化与 case_ids 为空时无命中。"""
    with pytest.raises(HTTPException) as missing:
        asyncio.run(ds_api.get_dataset_impact(dataset_id=99, db=_FakeDB(), user=_user()))
    assert missing.value.status_code == 404

    dataset = _dataset(9)
    suite = SimpleNamespace(id=201, name="s", case_ids=None, parameterization=None)
    db = _FakeDB(
        objects={TestDataset: dataset},
        results=[_Result(rows=[]), _Result(rows=[suite]), _Result(rows=[])],
    )
    result = asyncio.run(ds_api.get_dataset_impact(dataset_id=9, db=db, user=_user()))
    assert result.total_count == 0
    assert result.suites == []


def test_list_dataset_versions_404_when_dataset_missing():
    """版本列表：数据集缺失 404。"""
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ds_api.list_dataset_versions(dataset_id=99, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


def test_rollback_dataset_missing_dataset_and_snapshot():
    """回滚：数据集缺失 404；目标版本缺失 404。"""
    with pytest.raises(HTTPException) as missing_dataset:
        asyncio.run(ds_api.rollback_dataset(dataset_id=99, version=1, db=_FakeDB(), user=_user()))
    assert missing_dataset.value.status_code == 404

    dataset = _dataset(8)
    with pytest.raises(HTTPException) as missing_version:
        asyncio.run(
            ds_api.rollback_dataset(
                dataset_id=8, version=2, db=_FakeDB(objects={TestDataset: dataset}, results=[_Result()]), user=_user()
            )
        )
    assert missing_version.value.status_code == 404


def test_rollback_dataset_storage_failure_returns_503(monkeypatch):
    """回滚读取快照 rows 失败时回滚事务并返回 503。"""
    dataset = _dataset(8)
    snapshot = _version(1)

    def failing_rows(_source):
        raise DatasetStorageError("minio down")

    monkeypatch.setattr(ds_api, "rows_from_source", failing_rows)
    db = _FakeDB(objects={TestDataset: dataset}, results=[_Result(scalar=snapshot)])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ds_api.rollback_dataset(dataset_id=8, version=1, db=db, user=_user()))
    assert exc.value.status_code == 503
    assert db.rollbacks == 1


def test_rollback_dataset_commit_failure_returns_409():
    """回滚提交失败映射为 409 并回滚事务。"""
    dataset = _dataset(8, rows=[{"age": "old"}])
    snapshot = _version(1, rows=[{"age": 18}])
    db = _FakeDB(objects={TestDataset: dataset}, results=[_Result(scalar=snapshot)])
    db.commit_error = RuntimeError("db down")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ds_api.rollback_dataset(dataset_id=8, version=1, db=db, user=_user()))
    assert exc.value.status_code == 409
    assert db.rollbacks == 1


def test_rollback_dataset_restores_minio_snapshot(monkeypatch):
    """回滚到 MinIO 快照：重新上传 current 与版本对象，删除旧 current 对象。"""
    dataset = _dataset(8, rows=[{"age": "old"}], object_name="datasets/10/8/current-old.json")
    snapshot = _version(
        1,
        rows=[],
        storage_mode="minio",
        object_name="datasets/10/8/version-1.json",
        schema_fields=[{"name": "age", "type": "integer"}],
        validation_policy="hard",
    )
    uploaded = _patch_uploads(monkeypatch)
    monkeypatch.setattr(ds_api, "rows_from_source", lambda _source: [{"age": 18}])
    deleted = _patch_delete_file(monkeypatch, error=RuntimeError("minio down"))
    db = _FakeDB(objects={TestDataset: dataset}, results=[_Result(scalar=snapshot), _Result(scalar=1)])
    result = asyncio.run(ds_api.rollback_dataset(dataset_id=8, version=1, db=db, user=_user()))
    assert result.rows == [{"age": 18}]
    assert result.storage_mode == "minio"
    assert result.schema_fields == [{"name": "age", "type": "integer"}]
    assert result.validation_policy == "hard"
    assert uploaded[0].startswith("datasets/10/8/current-")
    assert uploaded[1] == "datasets/10/8/version-2.json"
    assert deleted == ["datasets/10/8/current-old.json"]
    assert db.commits == 1


def test_upload_dataset_missing_dataset_and_storage_failure(monkeypatch):
    """上传：数据集缺失 404；版本对象写入失败回滚并返回 503。"""
    file = UploadFile(filename="x.json", file=io.BytesIO(b'[{"k": 1}]'))
    with pytest.raises(HTTPException) as missing:
        asyncio.run(ds_api.upload_dataset(dataset_id=999, file=file, db=_FakeDB(), user=_user()))
    assert missing.value.status_code == 404

    dataset = _dataset(6, rows=[], storage_mode="minio", object_name="datasets/10/6/current.json")
    uploaded = _patch_uploads(monkeypatch, fail_on_version=True)
    cleaned = _patch_cleanup(monkeypatch)
    db = _FakeDB(objects={TestDataset: dataset})
    file = UploadFile(filename="x.json", file=io.BytesIO(b'[{"k": 1}]'))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ds_api.upload_dataset(dataset_id=6, file=file, db=db, user=_user()))
    assert exc.value.status_code == 503
    assert db.rollbacks == 1
    assert cleaned == [(10, 6, uploaded)]
    assert uploaded[0].startswith("datasets/10/6/current-")


def test_upload_dataset_commit_failure_returns_409():
    """上传提交失败映射为 409 并回滚事务。"""
    dataset = _dataset(6, rows=[])
    db = _FakeDB(objects={TestDataset: dataset})
    db.commit_error = RuntimeError("db down")
    file = UploadFile(filename="x.json", file=io.BytesIO(b'[{"k": 1}]'))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ds_api.upload_dataset(dataset_id=6, file=file, db=db, user=_user()))
    assert exc.value.status_code == 409
    assert db.rollbacks == 1


def test_upload_dataset_swaps_previous_object(monkeypatch):
    """上传覆盖后删除旧 current 对象；删除异常被吞掉。"""
    dataset = _dataset(6, rows=[], storage_mode="minio", object_name="datasets/10/6/current-old.json")
    _patch_uploads(monkeypatch)
    deleted = _patch_delete_file(monkeypatch, error=RuntimeError("minio down"))
    db = _FakeDB(objects={TestDataset: dataset})
    file = UploadFile(filename="x.json", file=io.BytesIO(b'[{"k": 1}]'))
    result = asyncio.run(ds_api.upload_dataset(dataset_id=6, file=file, db=db, user=_user()))
    assert result.storage_mode == "minio"
    assert result.rows == [{"k": 1}]
    assert deleted == ["datasets/10/6/current-old.json"]


def test_validate_dataset_rejects_oversize_rows():
    """独立校验端点同样受库内行数上限约束。"""
    body = DatasetValidateIn(rows=[{"k": "x" * 1000} for _ in range(600)])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ds_api.validate_dataset(body=body, _=_user()))
    assert exc.value.status_code == 400
