"""Startup selects the local schema and queue only for the local profile."""

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import main
from app.core import local_run_ids, local_schema, local_workspace
from app.services import local_jobs


@pytest.mark.asyncio
async def test_local_lifespan_starts_schema_workspace_and_queue(monkeypatch):
    events = []
    sync_engine = object()
    monkeypatch.setattr(
        main, "settings", SimpleNamespace(ATP_LOCAL_MODE=True, OTEL_SERVICE_NAME="test", APP_AUTO_CREATE_TABLES=False)
    )
    monkeypatch.setattr(sys.modules["app.core.database"], "sync_engine", sync_engine, raising=False)
    monkeypatch.setattr(main, "setup_logging", lambda: events.append("logging"))
    monkeypatch.setattr(main, "init_tracer", lambda _name: events.append("tracer"))
    monkeypatch.setattr(main, "shutdown_tracer", lambda: events.append("shutdown"))
    monkeypatch.setattr(main, "ensure_bucket", lambda: events.append("bucket"))
    monkeypatch.setattr(main, "_init_admin", AsyncMock(side_effect=lambda: events.append("admin")))
    monkeypatch.setattr(
        main, "engine", SimpleNamespace(dispose=AsyncMock(side_effect=lambda: events.append("dispose")))
    )
    monkeypatch.setattr(local_schema, "ensure_local_schema", lambda engine: events.append(("schema", engine)))
    monkeypatch.setattr(local_run_ids, "install_local_run_id_allocator", lambda: events.append("ids"))
    monkeypatch.setattr(
        local_workspace, "ensure_local_workspace", AsyncMock(side_effect=lambda: events.append("workspace"))
    )
    monkeypatch.setattr(local_jobs, "start_local_runner", lambda: events.append("start"))
    monkeypatch.setattr(local_jobs, "stop_local_runner", lambda: events.append("stop"))
    from app.api.v1 import web_recordings
    from app.services import execution_dispatch

    monkeypatch.setattr(
        web_recordings, "close_all_recordings", AsyncMock(side_effect=lambda: events.append("recordings"))
    )
    # 投递器在 lifespan 内以函数级导入启动/停止，替身须打在来源模块上；
    # 它应在本地队列之后启动，并在本地队列之前停止。
    monkeypatch.setattr(execution_dispatch, "start_dispatcher", lambda: events.append("dispatch_start"))
    monkeypatch.setattr(execution_dispatch, "stop_dispatcher", lambda: events.append("dispatch_stop"))

    async with main.lifespan(main.app):
        assert ("schema", sync_engine) in events
        assert events.index("workspace") < events.index("start") < events.index("dispatch_start")

    assert events[-5:] == ["dispatch_stop", "stop", "recordings", "dispose", "shutdown"]


@pytest.mark.asyncio
async def test_server_lifespan_checks_alembic_without_local_queue(monkeypatch):
    events = []
    monkeypatch.setattr(
        main, "settings", SimpleNamespace(ATP_LOCAL_MODE=False, OTEL_SERVICE_NAME="test", APP_AUTO_CREATE_TABLES=False)
    )
    monkeypatch.setattr(main, "setup_logging", lambda: None)
    monkeypatch.setattr(main, "verify_alembic_head_or_warn", lambda: events.append("alembic"))
    monkeypatch.setattr(main, "init_tracer", lambda _name: None)
    monkeypatch.setattr(main, "shutdown_tracer", lambda: None)
    monkeypatch.setattr(main, "ensure_bucket", lambda: None)
    monkeypatch.setattr(main, "_init_admin", AsyncMock())
    monkeypatch.setattr(main, "engine", SimpleNamespace(dispose=AsyncMock()))
    from app.api.v1 import web_recordings

    monkeypatch.setattr(web_recordings, "close_all_recordings", AsyncMock())
    from app.services import execution_dispatch

    monkeypatch.setattr(execution_dispatch, "start_dispatcher", lambda: events.append("dispatch_start"))
    monkeypatch.setattr(execution_dispatch, "stop_dispatcher", lambda: None)

    async with main.lifespan(main.app):
        # 服务器模式不启动本地队列，但共用投递器仍随 API 生命周期启动。
        assert events == ["alembic", "dispatch_start"]


@pytest.mark.asyncio
async def test_local_unsupported_write_guard_blocks_only_unimplemented_prefixes(monkeypatch):
    async def next_response(_request):
        return "next"

    monkeypatch.setattr(main, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    request = SimpleNamespace(method="POST", url=SimpleNamespace(path="/api/v1/plans"))

    # 本地已开放手动套件/计划、性能与 Hermes；只有尚未纳入的能力继续被 409 拦截。
    for path in ("/api/v1/plans", "/api/v1/suites", "/api/v1/devices/scan", "/api/v1/mobile-special/tasks"):
        request.url.path = path
        assert await main.reject_unsupported_local_writes(request, next_response) == "next"
    for path in (
        "/api/v1/plans/webhook",
        "/api/v1/device-mirror/devices",
        "/api/v1/ios-apps",
        "/api/v1/performance/nodes",
        "/api/v1/ai-cases",
    ):
        request.url.path = path
        assert (await main.reject_unsupported_local_writes(request, next_response)).status_code == 409

    request.url.path = "/api/v1/ios-apps"
    request.method = "GET"
    assert await main.reject_unsupported_local_writes(request, next_response) == "next"
    request.method = "POST"
    monkeypatch.setattr(main, "settings", SimpleNamespace(ATP_LOCAL_MODE=False))
    assert await main.reject_unsupported_local_writes(request, next_response) == "next"
