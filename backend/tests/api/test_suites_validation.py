import asyncio
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_engineer=lambda: None,
    require_admin=_p3c_noop,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)

from app.api.v1 import suites
from app.models.bootstrap import load_all_models
from app.models.project import Project
from app.models.suite import TestSuite
from app.schemas.suite import TestSuiteCreate, TestSuiteUpdate


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _ExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _ScalarResult(self._items)


class _FakeSuiteRun:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.created_at = kwargs.get("created_at")
        self.duration_ms = kwargs.get("duration_ms")
        self.error_message = kwargs.get("error_message")
        self.result_summary = kwargs.get("result_summary", {})
        self.case_run_ids = kwargs.get("case_run_ids", [])
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeDB:
    def __init__(self, *, project=None, suite=None, cases=None, env=None, run=None):
        self.project = project
        self.suite = suite
        self.cases = cases or []
        self.env = env
        self.run = run
        self.added = []
        self.deleted = []

    async def get(self, model, pk):
        if model is Project:
            return self.project if self.project and self.project.id == pk else None
        if model is TestSuite:
            return self.suite if self.suite and self.suite.id == pk else None
        if model.__name__ == "Environment":
            return self.env if self.env and self.env.id == pk else None
        if model.__name__ == "SuiteRun":
            return self.run if self.run and self.run.id == pk else None
        return None

    async def execute(self, _stmt):
        return _ExecuteResult(self.cases)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, TestSuite):
            self.suite = obj

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        if self.suite is not None and self.suite.id is None:
            self.suite.id = 501

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 501
        return None


def _project(project_id: int):
    return types.SimpleNamespace(id=project_id, name=f"Project-{project_id}")


def _case(case_id: int, project_id: int):
    return types.SimpleNamespace(id=case_id, module=types.SimpleNamespace(project_id=project_id))


def test_create_suite_persists_valid_ordered_case_ids():
    load_all_models()
    db = _FakeDB(
        project=_project(1),
        cases=[_case(12, 1), _case(11, 1)],
    )

    result = asyncio.run(
        suites.create_suite(
            body=TestSuiteCreate(
                name="Smoke Suite",
                project_id=1,
                case_ids=[
                    {"case_id": 12, "sort": 0},
                    {"case_id": 11, "sort": 1},
                ],
            ),
            db=db,
            current_user=types.SimpleNamespace(id=7),
        )
    )

    assert result.case_ids == [{"case_id": 12, "sort": 0}, {"case_id": 11, "sort": 1}]
    assert db.suite.case_ids == [{"case_id": 12, "sort": 0}, {"case_id": 11, "sort": 1}]


def test_create_suite_persists_execution_config():
    load_all_models()
    db = _FakeDB(
        project=_project(1),
        cases=[_case(12, 1), _case(11, 1)],
    )

    result = asyncio.run(
        suites.create_suite(
            body=TestSuiteCreate(
                name="Parallel Suite",
                project_id=1,
                case_ids=[
                    {"case_id": 12, "sort": 0},
                    {"case_id": 11, "sort": 1},
                ],
                config={
                    "execution_mode": "parallel",
                    "max_workers": 3,
                    "fail_strategy": "require-minimum-pass-rate",
                    "min_pass_rate": 0.75,
                },
            ),
            db=db,
            current_user=types.SimpleNamespace(id=7),
        )
    )

    assert result.config["execution_mode"] == "parallel"
    assert result.config["max_workers"] == 3
    assert result.config["fail_strategy"] == "require-minimum-pass-rate"
    assert result.config["min_pass_rate"] == 0.75


def test_create_suite_rejects_missing_case_id():
    load_all_models()
    db = _FakeDB(
        project=_project(1),
        cases=[_case(11, 1)],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.create_suite(
                body=TestSuiteCreate(
                    name="Broken Suite",
                    project_id=1,
                    case_ids=[
                        {"case_id": 11, "sort": 0},
                        {"case_id": 99, "sort": 1},
                    ],
                ),
                db=db,
                current_user=types.SimpleNamespace(id=7),
            )
        )

    assert exc.value.status_code == 400


def test_create_suite_rejects_duplicate_case_ids():
    load_all_models()
    db = _FakeDB(
        project=_project(1),
        cases=[_case(11, 1)],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.create_suite(
                body=TestSuiteCreate(
                    name="Duplicate Suite",
                    project_id=1,
                    case_ids=[
                        {"case_id": 11, "sort": 0},
                        {"case_id": 11, "sort": 1},
                    ],
                ),
                db=db,
                current_user=types.SimpleNamespace(id=7),
            )
        )

    assert exc.value.status_code == 400


