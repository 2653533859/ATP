import asyncio
from datetime import datetime, timezone
import types

from app.models.case import RunStatus
from app.services import suite_orchestrator


class _FakeScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def scalar_one(self):
        return self._values[0]

    def scalar_one_or_none(self):
        return self._values[0] if self._values else None

    def first(self):
        return self._values[0] if self._values else None

    def all(self):
        return list(self._values)


class _FakeSuiteDB:
    def __init__(self, objects=None, execute_results=None):
        self._objects = dict(objects or {})
        self._execute_results = list(execute_results or [])
        self.added = []
        self.commits = 0
        self._next_id = 100

    async def get(self, model, key):
        return self._objects.get((model.__name__, key))

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            self._next_id += 1
            obj.id = self._next_id
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def flush(self):
        return None

    async def refresh(self, _obj):
        return None

    async def execute(self, _stmt, _params=None):
        if self._execute_results:
            return self._execute_results.pop(0)
        if _params is not None:
            return _FakeScalarResult([datetime.now(timezone.utc)])
        return _FakeScalarResult([])


def test_suite_execute_case_run_runs_parameterized_iterations(monkeypatch):
    from app.worker import tasks

    dataset = types.SimpleNamespace(
        id=36,
        rows=[{"marker": "alpha"}, {"marker": "beta"}],
        schema_fields=[],
        validation_policy="soft",
    )
    case = types.SimpleNamespace(
        id=109,
        name="数据集用例",
        case_type="api",
        dataset_id=36,
        dataset_version=None,
        config={"steps": [{"url": "https://example.test?m={{marker}}"}]},
    )
    suite_run = types.SimpleNamespace(
        id=14,
        environment="default",
        triggered_by=1,
        trace_id="trace-14",
        identity_token="suite-ident-14",
        case_run_ids=[],
    )
    db = _FakeSuiteDB(objects={("TestDataset", 36): dataset})

    seen_vars = []

    async def fake_dispatch(_db, child_run, _case, merged_vars):
        seen_vars.append(dict(merged_vars))
        child_run.status = RunStatus.passed

    monkeypatch.setattr(tasks, "_safe_publish_run_event", lambda *_args, **_kwargs: asyncio.sleep(0))
    monkeypatch.setattr(tasks, "_safe_invalidate_stats_cache", lambda *_args, **_kwargs: asyncio.sleep(0))
    monkeypatch.setattr(tasks, "_record_run_outcome", lambda *_args, **_kwargs: None)

    outcome = asyncio.run(
        suite_orchestrator.execute_case_run(
            db,
            suite_run,
            case,
            {"base": "ok"},
            route_to_worker=False,
            dispatch_case_fn=fake_dispatch,
            record_outcome_fn=lambda *_args, **_kwargs: None,
        )
    )

    assert seen_vars == [
        {"base": "ok", "marker": "alpha"},
        {"base": "ok", "marker": "beta"},
    ]
    assert outcome["status"] == "passed"
    child_runs = [
        obj for obj in db.added if obj.__class__.__name__ == "TestRun" and getattr(obj, "parent_run_id", None)
    ]
    assert len(child_runs) == 2


def test_extract_case_run_error_falls_back_to_parameterized_child_run():
    case_run = types.SimpleNamespace(id=50, status=RunStatus.failed, error_message=None)
    db = _FakeSuiteDB(
        execute_results=[
            _FakeScalarResult([]),  # StepResult on parent
            _FakeScalarResult([(51, None)]),  # failed child TestRun
            _FakeScalarResult(["断言失败 [body] 期望 hello-beta"]),  # StepResult on child
        ]
    )

    err = asyncio.run(suite_orchestrator._extract_case_run_error(db, case_run))
    assert err == "断言失败 [body] 期望 hello-beta"
