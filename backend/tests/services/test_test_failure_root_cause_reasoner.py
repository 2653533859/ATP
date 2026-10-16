"""Unit Tests for Multimodal Test Failure Root-Cause Reasoner (T3.1)。"""

from __future__ import annotations

import pytest

from app.services.test_failure_root_cause_reasoner import (
    RootCauseCategory,
    analyze_test_failure_root_cause,
    batch_analyze_failures,
    clear_root_cause_store,
    get_root_cause_report,
    list_root_cause_reports,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_root_cause_store()
    yield
    clear_root_cause_store()


def test_database_deadlock_failure_reasoning():
    logs = """
    Traceback (most recent call last):
      File "/app/services/order_service.py", line 155, in checkout
        db.session.commit()
    sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (1213, 'Deadlock found when trying to get lock; try restarting transaction')
    """
    report = analyze_test_failure_root_cause(
        case_id="case_101",
        case_name="提交订单并发支付用例",
        console_logs=logs,
        http_status_code=500,
        http_response_body='{"code": 500, "error": "Internal database operational error"}',
    )

    assert report.case_id == "case_101"
    assert report.category == RootCauseCategory.DATABASE_EXECUTION_FAILURE
    assert report.confidence_score >= 0.90
    assert "死锁" in report.primary_root_cause_summary
    assert "order_service.py:155 in checkout()" == report.culprit_location
    assert len(report.causal_chain) >= 3
    assert "死锁" in report.causal_chain[0]
    assert "索引" in report.suggested_action


def test_network_gateway_timeout_reasoning():
    report = analyze_test_failure_root_cause(
        case_id="case_102",
        case_name="外部征信风控接口调用",
        console_logs="requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='api.credit.com'): Read timed out. (read timeout=5.0)",
        http_status_code=504,
        http_response_body="<html><body><h1>504 Gateway Time-out</h1></body></html>",
    )

    assert report.category == RootCauseCategory.NETWORK_GATEWAY_TIMEOUT
    assert report.confidence_score >= 0.90
    assert "超时熔断" in report.primary_root_cause_summary
    assert "网关" in report.causal_chain[1]


def test_downstream_service_null_pointer_crash_reasoning():
    logs = """
    File "/workspace/backend/payment_processor.py", line 88, in handle_callback
      user_id = payload['data']['user_info']['id']
    KeyError: 'user_info'
    """
    spans = [
        {
            "service_name": "pay-callback-service",
            "name": "handle_callback",
            "status": "ERROR",
            "error_message": "KeyError: 'user_info'",
        }
    ]

    report = analyze_test_failure_root_cause(
        case_id="case_103",
        case_name="第三方支付异步通知回调",
        console_logs=logs,
        http_status_code=500,
        http_response_body='{"status": 500, "message": "KeyError: user_info"}',
        spans=spans,
    )

    assert report.category == RootCauseCategory.DOWNSTREAM_SERVICE_CRASH
    assert report.culprit_service == "pay-callback-service"
    assert "payment_processor.py:88 in handle_callback()" == report.culprit_location
    assert "判空防御" in report.suggested_action


def test_ui_dom_locator_drift_reasoning():
    logs = """
    selenium.common.exceptions.NoSuchElementException: Message: no such element: Unable to locate element: {"method":"xpath","selector":"//button[@id='confirm-order']"}
    """

    report = analyze_test_failure_root_cause(
        case_id="case_104",
        case_name="购物车结账下单 UI 流程",
        console_logs=logs,
    )

    assert report.category == RootCauseCategory.UI_DOM_LOCATOR_DRIFT
    assert report.culprit_service == "frontend-web"
    assert "定位符失效漂移" in report.primary_root_cause_summary
    assert "智能自愈" in report.suggested_action


def test_auth_token_expired_reasoning():
    report = analyze_test_failure_root_cause(
        case_id="case_105",
        case_name="查询个人敏感资产流水",
        http_status_code=401,
        http_response_body='{"code": 401, "error": "Token expired, please login again"}',
    )

    assert report.category == RootCauseCategory.AUTHENTICATION_EXPIRED
    assert report.confidence_score >= 0.95
    assert "认证凭证" in report.primary_root_cause_summary


def test_batch_analyze_and_reports_crud():
    failures = [
        {"case_id": "c1", "case_name": "用例1", "http_status_code": 401},
        {"case_id": "c2", "case_name": "用例2", "console_logs": "AssertionError: expected 100 but was 90"},
    ]
    reports = batch_analyze_failures(failures)
    assert len(reports) == 2

    stored = get_root_cause_report(reports[0].diagnosis_id)
    assert stored is not None
    assert stored.case_id == "c1"

    listed = list_root_cause_reports(category=RootCauseCategory.AUTHENTICATION_EXPIRED.value)
    assert len(listed) == 1
    assert listed[0].case_id == "c1"
