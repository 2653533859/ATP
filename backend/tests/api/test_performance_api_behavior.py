import asyncio
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

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


_delay_recorder = _DelayRecorder()
sys.modules["app.worker.tasks_performance"] = types.SimpleNamespace(
    run_performance_test=_delay_recorder,
)

from app.api.v1 import performance
from app.models.bootstrap import load_all_models
from app.models.performance import PerformanceMetricSample, PerformanceRun, PerformanceRunStatus, PerformanceTest
from app.models.performance_node import PerformanceNode
from app.schemas.performance import (
    PerformanceBaselineUpdate,
    PerformanceRunOut,
    PerformanceRunTrigger,
    PerformanceScheduleUpdate,
    PerformanceTestCreate,
)
from app.services.performance_options import ENVIRONMENT_SNAPSHOT_KEY
from app.schemas.performance_node import PerformanceNodeCreate, PerformanceNodeUpdate

load_all_models()

_uploaded_objects: list[tuple[str, bytes, str]] = []
performance.minio_client.ensure_bucket = lambda: None
performance.minio_client.upload_bytes = (
    lambda object_name, data, content_type="application/octet-stream": _uploaded_objects.append(
        (object_name, data, content_type)
    )
    or object_name
)
performance.minio_client.presigned_url = (
    lambda object_name, expires_seconds=3600: f"http://minio.test/{object_name}?exp={expires_seconds}"
)


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

    async def flush(self):
        return None

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
        baseline_run_id=None,
        schedule_enabled=False,
        schedule_timezone="Asia/Shanghai",
        schedule_options={},
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


def test_create_performance_test_supports_locust_scripts():
    db = _FakeDB()
    body = PerformanceTestCreate(
        project_id=2,
        name="locust-homepage",
        executor="locust",
        script_object_name="performance/scripts/homepage.py",
        default_options={"users": 4, "run_time": "10s"},
    )

    result = asyncio.run(performance.create_performance_test(body=body, db=db, user=_User()))

    assert result.executor == "locust"
    assert result.script_object_name.endswith(".py")


def test_create_performance_test_supports_grpc_proto_and_validates_options():
    db = _FakeDB()
    body = PerformanceTestCreate(
        project_id=2,
        name="grpc-greeter",
        executor="grpc",
        script_object_name="performance/scripts/greeter.proto",
        default_options={
            "target": "api.example.test:50051",
            "service": "demo.v1.Greeter",
            "method": "SayHello",
            "request": {"name": "ATP"},
            "concurrency": 2,
            "iterations": 4,
        },
    )

    result = asyncio.run(performance.create_performance_test(body=body, db=db, user=_User()))

    assert result.executor == "grpc"
    assert result.script_object_name.endswith(".proto")


def test_list_performance_executors_exposes_ready_locust_and_grpc():
    result = asyncio.run(performance.list_performance_executors(_=None))
    by_name = {item.name: item for item in result}

    assert by_name["k6"].ready is True
    assert by_name["locust"].ready is True
    assert by_name["grpc"].ready is True
    assert by_name["jmeter"].ready is True


def test_upload_performance_script_supports_locust_extension():
    _uploaded_objects.clear()
    file = _Upload("locustfile.py", b"from locust import HttpUser")

    result = asyncio.run(
        performance.upload_performance_script(
            project_id=2,
            file=file,
            executor="locust",
            db=_FakeDB(),
            user=_User(),
        )
    )

    assert result.filename == "locustfile.py"
    assert result.script_object_name.endswith("-locustfile.py")
    assert _uploaded_objects[-1][2] == "text/x-python"


def test_upload_performance_script_supports_grpc_proto_extension():
    _uploaded_objects.clear()
    file = _Upload("greeter.proto", b'syntax = "proto3";')

    result = asyncio.run(
        performance.upload_performance_script(
            project_id=2,
            file=file,
            executor="grpc",
            db=_FakeDB(),
            user=_User(),
        )
    )

    assert result.filename == "greeter.proto"
    assert result.script_object_name.endswith("-greeter.proto")
    assert _uploaded_objects[-1][2] == "text/plain"


