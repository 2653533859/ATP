"""Unit tests for Contract Drift Breaking Evaluator Service (T3.2)."""

from __future__ import annotations

import pytest

from app.services.contract_drift_breaking_evaluator import (
    BreakingLevel,
    DriftChangeType,
    clear_drift_evaluation_reports,
    compare_schemas_compatibility,
    evaluate_contract_drift,
    get_drift_evaluation_report,
    list_drift_evaluation_reports,
)


@pytest.fixture(autouse=True)
def clean_reports():
    clear_drift_evaluation_reports()
    yield
    clear_drift_evaluation_reports()


def test_compare_request_schemas_breaking_changes():
    """验证请求体契约新增必填字段、类型改变与枚举缩减被准确判定为 BREAKING。"""
    design_schema = {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer"},
            "amount": {"type": "number"},
            "channel": {"type": "string", "enum": ["WEB", "APP", "H5"]},
            "coupon_code": {"type": "string"},
        },
        "required": ["order_id", "amount"],
    }

    live_schema = {
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},  # integer -> string 类型漂移 (BREAKING)
            "amount": {"type": "number"},
            "channel": {"type": "string", "enum": ["WEB", "APP"]},  # 缩减了 H5 枚举 (BREAKING)
            "coupon_code": {"type": "string"},
            "id_card_num": {"type": "string"},  # 新增字段且被标为必填 (BREAKING)
        },
        "required": ["order_id", "amount", "id_card_num"],  # 新增了 id_card_num 为必填项
    }

    drifts = compare_schemas_compatibility(design_schema, live_schema, is_request=True, path_prefix="$.request")

    # 验证检出 3 个 BREAKING 破坏性变更
    breaking_items = [d for d in drifts if d.breaking_level == BreakingLevel.BREAKING]
    assert len(breaking_items) >= 3

    # 1. 验证类型漂移
    type_drift = next(d for d in breaking_items if d.change_type == DriftChangeType.TYPE_CHANGED)
    assert "order_id" in type_drift.field_path
    assert type_drift.design_value == "integer"
    assert type_drift.live_value == "string"

    # 2. 验证新增必填项
    req_drift = next(d for d in breaking_items if d.change_type == DriftChangeType.REQUIRED_ADDED)
    assert "id_card_num" in req_drift.field_path

    # 3. 验证枚举缩减
    enum_drift = next(d for d in breaking_items if d.change_type == DriftChangeType.ENUM_RESTRICTED)
    assert "channel" in enum_drift.field_path


def test_compare_response_schemas_field_removed_is_breaking():
    """验证响应体中删除既有字段属于 BREAKING，而新增字段为 WARNING。"""
    design_resp_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "integer"},
            "status": {"type": "string"},
            "balance": {"type": "number"},  # 现网中将被删除
        },
        "required": ["code", "status"],
    }

    live_resp_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "integer"},
            "status": {"type": "string"},
            # balance 被删除 (BREAKING)
            "timestamp": {"type": "integer"},  # 响应体新增字段 (WARNING)
        },
        "required": ["code", "status"],
    }

    drifts = compare_schemas_compatibility(
        design_resp_schema, live_resp_schema, is_request=False, path_prefix="$.response.200"
    )

    # 验证响应体删除字段为 BREAKING
    del_drift = next(d for d in drifts if d.change_type == DriftChangeType.FIELD_REMOVED)
    assert del_drift.breaking_level == BreakingLevel.BREAKING
    assert "balance" in del_drift.field_path

    # 验证响应体新增字段为 WARNING
    add_drift = next(d for d in drifts if d.change_type == DriftChangeType.FIELD_ADDED)
    assert add_drift.breaking_level == BreakingLevel.WARNING
    assert "timestamp" in add_drift.field_path


def test_evaluate_contract_drift_compatible():
    """验证契约完全一致时判定为 COMPATIBLE 且得分为 100 分。"""
    common_contract = {
        "endpoint": "GET /api/v1/users/profile",
        "request_schema": {
            "type": "object",
            "properties": {"user_id": {"type": "integer"}},
            "required": ["user_id"],
        },
        "response_schemas": {
            "200": {
                "type": "object",
                "properties": {"code": {"type": "integer"}, "name": {"type": "string"}},
            }
        },
    }

    report = evaluate_contract_drift(common_contract, common_contract)

    assert report.overall_breaking_level == BreakingLevel.COMPATIBLE
    assert report.is_breaking is False
    assert report.compatibility_score_pct == 100.0
    assert report.breaking_changes_count == 0
    assert "完全兼容" in report.verdict_summary


def test_evaluate_contract_drift_breaking_summary_and_persistence():
    """验证端到端评估报告生成、扣分与历史检索。"""
    design_contract = {
        "endpoint": "POST /api/v1/pay",
        "request_schema": {"type": "object", "properties": {"pay_type": {"type": "string"}}},
        "response_schemas": {
            "200": {"type": "object", "properties": {"trade_no": {"type": "string"}, "fee": {"type": "number"}}}
        },
    }

    live_contract = {
        "endpoint": "POST /api/v1/pay",
        "request_schema": {
            "type": "object",
            "properties": {"pay_type": {"type": "string"}, "force_token": {"type": "string"}},
            "required": ["force_token"],  # 请求新增必填 (BREAKING)
        },
        "response_schemas": {
            "200": {
                "type": "object",
                "properties": {"trade_no": {"type": "string"}},  # 响应删除了 fee (BREAKING)
            }
        },
    }

    report = evaluate_contract_drift(design_contract, live_contract)

    assert report.overall_breaking_level == BreakingLevel.BREAKING
    assert report.is_breaking is True
    assert report.breaking_changes_count == 2
    assert report.compatibility_score_pct <= 40.0  # 100 - 30*2 = 40
    assert "严重阻断" in report.verdict_summary

    # 验证可查回
    fetched = get_drift_evaluation_report(report.evaluation_id)
    assert fetched is not None
    assert fetched.evaluation_id == report.evaluation_id
    assert len(list_drift_evaluation_reports()) == 1
