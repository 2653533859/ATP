"""P3.B MVP-B 参数化执行单测：dataset.rows 按行循环 + parent 聚合。"""

import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# stub celery_app 防真依赖
class _FakeCelery:
    def task(self, *a, **kw):
        def deco(fn):
            return fn

        return deco

    conf = types.SimpleNamespace(update=lambda **kw: None)


sys.modules.setdefault("app.worker.celery_app", types.SimpleNamespace(celery_app=_FakeCelery()))

# 防 api/* 测试用 SimpleNamespace 覆盖了 app.worker.tasks（sys.modules 级别污染），
# 这里强制清理后再导入真实模块
sys.modules.pop("app.worker.tasks", None)

from app.models.bootstrap import load_all_models
from app.models.case import RunStatus, TestCase, TestRun
from app.models.dataset import TestDataset
from app.worker import tasks as worker_tasks

load_all_models()


class _FakeDB:
    def __init__(self, store):
        self.store = store
        self._next_id = 1000
        self.commits = 0
        self.added: list = []

    async def get(self, cls, pk):
        return self.store.get((cls.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.store[(obj.__class__.__name__, obj.id)] = obj
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        return None


def _setup(rows, case_dataset_id=42):
    case = TestCase(id=5, name="c", module_id=1)
    case.dataset_id = case_dataset_id
    parent = TestRun(id=100, case_id=5, triggered_by=1, status=RunStatus.pending)
    parent.parent_run_id = None
    parent.result_summary = {}
    parent.trace_id = "trace-x"
    parent.environment = None
    ds = TestDataset(
        id=42,
        name="d",
        project_id=10,
        format="json",
        rows=rows,
        schema_fields=[],
        validation_policy="soft",
        creator_id=1,
    )
    store = {
        ("TestCase", 5): case,
        ("TestRun", 100): parent,
        ("TestDataset", 42): ds,
    }
    return case, parent, _FakeDB(store)


def test_parameterized_creates_one_child_per_row(monkeypatch):
    case, parent, db = _setup([{"x": 1}, {"x": 2}, {"x": 3}])

    dispatched_args: list[tuple] = []

    async def fake_dispatch(_db, child, _case, extra_vars):
        dispatched_args.append((child.id, child.iteration_index, dict(extra_vars)))
        child.status = RunStatus.passed
        return True

    monkeypatch.setattr(worker_tasks, "dispatch_case", fake_dispatch)

    async def noop_publish(*_a, **_kw):
        return None

    monkeypatch.setattr(worker_tasks, "_safe_publish_run_event", noop_publish)
    monkeypatch.setattr(worker_tasks, "_safe_invalidate_stats_cache", noop_publish)

    asyncio.run(worker_tasks._execute_parameterized(db, parent, case, {"env": "stg"}))

    # 3 个 child + iteration_data 入 extra_vars
    assert len(dispatched_args) == 3
    indexes = [a[1] for a in dispatched_args]
    assert indexes == [0, 1, 2]
    # 每个 dispatch 收到 row data merge
    assert dispatched_args[0][2] == {"env": "stg", "x": 1}
    assert dispatched_args[2][2] == {"env": "stg", "x": 3}


def test_parameterized_aggregates_passed_when_all_children_pass(monkeypatch):
    case, parent, db = _setup([{"a": 1}, {"a": 2}])

    async def fake_dispatch(_db, child, _case, _vars):
        child.status = RunStatus.passed
        return True

    monkeypatch.setattr(worker_tasks, "dispatch_case", fake_dispatch)
    monkeypatch.setattr(worker_tasks, "_safe_publish_run_event", lambda *a, **kw: _async_noop())
    monkeypatch.setattr(worker_tasks, "_safe_invalidate_stats_cache", lambda *a, **kw: _async_noop())

    asyncio.run(worker_tasks._execute_parameterized(db, parent, case, {}))
    assert parent.status == RunStatus.passed
    assert parent.result_summary["iteration_passed"] == 2
    assert parent.result_summary["iteration_failed"] == 0


def test_parameterized_aggregates_failed_when_any_child_failed(monkeypatch):
    case, parent, db = _setup([{"a": 1}, {"a": 2}])

    seq = iter([RunStatus.passed, RunStatus.failed])

    async def fake_dispatch(_db, child, _case, _vars):
        child.status = next(seq)
        return True

    monkeypatch.setattr(worker_tasks, "dispatch_case", fake_dispatch)
    monkeypatch.setattr(worker_tasks, "_safe_publish_run_event", lambda *a, **kw: _async_noop())
    monkeypatch.setattr(worker_tasks, "_safe_invalidate_stats_cache", lambda *a, **kw: _async_noop())

    asyncio.run(worker_tasks._execute_parameterized(db, parent, case, {}))
    assert parent.status == RunStatus.failed
    assert parent.result_summary["iteration_passed"] == 1
    assert parent.result_summary["iteration_failed"] == 1


def test_parameterized_aggregates_error_when_dispatch_raises(monkeypatch):
    case, parent, db = _setup([{"a": 1}])

    async def fake_dispatch(*_a, **_kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(worker_tasks, "dispatch_case", fake_dispatch)
    monkeypatch.setattr(worker_tasks, "_safe_publish_run_event", lambda *a, **kw: _async_noop())
    monkeypatch.setattr(worker_tasks, "_safe_invalidate_stats_cache", lambda *a, **kw: _async_noop())

    asyncio.run(worker_tasks._execute_parameterized(db, parent, case, {}))
    assert parent.status == RunStatus.error
    assert parent.result_summary["iteration_error"] == 1


def test_parameterized_falls_back_to_single_run_when_dataset_empty(monkeypatch):
    """dataset 存在但 rows 为空 → 当作普通用例跑一次（不创建 child）。"""
    case, parent, db = _setup([])

    dispatched_runs: list = []

    async def fake_dispatch(_db, run, _case, _vars):
        dispatched_runs.append(run.id)
        run.status = RunStatus.passed
        return True

    monkeypatch.setattr(worker_tasks, "dispatch_case", fake_dispatch)
    monkeypatch.setattr(worker_tasks, "_safe_invalidate_stats_cache", lambda *a, **kw: _async_noop())

    asyncio.run(worker_tasks._execute_parameterized(db, parent, case, {}))

    # 仅 parent 本身被 dispatch，无 child 入库
    assert dispatched_runs == [parent.id]
    assert not any(isinstance(a, TestRun) and a is not parent for a in db.added)


def test_parameterized_strict_schema_blocks_invalid_dataset(monkeypatch):
    case, parent, db = _setup([{"age": "old"}])
    case.config = {"dataset_strict_schema": True}
    dataset = db.store[("TestDataset", 42)]
    dataset.schema_fields = [{"name": "age", "type": "integer", "required": True, "default": None}]

    dispatched = []

    async def fake_dispatch(*_a, **_kw):
        dispatched.append(True)

    monkeypatch.setattr(worker_tasks, "dispatch_case", fake_dispatch)
    monkeypatch.setattr(worker_tasks, "_safe_publish_run_event", lambda *a, **kw: _async_noop())
    monkeypatch.setattr(worker_tasks, "_safe_invalidate_stats_cache", lambda *a, **kw: _async_noop())

    asyncio.run(worker_tasks._execute_parameterized(db, parent, case, {}))

    assert dispatched == []
    assert parent.status == RunStatus.error
    assert parent.result_summary["dataset_schema_valid"] is False
    assert parent.result_summary["dataset_strict_schema"] is True
    assert parent.result_summary["dataset_schema_issue_count"] == 1


def test_parameterized_hard_policy_enforces_schema_without_case_flag(monkeypatch):
    case, parent, db = _setup([{"age": "old"}])
    dataset = db.store[("TestDataset", 42)]
    dataset.validation_policy = "hard"
    dataset.schema_fields = [{"name": "age", "type": "integer", "required": True, "default": None}]

    monkeypatch.setattr(worker_tasks, "_safe_publish_run_event", lambda *a, **kw: _async_noop())
    monkeypatch.setattr(worker_tasks, "_safe_invalidate_stats_cache", lambda *a, **kw: _async_noop())

    asyncio.run(worker_tasks._execute_parameterized(db, parent, case, {}))

    assert parent.status == RunStatus.error
    assert parent.result_summary["dataset_strict_schema"] is True


def test_parameterized_soft_policy_records_schema_issues_but_runs(monkeypatch):
    case, parent, db = _setup([{"age": "old"}])
    dataset = db.store[("TestDataset", 42)]
    dataset.schema_fields = [{"name": "age", "type": "integer", "required": True, "default": None}]

    dispatched = []

    async def fake_dispatch(_db, child, _case, _vars):
        dispatched.append(child.id)
        child.status = RunStatus.passed
        return True

    monkeypatch.setattr(worker_tasks, "dispatch_case", fake_dispatch)
    monkeypatch.setattr(worker_tasks, "_safe_publish_run_event", lambda *a, **kw: _async_noop())
    monkeypatch.setattr(worker_tasks, "_safe_invalidate_stats_cache", lambda *a, **kw: _async_noop())

    asyncio.run(worker_tasks._execute_parameterized(db, parent, case, {}))

    assert len(dispatched) == 1
    assert parent.status == RunStatus.passed
    assert parent.result_summary["dataset_schema_valid"] is False
    assert parent.result_summary["dataset_strict_schema"] is False


async def _async_noop(*_a, **_kw):
    return None
