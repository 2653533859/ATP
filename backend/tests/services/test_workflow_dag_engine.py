"""Unit tests for T3.1 Multi-Protocol Mixed Workflow Flowchart DAG Engine.

Tests:
1. validate_and_toposort_workflow: Topological sorting of DAG dependencies
2. Cycle and self-loop detection
3. Nonexistent dependency detection
4. render_context_template variable interpolation
5. execute_workflow_dag heterogeneous node execution (HTTP, SQL, Redis, Mobile, Delay)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.workflow_dag_engine import (
    WorkflowDagError,
    execute_workflow_dag,
    render_context_template,
    validate_and_toposort_workflow,
)


def test_toposort_linear_and_diamond_dag():
    # Diamond graph: 1 -> (2, 3) -> 4
    nodes = [
        {"id": "node_4", "name": "Report", "type": "delay", "depends_on": ["node_2", "node_3"]},
        {"id": "node_2", "name": "Query SQL", "type": "sql", "depends_on": ["node_1"]},
        {"id": "node_3", "name": "Check Redis", "type": "redis", "depends_on": ["node_1"]},
        {"id": "node_1", "name": "Login HTTP", "type": "http", "depends_on": []},
    ]

    sorted_nodes = validate_and_toposort_workflow(nodes)
    order = [n["id"] for n in sorted_nodes]

    # Node 1 must be first
    assert order[0] == "node_1"
    # Node 4 must be last
    assert order[-1] == "node_4"
    # 2 and 3 must appear after 1 and before 4
    assert order.index("node_2") > order.index("node_1")
    assert order.index("node_3") > order.index("node_1")
    assert order.index("node_4") > order.index("node_2")
    assert order.index("node_4") > order.index("node_3")


def test_toposort_cycle_detection():
    # Cycle: A -> B -> C -> A
    nodes = [
        {"id": "A", "depends_on": ["C"]},
        {"id": "B", "depends_on": ["A"]},
        {"id": "C", "depends_on": ["B"]},
    ]
    with pytest.raises(WorkflowDagError) as exc_info:
        validate_and_toposort_workflow(nodes)
    assert "循环依赖" in str(exc_info.value) or "Cycle detected" in str(exc_info.value)


def test_toposort_self_loop_detection():
    nodes = [{"id": "self_loop", "depends_on": ["self_loop"]}]
    with pytest.raises(WorkflowDagError) as exc_info:
        validate_and_toposort_workflow(nodes)
    assert "自环依赖" in str(exc_info.value)


def test_toposort_nonexistent_dependency():
    nodes = [{"id": "node_a", "depends_on": ["phantom_node"]}]
    with pytest.raises(WorkflowDagError) as exc_info:
        validate_and_toposort_workflow(nodes)
    assert "不存在的节点" in str(exc_info.value)


def test_render_context_template():
    context = {"user_id": 999, "token": "jwt_secret_token", "env": "prod"}
    assert render_context_template("https://api.local/users/{{user_id}}", context) == "https://api.local/users/999"
    nested = {
        "headers": {"Authorization": "Bearer {{token}}"},
        "tags": ["env:{{env}}", 123],
    }
    rendered = render_context_template(nested, context)
    assert rendered["headers"]["Authorization"] == "Bearer jwt_secret_token"
    assert rendered["tags"][0] == "env:prod"


@pytest.mark.asyncio
async def test_execute_workflow_dag_mixed_nodes():
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {"token": "jwt-token-12345", "user_id": 88}
    mock_resp.headers = {"Content-Type": "application/json"}

    workflow = {
        "nodes": [
            {
                "id": "step_1_http",
                "name": "用户登录",
                "type": "http",
                "depends_on": [],
                "config": {
                    "url": "http://127.0.0.1:8000/api/v1/auth/login",
                    "method": "POST",
                    "extractions": {"auth_token": "token"},
                },
            },
            {
                "id": "step_2_sql",
                "name": "核查用户余额",
                "type": "sql",
                "depends_on": ["step_1_http"],
                "config": {
                    "query": "SELECT balance FROM user_accounts WHERE token = '{{auth_token}}'",
                },
            },
            {
                "id": "step_3_redis",
                "name": "检查缓存活跃标记",
                "type": "redis",
                "depends_on": ["step_1_http"],
                "config": {
                    "command": "GET",
                    "key": "session:{{auth_token}}",
                },
            },
            {
                "id": "step_4_mobile",
                "name": "移动端刷新界面",
                "type": "mobile",
                "depends_on": ["step_2_sql", "step_3_redis"],
                "config": {
                    "platform": "ios",
                    "action": "tap",
                    "params": {"x": 100, "y": 200},
                },
            },
            {
                "id": "step_5_delay",
                "name": "状态同步等待",
                "type": "delay",
                "depends_on": ["step_4_mobile"],
                "config": {"seconds": 0.01},
            },
        ]
    }

    with patch("httpx.AsyncClient.request", return_value=mock_resp):
        res = await execute_workflow_dag(workflow, initial_context={"trace_id": "test-trace"})

    assert res["status"] == "passed"
    assert res["total_nodes"] == 5
    assert res["executed_nodes"] == 5
    assert len(res["node_results"]) == 5

    # Check variable extracted and passed to subsequent nodes
    assert res["final_context"]["auth_token"] == {"token": "jwt-token-12345", "user_id": 88}

    executed_ids = [n["id"] for n in res["node_results"]]
    assert executed_ids[0] == "step_1_http"
    assert executed_ids[-1] == "step_5_delay"
