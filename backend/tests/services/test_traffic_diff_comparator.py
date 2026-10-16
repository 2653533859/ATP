"""Unit tests for Traffic Diff Comparator Service (T2.2)."""

from __future__ import annotations

import json
import pytest

from app.services.traffic_diff_comparator import (
    DiffSeverity,
    DiffType,
    NoiseFilterConfig,
    clear_diff_reports,
    compare_traffic_responses,
    get_diff_report,
    is_dynamic_noise_field,
    list_diff_reports,
)


@pytest.fixture(autouse=True)
def clean_reports():
    clear_diff_reports()
    yield
    clear_diff_reports()


def test_is_dynamic_noise_field():
    """验证时间戳、UUID 与调用链 Trace ID 噪声的智能识别。"""
    cfg = NoiseFilterConfig()

    assert is_dynamic_noise_field("timestamp", 1760600000000, cfg) is True
    assert is_dynamic_noise_field("server_time", "2026-10-16T12:00:00Z", cfg) is True
    assert is_dynamic_noise_field("trace_id", "abc-123", cfg) is True
    assert is_dynamic_noise_field("request_id", "req-xyz", cfg) is True
    assert is_dynamic_noise_field("random_token", "550e8400-e29b-41d4-a716-446655440000", cfg) is True

    # 业务核心字段不可当作噪声被忽略
    assert is_dynamic_noise_field("order_id", 1001, cfg) is False
    assert is_dynamic_noise_field("amount", 99.0, cfg) is False
    assert is_dynamic_noise_field("status", "SUCCESS", cfg) is False


def test_compare_identical_responses_with_noise_filtering():
    """验证当业务字段完全一致、仅存在动态时间戳和 UUID 差异时，判定为 100% 完美一致。"""
    baseline = {
        "code": 0,
        "message": "success",
        "data": {
            "order_id": 9999,
            "status": "PAID",
            "amount": 299.0,
            "created_at": "2026-10-16T10:00:00Z",
            "request_id": "req-1111-aaaa",
            "trace_id": "trace-old-123",
        },
    }

    replayed = {
        "code": 0,
        "message": "success",
        "data": {
            "order_id": 9999,
            "status": "PAID",
            "amount": 299.0,
            "created_at": "2026-10-16T15:30:00Z",  # 动态时间不同
            "request_id": "req-2222-bbbb",  # 请求 ID 不同
            "trace_id": "trace-new-456",  # 链路 ID 不同
        },
    }

    report = compare_traffic_responses(baseline, replayed)

    assert report.is_identical is True
    assert report.similarity_score_pct == 100.0
    assert report.total_differences_count == 0
    assert report.ignored_noise_fields_count >= 3  # 成功忽略了 3 处时间/UUID 噪声
    assert "完美一致" in report.diff_summary


def test_compare_detected_differences():
    """验证对字段删除、业务核心值篡改与类型漂移的精确捕捉。"""
    baseline = {
        "code": 0,
        "data": {
            "order_id": 1001,
            "amount": 100.0,
            "items": ["apple", "banana"],
            "obsolete_tag": "old",
        },
    }

    replayed = {
        "code": 500,  # 核心状态码被修改
        "data": {
            "order_id": "1001",  # int -> str 类型漂移
            "amount": 150.0,  # 核心金额篡改
            "items": ["apple"],  # 数组长度不符
            "new_feature_tag": "beta",  # 新增字段
            # 缺失了 obsolete_tag 字段
        },
    }

    report = compare_traffic_responses(
        baseline_response_body=json.dumps(baseline),
        replayed_response_body=json.dumps(replayed),
        baseline_status_code=200,
        replayed_status_code=500,  # HTTP 状态码不符
    )

    assert report.is_identical is False
    assert report.similarity_score_pct < 50.0
    assert report.critical_diffs_count >= 3

    # 1. 验证 HTTP 状态码不一致
    status_diff = next(d for d in report.differences if d.path == "$.status_code")
    assert status_diff.diff_type == DiffType.MODIFIED
    assert status_diff.severity == DiffSeverity.CRITICAL

    # 2. 验证业务 code 不一致
    code_diff = next(d for d in report.differences if d.path == "$.code")
    assert code_diff.diff_type == DiffType.MODIFIED
    assert code_diff.severity == DiffSeverity.CRITICAL

    # 3. 验证 order_id 类型漂移
    type_diff = next(d for d in report.differences if d.path == "$.data.order_id")
    assert type_diff.diff_type == DiffType.TYPE_CHANGED
    assert type_diff.severity == DiffSeverity.CRITICAL

    # 4. 验证 obsolete_tag 被删除
    del_diff = next(d for d in report.differences if d.path == "$.data.obsolete_tag")
    assert del_diff.diff_type == DiffType.DELETED
    assert del_diff.severity == DiffSeverity.CRITICAL

    # 5. 验证 new_feature_tag 新增
    add_diff = next(d for d in report.differences if d.path == "$.data.new_feature_tag")
    assert add_diff.diff_type == DiffType.ADDED
    assert add_diff.severity == DiffSeverity.WARNING

    # 6. 验证报告持久化
    fetched = get_diff_report(report.report_id)
    assert fetched is not None
    assert fetched.report_id == report.report_id
    assert len(list_diff_reports()) == 1
