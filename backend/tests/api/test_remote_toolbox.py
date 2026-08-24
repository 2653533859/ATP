"""Regression tests for the safe remote toolbox overview."""

from __future__ import annotations

import asyncio
import types
from datetime import datetime, timezone

from app.api.v1 import remote_toolbox
from app.api.v1 import health
from app.models.bootstrap import load_all_models
from app.schemas.remote_toolbox import RemoteToolboxCheck

load_all_models()


def _run(coro):
    return asyncio.run(coro)


def _check(key: str, category: str = "execution", status: str = "ok") -> RemoteToolboxCheck:
    return RemoteToolboxCheck(
        key=key,
        category=category,
        status=status,
        code="ok",
        latency_ms=1.0,
    )


def test_android_checks_distinguish_worker_and_adb_capability():
    checks = remote_toolbox._android_checks(
        [
            {
                "worker_id": "win-android-1",
                "queues": ["android", "mobile_special"],
                "capabilities": ["android"],
            }
        ],
        0.0,
    )

    assert [(item.key, item.status, item.code) for item in checks] == [
        ("android_worker", "ok", "online"),
        ("adb", "warning", "adb_capability_missing"),
    ]
    assert checks[0].resources[0].metadata["queues"] == ["android", "mobile_special"]
    assert "hostname" not in checks[0].resources[0].metadata


def test_android_checks_report_no_worker_without_exposing_registry_details():
    checks = remote_toolbox._android_checks([], 0.0)

    assert all(item.status == "warning" for item in checks)
    assert [item.code for item in checks] == ["no_worker", "no_worker"]
    assert "password" not in str([item.model_dump() for item in checks]).lower()


def test_web_check_uses_local_mode_without_querying_worker_registry(monkeypatch):
    monkeypatch.setattr(remote_toolbox.settings, "WEB_RECORDER_MODE", "local")

    async def fail_if_called():
        raise AssertionError("local mode must not query the worker registry")

    monkeypatch.setattr(remote_toolbox, "list_recording_workers", fail_if_called)
    result = _run(remote_toolbox._load_web_check())

    assert (result.status, result.code) == ("ok", "local_mode")


def test_web_check_marks_full_workers_as_degraded(monkeypatch):
    monkeypatch.setattr(remote_toolbox.settings, "WEB_RECORDER_MODE", "worker")

    async def workers():
        return [{"worker_id": "web-1", "active_sessions": 2, "capacity": 2}]

    monkeypatch.setattr(remote_toolbox, "list_recording_workers", workers)
    result = _run(remote_toolbox._load_web_check())

    assert (result.status, result.code) == ("warning", "no_worker")
    assert result.resources[0].metadata == {"active_sessions": 2, "capacity": 2}


def test_performance_check_whitelists_capabilities_before_returning_metadata():
    node = types.SimpleNamespace(
        node_id="perf-1",
        name="Performance 1",
        enabled=True,
        status="online",
        queue_name="performance",
        capabilities={"executors": ["k6", "grpc", {"token": "nested-must-not-leak"}], "token": "must-not-leak"},
        last_heartbeat_at=datetime.now(timezone.utc),
    )

    class _DB:
        async def execute(self, _statement):
            return types.SimpleNamespace(scalars=lambda: types.SimpleNamespace(all=lambda: [node]))

    result = _run(remote_toolbox._load_performance_check(_DB()))

    assert result.status == "ok"
    assert result.resources[0].metadata["capabilities"] == {"executors": ["k6", "grpc"]}
    assert "must-not-leak" not in str(result.model_dump())


def test_overview_aggregates_errors_and_keeps_dependency_payload_redacted(monkeypatch):
    async def postgres():
        return health.DependencyCheck(status="ok", latency_ms=1.0, code="ok")

    async def redis():
        return health.DependencyCheck(status="error", latency_ms=2.0, code="unreachable")

    async def minio():
        return health.DependencyCheck(status="ok", latency_ms=3.0, code="ok")

    async def android():
        return [_check("android_worker", status="ok"), _check("adb", status="ok")]

    async def web():
        return _check("web_worker")

    async def performance(_db):
        return _check("performance_node", status="warning")

    monkeypatch.setattr(remote_toolbox, "_probe_postgres", postgres)
    monkeypatch.setattr(remote_toolbox, "_probe_redis", redis)
    monkeypatch.setattr(remote_toolbox, "_probe_minio", minio)
    monkeypatch.setattr(remote_toolbox, "_load_android_checks", android)
    monkeypatch.setattr(remote_toolbox, "_load_web_check", web)
    monkeypatch.setattr(remote_toolbox, "_load_performance_check", performance)

    result = _run(remote_toolbox.get_remote_toolbox_overview(db=object(), _engineer=types.SimpleNamespace()))
    payload = result.model_dump()

    assert result.status == "error"
    assert [item.key for item in result.checks] == [
        "postgres",
        "redis",
        "minio",
        "android_worker",
        "adb",
        "web_worker",
        "performance_node",
    ]
    assert payload["checks"][1]["code"] == "unreachable"
    assert "172.31.27.133" not in str(payload)
    assert "password" not in str(payload).lower()