def test_upload_performance_script_supports_jmeter_extension():
    _uploaded_objects.clear()
    file = _Upload("smoke.jmx", b"<jmeterTestPlan />")

    result = asyncio.run(
        performance.upload_performance_script(
            project_id=2,
            file=file,
            executor="jmeter",
            db=_FakeDB(),
            user=_User(),
        )
    )

    assert result.filename == "smoke.jmx"
    assert _uploaded_objects[-1][2] == "application/xml"


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
        environment_id=None,
        options={"env": {"TENANT": "acme"}, "duration": "30s"},
    )

    result = asyncio.run(performance.trigger_performance_run(test_id=test.id, body=body, db=db, user=_User()))

    assert isinstance(result, PerformanceRun)
    assert result.status == PerformanceRunStatus.pending.value
    assert result.project_id == 2
    assert result.environment_id is None
    assert result.triggered_by == 7
    assert result.options_snapshot == {
        "env": {"BASE_URL": "https://example.test", "TENANT": "acme"},
        "vus": 5,
        "duration": "30s",
    }
    assert _delay_recorder.calls == [result.id]


def test_trigger_performance_run_injects_environment_and_hides_secret_snapshot(monkeypatch):
    _delay_recorder.calls.clear()
    test = _performance_test()
    test.default_options = {"vus": 5}

    from app.models.environment import Environment, EnvVariable

    environment = Environment(id=9, project_id=2, name="测试环境")
    variables = [
        EnvVariable(env_id=9, key="TARGET_URL", value="https://api.example.test", is_secret=False),
        EnvVariable(env_id=9, key="API_TOKEN", value="encrypted", is_secret=True),
    ]

    class _EnvironmentDB(_FakeDB):
        async def execute(self, _statement):
            return _ListResult(variables)

    monkeypatch.setattr(
        performance,
        "decrypt_env_vars",
        lambda _variables: {"TARGET_URL": "https://api.example.test", "API_TOKEN": "secret"},
    )
    db = _EnvironmentDB(
        {"PerformanceTest": {test.id: test}, "Environment": {environment.id: environment}},
    )

    result = asyncio.run(
        performance.trigger_performance_run(
            test_id=test.id,
            body=PerformanceRunTrigger(environment_id=9, options={"duration": "30s"}),
            db=db,
            user=_User(),
        )
    )

    assert result.environment_id == 9
    assert result.options_snapshot["vus"] == 5
    assert result.options_snapshot["duration"] == "30s"
    assert ENVIRONMENT_SNAPSHOT_KEY in result.options_snapshot
    assert "secret" not in str(result.options_snapshot)
    public = PerformanceRunOut.model_validate(result)
    assert public.model_dump()["options_snapshot"] == {"vus": 5, "duration": "30s"}
    assert _delay_recorder.calls == [result.id]


