"""消息队列影子队列分流隔离 REST API 集成测试 (T1.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.shadow_mq_queue_router import clear_mq_shunting_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_mq_shunting_store()
    yield
    app.dependency_overrides.clear()
    clear_mq_shunting_store()


def test_shadow_mq_shunting_api_flow():
    """测试 MQ 分流 API 完整链路: 注册规则 -> 路由消息 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 注册新规则
    reg_resp = client.post(
        "/api/v1/stress/shadow-traffic/mq-shunting/rules",
        json={
            "production_topic": "topic_order_created",
            "shadow_topic": "__shadow_topic_order_created__",
            "dead_letter_queue": "__shadow_topic_order_dlq__",
            "bypass_action": "REDIRECT_SHADOW_CONSUMER",
        },
        headers=HEADERS,
    )
    assert reg_resp.status_code == 200
    assert reg_resp.json()["rule"]["production_topic"] == "topic_order_created"

    # 2. 获取规则列表
    rules_resp = client.get("/api/v1/stress/shadow-traffic/mq-shunting/rules", headers=HEADERS)
    assert rules_resp.status_code == 200
    assert rules_resp.json()["total"] >= 4

    # 3. 路由消息
    route_resp = client.post(
        "/api/v1/stress/shadow-traffic/mq-shunting/route",
        json={
            "cluster_name": "prod_kafka_main",
            "messages": [
                {
                    "message_id": "msg_001",
                    "topic": "topic_order_created",
                    "headers": {"__atp_shadow_taint__": "true"},
                    "is_shadow_traffic": True,
                }
            ],
        },
        headers=HEADERS,
    )
    assert route_resp.status_code == 200
    report_data = route_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["redirected_to_shadow_count"] == 1

    # 4. 查详情与列表
    get_resp = client.get(f"/api/v1/stress/shadow-traffic/mq-shunting/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    list_resp = client.get("/api/v1/stress/shadow-traffic/mq-shunting/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 5. 清空
    clear_resp = client.delete("/api/v1/stress/shadow-traffic/mq-shunting/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/stress/shadow-traffic/mq-shunting/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
