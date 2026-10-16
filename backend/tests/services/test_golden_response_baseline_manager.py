"""Unit tests for Golden Response Baseline Manager Service (T2.3)."""

from __future__ import annotations

import json
import pytest

from app.services.golden_response_baseline_manager import (
    DriftAlertLevel,
    batch_verify_against_baselines,
    clear_golden_baselines,
    create_or_update_golden_baseline,
    delete_golden_baseline,
    get_batch_verification_report,
    get_golden_baseline,
    get_golden_baseline_by_endpoint,
    list_golden_baselines,
    verify_response_against_baseline,
)


@pytest.fixture(autouse=True)
def clean_baselines():
    clear_golden_baselines()
    yield
    clear_golden_baselines()


def test_create_and_query_golden_baseline():
    """验证黄金响应基线的版本化打标录入与多维检索。"""
    item = create_or_update_golden_baseline(
        endpoint="POST /api/v1/orders/checkout",
        golden_response_body={
            "code": 0,
            "data": {"order_id": 10001, "status": "CREATED", "amount": 199.0},
        },
        golden_response_status=200,
        version_tag="v1.0-prod-gold",
        tolerance_threshold_pct=95.0,
    )

    assert item.baseline_id.startswith("gbl_")
    assert item.endpoint == "POST /api/v1/orders/checkout"
    assert item.version_tag == "v1.0-prod-gold"

    # 按 ID 查回
    fetched = get_golden_baseline(item.baseline_id)
    assert fetched is not None
    assert fetched.baseline_id == item.baseline_id

    # 按 Endpoint 查回
    by_ep = get_golden_baseline_by_endpoint("POST /api/v1/orders/checkout", "v1.0-prod-gold")
    assert by_ep is not None
    assert by_ep.baseline_id == item.baseline_id

    # 列表检索
    items = list_golden_baselines(endpoint_pattern="orders")
    assert len(items) == 1


def test_verify_response_success_with_noise_ignored():
    """验证实测响应对齐黄金基线校验通过 (动态噪声自动忽略)。"""
    baseline = create_or_update_golden_baseline(
        endpoint="GET /api/v1/user/info",
        golden_response_body={
            "code": 0,
            "data": {
                "user_id": 888,
                "role": "VIP",
                "login_time": "2026-10-16T10:00:00Z",
                "request_id": "req-old-111",
            },
        },
        tolerance_threshold_pct=90.0,
    )

    # 实测响应中，动态时间与 request_id 发生变化，但核心业务字段完全相同
    actual_resp = {
        "code": 0,
        "data": {
            "user_id": 888,
            "role": "VIP",
            "login_time": "2026-10-16T18:00:00Z",  # 动态噪声
            "request_id": "req-new-222",  # 动态噪声
        },
    }

    res = verify_response_against_baseline(
        baseline_id_or_item=baseline,
        actual_response_body=json.dumps(actual_resp),
        actual_status_code=200,
    )

    assert res.passed is True
    assert res.alert_level == DriftAlertLevel.NORMAL
    assert res.similarity_score_pct == 100.0
    assert res.critical_diffs_count == 0


def test_verify_response_regression_critical_drift():
    """验证当实测响应缺失核心业务字段或状态码不符时触发 CRITICAL 偏离阻断报警。"""
    baseline = create_or_update_golden_baseline(
        endpoint="POST /api/v1/pay",
        golden_response_body={
            "code": 0,
            "status": "SUCCESS",
            "trade_no": "TX20261016001",
            "fee": 10.0,
        },
        tolerance_threshold_pct=95.0,
    )

    # 实测响应不仅状态码变为 500，且关键 fee 字段丢失
    actual_drifted = {
        "code": 500,
        "status": "FAILED",
        "trade_no": "TX20261016001",
        # fee 字段被删除
    }

    res = verify_response_against_baseline(
        baseline_id_or_item=baseline,
        actual_response_body=json.dumps(actual_drifted),
        actual_status_code=500,  # 状态码不符
    )

    assert res.passed is False
    assert res.alert_level == DriftAlertLevel.CRITICAL
    assert res.critical_diffs_count >= 2
    assert "严重回归阻断" in res.summary


def test_batch_verify_against_baselines():
    """验证批量实测流量对齐黄金基线的多接口全景回归校验。"""
    create_or_update_golden_baseline(
        endpoint="GET /api/v1/users",
        golden_response_body={"code": 0, "total": 10},
        version_tag="v1.0",
    )
    create_or_update_golden_baseline(
        endpoint="POST /api/v1/orders",
        golden_response_body={"code": 0, "order_id": 100},
        version_tag="v1.0",
    )

    actual_batch = [
        # 第 1 笔通过
        {"endpoint": "GET /api/v1/users", "response_body": '{"code": 0, "total": 10}'},
        # 第 2 笔篡改漂移
        {"endpoint": "POST /api/v1/orders", "response_body": '{"code": 999, "error": "failed"}'},
    ]

    report = batch_verify_against_baselines(actual_batch, default_version_tag="v1.0")

    assert report.total_verified == 2
    assert report.passed_count == 1
    assert report.drifted_count == 1
    assert report.pass_rate_pct == 50.0

    fetched = get_batch_verification_report(report.batch_id)
    assert fetched is not None
    assert fetched.batch_id == report.batch_id


def test_delete_golden_baseline():
    """验证黄金响应基线的删除能力。"""
    item = create_or_update_golden_baseline(
        endpoint="GET /temp",
        golden_response_body="{}",
    )
    assert delete_golden_baseline(item.baseline_id) is True
    assert get_golden_baseline(item.baseline_id) is None
    assert delete_golden_baseline(item.baseline_id) is False
