"""双端功能差异与缺失控件侦测器单测 (T2.2)"""

from __future__ import annotations

from app.services.parity_alignment_analyzer import (
    AlignedNodePair,
    AlignmentMatchType,
    ParityAlignmentMatrix,
    ParityNode,
)
from app.services.parity_gap_detector import (
    GapSeverity,
    ParityDiscrepancyReport,
    ParityGapType,
    detect_parity_gaps,
    is_core_business_node,
)


def test_is_core_business_node():
    pay_btn = ParityNode("b1", role="button", text="立即支付", identifier="btn_pay")
    assert is_core_business_node(pay_btn) is True

    refund_btn = ParityNode("b2", role="button", text="申请极速退款", identifier="btn_refund")
    assert is_core_business_node(refund_btn) is True

    about_label = ParityNode("l1", role="label", text="版权所有 © 2026", identifier="lbl_copyright")
    assert is_core_business_node(about_label) is False


def test_detect_parity_gaps_full_lifecycle():
    # 构造包含各类差异的对齐矩阵
    # 1. 核心缺失控件: 仅在 iOS 存在的 "申请极速退款" 按钮
    missing_core = ParityNode("ios_refund", role="button", text="申请极速退款", identifier="btn_refund")
    # 2. 次要缺失控件: 仅在 iOS 存在的 "分享至微博" 按钮
    missing_optional = ParityNode("ios_share", role="button", text="分享", identifier="btn_share")
    # 3. 目标端独有控件: 仅在 Android 存在的 "Android 专属立减 5 元" 按钮
    target_only = ParityNode("android_discount", role="button", text="立减支付", identifier="btn_discount")

    # 4. 角色冲突节点对: iOS 是 input 框，Android 退化为 label
    pair_role_mismatch = AlignedNodePair(
        pair_id="p_role",
        source_node=ParityNode("ios_in", role="input", text="优惠券码"),
        target_node=ParityNode("android_lbl", role="label", text="优惠券码"),
        alignment_score=0.90,
        match_type=AlignmentMatchType.EXACT,
    )

    # 5. 文案语义漂移节点对: 满减文案不一致
    pair_drift = AlignedNodePair(
        pair_id="p_drift",
        source_node=ParityNode("ios_t", role="label", text="满 100 减 20"),
        target_node=ParityNode("android_t", role="label", text="满 200 减 10"),
        alignment_score=0.60,
        match_type=AlignmentMatchType.PARTIAL,
    )

    matrix = ParityAlignmentMatrix(
        matrix_id="mat_test_001",
        screen_name="收银台结算中心",
        source_platform="ios",
        target_platform="android",
        total_source_nodes=4,
        total_target_nodes=3,
        aligned_pairs_count=2,
        source_only_count=2,
        target_only_count=1,
        overall_alignment_rate=0.5,
        aligned_pairs=[pair_role_mismatch, pair_drift],
        source_only_nodes=[missing_core, missing_optional],
        target_only_nodes=[target_only],
    )

    report = detect_parity_gaps(matrix)
    assert isinstance(report, ParityDiscrepancyReport)
    assert report.matrix_id == "mat_test_001"
    assert report.total_gaps_count == 5

    # 严重度核查:
    # 1 个 CRITICAL (iOS 极速退款缺失)
    assert report.critical_count == 1
    assert any(g.severity == GapSeverity.CRITICAL for g in report.gaps)
    # 2 个 HIGH (目标端立减核心缺失 + 角色冲突)
    assert report.high_count == 2
    # 2 个 MEDIUM (分享缺失 + 语义漂移)
    assert report.medium_count == 2

    # 类型核查
    gap_types = [g.gap_type for g in report.gaps]
    assert ParityGapType.MISSING_CORE_CONTROL in gap_types
    assert ParityGapType.MISSING_OPTIONAL_CONTROL in gap_types
    assert ParityGapType.ACTION_CAPABILITY_MISMATCH in gap_types
    assert ParityGapType.SEMANTIC_TEXT_DRIFT in gap_types

    # 字典序列化验证
    d = report.to_dict()
    assert d["report_id"].startswith("prep_")
    assert len(d["gaps"]) == 5
    assert d["critical_count"] == 1
