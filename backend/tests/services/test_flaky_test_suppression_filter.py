"""Unit tests for Flaky Test Suppression Filter Service (S2.3)."""

from __future__ import annotations

import pytest

from app.services.flaky_test_suppression_filter import (
    FlakyFilterMode,
    SuppressionAction,
    filter_flaky_tests_for_ci,
    get_flaky_filter_report,
    list_flaky_filter_reports,
    register_flaky_governance_override,
    reset_flaky_filter_registry,
)


@pytest.fixture(autouse=True)
def clean_flaky_filter():
    reset_flaky_filter_registry()
    yield
    reset_flaky_filter_registry()


def test_filter_stable_and_flaky_adaptive():
    cases = [
        {"case_id": 1, "case_name": "核心认证成功"},
        {"case_id": 2, "case_name": "轻度偶发超时接口"},
        {"case_id": 3, "case_name": "高频随机五五开死循环"},
    ]

    stats = {
        1: {"total_runs": 10, "passed_runs": 10, "failed_runs": 0},
        2: {"total_runs": 10, "passed_runs": 8, "failed_runs": 2},  # 失败率 20%, 抖动指数 0.4
        3: {"total_runs": 10, "passed_runs": 5, "failed_runs": 5},  # 失败率 50%, 抖动指数 1.0 (严重不稳定)
    }

    report = filter_flaky_tests_for_ci(
        cases_to_evaluate=cases,
        mode=FlakyFilterMode.AUTO_ADAPTIVE,
        historical_stats=stats,
    )

    assert report.total_cases_evaluated == 3
    assert report.stable_cases_count == 1
    assert report.flaky_cases_count == 2
    assert report.isolated_cases_count == 1  # Case 3 严重抖动被隔离
    assert report.retried_cases_count == 1  # Case 2 轻度抖动附加重试

    # Case 1 正常放行，Case 2 附加重试放行，Case 3 被隔离
    assert 1 in report.actionable_case_ids
    assert 2 in report.actionable_case_ids
    assert 3 not in report.actionable_case_ids
    assert 3 in report.quarantined_case_ids


def test_filter_strict_and_retry_only_modes():
    cases = [{"case_id": 10, "case_name": "轻微抖动用例"}]
    stats = {10: {"total_runs": 8, "passed_runs": 6, "failed_runs": 2}}

    # 1. 严格模式：只要有抖动一律隔离
    strict_report = filter_flaky_tests_for_ci(
        cases_to_evaluate=cases,
        mode=FlakyFilterMode.QUARANTINE_STRICT,
        historical_stats=stats,
    )
    assert strict_report.isolated_cases_count == 1
    assert 10 in strict_report.quarantined_case_ids
    assert 10 not in strict_report.actionable_case_ids

    # 2. 仅重试模式：保留在主干并附加重试
    retry_report = filter_flaky_tests_for_ci(
        cases_to_evaluate=cases,
        mode=FlakyFilterMode.RETRY_ONLY,
        historical_stats=stats,
    )
    assert retry_report.retried_cases_count == 1
    assert 10 in retry_report.actionable_case_ids
    assert len(retry_report.quarantined_case_ids) == 0


def test_governance_override_precedence():
    cases = [{"case_id": 99, "case_name": "历史已知网络闪断用例"}]

    # 显式覆盖治理策略：强制隔离
    register_flaky_governance_override(
        case_id=99,
        action=SuppressionAction.ISOLATED_TO_QUARANTINE,
        reason="已知跨机房专线晚间割接偶发抖动，等待运维网络修复",
        ticket_id="OPS-8848",
    )

    report = filter_flaky_tests_for_ci(cases_to_evaluate=cases)
    assert report.isolated_cases_count == 1
    assert 99 in report.quarantined_case_ids
    assert "OPS-8848" in report.evaluations[0].suppression_reason


def test_get_and_list_flaky_filter_reports():
    cases = [{"case_id": 1, "case_name": "稳固用例"}]
    report = filter_flaky_tests_for_ci(cases_to_evaluate=cases)

    fetched = get_flaky_filter_report(report.filter_id)
    assert fetched is not None
    assert fetched.filter_id == report.filter_id

    reports = list_flaky_filter_reports()
    assert len(reports) == 1
    assert reports[0].filter_id == report.filter_id
