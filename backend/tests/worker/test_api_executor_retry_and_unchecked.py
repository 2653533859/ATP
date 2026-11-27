"""Unit tests for write-safe HTTP retry semantics and require_assertions / UNCHECKED handling."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.models.bootstrap import load_all_models
from app.models.case import RunStatus
from app.worker.executors import api_executor

load_all_models()


def test_is_write_safe_retryable_only_allows_connect_and_proxy_errors():
    req = httpx.Request("POST", "https://api.example.com/orders")
    assert api_executor.is_write_safe_retryable(httpx.ConnectTimeout("connect timeout", request=req)) is True
    assert api_executor.is_write_safe_retryable(httpx.ConnectError("refused", request=req)) is True
    assert api_executor.is_write_safe_retryable(httpx.ProxyError("proxy down", request=req)) is True

    # Must NEVER retry after request may have reached the server
    assert api_executor.is_write_safe_retryable(httpx.ReadTimeout("read timeout", request=req)) is False
    assert api_executor.is_write_safe_retryable(httpx.WriteTimeout("write timeout", request=req)) is False
    assert (
        api_executor.is_write_safe_retryable(httpx.HTTPStatusError("500", request=req, response=httpx.Response(500)))
        is False
    )


def test_write_safe_retry_succeeds_after_connect_error_and_records_history():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json={"ok": True})

    async def _run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            resp, _, meta = await api_executor._send_request_with_write_safe_retry(
                client,
                "POST",
                "https://api.example.com/orders",
                10.0,
                {},
                None,
                100,
                retry_count=2,
                retry_delay_seconds=0.0,
            )
            assert resp.status_code == 200
            assert meta["attempts"] == 2
            assert meta["retried"] is True
            assert len(meta["history"]) == 1
            assert meta["history"][0]["error_type"] == "ConnectError"

    asyncio.run(_run())


def test_write_safe_retry_does_not_repeat_read_timeout():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.ReadTimeout("slow response after write", request=request)

    async def _run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(httpx.ReadTimeout):
                await api_executor._send_request_with_write_safe_retry(
                    client,
                    "POST",
                    "https://api.example.com/orders",
                    10.0,
                    {},
                    None,
                    100,
                    retry_count=3,
                    retry_delay_seconds=0.0,
                )
            assert attempts["count"] == 1

    asyncio.run(_run())


def test_run_api_case_require_assertions_blocks_before_http_call(monkeypatch):
    http_called = {"count": 0}

    async def fake_send(*_args, **_kwargs):
        http_called["count"] += 1
        raise AssertionError("HTTP should not be sent when require_assertions blocks zero-assertion step")

    monkeypatch.setattr(api_executor, "_send_request", fake_send)
    monkeypatch.setattr(api_executor, "_safe_publish_run_event", AsyncMock())
    monkeypatch.setattr(api_executor, "maybe_enqueue_run_healing", AsyncMock())
    monkeypatch.setattr(api_executor, "apply_healing_hook", lambda _sr: False)

    saved_steps = []

    class _FakeDB:
        def add(self, obj):
            saved_steps.append(obj)

        def add_all(self, objs):
            saved_steps.extend(objs)

        async def flush(self):
            return None

        async def commit(self):
            return None

    run = SimpleNamespace(id=101, trace_id="t-1", status=RunStatus.running, duration_ms=0, result_summary={})
    case = SimpleNamespace(
        id=202,
        project_id=1,
        config={
            "require_assertions": True,
            "steps": [
                {"name": "无断言写接口", "method": "POST", "url": "https://api.example.com/pay", "assertions": []}
            ],
        },
    )

    asyncio.run(api_executor.run_api_case(_FakeDB(), run, case, {}))
    assert http_called["count"] == 0
    assert run.status == RunStatus.failed
    assert saved_steps[0].response_data["verification_status"] == "unchecked"
    assert run.result_summary["unchecked_step_count"] == 1
