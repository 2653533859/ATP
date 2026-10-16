"""页面内存泄漏与 DOM 幽灵引用 REST API 集成测试 (T4.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.client_memory_leak_dom_detachment_detector import clear_memory_leak_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_memory_leak_store()
    yield
    app.dependency_overrides.clear()
    clear_memory_leak_store()


def test_client_memory_leak_api_flow():
    """测试内存泄露分析 API 流程: 分析快照 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 提交分析
    analyze_resp = client.post(
        "/api/v1/client-perf/memory-leak/analyze",
        json={
            "page_or_scenario": "device_center_tabs",
            "snapshots": [
                {"js_heap_used_bytes": 10000000, "event_listener_count": 5},
                {"js_heap_used_bytes": 10500000, "event_listener_count": 5},
            ],
            "detached_nodes": [],
        },
        headers=HEADERS,
    )
    assert analyze_resp.status_code == 200
    report_data = analyze_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["initial_heap_bytes"] == 10000000
    assert report_data["has_critical_leak"] is False

    # 2. 查询单次报告详情
    get_resp = client.get(f"/api/v1/client-perf/memory-leak/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 查列表
    list_resp = client.get("/api/v1/client-perf/memory-leak/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/client-perf/memory-leak/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/client-perf/memory-leak/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
