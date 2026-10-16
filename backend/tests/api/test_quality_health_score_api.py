"""全生命周期多维质量健康综合评分 REST API 集成测试 (T4.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.quality_health_composite_score_engine import clear_health_score_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_health_score_store()
    yield
    app.dependency_overrides.clear()
    clear_health_score_store()


def test_quality_health_score_api_flow():
    """测试质量健康评分 API: 计算 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 触发计算
    calc_resp = client.post(
        "/api/v1/gatekeeper/health-score/calculate",
        json={
            "target_name": "release-v4.2.0-final",
            "test_pass_rate_pct": 100.0,
            "code_coverage_pct": 88.0,
            "mutation_score_pct": 82.0,
            "p0_defects_count": 0,
            "p1_defects_count": 0,
            "p2_defects_count": 1,
            "change_risk_score": 8.0,
            "compliance_score_pct": 98.0,
        },
        headers=HEADERS,
    )
    assert calc_resp.status_code == 200
    report_data = calc_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["composite_score"] >= 85.0
    assert report_data["grade"] in ["A+", "A"]

    # 2. 查详情
    get_resp = client.get(f"/api/v1/gatekeeper/health-score/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 查列表
    list_resp = client.get("/api/v1/gatekeeper/health-score/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/gatekeeper/health-score/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
