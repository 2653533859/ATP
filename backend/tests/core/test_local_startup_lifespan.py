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

    monkeypatch.setattr(
        web_recordings, "close_all_recordings", AsyncMock(side_effect=lambda: events.append("recordings"))
    )

    async with main.lifespan(main.app):
        assert ("schema", sync_engine) in events
        assert events.index("workspace") < events.index("start")

    assert events[-4:] == ["stop", "recordings", "dispose", "shutdown"]


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

    async with main.lifespan(main.app):
        assert events == ["alembic"]


@pytest.mark.asyncio
async def test_local_unsupported_write_guard_does_not_affect_reads_or_server(monkeypatch):
    async def next_response(_request):
        return "next"

    request = SimpleNamespace(method="POST", url=SimpleNamespace(path="/api/v1/plans"))
    monkeypatch.setattr(main, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    blocked = await main.reject_unsupported_local_writes(request, next_response)
    assert blocked.status_code == 409

    request.method = "GET"
    assert await main.reject_unsupported_local_writes(request, next_response) == "next"
    request.method = "POST"
    monkeypatch.setattr(main, "settings", SimpleNamespace(ATP_LOCAL_MODE=False))
    assert await main.reject_unsupported_local_writes(request, next_response) == "next"
