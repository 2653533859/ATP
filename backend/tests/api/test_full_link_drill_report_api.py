"""全链路压力演练综合审计报告 REST API 集成测试 (T4.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.full_link_stress_drill_reporter import clear_full_drill_report_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_full_drill_report_store()
    yield
    app.dependency_overrides.clear()
    clear_full_drill_report_store()


def test_full_link_drill_report_api_flow():
    """测试演练报告 API 完整流程: 生成报告 -> 查详情 -> 导出 Markdown -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 提交指标并生成报告
    gen_resp = client.post(
        "/api/v1/stress/drill-report/summary/generate",
        json={
            "drill_id": "drill_pre_launch_01",
            "scenario_name": "支付结算核心全链路演练",
            "peak_concurrency_vu": 3000,
            "peak_tps": 5200.0,
            "p99_latency_ms": 110.0,
            "error_rate_pct": 0.005,
            "knee_point_concurrency": 3000,
            "knee_point_tps": 5200.0,
            "max_db_watermark_pct": 62.0,
            "max_redis_watermark_pct": 52.0,
            "max_mq_backlog": 900,
            "circuit_breaker_triggered": False,
            "failover_rto_ms": 1200.0,
        },
        headers=HEADERS,
    )
    assert gen_resp.status_code == 200
    report_data = gen_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["is_production_approved"] is True
    assert report_data["overall_drill_grade"] == "GRADE_A_EXCELLENT"

    # 2. 查单次报告详情
    get_resp = client.get(f"/api/v1/stress/drill-report/summary/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 导出 Markdown
    md_resp = client.get(f"/api/v1/stress/drill-report/summary/reports/{report_id}/markdown", headers=HEADERS)
    assert md_resp.status_code == 200
    assert "生产全链路压测综合审计与容量规划报告" in md_resp.json()["markdown"]

    # 4. 获取历史列表
    list_resp = client.get("/api/v1/stress/drill-report/summary/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 5. 清空
    clear_resp = client.delete("/api/v1/stress/drill-report/summary/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/stress/drill-report/summary/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
