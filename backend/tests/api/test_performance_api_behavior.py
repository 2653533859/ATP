import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _noop_async(*_args, **_kwargs):
    return None


def _noop_dependency(*_args, **_kwargs):
    return None


sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(
    assert_project_access=_noop_async,
    get_current_user=lambda: None,
    require_project_access=lambda *_a, **_kw: _noop_dependency,
)


class _DelayRecorder:
    def __init__(self):
        self.calls: list[int] = []

    def delay(self, run_id: int):
        self.calls.append(run_id)


_delay_recorder = _DelayRecorder()
sys.modules["app.worker.tasks_performance"] = types.SimpleNamespace(
    run_performance_test=_delay_recorder,
)

from app.api.v1 import performance
from app.models.bootstrap import load_all_models
from app.models.performance import PerformanceRun, PerformanceRunStatus, PerformanceTest
from app.schemas.performance import PerformanceRunTrigger, PerformanceTestCreate

load_all_models()

_uploaded_objects: list[tuple[str, bytes, str]] = []
performance.minio_client.ensure_bucket = lambda: None
performance.minio_client.upload_bytes = (
    lambda object_name, data, content_type="application/octet-stream": _uploaded_objects.append(
        (object_name, data, content_type)
    )
    or object_name
)
performance.minio_client.presigned_url = lambda object_name, expires_seconds=3600: f"http://minio.test/{object_name}?exp={expires_seconds}"


class _User:
    id = 7
    username = "alice"


class _FakeDB:
    def __init__(self, objects=None, fail_commit: bool = False):
        self.objects = objects or {}
        self.fail_commit = fail_commit
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def get(self, model, pk):
        return self.objects.get(model.__name__, {}).get(pk)

    def add(self, obj):
        obj.id = 100 + len(self.added)
        now = datetime(2026, 5, 29, tzinfo=timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self.added.append(obj)

    async def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("duplicate")

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, obj):
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime(2026, 5, 29, tzinfo=timezone.utc)
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = datetime(2026, 5, 29, tzinfo=timezone.utc)


def _performance_test(test_id: int = 3):
    now = datetime(2026, 5, 29, tzinfo=timezone.utc)
    return PerformanceTest(
        id=test_id,
        project_id=2,
        name="smoke",
        description=None,
        executor="k6",
        script_object_name="performance/scripts/smoke.js",
        default_options={"env": {"BASE_URL": "https://example.test"}, "vus": 5},
        creator_id=7,
        created_at=now,
        updated_at=now,
    )


class _Upload:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


def test_create_performance_test_persists_definition():
    db = _FakeDB()
    body = PerformanceTestCreate(
        project_id=2,
        name="homepage",
        script_object_name="performance/scripts/homepage.js",
        default_options={"vus": 3},
    )

    result = asyncio.run(performance.create_performance_test(body=body, db=db, user=_User()))

    assert result.id == 100
    assert result.project_id == 2
    assert result.creator_id == 7
    assert result.executor == "k6"
    assert db.commits == 1
    assert db.added == [result]


def test_upload_performance_script_stores_project_scoped_object():
    _uploaded_objects.clear()
    db = _FakeDB()
    file = _Upload("homepage smoke.js", b"export default function () {}")

    result = asyncio.run(performance.upload_performance_script(project_id=2, file=file, db=db, user=_User()))

    assert result.filename == "homepage-smoke.js"
    assert result.size == len(b"export default function () {}")
    assert result.script_object_name.startswith("performance/scripts/2/")
    assert result.script_object_name.endswith("-homepage-smoke.js")
    assert _uploaded_objects == [
        (result.script_object_name, b"export default function () {}", "application/javascript")
    ]


