"""Unit tests for isolated API debug sessions, chained fingerprints, offline assertion recheck, and 3-tier precheck."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services.api_debug_session import (
    ApiDebugSessionError,
    create_api_debug_session,
    delete_api_debug_session,
    execute_api_debug_session,
    get_api_debug_session,
    precheck_api_scenario_steps,
    recheck_api_debug_assertions,
)


def _mock_transport(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_precheck_three_tiers_save_debug_run():
    steps = [
        {
            "uid": "s1",
            "name": "登录",
            "method": "POST",
            "url": "",
            "assertions": [],
        }
    ]
    # save allows incomplete drafts and zero assertions
    assert precheck_api_scenario_steps(steps, env_vars={}, mode="save") == []

    # debug checks URL and required fields
    debug_issues = precheck_api_scenario_steps(steps, env_vars={}, mode="debug", target_step_uid="s1")
    assert any(item["field"] == "url" for item in debug_issues)

    # run additionally enforces >=1 assertion per step
    steps[0]["url"] = "https://api.example.com/login"
    assert precheck_api_scenario_steps(steps, env_vars={}, mode="debug", target_step_uid="s1") == []
    run_issues = precheck_api_scenario_steps(steps, env_vars={}, mode="run")
    assert any(item["section"] == "assertions" for item in run_issues)


def test_debug_session_unchecked_then_offline_recheck_without_resending_http():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"code": 0, "data": {"token": "tok_123"}})

    sess = create_api_debug_session(user_id=7, project_id=1, editor_id="ed-1", env_id=1)
    try:
        steps = [
            {
                "uid": "s1",
                "name": "获取令牌",
                "method": "POST",
                "url": "https://api.example.com/auth",
                "extractions": [{"variable": "token", "type": "jsonpath", "expression": "$.data.token"}],
                "assertions": [],
            }
        ]
        db = AsyncMock()

        async def _run():
            async with _mock_transport(handler) as client:
                exec_res = await execute_api_debug_session(
                    sess,
                    steps=steps,
                    target_step_uid="s1",
                    mode="single",
                    env_vars={},
                    db=db,
                    http_client=client,
                )
            assert exec_res["executed"][0]["status"] == "unchecked"
            assert len(calls) == 1

            # Add assertion and recheck offline -> ZERO additional HTTP requests!
            steps[0]["assertions"] = [{"target": "body", "operator": "eq", "expression": "$.code", "expected": "0"}]
            recheck_res = await recheck_api_debug_assertions(
                sess,
                steps=steps,
                target_step_uid="s1",
                env_vars={},
                db=db,
            )
            assert recheck_res["rechecked_offline"] is True
            assert recheck_res["step_result"]["status"] == "passed"
            assert len(calls) == 1

            # Changing request URL invalidates cached response via chained fingerprint
            steps[0]["url"] = "https://api.example.com/auth-v2"
            with pytest.raises(ApiDebugSessionError) as exc_info:
                await recheck_api_debug_assertions(
                    sess,
                    steps=steps,
                    target_step_uid="s1",
                    env_vars={},
                    db=db,
                )
            assert exc_info.value.status_code == 409

        asyncio.run(_run())
    finally:
        delete_api_debug_session(sess.session_id, user_id=7)


def test_debug_session_collect_mode_continues_after_assertion_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/step1":
            return httpx.Response(200, json={"code": 1, "token": "abc"})
        return httpx.Response(200, json={"code": 0, "ok": True})

    sess = create_api_debug_session(user_id=9, project_id=1, editor_id="ed-collect", env_id=None)
    try:
        steps = [
            {
                "uid": "s1",
                "name": "步骤1",
                "method": "GET",
                "url": "https://api.example.com/step1",
                "extractions": [{"variable": "token", "type": "jsonpath", "expression": "$.token"}],
                "assertions": [{"target": "body", "operator": "eq", "expression": "$.code", "expected": "0"}],
            },
            {
                "uid": "s2",
                "name": "步骤2",
                "method": "GET",
                "url": "https://api.example.com/step2",
                "headers": {"Authorization": "Bearer {{token}}"},
                "assertions": [],
            },
        ]
        db = AsyncMock()

        async def _run():
            async with _mock_transport(handler) as client:
                res = await execute_api_debug_session(
                    sess,
                    steps=steps,
                    target_step_uid="s2",
                    mode="collect",
                    env_vars={},
                    db=db,
                    http_client=client,
                )
            assert len(res["executed"]) == 2
            assert res["executed"][0]["status"] == "failed"
            assert res["executed"][1]["status"] == "unchecked"
            assert "s1" in sess.responses and "s2" in sess.responses

        asyncio.run(_run())
    finally:
        delete_api_debug_session(sess.session_id, user_id=9)


def test_debug_session_user_isolation():
    sess = create_api_debug_session(user_id=10, project_id=1, editor_id="iso", env_id=None)
    try:
        with pytest.raises(ApiDebugSessionError) as exc_info:
            get_api_debug_session(sess.session_id, user_id=11, is_admin=False)
        assert exc_info.value.status_code == 403
    finally:
        delete_api_debug_session(sess.session_id, user_id=10)


def test_debug_session_ssrf_guard_size_cap_and_frontend_assertion_aliases():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/huge":
            return httpx.Response(200, content=b"x" * (5 * 1024 * 1024 + 10))
        return httpx.Response(
            200,
            headers={"X-Request-Id": "req-9"},
            json={"code": 0, "data": {"name": "alpha"}},
        )

    sess = create_api_debug_session(user_id=12, project_id=1, editor_id="alias-ssrf", env_id=None)
    try:
        db = AsyncMock()

        async def _run():
            # 1. SSRF blocks localhost/private IP
            async with _mock_transport(handler) as client:
                ssrf_res = await execute_api_debug_session(
                    sess,
                    steps=[{"uid": "s1", "method": "GET", "url": "http://127.0.0.1:8000/health", "assertions": []}],
                    target_step_uid="s1",
                    mode="single",
                    env_vars={},
                    db=db,
                    http_client=client,
                )
            assert ssrf_res["executed"][0]["status"] == "error"
            assert "本机" in (ssrf_res["executed"][0]["error"] or "")

            # 2. Frontend assertion aliases (jsonpath, response_header, body_contains, not_empty)
            async with _mock_transport(handler) as client:
                alias_res = await execute_api_debug_session(
                    sess,
                    steps=[
                        {
                            "uid": "s2",
                            "method": "GET",
                            "url": "https://api.example.com/info",
                            "assertions": [
                                {"target": "jsonpath", "operator": "not_empty", "expression": "$.data.name"},
                                {
                                    "target": "response_header",
                                    "operator": "eq",
                                    "expression": "x-request-id",
                                    "expected": "req-9",
                                },
                                {"target": "body_contains", "operator": "contains", "expected": "alpha"},
                            ],
                        }
                    ],
                    target_step_uid="s2",
                    mode="single",
                    env_vars={},
                    db=db,
                    http_client=client,
                )
            assert alias_res["executed"][0]["status"] == "passed"

            # 3. Huge response (> 5 MiB) rejected
            async with _mock_transport(handler) as client:
                huge_res = await execute_api_debug_session(
                    sess,
                    steps=[{"uid": "s3", "method": "GET", "url": "https://api.example.com/huge", "assertions": []}],
                    target_step_uid="s3",
                    mode="single",
                    env_vars={},
                    db=db,
                    http_client=client,
                )
            assert huge_res["executed"][0]["status"] == "error"
            assert "5 MiB" in (huge_res["executed"][0]["error"] or "")

        asyncio.run(_run())
    finally:
        delete_api_debug_session(sess.session_id, user_id=12)
