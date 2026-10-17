"""异常步骤调用链深潜下钻与首因归因服务单测 (T2.2)"""

from __future__ import annotations

from app.services.step_trace_deep_dive_analyzer import (
    FailureAttributionType,
    clear_diagnosis_history,
    deep_dive_analyze_trace,
    list_diagnosis_history,
)


def test_deep_dive_downstream_service_error():
    clear_diagnosis_history()

    step_ctx = {
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "name": "步骤 3: 提交聚合支付",
        "status": "FAILED",
        "error_message": "下游服务返回 HTTP 500 内部服务错误",
    }

    spans = [
        {
            "span_id": "span_api_gw",
            "name": "POST /api/v1/pay",
            "service_name": "api-gateway",
            "duration_ms": 120.0,
            "status": {"code": "OK"},
            "attributes": {"http.status_code": 200},
        },
        {
            "span_id": "span_payment_svc",
            "parent_span_id": "span_api_gw",
            "name": "ProcessPayment",
            "service_name": "payment-service",
            "duration_ms": 100.0,
            "status": {"code": "OK"},
            "attributes": {"http.status_code": 200},
        },
        {
            "span_id": "span_bank_channel",
            "parent_span_id": "span_payment_svc",
            "name": "BankChannelPay",
            "service_name": "bank-channel-service",
            "duration_ms": 80.0,
            "status": {"code": "ERROR", "message": "银行通道网络不可达: Connection refused"},
            "attributes": {
                "http.status_code": 500,
                "exception.message": "银行通道网络不可达: Connection refused",
                "exception.stacktrace": "Traceback: ConnectTimeoutError at bank_client.py:42",
            },
        },
    ]

    diag = deep_dive_analyze_trace(step_ctx, spans)
    assert diag.attribution_type == FailureAttributionType.DOWNSTREAM_SERVICE_ERROR
    assert diag.root_cause_service == "bank-channel-service"
    assert diag.root_cause_span_id == "span_bank_channel"
    assert "Connection refused" in diag.error_message
    assert "ConnectTimeoutError" in diag.stack_trace
    assert diag.error_spans_count == 1
    assert "bank-channel-service" in diag.diagnosis_summary


def test_deep_dive_slow_database_query():
    clear_diagnosis_history()

    step_ctx = {
        "trace_id": "7ca6473577b34da6a3ce929d0e0e9988",
        "name": "步骤 2: 导出大批量报表",
        "status": "FAILED",
        "error_message": "步骤超时: 执行耗时超 3000ms 阈值",
    }

    spans = [
        {
            "span_id": "span_report_worker",
            "name": "GenerateReportTask",
            "service_name": "report-worker",
            "duration_ms": 3200.0,
            "status": {"code": "OK"},
        },
        {
            "span_id": "span_slow_db",
            "parent_span_id": "span_report_worker",
            "name": "db_query",
            "service_name": "report-db",
            "duration_ms": 3100.0,  # 严重慢查询
            "status": {"code": "OK"},
            "attributes": {
                "db.system": "postgresql",
                "db.statement": "SELECT * FROM test_case_runs WHERE project_id = 101 ORDER BY created_at DESC",
            },
        },
    ]

    diag = deep_dive_analyze_trace(step_ctx, spans, slow_query_threshold_ms=200.0)
    assert diag.attribution_type == FailureAttributionType.SLOW_DATABASE_QUERY
    assert diag.root_cause_service == "report-db"
    assert len(diag.slow_queries) == 1
    assert diag.slow_queries[0].duration_ms == 3100.0
    assert "索引" in diag.suggested_action

    history = list_diagnosis_history(limit=5)
    assert len(history) == 1
