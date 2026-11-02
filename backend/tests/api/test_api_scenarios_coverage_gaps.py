"""补齐 api_scenarios.py 的未覆盖分支：本地 JSON 存储读写、场景 CRUD、DAG/数据流校验与调试会话端点。

基线：test_api_scenario.py + test_api_contracts_routes.py 合并测量 55.86%（missing 92 / partial 36）。
本文件全部使用 fake DB、tmp 目录与 monkeypatch，不依赖真实数据库/Redis/MinIO，可独立运行。
"""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import api_scenarios
from app.models.bootstrap import load_all_models
from app.models.user import UserRole
from app.models.user_project import ProjectRole
from app.services.workflow_dag_engine import WorkflowDagError
from app.services.workflow_dataflow_validator import WorkflowDataflowError
from app.services.workflow_debugger import WorkflowDebuggerError

load_all_models()


class _Result:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows if rows is not None else []
        self._scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    """极简异步会话：execute 走预置队列，其余写操作只记录调用。"""

    def __init__(self, results=None):
        self.results = list(results or [])
        self.execute_calls = 0

    async def execute(self, _statement):
        self.execute_calls += 1
        return self.results.pop(0) if self.results else _Result()


def _user(role=UserRole.engineer, user_id=1):
    return SimpleNamespace(id=user_id, username="amy", role=role)


def _scenario(sid=1, *, project_id=1, module_id=None, name="场景A", code=None, updated="2026-11-01T00:00:00+00:00"):
    return {
        "id": sid,
        "scenario_code": code or f"SCN-{sid:04d}",
        "project_id": project_id,
        "module_id": module_id,
        "name": name,
        "updated_at": updated,
    }


def _access_recorder(monkeypatch):
    calls = []

    async def fake_access(_db, _user_obj, project_id, role):
        calls.append((project_id, role))

    monkeypatch.setattr(api_scenarios, "assert_project_access", fake_access)
    return calls


@pytest.fixture
def store_root(tmp_path, monkeypatch):
    root = tmp_path / "localdata"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(type(api_scenarios.settings), "LOCAL_DATA_PATH", property(lambda _self: root))
    return root


# ── 本地 JSON 存储 ────────────────────────────────────────────


def test_store_path_creates_directory_and_roundtrips(store_root):
    path = api_scenarios._store_path()
    assert path == store_root / "api_scenarios.json"
    assert store_root.is_dir()

    assert api_scenarios._load_all() == []

    items = [{"id": 1, "project_id": 1, "name": "场景"}]
    api_scenarios._save_all(items)
    assert api_scenarios._load_all() == items
    assert not (store_root / "api_scenarios.tmp").exists()


def test_load_all_handles_non_list_and_corrupted_backup(store_root):
    file = store_root / "api_scenarios.json"
    file.write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert api_scenarios._load_all() == []

    file.write_text("{broken json", encoding="utf-8")
    assert api_scenarios._load_all() == []
    assert (store_root / "api_scenarios.corrupted").exists()


def test_load_all_skips_backup_for_empty_corrupted_file(store_root):
    file = store_root / "api_scenarios.json"
    file.write_text("", encoding="utf-8")
    assert api_scenarios._load_all() == []
    assert not (store_root / "api_scenarios.corrupted").exists()
    assert file.exists()


def test_load_all_swallows_backup_rename_failure(store_root):
    file = store_root / "api_scenarios.json"
    file.write_text("{broken json", encoding="utf-8")
    (store_root / "api_scenarios.corrupted").mkdir()
    assert api_scenarios._load_all() == []
    assert file.exists()


