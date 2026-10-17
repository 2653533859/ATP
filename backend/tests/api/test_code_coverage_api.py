"""全链路代码覆盖率动态染色与增量发布准入 REST API 单测 (T1.3)"""

from __future__ import annotations

import json
import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.api.v1.code_coverage_api import clear_coverage_store
from app.main import app
from app.models.user import User

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_api_state():
    mock_user = User(id=1, email="cov_qa@example.com", username="cov_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_coverage_store()
    yield
    app.dependency_overrides.clear()
    clear_coverage_store()


def test_list_and_get_reports():
    client = TestClient(app)

    # 1. 查询预置覆盖率报告列表
    resp = client.get("/api/v1/code-coverage/reports", headers=HEADERS)
    assert resp.status_code == 200
    reports = resp.json()
    assert len(reports) >= 1
    rep_id = reports[0]["report_id"]

    # 2. 查询特定覆盖率报告详情
    detail_resp = client.get(f"/api/v1/code-coverage/reports/{rep_id}", headers=HEADERS)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["report_id"] == rep_id
    assert "backend/app/services/payment.py" in detail_resp.json()["files"]

    # 3. 404 测试
    not_found_resp = client.get("/api/v1/code-coverage/reports/non_existent_999", headers=HEADERS)
    assert not_found_resp.status_code == 404


def test_ingest_coverage_report():
    client = TestClient(app)

    # 上报 Coverage.py JSON
    sample_json = {
        "files": {
            "app/calc.py": {
                "executed_lines": [1, 2],
                "missing_lines": [],
                "summary": {"covered_lines": 2, "missing_lines": 0},
            }
        }
    }
    ingest_resp = client.post(
        "/api/v1/code-coverage/ingest",
        json={
            "report_format": "coverage_py",
            "content": json.dumps(sample_json),
            "project_id": "test_proj",
            "commit_id": "git_c1",
        },
        headers=HEADERS,
    )
    assert ingest_resp.status_code == 200
    data = ingest_resp.json()
    assert data["total_files"] == 1
    assert data["overall_line_coverage_pct"] == 100.0

    # 错误格式 400 校验
    err_resp = client.post(
        "/api/v1/code-coverage/ingest",
        json={
            "report_format": "unsupported_unknown_format",
            "content": "abc",
        },
        headers=HEADERS,
    )
    assert err_resp.status_code == 400


def test_diff_staining_and_file_detail():
    client = TestClient(app)

    diff_text = """diff --git a/backend/app/services/payment.py b/backend/app/services/payment.py
--- a/backend/app/services/payment.py
+++ b/backend/app/services/payment.py
@@ -6,3 +6,3 @@
+    if amount > 100:
+        execute_charge()
+    else:
+        fallback_charge()
"""
    diff_resp = client.post(
        "/api/v1/code-coverage/diff-staining",
        json={
            "diff_text": diff_text,
            "base_commit": "main",
            "target_commit": "feature/payment",
        },
        headers=HEADERS,
    )
    assert diff_resp.status_code == 200
    diff_data = diff_resp.json()
    assert diff_data["total_changed_files"] >= 1
    diff_report_id = diff_data["diff_report_id"]

    # 查询文件染色详情
    file_staining_resp = client.get(
        f"/api/v1/code-coverage/files/staining?diff_report_id={diff_report_id}&file_path=backend/app/services/payment.py",
        headers=HEADERS,
    )
    assert file_staining_resp.status_code == 200
    staining_detail = file_staining_resp.json()
    assert staining_detail["file_path"] == "backend/app/services/payment.py"
    assert "stained_lines" in staining_detail
    assert "red_uncovered_lines" in staining_detail