def test_upload_performance_script_rejects_non_k6_extension():
    db = _FakeDB()
    file = _Upload("payload.txt", b"not js")

    try:
        asyncio.run(performance.upload_performance_script(project_id=2, file=file, db=db, user=_User()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("应拒绝非 js 脚本")


def test_create_performance_test_returns_409_on_duplicate_name():
    db = _FakeDB(fail_commit=True)
    body = PerformanceTestCreate(
        project_id=2,
        name="homepage",
        script_object_name="performance/scripts/homepage.js",
    )

    try:
        asyncio.run(performance.create_performance_test(body=body, db=db, user=_User()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
        assert db.rollbacks == 1
    else:
        raise AssertionError("应返回 409")


def test_trigger_performance_run_merges_options_and_enqueues_task():
    _delay_recorder.calls.clear()
    test = _performance_test()
    db = _FakeDB({"PerformanceTest": {test.id: test}})
    body = PerformanceRunTrigger(
        environment_id=9,
        options={"env": {"TOKEN": "secret"}, "duration": "30s"},
    )

    result = asyncio.run(performance.trigger_performance_run(test_id=test.id, body=body, db=db, user=_User()))

    assert isinstance(result, PerformanceRun)
    assert result.status == PerformanceRunStatus.pending.value
    assert result.project_id == 2
    assert result.environment_id == 9
    assert result.triggered_by == 7
    assert result.options_snapshot == {
        "env": {"BASE_URL": "https://example.test", "TOKEN": "secret"},
        "vus": 5,
        "duration": "30s",
    }
    assert _delay_recorder.calls == [result.id]


def test_trigger_performance_run_rejects_vus_over_limit(monkeypatch):
    monkeypatch.setattr(performance.settings, "PERFORMANCE_MAX_VUS", 10)
    test = _performance_test()
    db = _FakeDB({"PerformanceTest": {test.id: test}})
    body = PerformanceRunTrigger(options={"vus": 11})

    try:
        asyncio.run(performance.trigger_performance_run(test_id=test.id, body=body, db=db, user=_User()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "VUs" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应拒绝超限 VUs")


def test_trigger_performance_run_rejects_duration_over_limit(monkeypatch):
    monkeypatch.setattr(performance.settings, "PERFORMANCE_MAX_DURATION_SECONDS", 60)
    test = _performance_test()
    db = _FakeDB({"PerformanceTest": {test.id: test}})
    body = PerformanceRunTrigger(options={"duration": "2m"})

    try:
        asyncio.run(performance.trigger_performance_run(test_id=test.id, body=body, db=db, user=_User()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "duration" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应拒绝超限 duration")


def test_trigger_performance_run_rejects_target_outside_allowlist(monkeypatch):
    monkeypatch.setattr(performance.settings, "PERFORMANCE_TARGET_ALLOWLIST", "example.test")
    test = _performance_test()
    db = _FakeDB({"PerformanceTest": {test.id: test}})
    body = PerformanceRunTrigger(options={"env": {"TARGET_URL": "https://evil.test/api"}})

    try:
        asyncio.run(performance.trigger_performance_run(test_id=test.id, body=body, db=db, user=_User()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "allowlist" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应拒绝非 allowlist 目标")


def test_trigger_performance_run_allows_allowlisted_subdomain(monkeypatch):
    _delay_recorder.calls.clear()
    monkeypatch.setattr(performance.settings, "PERFORMANCE_TARGET_ALLOWLIST", "example.test")
    test = _performance_test()
    test.default_options = {"env": {"BASE_URL": "https://api.example.test"}, "vus": 1}
    db = _FakeDB({"PerformanceTest": {test.id: test}})

    result = asyncio.run(performance.trigger_performance_run(test_id=test.id, body=PerformanceRunTrigger(), db=db, user=_User()))

    assert result.options_snapshot["env"]["BASE_URL"] == "https://api.example.test"
    assert _delay_recorder.calls == [result.id]


def test_trigger_performance_run_404_when_definition_missing():
    db = _FakeDB({"PerformanceTest": {}})
    body = PerformanceRunTrigger()

    try:
        asyncio.run(performance.trigger_performance_run(test_id=404, body=body, db=db, user=_User()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("应返回 404")


def test_get_performance_run_raw_result_returns_presigned_url():
    now = datetime(2026, 5, 29, tzinfo=timezone.utc)
    run = PerformanceRun(
        id=8,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.success.value,
        options_snapshot={},
        summary={},
        raw_result_object_name="performance/runs/8/summary.json",
        created_at=now,
        updated_at=now,
    )
    db = _FakeDB({"PerformanceRun": {run.id: run}})

    result = asyncio.run(performance.get_performance_run_raw_result(run_id=run.id, db=db, user=_User()))

    assert result.filename == "performance-run-8-summary.json"
    assert result.object_name == "performance/runs/8/summary.json"
    assert result.url == "http://minio.test/performance/runs/8/summary.json?exp=3600"


def test_get_performance_run_raw_result_404_when_missing_object():
    now = datetime(2026, 5, 29, tzinfo=timezone.utc)
    run = PerformanceRun(
        id=9,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.failed.value,
        options_snapshot={},
        summary={},
        created_at=now,
        updated_at=now,
    )
    db = _FakeDB({"PerformanceRun": {run.id: run}})

    try:
        asyncio.run(performance.get_performance_run_raw_result(run_id=run.id, db=db, user=_User()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("应返回 404")
