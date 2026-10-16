"""生产级测试合成数据 REST API 集成测试 (T3.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.synthetic_test_data_generator import clear_synthetic_data_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_synthetic_data_store()
    yield
    app.dependency_overrides.clear()
    clear_synthetic_data_store()


def test_synthetic_data_api_flow():
    """测试合成数据 API 流程: 生成批次 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 触发生成
    gen_resp = client.post(
        "/api/v1/llm-testing/synthetic-data/generate",
        json={
            "dataset_name": "checkout_payloads",
            "row_count": 8,
            "rules": [
                {"field_name": "order_amount", "data_type": "float", "min_value": 1.0, "max_value": 1000.0},
                {"field_name": "buyer_email", "data_type": "email"},
            ],
        },
        headers=HEADERS,
    )
    assert gen_resp.status_code == 200
    data = gen_resp.json()["batch"]
    batch_id = data["batch_id"]
    assert data["total_rows"] == 8
    assert len(data["rows"]) == 8

    # 2. 查批次详情
    get_resp = client.get(f"/api/v1/llm-testing/synthetic-data/batches/{batch_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["batch"]["batch_id"] == batch_id

    # 3. 查列表
    list_resp = client.get("/api/v1/llm-testing/synthetic-data/batches", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/llm-testing/synthetic-data/batches", headers=HEADERS)
    assert clear_resp.status_code == 200
