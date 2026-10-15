"""Unit tests for T3.3 Workflow Canvas Step-by-Step Breakpoint Debugger and Dataflow Watcher.

Tests:
1. create_debug_session initializes paused state and dataflow watchers
2. step_debug_session performs single node step-over, applies extractions, tracks context_diff
3. resume_debug_session runs until next breakpoint is reached
4. Execution to completion sets state='completed'
5. Session cleanup via stop_debug_session
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.workflow_debugger import (
    WorkflowDebuggerError,
    create_debug_session,
    get_debug_session,
    resume_debug_session,
    step_debug_session,
    stop_debug_session,
)


@pytest.fixture
def sample_dag_workflow():
    return {
        "nodes": [
            {
                "id": "node_1_http",
                "name": "登录接口",
                "type": "http",
                "depends_on": [],
                "config": {
                    "url": "https://api.local/login",
                    "extractions": {"auth_token": "token", "user_id": "uid"},
                },
            },
            {
                "id": "node_2_sql",
                "name": "查询用户",
                "type": "sql",
                "depends_on": ["node_1_http"],
                "config": {
                    "query": "SELECT * FROM users WHERE id = {{user_id}}",
                    "extractions": {"user_status": "status"},
                },
            },
            {
                "id": "node_3_redis",
                "name": "写入缓存",
                "type": "redis",
                "depends_on": ["node_2_sql"],
                "config": {
                    "command": "SET",
                    "key": "user:{{user_id}}",
                    "value": "active",
                },
            },
        ]
    }


@pytest.mark.asyncio
async def test_debug_session_step_over_and_watchers(sample_dag_workflow):
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {"token": "jwt_token_999", "uid": 12345}
    mock_resp.headers = {"Content-Type": "application/json"}

    with patch("httpx.AsyncClient.request", return_value=mock_resp):
        # 1. Start debug session paused at entry node
        snap = create_debug_session(
            sample_dag_workflow,
            breakpoints=["node_3_redis"],
            initial_context={"env": "staging"},
            watchers=["auth_token", "user_id", "user_status"],
        )
        sid = snap["session_id"]
        assert snap["state"] == "paused"
        assert snap["current_node_index"] == 0
        assert snap["current_node"]["id"] == "node_1_http"
        assert snap["next_node"]["id"] == "node_2_sql"

        # Check initial watchers (unextracted yet)
        watchers = {w["name"]: w for w in snap["watchers"]}
        assert watchers["auth_token"]["value"] is None

        # 2. Step Over Node 1 (HTTP)
        step_snap = await step_debug_session(sid)
        assert step_snap["state"] == "paused"
        assert step_snap["current_node_index"] == 1
        assert step_snap["current_node"]["id"] == "node_2_sql"
        assert len(step_snap["history"]) == 1
        assert step_snap["history"][0]["id"] == "node_1_http"
        assert step_snap["history"][0]["status"] == "passed"

        # Check diff and watchers updated
        diff = step_snap["context_diff"]
        assert "auth_token" in diff
        assert "user_id" in diff

        watchers_after_step = {w["name"]: w for w in step_snap["watchers"]}
        assert watchers_after_step["auth_token"]["value"] == {"token": "jwt_token_999", "uid": 12345}
        assert watchers_after_step["auth_token"]["changed_in_last_step"] is True

        # 3. Clean up
        assert stop_debug_session(sid) is True
        with pytest.raises(WorkflowDebuggerError):
            get_debug_session(sid)


@pytest.mark.asyncio
async def test_debug_session_resume_hits_breakpoint(sample_dag_workflow):
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {"token": "jwt_token_888", "uid": 777}
    mock_resp.headers = {"Content-Type": "application/json"}

    with patch("httpx.AsyncClient.request", return_value=mock_resp):
        # Breakpoint set on node_3_redis
        snap = create_debug_session(
            sample_dag_workflow,
            breakpoints=["node_3_redis"],
            initial_context={},
        )
        sid = snap["session_id"]
        assert snap["current_node_index"] == 0

        # Resume should run Node 1 and Node 2, and pause at Node 3
        resumed_snap = await resume_debug_session(sid)
        assert resumed_snap["state"] == "paused"
        assert resumed_snap["current_node"]["id"] == "node_3_redis"
        assert len(resumed_snap["history"]) == 2

        # Resume again: completes remaining nodes
        final_snap = await resume_debug_session(sid)
        assert final_snap["state"] == "completed"
        assert len(final_snap["history"]) == 3

        stop_debug_session(sid)
