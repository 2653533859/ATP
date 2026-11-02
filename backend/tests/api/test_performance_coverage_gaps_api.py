"""补齐 backend/app/api/v1/performance.py 剩余未覆盖分支的单元测试。

成功路径与幂等重放已有覆盖（见 test_performance_api_behavior.py）；本文件只针对
coverage.xml 中 hits=0 的错误分支：脚本后缀 / 环境 / 快照校验、节点容量与 draining、
多节点分片竞态与 409 / 400 守卫、基线、调度、停止信号失败以及各 404 路径。
全部直接调用路由函数并注入自建 _GapDB，不触碰真实网络 / MinIO / Celery broker。
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _noop_async(*_args, **_kwargs):
    return None


def _noop_dependency(*_args, **_kwargs):
    return None


sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(
    assert_project_access=_noop_async,
    get_current_user=lambda: None,
    require_engineer=lambda: None,
    require_project_access=lambda *_a, **_kw: _noop_dependency,
)


class _DelayRecorder:
    def __init__(self):
        self.calls: list[int] = []

    def delay(self, run_id: int):
        self.calls.append(run_id)

    def apply_async(self, args=(), queue=None, **_kwargs):
        self.calls.append(args[0] if args else None)


_delay_recorder = _DelayRecorder()
sys.modules["app.worker.tasks_performance"] = types.SimpleNamespace(
    run_performance_test=_delay_recorder,
)

from app.api.v1 import performance
from app.models.bootstrap import load_all_models
from app.models.performance import PerformanceRunStatus
from app.schemas.performance import (
    PerformanceBaselineUpdate,
    PerformanceCapacityAnalyzeRequest,
    PerformanceRunTrigger,
    PerformanceScheduleUpdate,
    PerformanceTestUpdate,
)
from app.schemas.performance_node import PerformanceNodeCreate, PerformanceNodeUpdate
from app.services.performance_dataset import PerformanceDatasetBindingError
from app.services.performance_idempotency import PerformanceIdempotencyConflict

load_all_models()


@pytest.fixture(autouse=True)
def _bind_task_recorder(monkeypatch):
    # 整套运行时 app.api.v1.performance 可能已被更早收集的文件以真实 Celery 任务导入，
    # 上面的 sys.modules 桩对已缓存模块无效；这里按属性替换，保证触发接口落到记录器而非 broker。
    monkeypatch.setattr(performance, "run_performance_test", _delay_recorder)


@pytest.fixture(autouse=True)
def _isolate_performance_settings(monkeypatch):
    monkeypatch.setattr(performance.settings, "ATP_LOCAL_MODE", False)
    monkeypatch.setattr(performance.settings, "PERFORMANCE_TARGET_ALLOWLIST", "")
    monkeypatch.setattr(performance.settings, "PERFORMANCE_MAX_VUS", 50)
    monkeypatch.setattr(performance.settings, "PERFORMANCE_MAX_DURATION_SECONDS", 900)


class _User:
    id = 7
    username = "alice"


class _ListResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = list(rows or [])
        self._scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._scalar


class _GapDB:
    """按模型名分桶的轻量 session；支持脚本化 execute 与指定第 N 次 commit 失败。"""

    def __init__(self, objects=None, *, commit_failures=None, execute_queue=None):
        self.objects = objects or {}
        self.commit_failures = set(commit_failures or ())
        self.execute_queue = list(execute_queue or [])
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self.locked_gets = []
        self.refreshed = []
        self.deleted = []

    async def get(self, model, pk, **kwargs):
        if kwargs.get("with_for_update"):
            self.locked_gets.append((model.__name__, pk))
        return self.objects.get(model.__name__, {}).get(pk)

    def add(self, obj):
        obj.id = 100 + len(self.added)
        now = datetime(2026, 5, 29, tzinfo=timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self.added.append(obj)

    async def execute(self, _statement):
        if self.execute_queue:
            return self.execute_queue.pop(0)
        return _ListResult()

    async def commit(self):
        self.commits += 1
        if self.commits in self.commit_failures:
            raise IntegrityError("insert", {}, RuntimeError("duplicate idempotency key"))

    async def flush(self):
        self.flushes += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime(2026, 5, 29, tzinfo=timezone.utc)
        obj.updated_at = datetime(2026, 5, 29, tzinfo=timezone.utc)

    async def delete(self, obj):
        self.deleted.append(obj)


def _http_error(coro, status_code: int) -> HTTPException:
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(coro)
    assert excinfo.value.status_code == status_code
    return excinfo.value


def _perf_test(test_id: int = 3, **overrides):
    values = dict(
        id=test_id,
        project_id=2,
        name="Load test",
        executor="k6",
        script_object_name="scripts/load.js",
        default_options={"vus": 5, "duration": 30},
        dataset_id=None,
        baseline_run_id=None,
        schedule_enabled=False,
        cron_expression=None,
        schedule_timezone="Asia/Shanghai",
        schedule_options={},
        schedule_environment_id=None,
        schedule_node_id=None,
        next_run_at=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _node(pk: int = 17, **overrides):
    values = dict(
        id=pk,
        node_id="node-%d" % pk,
        name="Node %d" % pk,
        queue_name="performance",
        status="online",
        enabled=True,
        labels={"managed_by": "ui"},
        capabilities={"executors": ["k6", "locust", "grpc", "jmeter"]},
        max_vus=None,
        max_concurrency=None,
        egress_allowlist=[],
        last_heartbeat_at=datetime.now(timezone.utc),
        last_error=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _run(run_id: int = 10, **overrides):
    values = dict(
        id=run_id,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.running.value,
        summary={},
        raw_result_object_name=None,
        options_snapshot={},
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class _CancelRecorder:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def __call__(self, run_id: int):
        self.calls.append(run_id)
        if self.error is not None:
            raise self.error


class _Upload:
    def __init__(self, filename: str = "load.js"):
        self.filename = filename

    async def read(self):
        return b"export default function () {}"


# ==== 校验辅助 ====


def test_validate_script_suffix_rejects_unknown_executor():
    with pytest.raises(HTTPException) as excinfo:
        performance._validate_script_suffix("nope", "load.js")
    assert excinfo.value.status_code == 400
    assert "nope" in excinfo.value.detail


def test_validate_script_suffix_rejects_wrong_extension():
    with pytest.raises(HTTPException) as excinfo:
        performance._validate_script_suffix("k6", "scripts/load.py")
    assert excinfo.value.status_code == 400


def test_load_environment_variables_404_when_environment_missing():
    err = _http_error(performance._load_environment_variables(_GapDB(), 5, 2), 404)
    assert "不存在" in err.detail


def test_load_environment_variables_rejects_foreign_project():
    db = _GapDB({"Environment": {5: SimpleNamespace(id=5, project_id=99)}})
    err = _http_error(performance._load_environment_variables(db, 5, 2), 400)
    assert "不属于当前项目" in err.detail


def test_build_options_snapshot_wraps_ramp_errors():
    with pytest.raises(HTTPException) as excinfo:
        performance._build_options_snapshot(None, {"auto_ramp": {"start_vus": 5, "max_vus": 1}}, {}, set())
    assert excinfo.value.status_code == 400


def test_validate_duration_fields_covers_stage_branches():
    performance._validate_duration_fields({"stages": [{"target": 5}, {"duration": "30s", "target": 5}]})
    with pytest.raises(HTTPException) as excinfo:
        performance._validate_duration_fields({"stages": [{"duration": "not-a-duration"}]})
    assert excinfo.value.status_code == 400


def test_max_vus_tolerates_non_numeric_candidates():
    options = {"vus": "abc", "users": "abc", "concurrency": "abc", "stages": [{"target": "abc"}]}
    assert performance._max_vus_from_options(options) == 0
    assert performance._max_vus_from_options({"users": "3"}) == 3


def test_target_hosts_reads_direct_host_option():
    hosts = performance._target_hosts_from_options({"host": "https://direct.example.test/load"})
    assert hosts == {"direct.example.test"}


def test_target_hosts_reads_target_metrics_variants(monkeypatch):
    metrics = {"target_metrics": {"prometheus_url": "https://prom.example.test"}}
    assert performance._target_hosts_from_options(metrics) == {"prom.example.test"}
    env_metrics = {"target_metrics": {"url_env": "PROM_URL"}, "env": {"PROM_URL": "https://env-prom.example.test"}}
    assert performance._target_hosts_from_options(env_metrics) == {"env-prom.example.test"}
    monkeypatch.setenv("ATP_PROM_ENV_URL", "https://os-prom.example.test")
    os_metrics = {"target_metrics": {"url_env": "ATP_PROM_ENV_URL"}}
    assert performance._target_hosts_from_options(os_metrics) == {"os-prom.example.test"}


def test_target_hosts_tolerates_broken_and_typed_dataset_rows():
    assert performance._target_hosts_from_options({"env": {"ATP_DATASET_JSON": "{oops"}}) == set()
    rows = json.dumps([1, {"TARGET_URL": "https://row.example.test"}, {"account": "a"}])
    assert performance._target_hosts_from_options({"env": {"ATP_DATASET_JSON": rows}}) == {"row.example.test"}


def test_validate_performance_options_rejects_unknown_executor():
    with pytest.raises(HTTPException) as excinfo:
        performance._validate_performance_options({"vus": 1}, "nope")
    assert excinfo.value.status_code == 400


def test_validate_performance_options_rejects_non_dict():
    with pytest.raises(HTTPException) as excinfo:
        performance._validate_performance_options("not-a-dict", "k6")
    assert excinfo.value.status_code == 400


def test_validate_performance_options_wraps_ramp_error():
    with pytest.raises(HTTPException) as excinfo:
        performance._validate_performance_options({"auto_ramp": "oops"}, "k6")
    assert excinfo.value.status_code == 400


def test_validate_performance_options_wraps_metric_boundary_error():
    with pytest.raises(HTTPException) as excinfo:
        performance._validate_performance_options({"target_metrics": "oops"}, "k6")
    assert excinfo.value.status_code == 400


def test_next_schedule_time_wraps_invalid_inputs():
    with pytest.raises(HTTPException) as excinfo:
        performance._next_schedule_time("0 1 * * *", "Not/AZone")
    assert excinfo.value.status_code == 400
    with pytest.raises(HTTPException) as excinfo:
        performance._next_schedule_time("definitely-not-cron", "UTC")
    assert excinfo.value.status_code == 400


def test_resolve_performance_node_local_mode_rejects_remote(monkeypatch):
    monkeypatch.setattr(performance.settings, "ATP_LOCAL_MODE", True)
    db = _GapDB()
    err = _http_error(performance._resolve_performance_node(db, 17, {}), 409)
    assert err.detail
    assert db.locked_gets == []


def test_resolve_performance_node_404_when_missing():
    err = _http_error(performance._resolve_performance_node(_GapDB(), 17, {}), 404)
    assert "不存在" in err.detail


def test_resolve_performance_node_rejects_disabled_node():
    node = _node(17, enabled=False, status="disabled")
    db = _GapDB({"PerformanceNode": {17: node}})
    err = _http_error(performance._resolve_performance_node(db, 17, {}), 409)
    assert err.detail


def test_resolve_performance_node_rejects_full_capacity(monkeypatch):
    node = _node(17)

    async def _no_capacity(*_args, **_kwargs):
        return False

    monkeypatch.setattr(performance, "node_has_capacity", _no_capacity)
    db = _GapDB({"PerformanceNode": {17: node}})
    err = _http_error(performance._resolve_performance_node(db, 17, {}, "k6"), 409)
    assert err.detail


def test_resolve_performance_dataset_wraps_binding_errors(monkeypatch):
    async def _raise_binding_error(*_args, **_kwargs):
        raise PerformanceDatasetBindingError("性能压测数据集不存在")

    monkeypatch.setattr(performance, "resolve_dataset_binding", _raise_binding_error)
    err = _http_error(performance._resolve_performance_dataset(_GapDB(), 9, 2), 400)
    assert "数据集不存在" in err.detail


# ==== 节点路由 ====


def test_list_performance_nodes_refreshes_effective_status():
    stale = datetime(2020, 1, 1, tzinfo=timezone.utc)
    nodes = [_node(1, status="offline"), _node(2, enabled=False), _node(3, last_heartbeat_at=stale)]
    db = _GapDB(execute_queue=[_ListResult(nodes)])
    result = asyncio.run(performance.list_performance_nodes(db, _User()))
    assert [node.status for node in result] == ["offline", "disabled", "offline"]


def test_create_performance_node_maps_commit_failure_to_409():
    db = _GapDB(commit_failures={1})
    body = PerformanceNodeCreate(node_id="node-b", name="Node B")
    err = _http_error(performance.create_performance_node(body, db, _User()), 409)
    assert err.detail
    assert db.rollbacks == 1


def test_get_performance_node_404():
    err = _http_error(performance.get_performance_node(5, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


def test_get_performance_node_recomputes_status():
    node = _node(5, last_heartbeat_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    db = _GapDB({"PerformanceNode": {5: node}})
    result = asyncio.run(performance.get_performance_node(5, db, _User()))
    assert result is node
    assert node.status == "offline"


def test_update_performance_node_404():
    body = PerformanceNodeUpdate(name="New name")
    err = _http_error(performance.update_performance_node(17, body, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


def test_update_performance_node_normalizes_egress_allowlist():
    node = _node(17)
    db = _GapDB({"PerformanceNode": {17: node}})
    body = PerformanceNodeUpdate(egress_allowlist=[" API.Example.test ", "b.example.test"])
    result = asyncio.run(performance.update_performance_node(17, body, db, _User()))
    assert result.egress_allowlist == ["api.example.test", "b.example.test"]
    assert result.labels["managed_by"] == "ui"
    assert db.commits == 1


def test_update_performance_node_sets_draining_status():
    node = _node(17)
    db = _GapDB({"PerformanceNode": {17: node}})
    body = PerformanceNodeUpdate(status="draining")
    result = asyncio.run(performance.update_performance_node(17, body, db, _User()))
    assert result.status == "draining"


def test_delete_performance_node_404():
    err = _http_error(performance.delete_performance_node(17, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


# ==== 压测定义 / 上传 / 基线 / 调度 ====


def test_upload_performance_script_rejects_unknown_executor():
    err = _http_error(performance.upload_performance_script(2, _Upload(), "nope", _GapDB(), _User()), 400)
    assert "nope" in err.detail


def test_update_performance_test_rejects_unknown_executor():
    item = _perf_test(executor="nope")
    db = _GapDB({"PerformanceTest": {3: item}})
    body = PerformanceTestUpdate()
    err = _http_error(performance.update_performance_test(3, body, db, _User()), 400)
    assert err.detail


def test_update_performance_test_switches_executor_with_suffix_check():
    item = _perf_test(script_object_name="scripts/load.py")
    db = _GapDB({"PerformanceTest": {3: item}})
    body = PerformanceTestUpdate(executor="locust")
    result = asyncio.run(performance.update_performance_test(3, body, db, _User()))
    assert result.executor == "locust"
    assert db.commits == 1


def test_update_performance_test_applies_options_and_clears_dataset():
    item = _perf_test(dataset_id=9)
    db = _GapDB({"PerformanceTest": {3: item}})
    body = PerformanceTestUpdate(default_options={"vus": 2, "duration": 60}, dataset_id=None)
    result = asyncio.run(performance.update_performance_test(3, body, db, _User()))
    assert result.default_options == {"vus": 2, "duration": 60}
    assert result.dataset_id is None


def test_set_performance_baseline_404_when_test_missing():
    body = PerformanceBaselineUpdate(run_id=10)
    err = _http_error(performance.set_performance_baseline(3, body, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


def test_set_performance_baseline_rejects_missing_run():
    item = _perf_test()
    db = _GapDB({"PerformanceTest": {3: item}})
    body = PerformanceBaselineUpdate(run_id=10)
    err = _http_error(performance.set_performance_baseline(3, body, db, _User()), 400)
    assert "基线运行不属于当前压测定义" in err.detail


def test_set_performance_baseline_rejects_unfinished_run():
    item = _perf_test()
    baseline = SimpleNamespace(id=10, performance_test_id=3, project_id=2, status=PerformanceRunStatus.running.value)
    db = _GapDB({"PerformanceTest": {3: item}, "PerformanceRun": {10: baseline}})
    body = PerformanceBaselineUpdate(run_id=10)
    err = _http_error(performance.set_performance_baseline(3, body, db, _User()), 400)
    assert "成功完成的运行" in err.detail


def test_set_performance_baseline_persists_successful_run():
    item = _perf_test()
    baseline = SimpleNamespace(id=10, performance_test_id=3, project_id=2, status=PerformanceRunStatus.success.value)
    db = _GapDB({"PerformanceTest": {3: item}, "PerformanceRun": {10: baseline}})
    body = PerformanceBaselineUpdate(run_id=10)
    result = asyncio.run(performance.set_performance_baseline(3, body, db, _User()))
    assert result.baseline_run_id == 10
    assert db.commits == 1


def test_clear_performance_baseline_404():
    err = _http_error(performance.clear_performance_baseline(3, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


def test_clear_performance_baseline_resets_reference():
    item = _perf_test(baseline_run_id=10)
    db = _GapDB({"PerformanceTest": {3: item}})
    result = asyncio.run(performance.clear_performance_baseline(3, db, _User()))
    assert result.baseline_run_id is None
    assert db.commits == 1


def test_update_performance_schedule_local_mode_rejects_enable(monkeypatch):
    monkeypatch.setattr(performance.settings, "ATP_LOCAL_MODE", True)
    body = PerformanceScheduleUpdate(enabled=True, cron_expression="* * * * *")
    err = _http_error(performance.update_performance_schedule(3, body, _GapDB(), _User()), 409)
    assert "本地" in err.detail


def test_update_performance_schedule_404():
    body = PerformanceScheduleUpdate(enabled=False)
    err = _http_error(performance.update_performance_schedule(3, body, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


def test_update_performance_schedule_loads_environment_and_computes_next_run():
    item = _perf_test()
    env_row = SimpleNamespace(key="TARGET_URL", value="https://env.example.test", is_secret=False)
    db = _GapDB(
        {"PerformanceTest": {3: item}, "Environment": {9: SimpleNamespace(id=9, project_id=2)}},
        execute_queue=[_ListResult([env_row])],
    )
    body = PerformanceScheduleUpdate(enabled=True, cron_expression="*/5 * * * *", environment_id=9)
    result = asyncio.run(performance.update_performance_schedule(3, body, db, _User()))
    assert result.schedule_enabled is True
    assert result.schedule_environment_id == 9
    assert result.next_run_at is not None
    assert db.commits == 1


def test_update_performance_schedule_disable_clears_next_run():
    item = _perf_test(
        schedule_enabled=True,
        cron_expression="0 1 * * *",
        next_run_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    db = _GapDB({"PerformanceTest": {3: item}})
    body = PerformanceScheduleUpdate(enabled=False)
    result = asyncio.run(performance.update_performance_schedule(3, body, db, _User()))
    assert result.schedule_enabled is False
    assert result.cron_expression is None
    assert result.next_run_at is None


# ==== 触发压测 ====


def test_trigger_rejects_conflicting_node_selectors():
    item = _perf_test()
    db = _GapDB({"PerformanceTest": {3: item}})
    body = PerformanceRunTrigger(performance_node_id=17, performance_node_ids=[18], options={})
    err = _http_error(performance.trigger_performance_run(3, body, db, _User()), 400)
    assert "不能同时传入" in err.detail


def test_trigger_rejects_duplicate_nodes():
    item = _perf_test()
    db = _GapDB({"PerformanceTest": {3: item}})
    body = PerformanceRunTrigger(performance_node_ids=[17, 17], options={})
    err = _http_error(performance.trigger_performance_run(3, body, db, _User()), 400)
    assert "不能重复" in err.detail


def test_trigger_rejects_shards_exceeding_load():
    item = _perf_test()
    db = _GapDB({"PerformanceTest": {3: item}})
    body = PerformanceRunTrigger(performance_node_ids=[17, 18], options={"vus": 1})
    err = _http_error(performance.trigger_performance_run(3, body, db, _User()), 400)
    assert "总负载必须不少于节点数" in err.detail


def test_trigger_rejects_missing_shard_plan(monkeypatch):
    item = _perf_test()
    nodes = {"PerformanceNode": {17: _node(17), 18: _node(18)}}
    db = _GapDB({"PerformanceTest": {3: item}, **nodes})
    monkeypatch.setattr(performance, "split_performance_options", lambda *_a, **_kw: None)
    body = PerformanceRunTrigger(performance_node_ids=[17, 18], options={})
    err = _http_error(performance.trigger_performance_run(3, body, db, _User()), 400)
    assert "分片配置缺失" in err.detail
    assert db.locked_gets == [("PerformanceNode", 17), ("PerformanceNode", 18)]


def test_trigger_rejects_blank_idempotency_key():
    item = _perf_test()
    db = _GapDB({"PerformanceTest": {3: item}})
    body = PerformanceRunTrigger.model_construct(
        environment_id=None,
        performance_node_id=None,
        performance_node_ids=[],
        idempotency_key="   ",
        options={},
    )
    err = _http_error(performance.trigger_performance_run(3, body, db, _User()), 400)
    assert "幂等键" in err.detail


def test_trigger_multinode_commit_race_returns_existing_run(monkeypatch):
    item = _perf_test()
    existing = SimpleNamespace(id=88, status=PerformanceRunStatus.running.value)
    db = _GapDB(
        {"PerformanceTest": {3: item}, "PerformanceNode": {17: _node(17), 18: _node(18)}},
        commit_failures={1},
    )
    calls = []

    async def fake_find(db_arg, *, project_id, performance_test_id, key, fingerprint):
        calls.append(key)
        return None if len(calls) == 1 else existing

    monkeypatch.setattr(performance, "find_idempotent_run", fake_find)
    body = PerformanceRunTrigger(performance_node_ids=[17, 18], idempotency_key="ci-1", options={})
    result = asyncio.run(performance.trigger_performance_run(3, body, db, _User()))
    assert result is existing
    assert len(calls) == 2
    assert db.rollbacks == 1


def test_trigger_multinode_commit_race_conflicts(monkeypatch):
    item = _perf_test()
    db = _GapDB(
        {"PerformanceTest": {3: item}, "PerformanceNode": {17: _node(17), 18: _node(18)}},
        commit_failures={1},
    )
    calls = []

    async def fake_find(db_arg, *, project_id, performance_test_id, key, fingerprint):
        calls.append(key)
        if len(calls) == 1:
            return None
        raise PerformanceIdempotencyConflict("幂等键已被其他压测请求使用")

    monkeypatch.setattr(performance, "find_idempotent_run", fake_find)
    body = PerformanceRunTrigger(performance_node_ids=[17, 18], idempotency_key="ci-2", options={})
    err = _http_error(performance.trigger_performance_run(3, body, db, _User()), 409)
    assert "幂等键" in err.detail


def test_trigger_multinode_commit_race_without_key_reraises():
    item = _perf_test()
    db = _GapDB(
        {"PerformanceTest": {3: item}, "PerformanceNode": {17: _node(17), 18: _node(18)}},
        commit_failures={1},
    )
    body = PerformanceRunTrigger(performance_node_ids=[17, 18], options={})
    with pytest.raises(IntegrityError):
        asyncio.run(performance.trigger_performance_run(3, body, db, _User()))
    assert db.rollbacks == 1


def test_trigger_single_commit_race_conflicts(monkeypatch):
    item = _perf_test()
    db = _GapDB({"PerformanceTest": {3: item}}, commit_failures={1})
    calls = []

    async def fake_find(db_arg, *, project_id, performance_test_id, key, fingerprint):
        calls.append(key)
        if len(calls) == 1:
            return None
        raise PerformanceIdempotencyConflict("幂等键已被其他压测请求使用")

    monkeypatch.setattr(performance, "find_idempotent_run", fake_find)
    body = PerformanceRunTrigger(idempotency_key="ci-3", options={})
    err = _http_error(performance.trigger_performance_run(3, body, db, _User()), 409)
    assert "幂等键" in err.detail


def test_trigger_single_commit_race_without_key_reraises():
    item = _perf_test()
    db = _GapDB({"PerformanceTest": {3: item}}, commit_failures={1})
    body = PerformanceRunTrigger(options={})
    with pytest.raises(IntegrityError):
        asyncio.run(performance.trigger_performance_run(3, body, db, _User()))
    assert db.rollbacks == 1


# ==== 容量分析 / 停止 / 报表导出 ====


def test_capacity_analyze_returns_curve():
    run = _run(10, status="success", options_snapshot={"vus": 10}, summary={"error_rate": 0.0, "p95_ms": 10.0})
    db = _GapDB(execute_queue=[_ListResult([run])])
    body = PerformanceCapacityAnalyzeRequest(run_ids=[10], max_error_rate=0.05, max_p95_ms=500.0, min_stable_runs=1)
    result = asyncio.run(performance.analyze_performance_capacity(2, body, db, _User()))
    assert result["max_stable_load"] == 10
    assert result["stable_run_count"] == 1
    assert result["observed_run_count"] == 1


def test_capacity_analyze_reports_missing_runs():
    run = _run(10, status="success", options_snapshot={"vus": 10}, summary={})
    db = _GapDB(execute_queue=[_ListResult([run])])
    body = PerformanceCapacityAnalyzeRequest(run_ids=[10, 99])
    err = _http_error(performance.analyze_performance_capacity(2, body, db, _User()), 404)
    assert "99" in err.detail


def test_list_performance_run_metrics_404():
    err = _http_error(performance.list_performance_run_metrics(999, 2000, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


def test_stop_performance_run_404():
    err = _http_error(performance.stop_performance_run(999, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


def test_stop_ignores_unparsable_shard_ids_and_cancels_pending_run(monkeypatch):
    run = _run(50, status=PerformanceRunStatus.pending.value, summary={"shard_ids": ["abc"]})
    db = _GapDB({"PerformanceRun": {50: run}})
    recorder = _CancelRecorder()
    monkeypatch.setattr(performance, "request_cancel", recorder)
    result = asyncio.run(performance.stop_performance_run(50, db, _User()))
    assert recorder.calls == [50]
    assert result.status == PerformanceRunStatus.cancelled.value
    assert run.finished_at is not None
    assert db.commits == 1


def test_stop_reports_503_when_shard_signal_fails(monkeypatch):
    parent = _run(50, status=PerformanceRunStatus.running.value, summary={"shard_ids": [51, 52]})
    shard_running = _run(51, status=PerformanceRunStatus.running.value)
    shard_pending = _run(52, status=PerformanceRunStatus.pending.value)
    db = _GapDB({"PerformanceRun": {50: parent, 51: shard_running, 52: shard_pending}})
    recorder = _CancelRecorder(error=RuntimeError("control unavailable"))
    monkeypatch.setattr(performance, "request_cancel", recorder)
    err = _http_error(performance.stop_performance_run(50, db, _User()), 503)
    assert "无法发送停止信号" in err.detail
    assert db.commits == 0


def test_stop_cancels_parent_when_all_shards_pending(monkeypatch):
    parent = _run(50, status=PerformanceRunStatus.pending.value, summary={"shard_ids": [51, 52]})
    shard_one = _run(51, status=PerformanceRunStatus.pending.value)
    shard_two = _run(52, status=PerformanceRunStatus.pending.value)
    db = _GapDB({"PerformanceRun": {50: parent, 51: shard_one, 52: shard_two}})
    recorder = _CancelRecorder()
    monkeypatch.setattr(performance, "request_cancel", recorder)
    result = asyncio.run(performance.stop_performance_run(50, db, _User()))
    assert recorder.calls == []
    assert result.status == PerformanceRunStatus.cancelled.value
    assert parent.finished_at is not None
    assert shard_one.status == PerformanceRunStatus.cancelled.value
    assert shard_two.status == PerformanceRunStatus.cancelled.value
    assert db.commits == 1


def test_stop_reports_503_when_single_signal_fails(monkeypatch):
    run = _run(50, status=PerformanceRunStatus.running.value)
    db = _GapDB({"PerformanceRun": {50: run}})
    recorder = _CancelRecorder(error=RuntimeError("boom"))
    monkeypatch.setattr(performance, "request_cancel", recorder)
    err = _http_error(performance.stop_performance_run(50, db, _User()), 503)
    assert "无法发送停止信号" in err.detail
    assert db.commits == 0


def test_run_gate_404():
    err = _http_error(performance.get_performance_run_gate(999, False, False, _GapDB(), _User()), 404)
    assert err.detail


def test_baseline_comparison_404_when_run_missing():
    err = _http_error(performance.get_performance_baseline_comparison(999, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


def test_baseline_comparison_409_when_baseline_not_set():
    run = _run(10)
    item = _perf_test(baseline_run_id=None)
    db = _GapDB({"PerformanceRun": {10: run}, "PerformanceTest": {3: item}})
    err = _http_error(performance.get_performance_baseline_comparison(10, db, _User()), 409)
    assert err.detail


def test_baseline_comparison_409_when_baseline_run_missing():
    run = _run(10)
    item = _perf_test(baseline_run_id=55)
    db = _GapDB({"PerformanceRun": {10: run}, "PerformanceTest": {3: item}})
    err = _http_error(performance.get_performance_baseline_comparison(10, db, _User()), 409)
    assert err.detail


def test_export_run_json_404():
    err = _http_error(performance.export_performance_run_json(999, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


def test_export_run_csv_404():
    err = _http_error(performance.export_performance_run_csv(999, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


def test_get_run_raw_result_404():
    err = _http_error(performance.get_performance_run_raw_result(999, _GapDB(), _User()), 404)
    assert "不存在" in err.detail


def test_update_performance_test_wraps_invalid_grpc_options():
    item = _perf_test(executor="grpc", script_object_name="scripts/greeter.proto")
    db = _GapDB({"PerformanceTest": {3: item}})
    body = PerformanceTestUpdate(
        default_options={
            "target": "api.example.test:50051",
            "service": "Greeter",
            "method": "SayHello",
            "request": {"name": "ATP"},
        }
    )

    err = _http_error(performance.update_performance_test(3, body, db, _User()), 400)

    assert "include its package" in err.detail


def test_resolve_performance_node_rejects_unsupported_executor():
    node = _node(17, capabilities={"executors": ["locust"]})
    db = _GapDB({"PerformanceNode": {17: node}})

    err = _http_error(performance._resolve_performance_node(db, 17, {}, "k6"), 409)

    assert "不支持" in err.detail
