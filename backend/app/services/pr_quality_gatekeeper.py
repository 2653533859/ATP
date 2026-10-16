"""PR 代码变更全要素质量门禁与合并准入判定仲裁器 (S4.1).

综合代码变更风险指数 (S2.2)、精准推荐回归测试通过率 (S1.3)、
代码变异断言有效性得分 (S3.3) 以及核心模块审批流，
执行自动化质量门禁裁决，判定 PR 是否满足合流条件 (MERGE_APPROVED / MERGE_BLOCKED / CONDITIONAL_PASS)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class MergeGateVerdict(str, Enum):
    MERGE_APPROVED = "MERGE_APPROVED"  # 准入通过: 所有硬性质量门禁全部达标
    MERGE_BLOCKED = "MERGE_BLOCKED"  # 阻断合流: 存在阻断性硬门禁违规，禁止合并入主干
    CONDITIONAL_PASS = "CONDITIONAL_PASS"  # 带条件通过: 存在次要风险告警，需模块负责人复核签字


@dataclass
class GateRuleEvaluation:
    rule_id: str
    rule_name: str
    passed: bool
    severity: str  # blocking | warning
    measured_value: Any
    threshold_value: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "passed": self.passed,
            "severity": self.severity,
            "measured_value": self.measured_value,
            "threshold_value": self.threshold_value,
            "message": self.message,
        }


@dataclass
class PrGateVerdictReport:
    gate_id: str
    pr_id: str
    commit_sha: str
    author: str
    target_branch: str
    verdict: MergeGateVerdict
    is_mergeable: bool
    overall_compliance_score: float  # 0.0 ~ 100.0
    blocking_reasons: list[str]
    warning_reasons: list[str]
    evaluated_rules: list[GateRuleEvaluation]
    remediation_steps: list[str]
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "pr_id": self.pr_id,
            "commit_sha": self.commit_sha,
            "author": self.author,
            "target_branch": self.target_branch,
            "verdict": self.verdict.value,
            "is_mergeable": self.is_mergeable,
            "overall_compliance_score": round(self.overall_compliance_score, 2),
            "blocking_reasons": self.blocking_reasons,
            "warning_reasons": self.warning_reasons,
            "evaluated_rules": [r.to_dict() for r in self.evaluated_rules],
            "remediation_steps": self.remediation_steps,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


# 内存报告仓库
_PR_GATE_REPORTS: dict[str, PrGateVerdictReport] = {}


def evaluate_pr_quality_gate(
    pr_id: str | int,
    commit_sha: str,
    author: str = "developer",
    target_branch: str = "main",
    test_pass_rate_pct: float = 100.0,
    test_failed_cases_count: int = 0,
    risk_score: float = 20.0,
    risk_level: str = "LOW",
    mutation_score_pct: float | None = 80.0,
    has_dual_approvals: bool = False,
    min_pass_rate_threshold: float = 100.0,
    min_mutation_score_threshold: float = 70.0,
) -> PrGateVerdictReport:
    """综合多维度质量与安全指标执行 PR 合并准入裁决。"""
    gate_id = f"gate_{uuid.uuid4().hex[:12]}"
    rules: list[GateRuleEvaluation] = []
    blocking_reasons: list[str] = []
    warning_reasons: list[str] = []
    remediation: list[str] = []

    # 1. 规则 1：测试通过率门禁 (硬卡点)
    rule_pass = GateRuleEvaluation(
        rule_id="RULE_TEST_PASS_RATE",
        rule_name="自动化精准回归用例通过率门禁",
        passed=(test_failed_cases_count == 0 and test_pass_rate_pct >= min_pass_rate_threshold),
        severity="blocking",
        measured_value=f"{test_pass_rate_pct:.1f}% (失败 {test_failed_cases_count} 个)",
        threshold_value=f"{min_pass_rate_threshold:.1f}%",
        message="自动化测试用例全部执行通过"
        if test_failed_cases_count == 0
        else f"存在 {test_failed_cases_count} 个失败用例阻断合流",
    )
    rules.append(rule_pass)
    if not rule_pass.passed:
        blocking_reasons.append(
            f"自动化测试存在失败用例: 通过率仅 {test_pass_rate_pct:.1f}% (失败 {test_failed_cases_count} 个)"
        )
        remediation.append("排查并修复所有失败的自动化测试用例，确保 CI 推荐测试集 100% 变绿。")

    # 2. 规则 2：代码变异断言有效性门禁
    if mutation_score_pct is not None:
        mut_passed = mutation_score_pct >= min_mutation_score_threshold
        rule_mut = GateRuleEvaluation(
            rule_id="RULE_MUTATION_SCORE",
            rule_name="代码变异断言充分性门禁 (Mutation Score)",
            passed=mut_passed,
            severity="blocking" if mutation_score_pct < 50.0 else "warning",
            measured_value=f"{mutation_score_pct:.1f}%",
            threshold_value=f"{min_mutation_score_threshold:.1f}%",
            message=f"代码变异得分达到 {mutation_score_pct:.1f}%"
            if mut_passed
            else f"变异得分过低 ({mutation_score_pct:.1f}%)，测试断言虚设/存活变异体过多",
        )
        rules.append(rule_mut)
        if not mut_passed:
            if mutation_score_pct < 50.0:
                blocking_reasons.append(f"代码变异得分严重不达标 ({mutation_score_pct:.1f}% < 50%)，断言严重脆弱虚设")
                remediation.append("查看变异测试存活变异体清单，为缺少实质断言的代码分支补充严格的 assert 校验。")
            else:
                warning_reasons.append(
                    f"代码变异得分略低 ({mutation_score_pct:.1f}% < {min_mutation_score_threshold:.1f}%)，建议补充断言"
                )
                remediation.append("建议补充边界值与异常分支断言，提高对代码突变逻辑的防御度。")

    # 3. 规则 3：代码变更风险与双人审批门禁
    clean_level = risk_level.upper()
    if clean_level == "CRITICAL":
        risk_passed = has_dual_approvals
        rule_risk = GateRuleEvaluation(
            rule_id="RULE_CRITICAL_CHANGE_APPROVAL",
            rule_name="极高风险变更双人评审签批门禁 (Reviewer Sign-off)",
            passed=risk_passed,
            severity="blocking",
            measured_value=f"风险分 {risk_score:.1f} (CRITICAL) · 双人签字: {has_dual_approvals}",
            threshold_value="风险分 ≥ 75 必须获得至少 2 位核心研发审批",
            message="极高风险变更已获得双人签批" if risk_passed else "极高风险变更尚未获得双人签批，禁止合入主干",
        )
        rules.append(rule_risk)
        if not risk_passed:
            blocking_reasons.append("变更风险指数达 CRITICAL 极高危等级，且尚未获得 2 位核心研发双人签字确认")
            remediation.append("联系项目架构师或核心技术负责人 (Reviewers) 对本次高危涉敏代码变更进行复核并批准。")
    elif clean_level == "HIGH":
        warning_reasons.append("本次变更风险等级为 HIGH，建议相关模块负责人重点关注。")

    # 4. 仲裁综合裁决与合规质量分
    passed_rules_count = sum(1 for r in rules if r.passed)
    compliance_score = (float(passed_rules_count) / float(len(rules)) * 100.0) if rules else 100.0

    if blocking_reasons:
        verdict = MergeGateVerdict.MERGE_BLOCKED
        is_mergeable = False
    elif warning_reasons:
        verdict = MergeGateVerdict.CONDITIONAL_PASS
        is_mergeable = True
    else:
        verdict = MergeGateVerdict.MERGE_APPROVED
        is_mergeable = True

    report = PrGateVerdictReport(
        gate_id=gate_id,
        pr_id=str(pr_id),
        commit_sha=commit_sha,
        author=author,
        target_branch=target_branch,
        verdict=verdict,
        is_mergeable=is_mergeable,
        overall_compliance_score=compliance_score,
        blocking_reasons=blocking_reasons,
        warning_reasons=warning_reasons,
        evaluated_rules=rules,
        remediation_steps=remediation,
    )

    _PR_GATE_REPORTS[gate_id] = report
    logger.info(
        "PR gate evaluated: pr=%s sha=%s verdict=%s mergeable=%s score=%.1f",
        pr_id,
        commit_sha[:8],
        verdict.value,
        is_mergeable,
        compliance_score,
    )
    return report


def get_pr_gate_report(gate_id: str) -> PrGateVerdictReport | None:
    """获取指定 PR 门禁裁决报告。"""
    return _PR_GATE_REPORTS.get(gate_id)


def list_pr_gate_reports() -> list[PrGateVerdictReport]:
    """查询历史 PR 门禁裁决报告列表。"""
    return list(_PR_GATE_REPORTS.values())


def reset_pr_gate_registry() -> None:
    """单元测试清理状态使用。"""
    _PR_GATE_REPORTS.clear()
