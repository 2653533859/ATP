import asyncio
from types import SimpleNamespace

import pytest

from app.services.performance_dataset import (
    PerformanceDatasetBindingError,
    load_dataset_rows,
    resolve_dataset_binding,
    serialize_dataset_rows,
)


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _DatasetDB:
    def __init__(self, dataset=None, version=None):
        self.dataset = dataset
        self.version = version

    async def get(self, model, _pk):
        if model.__name__ == "TestDataset":
            return self.dataset
        return None

    async def execute(self, _statement):
        return _ScalarResult(self.version)


def test_resolve_dataset_binding_checks_project_and_returns_latest_version():
    dataset = SimpleNamespace(project_id=3, rows=[{"user": "a"}])
    db = _DatasetDB(dataset=dataset, version=7)

    assert asyncio.run(resolve_dataset_binding(db, 9, 3)) == (9, 7)


def test_resolve_dataset_binding_rejects_missing_or_cross_project_dataset():
    with pytest.raises(PerformanceDatasetBindingError, match="不存在"):
        asyncio.run(resolve_dataset_binding(_DatasetDB(), 9, 3))

    with pytest.raises(PerformanceDatasetBindingError, match="不属于"):
        asyncio.run(resolve_dataset_binding(_DatasetDB(dataset=SimpleNamespace(project_id=4)), 9, 3))


def test_load_dataset_rows_falls_back_to_current_rows_for_legacy_run():
    rows = [{"user": "a"}, {"user": "b"}]
    db = _DatasetDB(dataset=SimpleNamespace(rows=rows))

    assert asyncio.run(load_dataset_rows(db, 9, None)) == rows
    assert asyncio.run(load_dataset_rows(db, None, None)) == []


def test_serialize_dataset_rows_is_compact_and_unicode_safe():
    assert serialize_dataset_rows([{"名称": "张三", "id": 1}]) == '[{"名称":"张三","id":1}]'
