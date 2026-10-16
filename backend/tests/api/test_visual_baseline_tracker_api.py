"""视觉基线版本化管理 REST API 集成测试 (T1.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.visual_golden_baseline_branch_tracker import clear_baseline_tracker_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_baseline_tracker_store()
    yield
    app.dependency_overrides.clear()
    clear_baseline_tracker_store()


def test_visual_baseline_api_flow():
    """测试基线管理 API 流程: 登记 -> 提升 -> 跨分支比对 -> 查详情 -> 清空。"""
    client = TestClient(app)

    # 1. 登记主干基线
    main_resp = client.post(
        "/api/v1/visual/baselines/register",
        json={
            "page_route": "/order/list",
            "branch_name": "main",
            "version_tag": "v1.0.0",
            "viewport_snapshots": {"DESKTOP": "hash_1001"},
            "is_active_golden": True,
        },
        headers=HEADERS,
    )
    assert main_resp.status_code == 200
    main_b_id = main_resp.json()["baseline"]["baseline_id"]

    # 2. 登记特性分支基线并提升
    feat_resp = client.post(
        "/api/v1/visual/baselines/register",
        json={
            "page_route": "/order/list",
            "branch_name": "feat/order-opt",
            "version_tag": "v1.1.0",
            "viewport_snapshots": {"DESKTOP": "hash_1002"},
            "changelog": "重构订单表格间距",
        },
        headers=HEADERS,
    )
    assert feat_resp.status_code == 200
    feat_b_id = feat_resp.json()["baseline"]["baseline_id"]

    promote_resp = client.post(f"/api/v1/visual/baselines/{feat_b_id}/promote", headers=HEADERS)
    assert promote_resp.status_code == 200
    assert promote_resp.json()["baseline"]["is_active_golden"] is True

    # 3. 跨分支比对
    compare_resp = client.post(
        "/api/v1/visual/baselines/cross-branch-compare",
        json={
            "page_route": "/order/list",
            "source_branch": "feat/order-opt",
            "target_branch": "main",
        },
        headers=HEADERS,
    )
    assert compare_resp.status_code == 200
    report = compare_resp.json()["report"]
    assert report["evolution_type"] == "INTENTIONAL_REDESIGN"
    assert report["has_viewport_drifts"] is True

    # 4. 查详情与清空
    get_resp = client.get(f"/api/v1/visual/baselines/{main_b_id}", headers=HEADERS)
    assert get_resp.status_code == 200

    clear_resp = client.delete("/api/v1/visual/baselines/clear", headers=HEADERS)
    assert clear_resp.status_code == 200
