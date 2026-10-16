"""全景质量审计报告 REST API 集成测试 (T4.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.comprehensive_test_audit_report_generator import clear_audit_report_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_audit_report_store()
    yield
    app.dependency_overrides.clear()
    clear_audit_report_store()


def test_audit_report_api_flow():
    """测试全景审计报告 API 流程: 生成 -> 验签 -> Markdown导出 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 生成报告
    gen_resp = client.post(
        "/api/v1/gatekeeper/audit-report/generate",
        json={
            "target_version": "v4.2.0-release",
            "project_name": "ATP 自动化测试平台",
        },
        headers=HEADERS,
    )
    assert gen_resp.status_code == 200
    report_data = gen_resp.json()["report"]
    report_id = report_data["report_id"]
    assert len(report_data["sha256_audit_fingerprint"]) == 64

    # 2. 验签完整性
    verify_resp = client.post(
        f"/api/v1/gatekeeper/audit-report/{report_id}/verify",
        json={},
        headers=HEADERS,
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["valid"] is True

    # 3. 查详情
    get_resp = client.get(f"/api/v1/gatekeeper/audit-report/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 4. 导出 Markdown
    md_resp = client.get(f"/api/v1/gatekeeper/audit-report/reports/{report_id}/markdown", headers=HEADERS)
    assert md_resp.status_code == 200
    assert "text/markdown" in md_resp.headers["content-type"]
    assert "# ATP 自动化测试平台 交付与发版质量全景审计报告" in md_resp.text

    # 5. 查列表
    list_resp = client.get("/api/v1/gatekeeper/audit-report/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 6. 清空
    clear_resp = client.delete("/api/v1/gatekeeper/audit-report/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
