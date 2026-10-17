"""全链路分布式追踪与 OpenTelemetry 观测 REST API 集成测试 (T1.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.w3c_trace_context_injector import clear_injected_trace_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_injected_trace_store()
    yield
    app.dependency_overrides.clear()
    clear_injected_trace_store()


def test_observability_trace_api_flow():
    """测试完整流程：注入 W3C TraceContext -> 从 Headers 提取 -> 衍生下游子 Span -> 查询上下文列表 -> 清空历史。"""
    client = TestClient(app)

    # 1. 注入 W3C TraceContext
    inj_resp = client.post(
        "/api/v1/observability/trace/inject",
        json={
            "headers": {"Content-Type": "application/json"},
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
            "span_id": "00f067aa0ba902b7",
            "sampled": True,
            "tracestate": "atp=c:stress;s:1",
            "carrier_type": "http",
        },
        headers=HEADERS,
    )
    assert inj_resp.status_code == 200
    inj_data = inj_resp.json()
    assert inj_data["context"]["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert inj_data["context"]["span_id"] == "00f067aa0ba902b7"
    assert "traceparent" in inj_data["injected_headers"]
    traceparent_val = inj_data["injected_headers"]["traceparent"]
    assert traceparent_val == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    # 2. 从 Headers 提取 TraceContext
    ext_resp = client.post(
        "/api/v1/observability/trace/extract",
        json={"headers": inj_data["injected_headers"]},
        headers=HEADERS,
    )
    assert ext_resp.status_code == 200
    ext_data = ext_resp.json()
    assert ext_data["context"]["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert ext_data["context"]["span_id"] == "00f067aa0ba902b7"
    assert ext_data["context"]["sampled"] is True

    # 测试提取非法 traceparent 报错 400
    bad_resp = client.post(
        "/api/v1/observability/trace/extract",
        json={"headers": {"traceparent": "00-00000000000000000000000000000000-00f067aa0ba902b7-01"}},
        headers=HEADERS,
    )
    assert bad_resp.status_code == 400

    # 3. 衍生下游子 Span
    child_resp = client.post(
        "/api/v1/observability/trace/child-span",
        json={
            "parent_traceparent": traceparent_val,
            "parent_tracestate": "atp=c:stress;s:1",
            "new_span_id": "1122334455667788",
            "new_tracestate_tag": "step=checkout",
        },
        headers=HEADERS,
    )
    assert child_resp.status_code == 200
    child_data = child_resp.json()
    assert child_data["child_context"]["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert child_data["child_context"]["parent_span_id"] == "00f067aa0ba902b7"
    assert child_data["child_context"]["span_id"] == "1122334455667788"
    assert "step=checkout" in child_data["child_context"]["tracestate"]

    # 4. 查询注入历史列表
    list_resp = client.get("/api/v1/observability/trace/contexts", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 2

    # 5. 清空上下文
    del_resp = client.delete("/api/v1/observability/trace/contexts", headers=HEADERS)
    assert del_resp.status_code == 200
    empty_resp = client.get("/api/v1/observability/trace/contexts", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
