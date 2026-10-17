"""增量影响面计算与精准用例推荐 REST API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_app_auth():
    mock_user = User(id=1, email="prec_qa@example.com", username="prec_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    yield
    app.dependency_overrides.clear()


def test_diff_analyze_endpoint():
    client = TestClient(app)

    diff = """--- a/discount.py
+++ b/discount.py
@@ -1,4 +1,4 @@
 def calculate_discount(price, rate):
-    return price * rate
+    return price * (rate - 0.05)
"""
    source = """def calculate_discount(price, rate):
    return price * (rate - 0.05)
"""

    resp = client.post(
        "/api/v1/precision-regression/diff/analyze",
        json={
            "diff_text": diff,
            "source_files": {"discount.py": source},
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()["report"]
    assert data["changed_symbols_count"] == 1
    assert data["symbols"][0]["symbol_name"] == "calculate_discount"


def test_recommend_endpoint():
    client = TestClient(app)

    resp = client.post(
        "/api/v1/precision-regression/recommend",
        json={
            "changed_symbols": ["calculate_discount"],
            "total_suite_size": 100,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    res = resp.json()["result"]
    assert res["impacted_endpoints_count"] == 2
    assert res["impacted_cases_count"] == 3
    assert res["regression_reduction_ratio"] == 0.97
    assert res["estimated_time_saved_seconds"] == 970.0


def test_end_to_end_analyze_and_recommend():
    client = TestClient(app)

    diff = """--- a/order.py
+++ b/order.py
@@ -1,4 +1,4 @@
-def checkout(self, user_id, amount):
+def checkout(self, user_id, amount, coupon_code=None):
     pass
"""
    source = """class OrderService:
    def checkout(self, user_id, amount, coupon_code=None):
        pass
"""

    resp = client.post(
        "/api/v1/precision-regression/analyze-and-recommend",
        json={
            "diff_text": diff,
            "source_files": {"order.py": source},
            "total_suite_size": 50,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["diff_symbol_report"]["changed_symbols_count"] == 1
    assert data["diff_symbol_report"]["symbols"][0]["change_type"] == "SIGNATURE_CHANGED"
    assert data["precision_recommendation"]["impacted_cases_count"] >= 1


def test_coverage_and_lineage_registration():
    client = TestClient(app)

    # 1. 动态注册新血缘
    reg_resp = client.post(
        "/api/v1/precision-regression/lineage/register",
        json={
            "symbol_name": "RefundService.process_refund",
            "endpoint": "POST /api/v1/refunds/apply",
            "case_id": "case_refund_flow_01",
            "case_name": "用户退款申请流程测试",
            "cost_seconds": 18.0,
            "priority": "P0",
        },
        headers=HEADERS,
    )
    assert reg_resp.status_code == 200
    assert "成功建立血缘节点" in reg_resp.json()["message"]

    # 2. 反向查询用例覆盖
    cov_resp = client.get("/api/v1/precision-regression/coverage/case_refund_flow_01", headers=HEADERS)
    assert cov_resp.status_code == 200
    cov = cov_resp.json()["coverage"]
    assert "POST /api/v1/refunds/apply" in cov["covered_endpoints"]
    assert "RefundService.process_refund" in cov["covered_symbols"]
