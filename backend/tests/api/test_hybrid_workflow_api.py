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


def test_hybrid_workflow_evidence_and_guard_endpoints():
    client = TestClient(app)

    wf_id = "wf_guard_test"
    nodes = [
        {"node_id": "step_1", "node_name": "HTTP 节点", "node_type": "http_request", "config": {}},
    ]

    # 1. 执行并生成运行记录
    exec_resp = client.post(
        "/api/v1/workflow/execute",
        json={
            "workflow_id": wf_id,
            "workflow_name": "沙箱测试流",
            "nodes": nodes,
            "edges": [],
        },
        headers=HEADERS,
    )
    assert exec_resp.status_code == 200
    run_id = exec_resp.json()["report"]["run_id"]

    # 2. 为运行记录生成 64 位 SHA-256 签名证书
    sign_resp = client.post(
        "/api/v1/workflow/evidence/sign",
        json={"run_id": run_id, "signer": "atp-auditor"},
        headers=HEADERS,
    )
    assert sign_resp.status_code == 200
    cert = sign_resp.json()["certificate"]
    assert len(cert["evidence_sha256"]) == 64

    # 3. 正常验签
    verify_resp = client.post(
        "/api/v1/workflow/evidence/verify",
        json={
            "certificate": cert,
            "report": exec_resp.json()["report"],
        },
        headers=HEADERS,
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["is_valid"] is True
    assert "EVIDENCE_VERIFIED" in verify_resp.json()["message"]

    # 4. 获取证书详情与全量列表
    cert_resp = client.get(f"/api/v1/workflow/evidence/{run_id}", headers=HEADERS)
    assert cert_resp.status_code == 200
    assert cert_resp.json()["certificate"]["evidence_sha256"] == cert["evidence_sha256"]

    list_certs_resp = client.get("/api/v1/workflow/evidences", headers=HEADERS)
    assert list_certs_resp.status_code == 200
    assert list_certs_resp.json()["total"] >= 1

    # 5. 查询看门狗违规历史
    viol_resp = client.get("/api/v1/workflow/guard/violations", headers=HEADERS)
    assert viol_resp.status_code == 200
    assert isinstance(viol_resp.json()["violations"], list)
