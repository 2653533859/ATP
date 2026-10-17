"""混合工作流编排与执行管理 API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.hybrid_workflow_dag_engine import clear_workflow_runs

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_app_and_state():
    clear_workflow_runs()
    mock_user = User(id=1, email="workflow_engineer@example.com", username="wf_eng", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    yield
    app.dependency_overrides.clear()
    clear_workflow_runs()


def test_workflow_api_full_flow():
    client = TestClient(app)

    wf_id = "wf_e2e_hybrid_test"

    nodes = [
        {
            "node_id": "step_1_http",
            "node_name": "API 创建购物车商品",
            "node_type": "http_request",
            "config": {"url": "/api/v1/cart", "method": "POST"},
        },
        {
            "node_id": "step_2_web",
            "node_name": "Web UI 结算确认",
            "node_type": "web_ui_step",
            "config": {"action": "click_checkout"},
        },
        {
            "node_id": "step_3_db",
            "node_name": "Postgres 最终对账",
            "node_type": "database_query",
            "config": {"db_type": "postgresql"},
        },
    ]

    edges = [
        {"edge_id": "e1", "source_node_id": "step_1_http", "target_node_id": "step_2_web"},
        {"edge_id": "e2", "source_node_id": "step_2_web", "target_node_id": "step_3_db"},
    ]

    # 1. 保存工作流草稿
    save_resp = client.post(
        "/api/v1/workflow/save",
        json={
            "workflow_id": wf_id,
            "workflow_name": "全链路跨端结算自动化工作流",
            "nodes": nodes,
            "edges": edges,
        },
        headers=HEADERS,
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["workflow_id"] == wf_id
    assert save_resp.json()["nodes_count"] == 3

    # 2. 读取工作流草稿
    get_draft_resp = client.get(f"/api/v1/workflow/draft/{wf_id}", headers=HEADERS)
    assert get_draft_resp.status_code == 200
    assert get_draft_resp.json()["draft"]["workflow_name"] == "全链路跨端结算自动化工作流"

    # 3. 触发工作流执行
    exec_resp = client.post(
        "/api/v1/workflow/execute",
        json={
            "workflow_id": wf_id,
            "workflow_name": "全链路跨端结算自动化工作流",
            "nodes": nodes,
            "edges": edges,
            "initial_variables": {"env": "staging"},
        },
        headers=HEADERS,
    )
    assert exec_resp.status_code == 200
    report = exec_resp.json()["report"]
    assert report["workflow_id"] == wf_id
    assert report["total_nodes"] == 3
    assert report["executed_nodes_count"] == 3
    assert report["status"] == "SUCCESS"
    run_id = report["run_id"]

    # 4. 获取运行报告
    run_resp = client.get(f"/api/v1/workflow/run/{run_id}", headers=HEADERS)
    assert run_resp.status_code == 200
    assert run_resp.json()["report"]["run_id"] == run_id

    # 5. 变量总线独立求值测试
    resolve_resp = client.post(
        "/api/v1/workflow/variable/resolve",
        json={
            "raw_config": {"url": "https://{{host}}/orders/{{order.id}}"},
            "context_variables": {"host": "shop.test", "order": {"id": "ORD_888"}},
        },
        headers=HEADERS,
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["resolved_config"]["url"] == "https://shop.test/orders/ORD_888"
