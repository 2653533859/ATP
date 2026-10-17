"""双端响应体深度结构 Diff 对比器单测 (T2.1)"""

from __future__ import annotations

from app.services.traffic_response_diff_comparator import (
    DiffSeverity,
    ResponseDiffCategory,
    compare_traffic_responses,
)


def test_status_code_mismatch_blocker():
    base_body = {"code": 200, "data": "ok"}
    act_body = {"code": 500, "error": "Internal Error"}

    report = compare_traffic_responses(
        record_id="rec_01",
        baseline_status_code=200,
        baseline_body=base_body,
        replayed_status_code=500,
        replayed_body=act_body,
    )
    assert report.is_identical is False
    assert report.has_critical_breaking is True
    sc_diff = next(d for d in report.diffs if d.category == ResponseDiffCategory.STATUS_CODE_MISMATCH)
    assert sc_diff.severity == DiffSeverity.BLOCKER
    assert sc_diff.baseline_value == 200
    assert sc_diff.replayed_value == 500


def test_missing_and_unexpected_keys():
    base_body = {
        "order_id": "OD_1001",
        "user_id": 999,
        "items": ["apple", "banana"],
    }
    act_body = {
        "order_id": "OD_1001",
        "items": ["apple", "banana"],
        "extra_trace_id": "tr_new_777",
    }

    report = compare_traffic_responses(
        record_id="rec_02",
        baseline_status_code=200,
        baseline_body=base_body,
        replayed_status_code=200,
        replayed_body=act_body,
    )
    assert report.is_identical is False
    assert report.diff_count == 2

    # 验证 missing key (user_id)
    missing = next(d for d in report.diffs if d.category == ResponseDiffCategory.MISSING_KEY)
    assert missing.json_path == "$.user_id"
    assert missing.severity == DiffSeverity.MAJOR

    # 验证 unexpected key (extra_trace_id)
    extra = next(d for d in report.diffs if d.category == ResponseDiffCategory.UNEXPECTED_KEY)
    assert extra.json_path == "$.extra_trace_id"
    assert extra.severity == DiffSeverity.INFO


def test_type_and_value_mismatches():
    base_body = {
        "amount": 99.5,
        "roles": ["admin"],
        "profile": {"city": "Beijing"},
    }
    act_body = {
        "amount": 105.0,  # 数值偏离
        "roles": "admin",  # 类型偏离 (list vs str)
        "profile": None,  # 空值不匹配
    }

    report = compare_traffic_responses(
        record_id="rec_03",
        baseline_status_code=200,
        baseline_body=base_body,
        replayed_status_code=200,
        replayed_body=act_body,
    )
    assert report.is_identical is False
    assert report.diff_summary[ResponseDiffCategory.VALUE_MISMATCH.value] == 1
    assert report.diff_summary[ResponseDiffCategory.TYPE_MISMATCH.value] == 2


def test_identical_responses():
    base_body = {"status": "success", "data": {"count": 10, "items": [1, 2]}}
    act_body = {"status": "success", "data": {"count": 10, "items": [1, 2]}}

    report = compare_traffic_responses(
        record_id="rec_04",
        baseline_status_code=200,
        baseline_body=base_body,
        replayed_status_code=200,
        replayed_body=act_body,
    )
    assert report.is_identical is True
    assert report.diff_count == 0
    assert report.has_critical_breaking is False


def test_header_comparison():
    report = compare_traffic_responses(
        record_id="rec_05",
        baseline_status_code=200,
        baseline_body={"msg": "ok"},
        replayed_status_code=200,
        replayed_body={"msg": "ok"},
        baseline_headers={"Content-Type": "application/json"},
        replayed_headers={"Content-Type": "text/plain"},
    )
    assert report.is_identical is False
    assert any(d.json_path == "$.headers.Content-Type" for d in report.diffs)
