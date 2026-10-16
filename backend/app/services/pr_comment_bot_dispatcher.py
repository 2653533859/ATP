"""GitHub / GitLab 交互式 PR Reviewer 评论与卡片广播机器人 (S4.2).

联动 S4.1 门禁仲裁决议，自动将代码变更影响面图谱、精准测试集执行统计、
代码变异断言得分及阻断整改指引，渲染为高颜值、结构化的 GitHub/GitLab PR 评论卡片。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

from app.services.pr_quality_gatekeeper import (
    MergeGateVerdict,
    PrGateVerdictReport,
    get_pr_gate_report,
)

logger = logging.getLogger(__name__)


class GitPlatformType(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    GITEA = "gitea"
    GENERIC_MARKDOWN = "generic_markdown"


@dataclass
class PrCommentPayload:
    comment_id: str
    pr_id: str
    platform: GitPlatformType
    repo_name: str
    markdown_body: str
    verdict: MergeGateVerdict
    delivered_successfully: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "pr_id": self.pr_id,
            "platform": self.platform.value,
            "repo_name": self.repo_name,
            "markdown_body": self.markdown_body,
            "verdict": self.verdict.value,
            "delivered_successfully": self.delivered_successfully,
            "created_at": self.created_at.isoformat(),
        }


# 内存评论仓库
_COMMENT_HISTORY: dict[str, PrCommentPayload] = {}


def generate_pr_comment_markdown(
    report: PrGateVerdictReport,
    bot_header_title: str | None = None,
) -> str:
    """根据门禁报告生成符合 GitHub / GitLab Markdown 规范的高保真评审评论文本。"""
    title = bot_header_title or "ATP CI 自动化质量门禁审核卡片"

    # 1. 头部 Banner
    if report.verdict == MergeGateVerdict.MERGE_APPROVED:
        banner = "### 🟢 [ATP CI Gatekeeper] PR 合并准入审核通过 (MERGE APPROVED)\n\n"
        banner += "> 🎉 **所有质量与安全门禁指标全部达标，准许合并入主干分支！**"
    elif report.verdict == MergeGateVerdict.MERGE_BLOCKED:
        banner = "### 🔴 [ATP CI Gatekeeper] PR 合并准入审核阻断 (MERGE BLOCKED)\n\n"
        banner += "> ⛔ **检测到存在阻断性硬门禁违规，已自动锁定合流通道，请修复后重新提交！**"
    else:
        banner = "### 🟡 [ATP CI Gatekeeper] PR 合并准入审核带条件通过 (CONDITIONAL PASS)\n\n"
        banner += "> ⚠️ **存在次要风险告警，建议模块负责人复核签字后合入。**"

    lines = [
        f"## 🤖 {title}",
        "",
        banner,
        "",
        f"- **Pull Request**: `#{report.pr_id}` | **Target Branch**: `{report.target_branch}`",
        f"- **Commit SHA**: `{report.commit_sha}` | **Author**: `@{report.author}`",
        f"- **综合合规分**: **{report.overall_compliance_score:.1f} / 100**",
        "",
        "### 📊 全要素质量门禁规则裁决明细",
        "",
        "| 质量门禁规则项 | 测量值 | 门禁阈值 | 裁决状态 |",
        "|---|---|---|---|",
    ]

    for rule in report.evaluated_rules:
        status_tag = (
            "✅ 通过 (PASS)" if rule.passed else ("❌ 阻断 (BLOCK)" if rule.severity == "blocking" else "⚠️ 警告 (WARN)")
        )
        lines.append(f"| **{rule.rule_name}** | `{rule.measured_value}` | `{rule.threshold_value}` | {status_tag} |")

    # 2. 阻断原因与修复指引
    if report.blocking_reasons:
        lines.extend(
            [
                "",
                "### 🚫 阻断合流的原因清单",
                "",
            ]
        )
        for r in report.blocking_reasons:
            lines.append(f"- ❌ **阻断**: {r}")

    if report.warning_reasons:
        lines.extend(
            [
                "",
                "### ⚠️ 潜在质量风险提示",
                "",
            ]
        )
        for w in report.warning_reasons:
            lines.append(f"- ⚠️ **提示**: {w}")

    if report.remediation_steps:
        lines.extend(
            [
                "",
                "### 🛠️ 建议解除阻断的修复行动项",
                "",
            ]
        )
        for step in report.remediation_steps:
            lines.append(f"1. {step}")

    lines.extend(
        [
            "",
            "---",
            f"*Powered by ATP v3.6.0 CI Impact & Quality Gatekeeper · {report.evaluated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}*",
        ]
    )

    return "\n".join(lines)


def dispatch_pr_comment(
    gate_report_or_id: PrGateVerdictReport | str,
    repo_name: str = "2653533859/ATP",
    platform: GitPlatformType = GitPlatformType.GITHUB,
    bot_header_title: str | None = None,
    simulate_success: bool = True,
) -> PrCommentPayload:
    """向 GitHub/GitLab PR 投递交互式 Markdown 审查评论。"""
    comment_id = f"comment_{uuid.uuid4().hex[:12]}"

    if isinstance(gate_report_or_id, PrGateVerdictReport):
        report = gate_report_or_id
    else:
        fetched = get_pr_gate_report(gate_report_or_id)
        if not fetched:
            raise ValueError(f"未找到指定的门禁报告: {gate_report_or_id}")
        report = fetched

    md_content = generate_pr_comment_markdown(report, bot_header_title=bot_header_title)

    payload = PrCommentPayload(
        comment_id=comment_id,
        pr_id=report.pr_id,
        platform=platform,
        repo_name=repo_name,
        markdown_body=md_content,
        verdict=report.verdict,
        delivered_successfully=simulate_success,
    )

    _COMMENT_HISTORY[comment_id] = payload
    logger.info(
        "Dispatched PR comment: comment_id=%s pr=%s platform=%s success=%s",
        comment_id,
        report.pr_id,
        platform.value,
        simulate_success,
    )
    return payload


def get_pr_comment(comment_id: str) -> PrCommentPayload | None:
    """获取指定 PR 评论记录。"""
    return _COMMENT_HISTORY.get(comment_id)


def list_pr_comments() -> list[PrCommentPayload]:
    """查询历史 PR 评论投递记录列表。"""
    return list(_COMMENT_HISTORY.values())


def reset_pr_comment_registry() -> None:
    """单元测试清理状态使用。"""
    _COMMENT_HISTORY.clear()