def test_read_snapshot_missing_non_list_and_unreadable(store_root):
    assert api_scenarios.read_project_scenarios_snapshot(7) == []

    file = store_root / "api_scenarios.json"
    file.write_text(json.dumps({"a": 1}), encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        api_scenarios.read_project_scenarios_snapshot(7)
    assert exc.value.status_code == 503

    file.unlink()
    file.mkdir()
    with pytest.raises(HTTPException) as os_exc:
        api_scenarios.read_project_scenarios_snapshot(7)
    assert os_exc.value.status_code == 503


def test_read_snapshot_filters_to_project_dicts(store_root):
    file = store_root / "api_scenarios.json"
    raw = [
        {"id": 1, "project_id": 7},
        {"id": 2, "project_id": 8},
        "not-a-dict",
        {"id": 3, "project_id": 7, "steps": []},
    ]
    file.write_text(json.dumps(raw), encoding="utf-8")
    snapshot = api_scenarios.read_project_scenarios_snapshot(7)
    assert [item["id"] for item in snapshot] == [1, 3]


# ── sourceCase 绑定 ──────────────────────────────────────────


def test_bind_source_cases_returns_input_without_source_ids():
    steps = [{"url": "/a"}, {"sourceCaseId": True}, {"sourceCaseId": "11"}, {"sourceCaseId": 1.5}]
    db = _FakeDB()
    assert asyncio.run(api_scenarios._bind_source_cases(db, 1, steps)) is steps
    assert db.execute_calls == 0


def test_bind_source_cases_drops_fingerprint_for_missing_source():
    db = _FakeDB(results=[_Result(rows=[])])
    step = {"sourceCaseId": 5, "sourceCaseFingerprint": "f" * 64, "url": "/a"}
    bound = asyncio.run(api_scenarios._bind_source_cases(db, 1, [step]))
    assert "sourceCaseFingerprint" not in bound[0]
    assert step["sourceCaseFingerprint"] == "f" * 64
    assert db.execute_calls == 1


def test_bind_source_cases_preserve_or_recompute_fingerprint(monkeypatch):
    calls = []

    def fake_fingerprint(case):
        calls.append(case.id)
        return "a" * 64

    monkeypatch.setattr(api_scenarios, "case_request_fingerprint", fake_fingerprint)
    source = SimpleNamespace(id=11, config={})
    db = _FakeDB(results=[_Result(rows=[source])] * 4)

    valid = "b" * 64
    kept = asyncio.run(
        api_scenarios._bind_source_cases(
            db, 7, [{"sourceCaseId": 11, "sourceCaseFingerprint": valid}], preserve_existing=True
        )
    )
    assert kept[0]["sourceCaseFingerprint"] == valid and calls == []

    invalid = asyncio.run(
        api_scenarios._bind_source_cases(
            db, 7, [{"sourceCaseId": 11, "sourceCaseFingerprint": "XYZ"}], preserve_existing=True
        )
    )
    assert invalid[0]["sourceCaseFingerprint"] == "a" * 64 and calls == [11]

    weird = asyncio.run(
        api_scenarios._bind_source_cases(
            db, 7, [{"sourceCaseId": 11, "sourceCaseFingerprint": 123}], preserve_existing=True
        )
    )
    assert weird[0]["sourceCaseFingerprint"] == "a" * 64 and calls == [11, 11]

    recomputed = asyncio.run(
        api_scenarios._bind_source_cases(db, 7, [{"sourceCaseId": 11, "sourceCaseFingerprint": valid}])
    )
    assert recomputed[0]["sourceCaseFingerprint"] == "a" * 64 and calls == [11, 11, 11]


# ── 场景列表/详情/创建 ───────────────────────────────────────


def test_list_api_scenarios_admin_returns_all_sorted(monkeypatch):
    rows = [
        _scenario(1, updated="2026-11-02T10:00:00+00:00"),
        _scenario(2, updated="2026-11-01T10:00:00+00:00"),
        _scenario(3, updated=None),
    ]
    monkeypatch.setattr(api_scenarios, "_load_all", lambda: rows)

    result = asyncio.run(
        api_scenarios.list_api_scenarios(
            project_id=None, module_id=None, keyword=None, current_user=_user(role=UserRole.admin), db=_FakeDB()
        )
    )

    assert [item["id"] for item in result] == [1, 2, 3]


def test_list_api_scenarios_requires_project_for_non_admin():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            api_scenarios.list_api_scenarios(
                project_id=None, module_id=None, keyword=None, current_user=_user(), db=_FakeDB()
            )
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "project_id is required"


def test_list_api_scenarios_filters_project_module_and_keyword(monkeypatch):
    calls = _access_recorder(monkeypatch)
    rows = [
        _scenario(1, project_id=1, module_id=5, name="订单创建", code="SCN-0001", updated="2026-11-02T10:00:00+00:00"),
        _scenario(2, project_id=2, module_id=6, name="支付回归", code="SCN-0002", updated="2026-11-01T10:00:00+00:00"),
    ]
    monkeypatch.setattr(api_scenarios, "_load_all", lambda: rows)
    db = _FakeDB()
    admin = _user(role=UserRole.admin)

    by_project = asyncio.run(
        api_scenarios.list_api_scenarios(project_id=1, module_id=None, keyword=None, current_user=_user(), db=db)
    )
    assert [item["id"] for item in by_project] == [1]
    assert calls == [(1, ProjectRole.viewer)]

    by_module = asyncio.run(
        api_scenarios.list_api_scenarios(project_id=1, module_id=6, keyword=None, current_user=admin, db=db)
    )
    assert by_module == []

    by_name = asyncio.run(
        api_scenarios.list_api_scenarios(project_id=None, module_id=None, keyword="订单", current_user=admin, db=db)
    )
    assert [item["id"] for item in by_name] == [1]

    by_code = asyncio.run(
        api_scenarios.list_api_scenarios(project_id=None, module_id=None, keyword="scn-0002", current_user=admin, db=db)
    )
    assert [item["id"] for item in by_code] == [2]

    blank = asyncio.run(
        api_scenarios.list_api_scenarios(project_id=None, module_id=None, keyword="   ", current_user=admin, db=db)
    )
    assert [item["id"] for item in blank] == [1, 2]

    empty = asyncio.run(
        api_scenarios.list_api_scenarios(project_id=None, module_id=None, keyword="", current_user=admin, db=db)
    )
    assert [item["id"] for item in empty] == [1, 2]


def test_get_api_scenario_access_and_404(monkeypatch):
    calls = _access_recorder(monkeypatch)
    rows = [_scenario(1, project_id=5), {"id": 2, "project_id": None, "name": "无边项目"}]
    monkeypatch.setattr(api_scenarios, "_load_all", lambda: rows)

    found = asyncio.run(api_scenarios.get_api_scenario(scenario_id=1, current_user=_user(), db=_FakeDB()))
    assert found["id"] == 1 and calls == [(5, ProjectRole.viewer)]

    orphan = asyncio.run(api_scenarios.get_api_scenario(scenario_id=2, current_user=_user(), db=_FakeDB()))
    assert orphan["id"] == 2 and calls == [(5, ProjectRole.viewer)]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(api_scenarios.get_api_scenario(scenario_id=99, current_user=_user(), db=_FakeDB()))
    assert exc.value.status_code == 404


def test_create_api_scenario_binds_steps_and_persists(store_root, monkeypatch):
    calls = _access_recorder(monkeypatch)
    db = _FakeDB(results=[_Result(rows=[])])
    body = api_scenarios.ApiScenarioSaveIn(
        project_id=1,
        module_id=5,
        name="  订单场景  ",
        description="  说明  ",
        env_id=3,
        steps=[{"sourceCaseId": 99, "url": "/a"}, {"url": "/b"}],
    )

    record = asyncio.run(api_scenarios.create_api_scenario(body=body, current_user=_user(), db=db))

    assert record["id"] == 1 and record["scenario_code"] == "SCN-0001"
    assert record["name"] == "订单场景" and record["description"] == "说明"
    assert record["step_count"] == 2 and record["env_id"] == 3 and record["module_id"] == 5
    assert record["last_run_status"] is None and record["last_run_at"] is None
    assert all("sourceCaseFingerprint" not in step for step in record["steps"])
    assert api_scenarios._load_all() == [record]
    assert calls == [(1, ProjectRole.editor)]

    second = asyncio.run(
        api_scenarios.create_api_scenario(
            body=api_scenarios.ApiScenarioSaveIn(project_id=1, name="第二个场景", steps=[]),
            current_user=_user(),
            db=db,
        )
    )
    assert second["id"] == 2 and second["scenario_code"] == "SCN-0002"
    assert db.execute_calls == 1


# ── 场景更新/运行记录/删除 ───────────────────────────────────


def test_update_api_scenario_cross_project_and_404(store_root, monkeypatch):
    calls = _access_recorder(monkeypatch)
    api_scenarios._save_all(
        [
            _scenario(1, project_id=2, name="旧名", code="SCN-0001"),
            _scenario(2, project_id=1, name="另一个", code="SCN-0002"),
        ]
    )
    db = _FakeDB()

    # 命中场景与 body 同项目：只校验一次 body 项目
    updated = asyncio.run(
        api_scenarios.update_api_scenario(
            scenario_id=2,
            body=api_scenarios.ApiScenarioSaveIn(project_id=1, name="新名", steps=[]),
            current_user=_user(),
            db=db,
        )
    )
    assert updated["name"] == "新名" and updated["step_count"] == 0
    assert updated["project_id"] == 1 and updated["module_id"] is None
    assert calls == [(1, ProjectRole.editor)]

    # 跨项目迁移：先校验 body 项目，再校验旧项目
    migrated = asyncio.run(
        api_scenarios.update_api_scenario(
            scenario_id=1,
            body=api_scenarios.ApiScenarioSaveIn(project_id=1, name="  迁移  ", steps=[]),
            current_user=_user(),
            db=db,
        )
    )
    assert migrated["project_id"] == 1 and migrated["name"] == "迁移"
    assert calls == [(1, ProjectRole.editor), (1, ProjectRole.editor), (2, ProjectRole.editor)]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            api_scenarios.update_api_scenario(
                scenario_id=99,
                body=api_scenarios.ApiScenarioSaveIn(project_id=1, name="不存在", steps=[]),
                current_user=_user(),
                db=db,
            )
        )
    assert exc.value.status_code == 404
    assert calls[-1] == (1, ProjectRole.editor)


