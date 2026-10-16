"""Web Vitals 全景审计报告 REST API 集成测试 (T4.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.web_vitals_experience_audit_reporter import clear_web_vitals_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_web_vitals_store()
    yield
    app.dependency_overrides.clear()
    clear_web_vitals_store()


def test_client_web_vitals_api_flow():
    """测试 Web Vitals API 完整流程: 生成报告 -> 查详情 -> 导出 Markdown -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 生成报告
    gen_resp = client.post(
        "/api/v1/client-perf/web-vitals-report/generate",
        json={
            "target_url_or_page": "https://atp.example.com/plans",
            "lcp_ms": 2100.0,
            "inp_ms": 150.0,
            "cls_score": 0.05,
            "fcp_ms": 1100.0,
            "ttfb_ms": 400.0,
        },
        headers=HEADERS,
    )
    assert gen_resp.status_code == 200
    report_data = gen_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["overall_cwv_passed"] is True
    assert report_data["performance_score_pct"] == 100.0

    # 2. 查询单次报告
    get_resp = client.get(f"/api/v1/client-perf/web-vitals-report/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 导出 Markdown
    md_resp = client.get(f"/api/v1/client-perf/web-vitals-report/reports/{report_id}/markdown", headers=HEADERS)
    assert md_resp.status_code == 200
    assert "Web Vitals 核心体验审计报告" in md_resp.json()["markdown"]

    # 4. 查列表
    list_resp = client.get("/api/v1/client-perf/web-vitals-report/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 5. 清空
    clear_resp = client.delete("/api/v1/client-perf/web-vitals-report/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/client-perf/web-vitals-report/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