def test_trigger_performance_run_rejects_sensitive_direct_environment_overrides():
    test = _performance_test()
    db = _FakeDB({"PerformanceTest": {test.id: test}})
    body = PerformanceRunTrigger(options={"env": {"API_TOKEN": "secret"}})

    try:
        asyncio.run(performance.trigger_performance_run(test_id=test.id, body=body, db=db, user=_User()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "敏感变量" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("敏感变量不应直接写入压测参数")


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

    result = asyncio.run(
        performance.trigger_performance_run(test_id=test.id, body=PerformanceRunTrigger(), db=db, user=_User())
    )

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


def test_stop_performance_run_marks_running_run_as_cancelling(monkeypatch):
    now = datetime(2026, 5, 29, tzinfo=timezone.utc)
    run = PerformanceRun(
        id=6,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.running.value,
        options_snapshot={"duration": "30s"},
        summary={},
        created_at=now,
        updated_at=now,
    )
    db = _FakeDB({"PerformanceRun": {run.id: run}})
    requested: list[int] = []
    monkeypatch.setattr(performance, "request_cancel", requested.append)

    result = asyncio.run(performance.stop_performance_run(run_id=run.id, db=db, user=_User()))

    assert result is run
    assert requested == [run.id]
    assert run.status == PerformanceRunStatus.cancelling.value
    assert run.error_message == "正在停止压测"
    assert run.finished_at is None
    assert db.commits == 1


def test_stop_performance_run_finishes_pending_run_as_cancelled(monkeypatch):
    now = datetime(2026, 5, 29, tzinfo=timezone.utc)
    run = PerformanceRun(
        id=7,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.pending.value,
        options_snapshot={},
        summary={},
        created_at=now,
        updated_at=now,
    )
    db = _FakeDB({"PerformanceRun": {run.id: run}})
    monkeypatch.setattr(performance, "request_cancel", lambda _run_id: None)

    asyncio.run(performance.stop_performance_run(run_id=run.id, db=db, user=_User()))

    assert run.status == PerformanceRunStatus.cancelled.value
    assert run.finished_at is not None


def test_stop_performance_run_cascades_to_shards(monkeypatch):
    now = datetime(2026, 5, 29, tzinfo=timezone.utc)
    parent = PerformanceRun(
        id=20,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.running.value,
        options_snapshot={},
        summary={"shard_ids": [21, 22]},
        created_at=now,
        updated_at=now,
    )
    running = PerformanceRun(
        id=21,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.running.value,
        options_snapshot={},
        summary={"shard_index": 0},
        parent_run_id=20,
    )
    pending = PerformanceRun(
        id=22,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.pending.value,
        options_snapshot={},
        summary={"shard_index": 1},
        parent_run_id=20,
    )
    db = _FakeDB({"PerformanceRun": {20: parent, 21: running, 22: pending}})
    requested: list[int] = []
    monkeypatch.setattr(performance, "request_cancel", requested.append)

    result = asyncio.run(performance.stop_performance_run(run_id=20, db=db, user=_User()))

    assert result is parent
    assert requested == [21]
    assert parent.status == PerformanceRunStatus.cancelling.value
    assert running.status == PerformanceRunStatus.cancelling.value
    assert pending.status == PerformanceRunStatus.cancelled.value
    assert pending.finished_at is not None


def test_stop_performance_run_rejects_terminal_run(monkeypatch):
    now = datetime(2026, 5, 29, tzinfo=timezone.utc)
    run = PerformanceRun(
        id=8,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.success.value,
        options_snapshot={},
        summary={},
        created_at=now,
        updated_at=now,
    )
    db = _FakeDB({"PerformanceRun": {run.id: run}})
    monkeypatch.setattr(performance, "request_cancel", lambda _run_id: pytest.fail("stop must not be requested"))

    with pytest.raises(Exception) as caught:
        asyncio.run(performance.stop_performance_run(run_id=run.id, db=db, user=_User()))
    assert caught.value.status_code == 409


def _performance_run_for_export(run_id: int = 10):
    now = datetime(2026, 5, 29, tzinfo=timezone.utc)
    return PerformanceRun(
        id=run_id,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.failed.value,
        options_snapshot={
            "vus": 5,
            "env": {"TARGET_URL": "https://example.test", "API_TOKEN": "secret"},
            ENVIRONMENT_SNAPSHOT_KEY: {"API_TOKEN": "ciphertext"},
        },
        summary={
            "rps": 12.5,
            "p95_ms": 620,
            "p99_ms": 900,
            "error_rate": 0.02,
            "thresholds": {
                "http_req_duration": {"p(95)<500": {"ok": False}},
                "http_req_failed": {"rate<0.01": {"ok": True}},
            },
        },
        error_message="threshold failed",
        created_at=now,
        updated_at=now,
        started_at=now,
        finished_at=now,
        duration_ms=30000,
    )


@pytest.mark.parametrize(
    ("executor_options", "expected_seconds"),
    [({"run_time": "30s"}, 30), ({"duration_seconds": 45}, 45)],
)
def test_performance_progress_estimate_supports_non_k6_duration_options(executor_options, expected_seconds):
    from app.schemas.performance import _expected_duration_seconds

    run = _performance_run_for_export()
    run.status = PerformanceRunStatus.running.value
    run.options_snapshot = executor_options
    run.started_at = datetime.now(timezone.utc) - timedelta(seconds=expected_seconds / 2)

    result = PerformanceRunOut.model_validate(run)

    assert _expected_duration_seconds(executor_options) == expected_seconds
    assert 40 <= result.progress_percent <= 60


def test_export_performance_run_json_is_safe_and_contains_gate():
    run = _performance_run_for_export()
    db = _FakeDB({"PerformanceRun": {run.id: run}})

    response = asyncio.run(performance.export_performance_run_json(run_id=run.id, db=db, user=_User()))
    payload = json.loads(response.body)

    assert response.media_type == "application/json"
    assert payload["threshold_gate"] == {"status": "failed", "total": 2, "passed": 1, "failed": 1}
    assert payload["performance_gate"]["status"] == "failed"
    assert payload["thresholds"] == [
        {"metric": "http_req_duration", "rule": "p(95)<500", "ok": False},
        {"metric": "http_req_failed", "rule": "rate<0.01", "ok": True},
    ]
    exported_snapshot = payload["run"]["options_snapshot"]
    assert ENVIRONMENT_SNAPSHOT_KEY not in exported_snapshot
    assert "API_TOKEN" not in exported_snapshot["env"]


def test_export_performance_run_csv_contains_summary_and_threshold_rows():
    run = _performance_run_for_export(11)
    db = _FakeDB({"PerformanceRun": {run.id: run}})

    response = asyncio.run(performance.export_performance_run_csv(run_id=run.id, db=db, user=_User()))
    content = response.body.decode("utf-8-sig")

    assert response.media_type == "text/csv"
    assert "run_id,performance_test_id,status" in content
    assert "11,3,failed" in content
    assert "http_req_duration,p(95)<500,False" in content
    assert "http_req_failed,rate<0.01,True" in content


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


# ── Q15-05：补齐 options 解析 helper 与 GET/PATCH/LIST 路由 ──────────
# 上面的用例集中在创建、上传与触发；options 的时长/VUs 解析、域名 allowlist 判定
# 以及读取类路由此前一行没跑过。这些 helper 决定"这次压测允不允许打出去"，
# 解析错一个单位就等于把 30 分钟的压测当成 30 秒放行。


class _ListResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _QueryDB(_FakeDB):
    def __init__(self, rows, objects=None):
        super().__init__(objects=objects)
        self._rows = rows
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _ListResult(self._rows)


def test_safe_script_filename_sanitizes_and_defaults():
    assert performance._safe_script_filename(None) == "script.js"
    assert performance._safe_script_filename("../../etc/passwd.js") == "passwd.js"
    assert performance._safe_script_filename("我的 脚本!.MJS") == "script.mjs"
    assert performance._safe_script_filename("load test.js") == "load-test.js"
    # 去掉目录后缀名仍需保留，避免绕过 .js/.mjs 白名单
    assert performance._safe_script_filename("evil.js.sh").endswith(".sh")


def test_parse_duration_seconds_handles_every_unit():
    assert performance._parse_duration_seconds(None) is None
    assert performance._parse_duration_seconds(30) == 30.0
    assert performance._parse_duration_seconds(1.5) == 1.5
    assert performance._parse_duration_seconds(["30s"]) is None
    assert performance._parse_duration_seconds("500ms") == 0.5
    assert performance._parse_duration_seconds("45") == 45.0
    assert performance._parse_duration_seconds("45s") == 45.0
    assert performance._parse_duration_seconds("2m") == 120.0
    assert performance._parse_duration_seconds("1h") == 3600.0
    assert performance._parse_duration_seconds("  10M  ") == 600.0
    assert performance._parse_duration_seconds("soon") is None


def test_max_vus_reads_both_vus_and_stage_targets():
    assert performance._max_vus_from_options({}) == 0
    assert performance._max_vus_from_options({"vus": "12"}) == 12
    assert performance._max_vus_from_options({"vus": "abc"}) == 0
    assert performance._max_vus_from_options({"stages": [{"target": 5}, {"target": 50}]}) == 50
    # 非法 stage 被跳过而不是让整个请求 500
    assert performance._max_vus_from_options({"stages": ["oops", {"target": None}, {"target": 3}]}) == 3


def test_max_duration_sums_stages_but_takes_the_max_otherwise():
    assert performance._max_duration_from_options({}) == 0.0
    assert performance._max_duration_from_options({"duration": "90s"}) == 90.0
    # 分阶段是串行执行，总时长应为累加
    assert performance._max_duration_from_options({"stages": [{"duration": "30s"}, {"duration": "1m"}]}) == 90.0
    assert performance._max_duration_from_options({"stages": ["bad", {"duration": "oops"}]}) == 0.0


def test_target_hosts_only_reads_the_known_env_keys():
    options = {
        "env": {
            "TARGET_URL": "https://a.example.test/path",
            "base_url": "http://b.example.test",
            "OTHER": "https://ignored.test",
            "URL": 123,
        }
    }

    assert performance._target_hosts_from_options(options) == {"a.example.test", "b.example.test"}
    assert performance._target_hosts_from_options({"env": "not-a-dict"}) == set()
    assert performance._target_hosts_from_options({}) == set()


def test_host_allowed_matches_exact_and_subdomains():
    assert performance._host_allowed("anything.test", set()) is True, "allowlist 为空表示不限制"
    assert performance._host_allowed("example.test", {"example.test"}) is True
    assert performance._host_allowed("api.example.test", {"example.test"}) is True
    assert performance._host_allowed("notexample.test", {"example.test"}) is False


def test_validate_options_rejects_a_non_dict():
    try:
        performance._validate_performance_options(["vus", 1])
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("options 非对象必须 400")


def test_merge_options_merges_env_without_dropping_defaults():
    merged = performance._merge_options(
        {"vus": 5, "env": {"BASE_URL": "https://a.test", "TOKEN": "x"}},
        {"vus": 10, "env": {"BASE_URL": "https://b.test"}},
    )

    assert merged["vus"] == 10
    assert merged["env"] == {"BASE_URL": "https://b.test", "TOKEN": "x"}
    assert performance._merge_options(None, None) == {}


def test_list_performance_tests_filters_by_project():
    rows = [_performance_test(3)]
    db = _QueryDB(rows)

    result = asyncio.run(performance.list_performance_tests(project_id=2, db=db, _=None))

    assert result == rows
    assert "performance_tests" in str(db.statements[0])


def test_get_performance_test_returns_the_definition():
    item = _performance_test(3)
    db = _FakeDB({"PerformanceTest": {3: item}})

    assert asyncio.run(performance.get_performance_test(test_id=3, db=db, user=_User())) is item


def test_get_performance_test_404():
    try:
        asyncio.run(performance.get_performance_test(test_id=99, db=_FakeDB(), user=_User()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("应返回 404")


def test_update_performance_test_applies_only_supplied_fields():
    from app.schemas.performance import PerformanceTestUpdate

    item = _performance_test(3)
    db = _FakeDB({"PerformanceTest": {3: item}})

    asyncio.run(
        performance.update_performance_test(
            test_id=3,
            body=PerformanceTestUpdate(name="renamed"),
            db=db,
            user=_User(),
        )
    )

    assert item.name == "renamed"
    assert item.script_object_name == "performance/scripts/smoke.js", "未提交字段保持原值"
    assert db.commits == 1


def test_update_performance_test_validates_new_default_options(monkeypatch):
    from app.schemas.performance import PerformanceTestUpdate

    monkeypatch.setattr(performance.settings, "PERFORMANCE_MAX_VUS", 10)
    item = _performance_test(3)
    db = _FakeDB({"PerformanceTest": {3: item}})

    try:
        asyncio.run(
            performance.update_performance_test(
                test_id=3,
                body=PerformanceTestUpdate(default_options={"vus": 500}),
                db=db,
                user=_User(),
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("超限 options 必须 400")

    assert db.commits == 0, "校验失败不得落库"


def test_update_performance_test_accepts_description_and_script():
    from app.schemas.performance import PerformanceTestUpdate

    item = _performance_test(3)
    db = _FakeDB({"PerformanceTest": {3: item}})

    asyncio.run(
        performance.update_performance_test(
            test_id=3,
            body=PerformanceTestUpdate(description="说明", script_object_name="performance/scripts/new.js"),
            db=db,
            user=_User(),
        )
    )

    assert item.description == "说明"
    assert item.script_object_name == "performance/scripts/new.js"


def test_update_performance_test_404():
    from app.schemas.performance import PerformanceTestUpdate

    try:
        asyncio.run(
            performance.update_performance_test(
                test_id=99, body=PerformanceTestUpdate(name="x"), db=_FakeDB(), user=_User()
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("应返回 404")


def test_set_performance_baseline_accepts_only_a_successful_run():
    item = _performance_test(3)
    run = PerformanceRun(
        id=21,
        performance_test_id=item.id,
        project_id=item.project_id,
        status=PerformanceRunStatus.success.value,
        options_snapshot={},
        summary={"p95_ms": 120},
    )
    db = _FakeDB({"PerformanceTest": {item.id: item}, "PerformanceRun": {run.id: run}})

    result = asyncio.run(
        performance.set_performance_baseline(
            test_id=item.id,
            body=PerformanceBaselineUpdate(run_id=run.id),
            db=db,
            user=_User(),
        )
    )

    assert result is item
    assert item.baseline_run_id == run.id


def test_set_performance_baseline_rejects_a_run_from_another_test():
    item = _performance_test(3)
    run = PerformanceRun(
        id=22,
        performance_test_id=99,
        project_id=item.project_id,
        status=PerformanceRunStatus.success.value,
        options_snapshot={},
        summary={},
    )
    db = _FakeDB({"PerformanceTest": {item.id: item}, "PerformanceRun": {run.id: run}})

    with pytest.raises(Exception) as caught:
        asyncio.run(
            performance.set_performance_baseline(
                test_id=item.id,
                body=PerformanceBaselineUpdate(run_id=run.id),
                db=db,
                user=_User(),
            )
        )
    assert caught.value.status_code == 400


def test_update_performance_schedule_calculates_next_run_and_persists_options():
    item = _performance_test(3)
    db = _FakeDB({"PerformanceTest": {item.id: item}})

    asyncio.run(
        performance.update_performance_schedule(
            test_id=item.id,
            body=PerformanceScheduleUpdate(
                enabled=True,
                cron_expression="*/15 * * * *",
                timezone="Asia/Shanghai",
                options={"duration": "30s"},
            ),
            db=db,
            user=_User(),
        )
    )

    assert item.schedule_enabled is True
    assert item.cron_expression == "*/15 * * * *"
    assert item.schedule_options == {"duration": "30s"}
    assert item.next_run_at is not None


def test_update_performance_schedule_requires_cron_when_enabled():
    item = _performance_test(3)
    with pytest.raises(Exception) as caught:
        asyncio.run(
            performance.update_performance_schedule(
                test_id=item.id,
                body=PerformanceScheduleUpdate(enabled=True),
                db=_FakeDB({"PerformanceTest": {item.id: item}}),
                user=_User(),
            )
        )
    assert caught.value.status_code == 400


def test_baseline_comparison_and_gate_are_project_scoped_contracts():
    item = _performance_test(3)
    baseline = PerformanceRun(
        id=31,
        performance_test_id=item.id,
        project_id=item.project_id,
        status=PerformanceRunStatus.success.value,
        options_snapshot={},
        summary={"rps": 10, "p95_ms": 100, "p99_ms": 180, "error_rate": 0.01},
    )
    current = PerformanceRun(
        id=32,
        performance_test_id=item.id,
        project_id=item.project_id,
        status=PerformanceRunStatus.success.value,
        options_snapshot={},
        summary={"rps": 12, "p95_ms": 120, "p99_ms": 160, "error_rate": 0.02},
    )
    item.baseline_run_id = baseline.id
    db = _FakeDB(
        {
            "PerformanceTest": {item.id: item},
            "PerformanceRun": {baseline.id: baseline, current.id: current},
        }
    )

    comparison = asyncio.run(performance.get_performance_baseline_comparison(run_id=current.id, db=db, user=_User()))
    gate = asyncio.run(performance.get_performance_run_gate(run_id=current.id, db=db, user=_User()))

    assert comparison["baseline_run_id"] == baseline.id
    assert {row["metric"]: row["direction"] for row in comparison["metrics"]} == {
        "rps": "improvement",
        "p95_ms": "regression",
        "p99_ms": "improvement",
        "error_rate": "regression",
    }
    assert gate == {
        "status": "not_configured",
        "ready": True,
        "run_status": "success",
        "total": 0,
        "passed": 0,
        "failed": 0,
    }


def test_list_performance_runs_is_scoped_and_capped():
    run = PerformanceRun(
        id=1,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.pending.value,
        options_snapshot={},
        summary={},
        triggered_by=7,
        created_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
    )
    db = _QueryDB([run])

    result = asyncio.run(performance.list_performance_runs(project_id=2, db=db, user=_User()))

    assert result == [run]
    assert "LIMIT" in str(db.statements[0]).upper(), "列表必须封顶，避免一次拉回全部历史"


def test_get_performance_run_returns_the_run():
    run = PerformanceRun(
        id=5,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.success.value,
        options_snapshot={},
        summary={},
        triggered_by=7,
        created_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
    )
    db = _FakeDB({"PerformanceRun": {5: run}})

    assert asyncio.run(performance.get_performance_run(run_id=5, db=db, user=_User())) is run


def test_list_performance_run_metrics_returns_time_ordered_samples():
    run = PerformanceRun(
        id=55,
        performance_test_id=3,
        project_id=2,
        status=PerformanceRunStatus.success.value,
        options_snapshot={},
        summary={},
        created_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
    )
    sample = PerformanceMetricSample(
        id=1,
        run_id=run.id,
        captured_at=datetime(2026, 5, 29, 1, 0, tzinfo=timezone.utc),
        node_id="worker-1",
        source="performance-worker",
        metrics={"cpu_percent": 42.0},
        errors=[],
    )
    db = _QueryDB([sample], {"PerformanceRun": {run.id: run}})

    result = asyncio.run(performance.list_performance_run_metrics(run_id=run.id, db=db, user=_User()))

    assert result == [sample]
    assert "performance_metric_samples" in str(db.statements[0])


def test_get_performance_run_404():
    try:
        asyncio.run(performance.get_performance_run(run_id=5, db=_FakeDB(), user=_User()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("应返回 404")


def test_upload_performance_script_rejects_an_empty_file():
    class _EmptyUpload:
        filename = "load.js"

        async def read(self):
            return b""

    try:
        asyncio.run(
            performance.upload_performance_script(project_id=2, file=_EmptyUpload(), db=_FakeDB(), user=_User())
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("空脚本必须 400")


def test_upload_performance_script_enforces_the_two_megabyte_limit():
    class _BigUpload:
        filename = "load.js"

        async def read(self):
            return b"a" * (2 * 1024 * 1024 + 1)

    try:
        asyncio.run(performance.upload_performance_script(project_id=2, file=_BigUpload(), db=_FakeDB(), user=_User()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 413
    else:
        raise AssertionError("超限脚本必须 413")


def _performance_node(node_id: int = 17, *, status: str = "online", max_vus: int | None = None):
    now = datetime.now(timezone.utc)
    return PerformanceNode(
        id=node_id,
        node_id=f"worker-{node_id}",
        name=f"worker-{node_id}",
        queue_name="performance",
        status=status,
        enabled=True,
        labels={},
        capabilities={"executor": "k6"},
        max_vus=max_vus,
        max_concurrency=None,
        egress_allowlist=[],
        last_heartbeat_at=now,
        created_at=now,
        updated_at=now,
    )


def test_create_performance_node_starts_offline_until_worker_heartbeat():
    db = _FakeDB()
    body = PerformanceNodeCreate(
        node_id="worker-a",
        name="Worker A",
        queue_name="performance.worker-a",
        max_vus=20,
        egress_allowlist=["api.example.test", "API.EXAMPLE.TEST"],
    )

    result = asyncio.run(performance.create_performance_node(body=body, db=db, _=None))

    assert result.status == "offline"
    assert result.egress_allowlist == ["api.example.test"]
    assert result.max_vus == 20
    assert db.commits == 1


def test_update_performance_node_disabling_it_sets_disabled_status():
    node = _performance_node()
    db = _FakeDB({"PerformanceNode": {node.id: node}})

    result = asyncio.run(
        performance.update_performance_node(node_id=node.id, body=PerformanceNodeUpdate(enabled=False), db=db, _=None)
    )

    assert result is node
    assert node.enabled is False
    assert node.status == "disabled"


def test_trigger_performance_run_records_selected_node():
    _delay_recorder.calls.clear()
    test = _performance_test()
    node = _performance_node(max_vus=10)
    db = _FakeDB({"PerformanceTest": {test.id: test}, "PerformanceNode": {node.id: node}})

    result = asyncio.run(
        performance.trigger_performance_run(
            test_id=test.id,
            body=PerformanceRunTrigger(performance_node_id=node.id, options={"vus": 10}),
            db=db,
            user=_User(),
        )
    )

    assert result.performance_node_id == node.id
    assert _delay_recorder.calls == [result.id]


def test_trigger_performance_run_creates_multi_node_shards():
    _delay_recorder.calls.clear()
    test = _performance_test()
    first = _performance_node(17)
    second = _performance_node(18)
    db = _FakeDB(
        {
            "PerformanceTest": {test.id: test},
            "PerformanceNode": {first.id: first, second.id: second},
        }
    )

    result = asyncio.run(
        performance.trigger_performance_run(
            test_id=test.id,
            body=PerformanceRunTrigger(performance_node_ids=[first.id, second.id], options={"vus": 10}),
            db=db,
            user=_User(),
        )
    )

    children = [item for item in db.added if isinstance(item, PerformanceRun) and item is not result]
    assert result.summary["sharded"] is True
    assert len(children) == 2
    assert [child.options_snapshot["vus"] for child in children] == [5, 5]
    assert all(child.parent_run_id == result.id for child in children)
    assert _delay_recorder.calls == [child.id for child in children]


def test_trigger_performance_run_rejects_an_offline_selected_node():
    test = _performance_test()
    node = _performance_node(status="offline")
    node.last_heartbeat_at = None
    db = _FakeDB({"PerformanceTest": {test.id: test}, "PerformanceNode": {node.id: node}})

    with pytest.raises(Exception) as caught:
        asyncio.run(
            performance.trigger_performance_run(
                test_id=test.id,
                body=PerformanceRunTrigger(performance_node_id=node.id),
                db=db,
                user=_User(),
            )
        )

    assert caught.value.status_code == 409
    assert db.added == []


def test_update_performance_schedule_records_selected_node():
    test = _performance_test()
    node = _performance_node(max_vus=20)
    db = _FakeDB({"PerformanceTest": {test.id: test}, "PerformanceNode": {node.id: node}})

    asyncio.run(
        performance.update_performance_schedule(
            test_id=test.id,
            body=PerformanceScheduleUpdate(
                enabled=True,
                cron_expression="*/15 * * * *",
                timezone="Asia/Shanghai",
                performance_node_id=node.id,
                options={"vus": 10},
            ),
            db=db,
            user=_User(),
        )
    )

    assert test.schedule_node_id == node.id


class _ScalarOnlyResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _DatasetBindingDB(_FakeDB):
    def __init__(self, objects=None, version=1):
        super().__init__(objects=objects)
        self.version = version
        self.execute_calls = 0

    async def execute(self, _statement):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _ScalarOnlyResult(self.version)
        return _ScalarOnlyResult(SimpleNamespace(rows=[{"account": "alice"}]))


def test_create_performance_test_binds_a_project_dataset_version():
    from types import SimpleNamespace

    dataset = SimpleNamespace(project_id=2)
    db = _DatasetBindingDB({"TestDataset": {9: dataset}}, version=3)
    body = PerformanceTestCreate(
        project_id=2,
        name="dataset-load",
        script_object_name="performance/scripts/dataset.js",
        dataset_id=9,
    )

    result = asyncio.run(performance.create_performance_test(body=body, db=db, user=_User()))

    assert result.dataset_id == 9


def test_trigger_performance_run_pins_the_current_dataset_version():
    _delay_recorder.calls.clear()
    from types import SimpleNamespace

    test = _performance_test()
    test.dataset_id = 9
    dataset = SimpleNamespace(project_id=2)
    db = _DatasetBindingDB(
        {"PerformanceTest": {test.id: test}, "TestDataset": {9: dataset}},
        version=4,
    )

    result = asyncio.run(
        performance.trigger_performance_run(
            test_id=test.id,
            body=PerformanceRunTrigger(),
            db=db,
            user=_User(),
        )
    )

    assert result.dataset_id == 9
    assert result.dataset_version == 4
    assert _delay_recorder.calls == [result.id]