def test_record_api_scenario_run_updates_and_404(store_root, monkeypatch):
    calls = _access_recorder(monkeypatch)
    api_scenarios._save_all([_scenario(1, project_id=3, name="A"), _scenario(2, project_id=None, name="无边")])

    updated = asyncio.run(
        api_scenarios.record_api_scenario_run(
            scenario_id=1,
            body=api_scenarios.ApiScenarioRunRecordIn(status="failed", duration_ms=88),
            current_user=_user(),
            db=_FakeDB(),
        )
    )
    assert updated["last_run_status"] == "failed"
    assert updated["last_run_duration_ms"] == 88
    assert updated["last_run_at"] is not None
    assert calls == [(3, ProjectRole.viewer)]

    orphan = asyncio.run(
        api_scenarios.record_api_scenario_run(
            scenario_id=2,
            body=api_scenarios.ApiScenarioRunRecordIn(),
            current_user=_user(),
            db=_FakeDB(),
        )
    )
    assert orphan["last_run_status"] == "passed" and orphan["last_run_duration_ms"] == 0
    assert calls == [(3, ProjectRole.viewer)]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            api_scenarios.record_api_scenario_run(
                scenario_id=9,
                body=api_scenarios.ApiScenarioRunRecordIn(),
                current_user=_user(),
                db=_FakeDB(),
            )
        )
    assert exc.value.status_code == 404