def test_update_suite_rejects_case_from_another_project():
    load_all_models()
    db = _FakeDB(
        suite=TestSuite(id=33, name="Smoke", project_id=1, creator_id=7),
        cases=[_case(22, 2)],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.update_suite(
                suite_id=33,
                body=TestSuiteUpdate(case_ids=[{"case_id": 22, "sort": 0}]),
                db=db,
                user=types.SimpleNamespace(id=7),
            )
        )

    assert exc.value.status_code == 400


def test_update_suite_updates_execution_config():
    load_all_models()
    suite = TestSuite(
        id=33,
        name="Smoke",
        project_id=1,
        creator_id=7,
        config={"execution_mode": "sequential", "fail_strategy": "continue"},
    )
    db = _FakeDB(suite=suite, cases=[])

    result = asyncio.run(
        suites.update_suite(
            suite_id=33,
            body=TestSuiteUpdate(
                config={
                    "execution_mode": "parallel",
                    "max_workers": 4,
                    "fail_strategy": "fast-fail",
                    "min_pass_rate": 0.5,
                }
            ),
            db=db,
            user=types.SimpleNamespace(id=7),
        )
    )


def test_trigger_suite_run_persists_and_dispatches_trace_id(monkeypatch):
    load_all_models()
    delayed = {}
    suite = _FakeSuiteRun(
        id=33,
        case_ids=[{"case_id": 12, "sort": 0}],
        creator_id=7,
        project_id=1,
    )
    db = _FakeDB(suite=suite, cases=[])

    monkeypatch.setattr(suites, "SuiteRun", _FakeSuiteRun)
    monkeypatch.setattr(suites, "get_trace_id", lambda: "trace-suite-33")
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks",
        types.SimpleNamespace(
            run_test_suite=types.SimpleNamespace(
                delay=lambda run_id, extra_vars, trace_id: delayed.update(
                    run_id=run_id,
                    extra_vars=extra_vars,
                    trace_id=trace_id,
                )
            )
        ),
    )

    result = asyncio.run(
        suites.trigger_suite_run(
            suite_id=33,
            body=suites.SuiteRunTrigger(extra_vars={"branch": "main"}),
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    assert result.trace_id == "trace-suite-33"
    assert result.id == 501
    assert db.added[0].trace_id == "trace-suite-33"
    assert delayed == {"run_id": 501, "extra_vars": {"branch": "main"}, "trace_id": "trace-suite-33"}


# ── Q14-02 路由清扫：CRUD 阶梯 / 环境合并 / 执行记录 ────────


def _wire_dispatch(monkeypatch):
    """替换 SuiteRun ORM 与 Celery delay，返回 delayed 记录。"""
    delayed = {}
    monkeypatch.setattr(suites, "SuiteRun", _FakeSuiteRun)
    monkeypatch.setattr(suites, "get_trace_id", lambda: None)
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks",
        types.SimpleNamespace(
            run_test_suite=types.SimpleNamespace(
                delay=lambda run_id, extra_vars, trace_id: delayed.update(
                    run_id=run_id, extra_vars=extra_vars, trace_id=trace_id
                )
            )
        ),
    )
    return delayed


def test_create_suite_project_404():
    load_all_models()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.create_suite(
                body=TestSuiteCreate(name="孤儿套件", project_id=99, case_ids=[]),
                db=_FakeDB(),
                current_user=types.SimpleNamespace(id=7),
            )
        )
    assert exc.value.status_code == 404


def test_create_suite_empty_case_ids_skips_validation_query():
    load_all_models()
    db = _FakeDB(project=_project(1), cases=[])

    result = asyncio.run(
        suites.create_suite(
            body=TestSuiteCreate(name="空套件", project_id=1, case_ids=[]),
            db=db,
            current_user=types.SimpleNamespace(id=7),
        )
    )
    assert result.case_ids == []


def test_list_suites_returns_rows():
    load_all_models()
    row = TestSuite(id=1, name="s", project_id=5, creator_id=7)
    db = _FakeDB(cases=[row])  # execute 复用 cases 作为返回行

    assert asyncio.run(suites.list_suites(project_id=5, db=db, user=types.SimpleNamespace(id=7))) == [row]
    assert asyncio.run(suites.list_suites(project_id=None, db=db, user=types.SimpleNamespace(id=7))) == [row]


