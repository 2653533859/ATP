"""智能缺陷聚类去重与聚合管理 REST API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.api.v1.defect_intelligence_api import clear_defect_intelligence_store
from app.main import app
from app.models.user import User

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_api_state():
    mock_user = User(id=1, email="defect_qa@example.com", username="defect_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_defect_intelligence_store()
    yield
    app.dependency_overrides.clear()
    clear_defect_intelligence_store()


def test_list_and_get_clusters():
    client = TestClient(app)

    # 1. 查询默认种子主缺陷组
    resp = client.get("/api/v1/defect-intelligence/clusters", headers=HEADERS)
    assert resp.status_code == 200
    clusters = resp.json()
    assert len(clusters) >= 1
    cid = clusters[0]["cluster_id"]

    # 2. 查询特定聚类详情
    detail_resp = client.get(f"/api/v1/defect-intelligence/clusters/{cid}", headers=HEADERS)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["cluster_id"] == cid
    assert detail_resp.json()["total_failures_count"] >= 1

    # 3. 404 测试
    not_found_resp = client.get("/api/v1/defect-intelligence/clusters/non_existent_999", headers=HEADERS)
    assert not_found_resp.status_code == 404


def test_extract_fingerprint_endpoint():
    client = TestClient(app)

    resp = client.post(
        "/api/v1/defect-intelligence/fingerprint",
        json={
            "raw_error_message": "ConnectionRefusedError: Port 6379 unreachable at 0x7fa123",
            "raw_stack_trace": '  File "/app/services/cache.py", line 15, in get_cache\n    conn()',
            "exception_type": "ConnectionRefusedError",
            "target_endpoint": "/api/v1/cache/item",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["failure_fingerprint"]) == 64
    assert data["exception_type"] == "ConnectionRefusedError"
    assert "<HEX_ADDR>" in data["normalized_message"]


def test_batch_cluster_deduplicate_endpoint():
    client = TestClient(app)

    failures = [
        {
            "run_id": "run_001",
            "case_id": f"c_{i}",
            "case_name": f"用例_{i}",
            "error_message": f"PostgresTimeout: slow query at 0x{i}00",
            "stack_trace": '  File "/app/services/db.py", line 20, in query\n    exec()',
            "target_service": "db-service",
        }
        for i in range(1, 6)
    ]

    resp = client.post(
        "/api/v1/defect-intelligence/cluster-deduplicate",
        json={
            "failures": failures,
            "similarity_threshold": 0.80,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["total_raw_failures"] == 5
    assert res_data["total_deduplicated_clusters"] == 1
    assert res_data["deduplication_ratio_pct"] == 80.0  # 5 个去重为 1 个，节省 80%

    cl = res_data["clusters"][0]
    assert len(cl["linked_case_ids"]) == 5


def test_merge_cluster_to_defect():
    client = TestClient(app)

    clusters_resp = client.get("/api/v1/defect-intelligence/clusters", headers=HEADERS)
    cid = clusters_resp.json()[0]["cluster_id"]

    merge_resp = client.post(
        f"/api/v1/defect-intelligence/clusters/{cid}/merge",
        json={"target_defect_id": "JIRA-BUG-8899"},
        headers=HEADERS,
    )
    assert merge_resp.status_code == 200
    assert merge_resp.json()["status"] == "success"
    assert merge_resp.json()["cluster"]["existing_defect_id"] == "JIRA-BUG-8899"