def test_delete_api_scenario_removes_and_checks_access(store_root, monkeypatch):
    calls = _access_recorder(monkeypatch)
    api_scenarios._save_all([_scenario(1, project_id=5), _scenario(2, project_id=None)])

    assert asyncio.run(api_scenarios.delete_api_scenario(scenario_id=1, current_user=_user(), db=_FakeDB())) is None
    assert calls == [(5, ProjectRole.editor)]
    assert [item["id"] for item in api_scenarios._load_all()] == [2]

    assert asyncio.run(api_scenarios.delete_api_scenario(scenario_id=2, current_user=_user(), db=_FakeDB())) is None
    assert calls == [(5, ProjectRole.editor)]
    assert api_scenarios._load_all() == []

    with pytest.raises(HTTPException) as exc:
        asyncio.run(api_scenarios.delete_api_scenario(scenario_id=9, current_user=_user(), db=_FakeDB()))
    assert exc.value.status_code == 404


# ── 工作流 DAG / 数据流端点 ──────────────────────────────────


def test_validate_workflow_dag_endpoint_success_and_error(monkeypatch):
    captured = []

    def fake_validate(nodes):
        captured.append(nodes)
        return [{"id": "b"}, {"id": 7}]

    monkeypatch.setattr(api_scenarios, "validate_and_toposort_workflow", fake_validate)
    body = api_scenarios.WorkflowDagValidateIn(nodes=[{"id": "a"}])

    result = asyncio.run(api_scenarios.validate_workflow_dag_endpoint(body=body, _user=_user()))

    assert captured == [[{"id": "a"}]]
    assert result == {
        "valid": True,
        "total_nodes": 2,
        "execution_order": ["b", "7"],
        "sorted_nodes": [{"id": "b"}, {"id": 7}],
    }

    def boom(_nodes):
        raise WorkflowDagError("存在环路依赖")

    monkeypatch.setattr(api_scenarios, "validate_and_toposort_workflow", boom)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api_scenarios.validate_workflow_dag_endpoint(body=body, _user=_user()))
    assert exc.value.status_code == 400 and exc.value.detail == "存在环路依赖"


