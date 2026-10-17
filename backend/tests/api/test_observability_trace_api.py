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


def test_execution_trace_propagation_api():
    """测试任务执行上下文绑定、步骤多步衍生注入、Trail 查询与 Sessions 清空。"""
    client = TestClient(app)

    # 1. 绑定执行任务
    bind_resp = client.post(
        "/api/v1/observability/trace/execution/bind",
        json={
            "run_id": "run_api_test_001",
            "case_id": "case_payment",
            "carrier_type": "celery_async",
            "metadata": {"executor": "httpx"},
        },
        headers=HEADERS,
    )
    assert bind_resp.status_code == 200
    session_data = bind_resp.json()["session"]
    root_trace_id = session_data["trace_id"]
    assert len(root_trace_id) == 32

    # 2. 步骤 1 衍生注入
    step1_resp = client.post(
        "/api/v1/observability/trace/execution/step",
        json={
            "run_id": "run_api_test_001",
            "step_index": 1,
            "step_name": "创建订单",
            "request_headers": {"Content-Type": "application/json"},
            "carrier_type": "http",
        },
        headers=HEADERS,
    )
    assert step1_resp.status_code == 200
    step1_data = step1_resp.json()["step_record"]
    assert root_trace_id in step1_data["traceparent"]
    assert "traceparent" in step1_data["injected_headers"]

    # 3. 步骤 2 衍生注入
    step2_resp = client.post(
        "/api/v1/observability/trace/execution/step",
        json={
            "run_id": "run_api_test_001",
            "step_index": 2,
            "step_name": "扣款支付",
            "request_headers": {"Authorization": "Bearer pay_key"},
            "carrier_type": "http",
        },
        headers=HEADERS,
    )
    assert step2_resp.status_code == 200
    step2_data = step2_resp.json()["step_record"]
    assert root_trace_id in step2_data["traceparent"]
    assert step2_data["step_span_id"] != step1_data["step_span_id"]

    # 4. 获取执行 Trail
    trail_resp = client.get("/api/v1/observability/trace/trail/run_api_test_001", headers=HEADERS)
    assert trail_resp.status_code == 200
    trail_data = trail_resp.json()["session"]
    assert trail_data["steps_count"] == 2
    assert len(trail_data["steps"]) == 2

    # 5. 查询 Sessions 列表并清空
    sess_resp = client.get("/api/v1/observability/trace/sessions", headers=HEADERS)
    assert sess_resp.status_code == 200
    assert sess_resp.json()["total"] >= 1

    del_resp = client.delete("/api/v1/observability/trace/sessions", headers=HEADERS)
    assert del_resp.status_code == 200
    empty_sess = client.get("/api/v1/observability/trace/sessions", headers=HEADERS)


def test_otlp_export_api():
    """测试将 Span 批量导出为 OTLP 格式、查询导出批次并清空缓冲区。"""
    client = TestClient(app)

    # 1. 导出 Spans
    exp_resp = client.post(
        "/api/v1/observability/trace/export",
        json={
            "service_name": "checkout-suite",
            "target_endpoint": "http://jaeger:4318/v1/traces",
            "spans": [
                {
                    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
                    "span_id": "00f067aa0ba902b7",
                    "name": "POST /order",
                    "kind": 3,
                    "attributes": {"http.status": 200},
                    "status_code": 1,
                }
            ],
            "extra_resource_attributes": {"cluster": "shanghai-zone-a"},
        },
        headers=HEADERS,
    )
    assert exp_resp.status_code == 200
    exp_data = exp_resp.json()["export_result"]
    assert exp_data["status"] == "SUCCESS"
    assert exp_data["spans_count"] == 1
    assert "otlp_payload" in exp_data

    # 2. 查询导出的批次
    list_resp = client.get("/api/v1/observability/trace/exports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 3. 清空导出缓冲区
    del_resp = client.delete("/api/v1/observability/trace/exports", headers=HEADERS)
    assert del_resp.status_code == 200
    empty_resp = client.get("/api/v1/observability/trace/exports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
