import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.case import CaseType, RunStatus
from app.worker import case_dispatch
from app.worker.dispatch import is_web_lowcode_config


@pytest.mark.parametrize(
    ("cfg", "expected"),
    [
        ({"steps": [{"action": "goto"}]}, True),
        ({"steps": []}, True),
        ({"steps": None}, True),
        ({"script_path": "scripts/test_case.py"}, False),
        ({}, False),
        (None, False),
    ],
)
def test_is_web_lowcode_config(cfg, expected):
    assert is_web_lowcode_config(cfg) is expected


class _FakeDB:
    def __init__(self):
        self.commit_calls = 0

    async def commit(self):
        self.commit_calls += 1


@pytest.mark.parametrize(
    ("case_type", "executor_name"),
    [
        (CaseType.api, "api"),
        (CaseType.graphql, "graphql"),
        (CaseType.websocket, "websocket"),
        (CaseType.grpc, "grpc"),
    ],
)
def test_dispatch_case_routes_protocol_cases(monkeypatch, case_type, executor_name):
    called = []
    db = _FakeDB()
    run = types.SimpleNamespace(status=None, error_message=None)
    case = types.SimpleNamespace(case_type=case_type, config={"steps": [{"name": "请求"}]})

    async def _recorder(_db, _run, _case, _extra_vars):
        called.append(executor_name)

    monkeypatch.setitem(sys.modules, "app.worker.executors.api_executor", types.SimpleNamespace(run_api_case=_recorder))
    monkeypatch.setitem(
        sys.modules, "app.worker.executors.graphql_executor", types.SimpleNamespace(run_graphql_case=_recorder)
    )
    monkeypatch.setitem(
        sys.modules, "app.worker.executors.websocket_executor", types.SimpleNamespace(run_websocket_case=_recorder)
    )
    monkeypatch.setitem(
        sys.modules, "app.worker.executors.grpc_executor", types.SimpleNamespace(run_grpc_case=_recorder)
    )

    asyncio.run(case_dispatch.dispatch_case(db, run, case, {"token": "x"}))

    assert called == [executor_name]
    assert db.commit_calls == 0


@pytest.mark.parametrize("case_type", [CaseType.graphql, CaseType.websocket, CaseType.grpc])
@pytest.mark.parametrize("config", [{}, {"steps": []}, {"steps": None}])
def test_dispatch_case_rejects_protocol_cases_without_steps(case_type, config):
    db = _FakeDB()
    run = types.SimpleNamespace(status=None, error_message=None)
    case = types.SimpleNamespace(case_type=case_type, config=config)

    result = asyncio.run(case_dispatch.dispatch_case(db, run, case, {}))

    assert result is False
    assert run.status == RunStatus.error
    assert run.error_message == "协议用例未配置可执行步骤"
    assert db.commit_calls == 1


@pytest.mark.parametrize(
    ("cfg", "executor_name"),
    [
        ({"steps": [{"action": "goto"}]}, "web_lowcode"),
        ({"script_path": "cases/test_web.py"}, "web_script"),
    ],
)
def test_dispatch_case_routes_web_modes(monkeypatch, cfg, executor_name):
    called = []
    db = _FakeDB()
    run = types.SimpleNamespace(status=None, error_message=None)
    case = types.SimpleNamespace(case_type=CaseType.web, config=cfg)

    async def _web_lowcode(_db, _run, _case, _extra_vars):
        called.append("web_lowcode")

    async def _web_script(_db, _run, _case, _extra_vars):
        called.append("web_script")

    monkeypatch.setitem(
        sys.modules, "app.worker.executors.web_lowcode_executor", types.SimpleNamespace(run_web_lowcode=_web_lowcode)
    )
    monkeypatch.setitem(
        sys.modules, "app.worker.executors.web_executor", types.SimpleNamespace(run_web_case=_web_script)
    )

    asyncio.run(case_dispatch.dispatch_case(db, run, case, {}))

    assert called == [executor_name]


@pytest.mark.parametrize(
    ("cfg", "executor_name"),
    [
        ({"steps": [{"action": "tap"}]}, "android_lowcode"),
        ({"script_path": "cases/test_android.py"}, "android_script"),
    ],
)
def test_dispatch_case_routes_android_modes(monkeypatch, cfg, executor_name):
    called = []
    db = _FakeDB()
    run = types.SimpleNamespace(status=None, error_message=None)
    case = types.SimpleNamespace(case_type=CaseType.android, config=cfg)

    async def _android_lowcode(_db, _run, _case, _extra_vars):
        called.append("android_lowcode")

    async def _android_script(_db, _run, _case, _extra_vars):
        called.append("android_script")

    monkeypatch.setitem(
        sys.modules,
        "app.worker.executors.android_lowcode_executor",
        types.SimpleNamespace(run_android_lowcode=_android_lowcode),
    )
    monkeypatch.setitem(
        sys.modules, "app.worker.executors.android_executor", types.SimpleNamespace(run_android_case=_android_script)
    )

    asyncio.run(case_dispatch.dispatch_case(db, run, case, {}))

    assert called == [executor_name]


def test_dispatch_case_marks_unsupported_case_type_as_error():
    db = _FakeDB()
    run = types.SimpleNamespace(status=None, error_message=None)
    case = types.SimpleNamespace(case_type="desktop", config={})

    asyncio.run(case_dispatch.dispatch_case(db, run, case, {}))

    assert run.status == RunStatus.error
    assert run.error_message == "执行器尚未实现: desktop"
    assert db.commit_calls == 1


def test_tasks_module_uses_shared_dispatch_helper_for_all_case_execution_paths():
    tasks_file = Path(__file__).resolve().parents[2] / "app" / "worker" / "tasks.py"
    content = tasks_file.read_text(encoding="utf-8")

    assert "from app.worker.case_dispatch import dispatch_case" in content
    # 2 原始（case 单跑 + suite 内 dispatch）+ 2 P3.B 参数化执行（fallback 单跑 + child loop）
    assert content.count("await dispatch_case(") == 4
    assert "if case.case_type == CaseType.api:" not in content
