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


def test_clock_skew_compensation_api():
    """测试跨网络时钟偏移补偿、Span 因果对齐、历史查询与清空 API。"""
    client = TestClient(app)

    # 1. 提交客户端测试步骤与服务调用链进行时钟校准
    req_payload = {
        "client_step_span": {
            "span_id": "step_span_99",
            "start_time_ms": 1000.0,
            "end_time_ms": 1200.0,
        },
        "server_spans": [
            {
                "span_id": "server_span_01",
                "service_name": "payment-api",
                "start_time_ms": 1060.0,  # 存在 +40ms 偏移
                "end_time_ms": 1220.0,
            }
        ],
        "service_name": "payment-api",
    }

    resp = client.post(
        "/api/v1/observability/trace/skew-compensate",
        json=req_payload,
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "calibration" in data
    assert data["calibration"]["is_skew_detected"] is True
    assert len(data["aligned_spans"]) == 1
    aligned = data["aligned_spans"][0]
    assert aligned["clock_skew_compensated"] is True
    assert aligned["start_time_ms"] >= 1000.0
    assert aligned["end_time_ms"] <= 1200.0

    # 2. 查询校准记录
    list_resp = client.get("/api/v1/observability/trace/skew-calibrations", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 3. 清空校准记录
    del_resp = client.delete("/api/v1/observability/trace/skew-calibrations", headers=HEADERS)
    assert del_resp.status_code == 200
    empty_resp = client.get("/api/v1/observability/trace/skew-calibrations", headers=HEADERS)
    assert empty_resp.json()["total"] == 0


def test_deep_dive_analysis_api():
    """测试异常步骤调用链深潜下钻、首因定位、诊断历史查询与清空 API。"""
    client = TestClient(app)

    # 1. 提交异常步骤深潜分析请求
    req_payload = {
        "step_context": {
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
            "name": "步骤 2: 扣减用户积分",
            "status": "FAILED",
            "error_message": "下游积分服务返回 500 异常",
        },
        "spans": [
            {
                "span_id": "span_pts_svc",
                "service_name": "points-service",
                "name": "DeductPoints",
                "duration_ms": 85.0,
                "status": {"code": "ERROR", "message": "账户已冻结，无法扣减积分"},
                "attributes": {
                    "http.status_code": 500,
                    "exception.message": "账户已冻结，无法扣减积分",
                    "exception.stacktrace": "Traceback: AccountFrozenException at points.py:102",
                },
            }
        ],
        "slow_query_threshold_ms": 150.0,
    }

    resp = client.post(
        "/api/v1/observability/trace/deep-dive",
        json=req_payload,
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "diagnosis" in data
    diag = data["diagnosis"]
    assert diag["attribution_type"] == "DOWNSTREAM_SERVICE_ERROR"
    assert diag["root_cause_service"] == "points-service"
    assert "账户已冻结" in diag["error_message"]
    assert "AccountFrozenException" in diag["stack_trace"]

    # 2. 查询诊断历史
    list_resp = client.get("/api/v1/observability/trace/diagnoses", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 3. 清空诊断历史
    del_resp = client.delete("/api/v1/observability/trace/diagnoses", headers=HEADERS)
    assert del_resp.status_code == 200
    empty_resp = client.get("/api/v1/observability/trace/diagnoses", headers=HEADERS)
    assert empty_resp.json()["total"] == 0


def test_trace_lineage_api():
    """测试跨协议多跳调用链拓扑重构、单链查询、列表与清空 API。"""
    client = TestClient(app)

    trace_id = "f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5"

    # 1. 提交跨协议 Span 重构请求
    req_payload = {
        "trace_id": trace_id,
        "spans": [
            {
                "span_id": "span_root_gw",
                "name": "GET /api/v1/items",
                "service_name": "api-gateway",
                "duration_ms": 110.0,
            },
            {
                "span_id": "span_child_cache",
                "parent_span_id": "span_root_gw",
                "name": "GET user_cache",
                "service_name": "redis-cluster",
                "duration_ms": 12.0,
                "attributes": {"db.system": "redis"},
            },
            {
                "span_id": "span_child_db",
                "parent_span_id": "span_root_gw",
                "name": "SELECT items",
                "service_name": "item-db",
                "duration_ms": 55.0,
                "attributes": {"db.system": "mysql"},
            },
        ],
    }

    resp = client.post(
        "/api/v1/observability/trace/lineage",
        json=req_payload,
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "lineage" in data
    lineage = data["lineage"]
    assert lineage["trace_id"] == trace_id
    assert lineage["total_spans"] == 3
    assert lineage["services_count"] == 3
    assert "redis" in lineage["protocols_covered"]
    assert "mysql" in lineage["protocols_covered"]
    assert len(lineage["nodes"]) == 3
    assert len(lineage["edges"]) == 2

    # 2. 查询指定 TraceID 血缘
    detail_resp = client.get(f"/api/v1/observability/trace/lineage/{trace_id}", headers=HEADERS)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["lineage"]["trace_id"] == trace_id

    # 3. 查询全量血缘列表
    list_resp = client.get("/api/v1/observability/trace/lineages", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 4. 清空血缘记录
    del_resp = client.delete("/api/v1/observability/trace/lineages", headers=HEADERS)
    assert del_resp.status_code == 200
    empty_resp = client.get("/api/v1/observability/trace/lineages", headers=HEADERS)
    assert empty_resp.json()["total"] == 0


def test_trace_sampling_and_sanitizing_api():
    """测试采样评估、Span 敏感信息脱敏、配置读取与动态更新 API。"""
    client = TestClient(app)

    # 1. 评估采样策略 (评估错误链路是否强制采样)
    eval_resp = client.post(
        "/api/v1/observability/trace/sampling/evaluate",
        json={
            "trace_id": "3af1234577b34da6a3ce929d0e0e1122",
            "is_error": True,
            "duration_ms": 120.0,
        },
        headers=HEADERS,
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["sampled"] is True
    assert "ERROR_PRIORITY_FORCED" in eval_resp.json()["decision_reason"]

    # 2. 批量执行 Span 脱敏过滤
    sanitize_resp = client.post(
        "/api/v1/observability/trace/sampling/sanitize",
        json={
            "spans": [
                {
                    "span_id": "span_test_01",
                    "name": "GET /api/user?token=secret123",
                    "attributes": {
                        "authorization": "Bearer eyJhbGciOi...",
                        "user_phone": "13912345678",
                        "password": "my_password",
                    },
                }
            ]
        },
        headers=HEADERS,
    )
    assert sanitize_resp.status_code == 200
    cleaned = sanitize_resp.json()["sanitized_spans"][0]
    assert "secret123" not in cleaned["name"]
    assert cleaned["attributes"]["password"] == "******"
    assert "139****5678" in cleaned["attributes"]["user_phone"]

    # 3. 获取并更新采样配置
    cfg_resp = client.get("/api/v1/observability/trace/sampling/config", headers=HEADERS)
    assert cfg_resp.status_code == 200
    assert "config" in cfg_resp.json()

    up_resp = client.put(
        "/api/v1/observability/trace/sampling/config",
        json={
            "strategy": "ERROR_PRIORITY",
            "base_sample_rate": 0.35,
            "slow_span_threshold_ms": 90.0,
        },
        headers=HEADERS,
    )
    assert up_resp.status_code == 200
    assert up_resp.json()["config"]["strategy"] == "ERROR_PRIORITY"
    assert up_resp.json()["config"]["base_sample_rate"] == 0.35


def test_trace_evidence_signing_and_verification_api():
    """测试 64 位 SHA-256 存证证书签名、在线防篡改验签、单条查询与清空 API。"""
    client = TestClient(app)

    trace_id = "55a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5"
    run_id = "run_audit_999"
    spans = [
        {
            "span_id": "span_root",
            "service_name": "gateway",
            "name": "POST /pay",
            "duration_ms": 95.0,
            "status": {"code": "OK"},
            "attributes": {"http.status_code": 200},
        }
    ]

    # 1. 签名存证
    sign_resp = client.post(
        "/api/v1/observability/trace/evidence/sign",
        json={
            "trace_id": trace_id,
            "run_id": run_id,
            "spans": spans,
            "signer": "atp-qa-auditor",
        },
        headers=HEADERS,
    )
    assert sign_resp.status_code == 200
    cert = sign_resp.json()["certificate"]
    assert cert["trace_id"] == trace_id
    assert len(cert["evidence_sha256"]) == 64

    # 2. 正常验签
    verify_resp = client.post(
        "/api/v1/observability/trace/evidence/verify",
        json={
            "certificate": cert,
            "spans": spans,
        },
        headers=HEADERS,
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["is_valid"] is True
    assert "EVIDENCE_VERIFIED" in verify_resp.json()["message"]

    # 3. 篡改验签失败
    tampered_spans = [dict(spans[0], duration_ms=96.0)]
    fail_verify_resp = client.post(
        "/api/v1/observability/trace/evidence/verify",
        json={
            "certificate": cert,
            "spans": tampered_spans,
        },
        headers=HEADERS,
    )
    assert fail_verify_resp.status_code == 200
    assert fail_verify_resp.json()["is_valid"] is False
    assert "TAMPERED_HASH_MISMATCH" in fail_verify_resp.json()["message"]

    # 4. 单条证书查询
    get_cert_resp = client.get(f"/api/v1/observability/trace/evidence/{trace_id}", headers=HEADERS)
    assert get_cert_resp.status_code == 200
    assert get_cert_resp.json()["certificate"]["evidence_sha256"] == cert["evidence_sha256"]

    # 5. 清空存证库
    del_resp = client.delete("/api/v1/observability/trace/evidences", headers=HEADERS)
    assert del_resp.status_code == 200
    empty_resp = client.get("/api/v1/observability/trace/evidences", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