def test_execute_workflow_dag_endpoint_forwards_and_maps_error(monkeypatch):
    recorded = {}

    async def fake_execute(payload, *, initial_context, failure_strategy):
        recorded["payload"] = payload
        recorded["initial_context"] = initial_context
        recorded["failure_strategy"] = failure_strategy
        return {"status": "completed", "executed": ["a"]}

    monkeypatch.setattr(api_scenarios, "execute_workflow_dag", fake_execute)
    body = api_scenarios.WorkflowDagExecuteIn(
        nodes=[{"id": "a"}], initial_context={"uid": 3}, failure_strategy="continue"
    )

    result = asyncio.run(api_scenarios.execute_workflow_dag_endpoint(body=body, _user=_user()))

    assert result == {"status": "completed", "executed": ["a"]}
    assert recorded == {
        "payload": {"nodes": [{"id": "a"}]},
        "initial_context": {"uid": 3},
        "failure_strategy": "continue",
    }

    async def boom(*_args, **_kwargs):
        raise WorkflowDagError("节点执行失败")

    monkeypatch.setattr(api_scenarios, "execute_workflow_dag", boom)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api_scenarios.execute_workflow_dag_endpoint(body=body, _user=_user()))
    assert exc.value.status_code == 400


def test_validate_workflow_dataflow_endpoint_maps_errors(monkeypatch):
    recorded = {}

    def fake_validate(nodes, *, initial_context, strict):
        recorded["nodes"] = nodes
        recorded["initial_context"] = initial_context
        recorded["strict"] = strict
        return {"valid": True, "issues": []}

    monkeypatch.setattr(api_scenarios, "validate_workflow_dataflow_topology", fake_validate)
    body = api_scenarios.WorkflowDataflowValidateIn(nodes=[{"id": "a"}], initial_context={"uid": 1}, strict=True)

    result = asyncio.run(api_scenarios.validate_workflow_dataflow_endpoint(body=body, _user=_user()))

    assert result == {"valid": True, "issues": []}
    assert recorded == {"nodes": [{"id": "a"}], "initial_context": {"uid": 1}, "strict": True}

    def boom_dataflow(*_args, **_kwargs):
        raise WorkflowDataflowError("未声明变量")

    monkeypatch.setattr(api_scenarios, "validate_workflow_dataflow_topology", boom_dataflow)
    with pytest.raises(HTTPException) as dataflow_exc:
        asyncio.run(api_scenarios.validate_workflow_dataflow_endpoint(body=body, _user=_user()))
    assert dataflow_exc.value.status_code == 400 and dataflow_exc.value.detail == "未声明变量"

    def boom_dag(*_args, **_kwargs):
        raise WorkflowDagError("存在环路依赖")

    monkeypatch.setattr(api_scenarios, "validate_workflow_dataflow_topology", boom_dag)
    with pytest.raises(HTTPException) as dag_exc:
        asyncio.run(api_scenarios.validate_workflow_dataflow_endpoint(body=body, _user=_user()))
    assert dag_exc.value.status_code == 400


# ── 调试会话端点 ──────────────────────────────────────────────


