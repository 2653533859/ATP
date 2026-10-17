"""双端一致性评分与兼容性报表引擎单测 (T2.3)"""

from __future__ import annotations

import pytest

from app.services.parity_alignment_analyzer import (
    AlignedNodePair,
    AlignmentMatchType,
    ParityAlignmentMatrix,
    ParityNode,
    ParityScreenTree,
)
from app.services.parity_gap_detector import (
    GapSeverity,
    ParityDiscrepancyReport,
    ParityGapItem,
    ParityGapType,
)
from app.services.parity_scoring_engine import (
    ParityGrade,
    ReleaseGateVerdict,
    calculate_parity_scores,
    clear_parity_reports,
    determine_parity_grade_and_verdict,
    evaluate_screen_parity_end_to_end,
    generate_parity_audit_report,
    get_parity_audit_report,
    list_parity_audit_reports,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_parity_reports()
    yield
    clear_parity_reports()


def test_calculate_parity_scores_perfect():
    # 完美对齐场景
    matrix = ParityAlignmentMatrix(
        matrix_id="mat_perf",
        screen_name="会员中心",
        source_platform="ios",
        target_platform="android",
        total_source_nodes=3,
        total_target_nodes=3,
        aligned_pairs_count=3,
        source_only_count=0,
        target_only_count=0,
        overall_alignment_rate=1.0,
        aligned_pairs=[
            AlignedNodePair(
                "p1", ParityNode("n1", "button"), ParityNode("t1", "button"), 1.0, AlignmentMatchType.EXACT
            ),
            AlignedNodePair("p2", ParityNode("n2", "label"), ParityNode("t2", "label"), 1.0, AlignmentMatchType.EXACT),
            AlignedNodePair("p3", ParityNode("n3", "input"), ParityNode("t3", "input"), 1.0, AlignmentMatchType.EXACT),
        ],
        source_only_nodes=[],
        target_only_nodes=[],
    )

    empty_report = ParityDiscrepancyReport(
        report_id="rep_perf",
        matrix_id="mat_perf",
        screen_name="会员中心",
        source_platform="ios",
        target_platform="android",
        total_gaps_count=0,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        gaps=[],
    )

    scores = calculate_parity_scores(matrix, empty_report)
    assert scores.control_alignment_score == 100.0
    assert scores.core_business_score == 100.0
    assert scores.text_consistency_score == 100.0
    assert scores.interaction_compatibility_score == 100.0
    assert scores.weighted_composite_score == 100.0

    grade, verdict = determine_parity_grade_and_verdict(scores, empty_report)
    assert grade == ParityGrade.GRADE_A
    assert verdict == ReleaseGateVerdict.PASS


def test_calculate_parity_scores_with_critical_blocks():
    matrix = ParityAlignmentMatrix(
        matrix_id="mat_crit",
        screen_name="订单结算页",
        source_platform="ios",
        target_platform="android",
        total_source_nodes=5,
        total_target_nodes=4,
        aligned_pairs_count=4,
        source_only_count=1,
        target_only_count=0,
        overall_alignment_rate=0.8,
        aligned_pairs=[],
        source_only_nodes=[ParityNode("ios_pay", "button", text="立即支付")],
        target_only_nodes=[],
    )

    crit_report = ParityDiscrepancyReport(
        report_id="rep_crit",
        matrix_id="mat_crit",
        screen_name="订单结算页",
        source_platform="ios",
        target_platform="android",
        total_gaps_count=1,
        critical_count=1,  # 存在 1 个核心业务缺失
        high_count=0,
        medium_count=0,
        low_count=0,
        gaps=[
            ParityGapItem("g1", ParityGapType.MISSING_CORE_CONTROL, GapSeverity.CRITICAL, "缺失立即支付", "描述"),
        ],
    )

    scores = calculate_parity_scores(matrix, crit_report)
    assert scores.core_business_score <= 65.0

    # 只要存在 CRITICAL 缺陷，必须一票否决定级为 GRADE_F 并阻断门禁
    grade, verdict = determine_parity_grade_and_verdict(scores, crit_report)
    assert grade == ParityGrade.GRADE_F
    assert verdict == ReleaseGateVerdict.BLOCK

    audit_report = generate_parity_audit_report(matrix, crit_report)
    assert audit_report.grade == ParityGrade.GRADE_F
    assert audit_report.verdict == ReleaseGateVerdict.BLOCK
    assert "门禁阻断" in audit_report.executive_summary


def test_evaluate_screen_parity_end_to_end_and_reports():
    tree1 = ParityScreenTree(
        screen_id="s1",
        screen_name="登录主页",
        platform="web",
        root_node=ParityNode(
            "root_web",
            "container",
            children=[
                ParityNode("btn_login", "button", text="登录"),
                ParityNode("input_acc", "input", text="用户名"),
            ],
        ),
    )
    tree2 = ParityScreenTree(
        screen_id="s2",
        screen_name="登录主页",
        platform="android",
        root_node=ParityNode(
            "root_android",
            "container",
            children=[
                ParityNode("btn_login_and", "button", text="登录"),
                ParityNode("input_acc_and", "input", text="用户名"),
            ],
        ),
    )

    rep = evaluate_screen_parity_end_to_end(tree1, tree2)
    assert rep.grade == ParityGrade.GRADE_A
    assert rep.verdict == ReleaseGateVerdict.PASS
    assert rep.composite_score >= 95.0

    # 查验历史列表与单项检索
    assert get_parity_audit_report(rep.report_id) is not None
    assert len(list_parity_audit_reports()) == 1
