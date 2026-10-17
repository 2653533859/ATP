"""低代码可视化漏测血缘与推荐补测 API 单测 (T2.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.visual_coverage_lineage_analyzer import clear_coverage_reports

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_app_and_state():
    clear_coverage_reports()
    mock_user = User(id=1, email="coverage_qa@example.com", username="cov_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    yield
    app.dependency_overrides.clear()
    clear_coverage_reports()


def test_coverage_lineage_api_flow():
    client = TestClient(app)

    nodes = [
        {
            "node_id": "node_req_pay",
            "node_name": "聚合支付下单",
            "category": "requirement",
            "expected_branches": ["success", "timeout_error"],
            "covered_branches": ["success"],
        },
        {
            "node_id": "node_api_refund",
            "node_name": "POST /api/refund",
            "category": "api_endpoint",
            "expected_branches": ["200_OK", "400_INVALID_ID"],
            "covered_branches": [],
        },
    ]

    edges = [
        {
            "edge_id": "e_p1",
            "source_id": "node_req_pay",
            "target_id": "node_api_refund",
            "relationship": "triggers",
        }
    ]

    # 1. 提交漏测血缘分析
    analyze_resp = client.post(
        "/api/v1/coverage/lineage/analyze",
        json={
            "project_id": "proj_fintech",
            "nodes": nodes,
            "edges": edges,
        },
        headers=HEADERS,
    )
    assert analyze_resp.status_code == 200
    report = analyze_resp.json()["report"]
    assert report["total_nodes_count"] == 2
    assert report["gap_nodes_count"] == 2
    report_id = report["report_id"]

    # 2. 获取报告详情
    get_rep_resp = client.get(f"/api/v1/coverage/lineage/{report_id}", headers=HEADERS)
    assert get_rep_resp.status_code == 200
    assert get_rep_resp.json()["report"]["report_id"] == report_id

    # 3. 获取历史列表
    list_resp = client.get("/api/v1/coverage/lineages", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 4. 针对漏测盲区智能合成用例草稿
    synth_resp = client.post(
        "/api/v1/coverage/synthesize",
        json={"gap_nodes": nodes},
        headers=HEADERS,
    )
    assert synth_resp.status_code == 200
    drafts = synth_resp.json()["drafts"]
    assert len(drafts) == 3  # node_req_pay 缺 1，node_api_refund 缺 2
    assert any(d["target_branch"] == "timeout_error" for d in drafts)
