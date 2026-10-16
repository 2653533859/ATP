"""Unit tests for PR Comment Bot Dispatcher Service (S4.2)."""

from __future__ import annotations

import pytest

from app.services.pr_comment_bot_dispatcher import (
    GitPlatformType,
    dispatch_pr_comment,
    generate_pr_comment_markdown,
    get_pr_comment,
    list_pr_comments,
    reset_pr_comment_registry,
)
from app.services.pr_quality_gatekeeper import (
    MergeGateVerdict,
    evaluate_pr_quality_gate,
    reset_pr_gate_registry,
)


@pytest.fixture(autouse=True)
def clean_comment_registry():
    reset_pr_gate_registry()
    reset_pr_comment_registry()
    yield
    reset_pr_gate_registry()
    reset_pr_comment_registry()


def test_generate_pr_comment_markdown_approved():
    report = evaluate_pr_quality_gate(
        pr_id="101",
        commit_sha="a1b2c3d4",
        author="alice",
        test_pass_rate_pct=100.0,
        mutation_score_pct=90.0,
        risk_score=15.0,
        risk_level="LOW",
    )

    markdown = generate_pr_comment_markdown(report)
    assert "🟢 [ATP CI Gatekeeper] PR 合并准入审核通过" in markdown
    assert "综合合规分" in markdown
    assert "100.0 / 100" in markdown
    assert "#101" in markdown
    assert "@alice" in markdown
    assert "全要素质量门禁规则裁决明细" in markdown


def test_generate_pr_comment_markdown_blocked():
    report = evaluate_pr_quality_gate(
        pr_id="102",
        commit_sha="e5f6a7b8",
        author="bob",
        test_pass_rate_pct=90.0,
        test_failed_cases_count=2,
        mutation_score_pct=35.0,
    )

    markdown = generate_pr_comment_markdown(report)
    assert "🔴 [ATP CI Gatekeeper] PR 合并准入审核阻断" in markdown
    assert "阻断合流的原因清单" in markdown
    assert "建议解除阻断的修复行动项" in markdown


def test_dispatch_pr_comment():
    report = evaluate_pr_quality_gate(
        pr_id="201",
        commit_sha="11223344",
        author="carol",
    )

    comment = dispatch_pr_comment(
        gate_report_or_id=report,
        repo_name="2653533859/ATP",
        platform=GitPlatformType.GITHUB,
        simulate_success=True,
    )

    assert comment.pr_id == "201"
    assert comment.platform == GitPlatformType.GITHUB
    assert comment.repo_name == "2653533859/ATP"
    assert comment.delivered_successfully is True
    assert comment.verdict == MergeGateVerdict.MERGE_APPROVED
    assert len(comment.markdown_body) > 100

    fetched = get_pr_comment(comment.comment_id)
    assert fetched is not None
    assert fetched.comment_id == comment.comment_id

    comments = list_pr_comments()
    assert len(comments) == 1
    assert comments[0].comment_id == comment.comment_id


def test_dispatch_pr_comment_invalid_gate_id():
    with pytest.raises(ValueError, match="未找到指定的门禁报告"):
        dispatch_pr_comment(gate_report_or_id="non_existent_gate_id")
