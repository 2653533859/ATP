"""漏测盲区智能补全用例草稿合成服务单测 (T2.2)"""

from __future__ import annotations

from app.services.missing_test_case_synthesizer import (
    synthesize_cases_for_all_gaps,
    synthesize_cases_for_gap_node,
)
from app.services.visual_coverage_lineage_analyzer import (
    CoverageLineageNode,
    CoverageRiskLevel,
    LineageCategory,
)


def test_synthesize_cases_for_api_and_ui_gaps():
    # 1. API 接口漏测节点
    node_api = CoverageLineageNode(
        node_id="api_login",
        node_name="POST /api/v1/auth/login",
        category=LineageCategory.API_ENDPOINT,
        expected_branches=["HTTP_200", "HTTP_401_BAD_PASSWORD"],
        covered_branches=["HTTP_200"],
        risk_level=CoverageRiskLevel.HIGH,
    )
    api_drafts = synthesize_cases_for_gap_node(node_api)
    assert len(api_drafts) == 1
    d = api_drafts[0]
    assert d.target_branch == "HTTP_401_BAD_PASSWORD"
    assert d.case_type == "api"
    assert d.priority == "P0"  # HIGH 风险映射为 P0
    assert len(d.steps) >= 2
    assert d.steps[0].action_type == "http_request"
    assert d.steps[1].action_type == "assertion"

    # 2. UI 交互漏测节点
    node_ui = CoverageLineageNode(
        node_id="ui_checkout_btn",
        node_name="结账按钮防重复点击",
        category=LineageCategory.UI_INTERACTION,
        expected_branches=["normal_click", "rapid_double_click_debounce"],
        covered_branches=["normal_click"],
        risk_level=CoverageRiskLevel.MEDIUM,
    )
    ui_drafts = synthesize_cases_for_gap_node(node_ui)
    assert len(ui_drafts) == 1
    d_ui = ui_drafts[0]
    assert d_ui.case_type == "web"
    assert d_ui.priority == "P1"
    assert d_ui.steps[0].action_type == "ui_action"

    # 3. 批量合成
    all_drafts = synthesize_cases_for_all_gaps([node_api, node_ui])
    assert len(all_drafts) == 2