def test_get_suite_404_and_happy():
    load_all_models()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(suites.get_suite(suite_id=404, db=_FakeDB(), user=types.SimpleNamespace(id=7)))
    assert exc.value.status_code == 404

    suite = TestSuite(id=33, name="s", project_id=1, creator_id=7)
    assert (
        asyncio.run(suites.get_suite(suite_id=33, db=_FakeDB(suite=suite), user=types.SimpleNamespace(id=7))) is suite
    )


def test_update_and_delete_suite_404():
    load_all_models()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.update_suite(suite_id=404, body=TestSuiteUpdate(), db=_FakeDB(), user=types.SimpleNamespace(id=7))
        )
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        asyncio.run(suites.delete_suite(suite_id=404, db=_FakeDB(), user=types.SimpleNamespace(id=7)))
    assert exc.value.status_code == 404


def test_delete_suite_removes_row():
    load_all_models()
    suite = TestSuite(id=33, name="s", project_id=1, creator_id=7)
    db = _FakeDB(suite=suite)

    asyncio.run(suites.delete_suite(suite_id=33, db=db, user=types.SimpleNamespace(id=7)))
    assert db.deleted == [suite]


def test_trigger_suite_run_404_and_empty_cases(monkeypatch):
    load_all_models()
    _wire_dispatch(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.trigger_suite_run(
                suite_id=404, body=suites.SuiteRunTrigger(), db=_FakeDB(), current_user=types.SimpleNamespace(id=9)
            )
        )
    assert exc.value.status_code == 404

    empty = _FakeSuiteRun(id=33, case_ids=[], project_id=1)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.trigger_suite_run(
                suite_id=33,
                body=suites.SuiteRunTrigger(),
                db=_FakeDB(suite=empty),
                current_user=types.SimpleNamespace(id=9),
            )
        )
    assert exc.value.status_code == 400 and "没有用例" in exc.value.detail


def test_trigger_suite_run_env_404(monkeypatch):
    load_all_models()
    _wire_dispatch(monkeypatch)
    suite = _FakeSuiteRun(id=33, case_ids=[{"case_id": 1, "sort": 0}], project_id=1)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.trigger_suite_run(
                suite_id=33,
                body=suites.SuiteRunTrigger(env_id=77),
                db=_FakeDB(suite=suite),
                current_user=types.SimpleNamespace(id=9),
            )
        )
    assert exc.value.status_code == 404 and "环境不存在" in exc.value.detail


def test_trigger_suite_run_merges_env_vars_with_extra_priority(monkeypatch):
    load_all_models()
    delayed = _wire_dispatch(monkeypatch)
    monkeypatch.setattr(suites, "decrypt_env_vars", lambda rows: {"HOST": "env-host", "TOKEN": "env-token"})
    suite = _FakeSuiteRun(id=33, case_ids=[{"case_id": 1, "sort": 0}], project_id=1)
    env = types.SimpleNamespace(id=77, name="staging", project_id=1)
    db = _FakeDB(suite=suite, env=env, cases=[])

    result = asyncio.run(
        suites.trigger_suite_run(
            suite_id=33,
            body=suites.SuiteRunTrigger(env_id=77, extra_vars={"HOST": "override-host"}),
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    assert result.environment == "staging"
    assert delayed["extra_vars"] == {"HOST": "override-host", "TOKEN": "env-token"}  # extra 覆盖环境变量


def test_trigger_suite_run_rejects_environment_from_another_project(monkeypatch):
    load_all_models()
    _wire_dispatch(monkeypatch)
    suite = _FakeSuiteRun(id=33, case_ids=[{"case_id": 1, "sort": 0}], project_id=1)
    env = types.SimpleNamespace(id=77, name="foreign", project_id=2)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.trigger_suite_run(
                suite_id=33,
                body=suites.SuiteRunTrigger(env_id=77),
                db=_FakeDB(suite=suite, env=env),
                current_user=types.SimpleNamespace(id=9),
            )
        )

    assert exc.value.status_code == 400 and "不属于套件所在项目" in exc.value.detail


def test_list_and_get_suite_runs():
    load_all_models()
    row = _FakeSuiteRun(id=88, suite_id=33)
    suite = _FakeSuiteRun(id=33, project_id=1)
    db = _FakeDB(cases=[row], run=row, suite=suite)

    assert asyncio.run(suites.list_suite_runs(suite_id=33, db=db, _=None)) == [row]
    assert asyncio.run(suites.list_suite_runs(suite_id=None, db=db, _=None)) == [row]
    assert asyncio.run(suites.get_suite_run(run_id=88, db=db, _=None)) is row

    with pytest.raises(HTTPException) as exc:
        asyncio.run(suites.get_suite_run(run_id=404, db=_FakeDB(), _=None))
    assert exc.value.status_code == 404