def test_start_workflow_debug_endpoint_success_and_error(monkeypatch):
    recorded = {}

    def fake_create(payload, *, breakpoints, initial_context, watchers):
        recorded["payload"] = payload
        recorded["breakpoints"] = breakpoints
        recorded["initial_context"] = initial_context
        recorded["watchers"] = watchers
        return {"session_id": "s1", "status": "paused"}

    monkeypatch.setattr(api_scenarios, "create_debug_session", fake_create)
    body = api_scenarios.WorkflowDebugStartIn(
        nodes=[{"id": "a"}], breakpoints=["a"], initial_context={"uid": 2}, watchers=["ctx.x"]
    )

    result = asyncio.run(api_scenarios.start_workflow_debug_endpoint(body=body, _user=_user()))

    assert result == {"session_id": "s1", "status": "paused"}
    assert recorded == {
        "payload": {"nodes": [{"id": "a"}]},
        "breakpoints": ["a"],
        "initial_context": {"uid": 2},
        "watchers": ["ctx.x"],
    }

    def boom(*_args, **_kwargs):
        raise WorkflowDagError("存在环路依赖")

    monkeypatch.setattr(api_scenarios, "create_debug_session", boom)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api_scenarios.start_workflow_debug_endpoint(body=body, _user=_user()))
    assert exc.value.status_code == 400


def test_debug_session_step_resume_get_stop(monkeypatch):
    async def fake_step(session_id):
        return {"session_id": session_id, "status": "paused", "cursor": 1}

    monkeypatch.setattr(api_scenarios, "step_debug_session", fake_step)
    stepped = asyncio.run(api_scenarios.step_workflow_debug_endpoint(session_id="s1", _user=_user()))
    assert stepped == {"session_id": "s1", "status": "paused", "cursor": 1}

    async def boom_step(_session_id):
        raise WorkflowDebuggerError("调试会话不存在")

    monkeypatch.setattr(api_scenarios, "step_debug_session", boom_step)
    with pytest.raises(HTTPException) as step_exc:
        asyncio.run(api_scenarios.step_workflow_debug_endpoint(session_id="s1", _user=_user()))
    assert step_exc.value.status_code == 404

    async def fake_resume(session_id):
        return {"session_id": session_id, "status": "completed"}

    monkeypatch.setattr(api_scenarios, "resume_debug_session", fake_resume)
    resumed = asyncio.run(api_scenarios.resume_workflow_debug_endpoint(session_id="s1", _user=_user()))
    assert resumed["status"] == "completed"

    async def boom_resume(_session_id):
        raise WorkflowDebuggerError("调试会话不存在")

    monkeypatch.setattr(api_scenarios, "resume_debug_session", boom_resume)
    with pytest.raises(HTTPException) as resume_exc:
        asyncio.run(api_scenarios.resume_workflow_debug_endpoint(session_id="s1", _user=_user()))
    assert resume_exc.value.status_code == 404

    def fake_get(session_id):
        return {"session_id": session_id, "status": "paused"}

    monkeypatch.setattr(api_scenarios, "get_debug_session", fake_get)
    fetched = asyncio.run(api_scenarios.get_workflow_debug_endpoint(session_id="s1", _user=_user()))
    assert fetched["status"] == "paused"

    def boom_get(_session_id):
        raise WorkflowDebuggerError("调试会话不存在")

    monkeypatch.setattr(api_scenarios, "get_debug_session", boom_get)
    with pytest.raises(HTTPException) as get_exc:
        asyncio.run(api_scenarios.get_workflow_debug_endpoint(session_id="s1", _user=_user()))
    assert get_exc.value.status_code == 404

    monkeypatch.setattr(api_scenarios, "stop_debug_session", lambda _session_id: True)
    assert asyncio.run(api_scenarios.stop_workflow_debug_endpoint(session_id="s1", _user=_user())) is None

    monkeypatch.setattr(api_scenarios, "stop_debug_session", lambda _session_id: False)
    with pytest.raises(HTTPException) as stop_exc:
        asyncio.run(api_scenarios.stop_workflow_debug_endpoint(session_id="s1", _user=_user()))
    assert stop_exc.value.status_code == 404
    assert stop_exc.value.detail == "调试会话不存在或已释放"
