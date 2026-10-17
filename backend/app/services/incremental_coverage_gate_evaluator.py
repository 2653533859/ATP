"""增量覆盖率发布准入卡点与红线裁决器服务 (T2.3)

在 CI/CD 流水线中针对 PR/Commit 判定增量代码覆盖率是否满足发布准入门槛:
1. 多维准入防线策略定义 (IncrementalCoverageGatePolicy: 行覆盖率红线、分支门槛、P0未覆盖零容忍、豁免白名单);
2. 增量代码行与分支覆盖率达标严格核算 (支持忽略 tests/* 及配置脚本等豁免路径);
3. 四态裁决结论输出 (CoverageGateVerdictAction: PASSED_CONFORMANT 合规通过、BLOCKED_DEFICIT 强阻断、WARNING_CONDITIONAL 预警);
4. 阻断红线明细与自动化整改补测建议生成 (IncrementalCoverageGateVerdict)。
"""

from __future__ import annotations

import enum
import fnmatch
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.diff_coverage_staining_engine import DiffCoverageReport, FileDiffCoverageStaining
from app.services.uncovered_branch_risk_analyzer import (
    BranchRiskSeverity,
    UncoveredBranchAnalysisReport,
)


class CoverageGateVerdictAction(str, enum.Enum):
    PASSED_CONFORMANT = "PASSED_CONFORMANT"  # 准入合规通过，允许合并或发布上线
    BLOCKED_DEFICIT = "BLOCKED_DEFICIT"  # 增量覆盖率未达标或存在 P0 高危未覆盖分支，强阻断发布
    WARNING_CONDITIONAL = "WARNING_CONDITIONAL"  # 接近及格线且无 P0 分支，预警提示需限期补测


@dataclass
class IncrementalCoverageGatePolicy:
    policy_id: str = "policy_default_enterprise"
    min_diff_line_coverage_pct: float = 85.0  # 增量行覆盖率门槛 (默认 >= 85.0%)
    min_diff_branch_coverage_pct: float = 70.0  # 增量分支覆盖率门槛 (默认 >= 70.0%)
    allow_p0_uncovered: bool = False  # 是否允许 P0 阻塞级分支未覆盖 (默认严格不允许 False)
    max_allowed_uncovered_lines: int = 15  # 允许的最大未覆盖变更行数上限
    exempt_file_patterns: List[str] = field(
        default_factory=lambda: [
            "tests/*",
            "test/*",
            "*.spec.ts",
            "*.test.ts",
            "test_*.py",
            "alembic/*",
            "migrations/*",
            "docs/*",
            "*.json",
            "*.md",
        ]
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IncrementalCoverageGateVerdict:
    verdict_id: str
    diff_report_id: str
    is_passed: bool
    action: CoverageGateVerdictAction
    actual_diff_line_coverage_pct: float
    target_min_diff_line_coverage_pct: float
    actual_diff_branch_coverage_pct: float
    target_min_diff_branch_coverage_pct: float
    p0_uncovered_count: int
    uncovered_lines_count: int
    breached_rules: List[str]
    remediation_suggestions: List[str]
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict_id": self.verdict_id,
            "diff_report_id": self.diff_report_id,
            "is_passed": self.is_passed,
            "action": self.action.value,
            "actual_diff_line_coverage_pct": round(self.actual_diff_line_coverage_pct, 1),
            "target_min_diff_line_coverage_pct": round(self.target_min_diff_line_coverage_pct, 1),
            "actual_diff_branch_coverage_pct": round(self.actual_diff_branch_coverage_pct, 1),
            "target_min_diff_branch_coverage_pct": round(self.target_min_diff_branch_coverage_pct, 1),
            "p0_uncovered_count": self.p0_uncovered_count,
            "uncovered_lines_count": self.uncovered_lines_count,
            "breached_rules": self.breached_rules,
            "remediation_suggestions": self.remediation_suggestions,
            "evaluated_at": self.evaluated_at,
        }


def _is_file_exempt(file_path: str, exempt_patterns: List[str]) -> bool:
    """检查文件是否命中豁免过滤白名单 (如测试文件/文档/配置)"""
    norm_path = file_path.replace("\\", "/").strip("/")
    for pat in exempt_patterns:
        if fnmatch.fnmatch(norm_path, pat) or fnmatch.fnmatch(norm_path.split("/")[-1], pat):
            return True
    return False


def evaluate_incremental_coverage_gate(
    diff_coverage_report: DiffCoverageReport,
    uncovered_analysis: Optional[UncoveredBranchAnalysisReport] = None,
    policy: Optional[IncrementalCoverageGatePolicy] = None,
) -> IncrementalCoverageGateVerdict:
    """综合评估本次 PR/Commit 增量覆盖率是否达到发布准入门槛"""
    verdict_id = f"gate_{uuid.uuid4().hex[:10]}"
    p = policy or IncrementalCoverageGatePolicy()
    breached_rules: List[str] = []
    suggestions: List[str] = []

    # 1. 过滤豁免文件后的增量覆盖率有效行数
    active_files: Dict[str, FileDiffCoverageStaining] = {}
    for path, f_cov in diff_coverage_report.files.items():
        if not _is_file_exempt(path, p.exempt_file_patterns):
            active_files[path] = f_cov

    tot_exec = sum(f.changed_executable_lines_count for f in active_files.values())
    tot_cov = sum(f.changed_covered_lines_count for f in active_files.values())
    tot_uncovered = sum(f.changed_uncovered_lines_count for f in active_files.values())

    tot_br = sum(f.changed_branches_total for f in active_files.values())
    tot_br_cov = sum(f.changed_branches_covered for f in active_files.values())

    line_pct = (tot_cov / tot_exec * 100.0) if tot_exec > 0 else 100.0
    br_pct = (tot_br_cov / tot_br * 100.0) if tot_br > 0 else 100.0

    # 2. 规则一：增量代码行覆盖率门槛
    if line_pct < p.min_diff_line_coverage_pct:
        breached_rules.append(
            f"增量代码行覆盖率 ({round(line_pct, 1)}%) 低于准入基准线 ({p.min_diff_line_coverage_pct}%)"
        )
        suggestions.append(
            f"建议针对变更代码增补单元测试或 API 集成测试用例，至少需新覆盖 {tot_uncovered} 行中的关键路径。"
        )

    # 3. 规则二：增量分支覆盖率门槛
    if tot_br > 0 and br_pct < p.min_diff_branch_coverage_pct:
        breached_rules.append(
            f"增量分支覆盖率 ({round(br_pct, 1)}%) 低于分支准入门槛 ({p.min_diff_branch_coverage_pct}%)"
        )
        suggestions.append(f"存在 {tot_br - tot_br_cov} 个条件分支未被测试覆盖，请针对 if/else 条件反例补充测试数据。")

    # 4. 规则三：P0 高危未覆盖分支零容忍
    p0_count = 0
    if uncovered_analysis:
        # 只统计非豁免文件中的 P0 分支
        for b in uncovered_analysis.branches:
            if not _is_file_exempt(b.file_path, p.exempt_file_patterns):
                if b.severity == BranchRiskSeverity.P0_BLOCKING:
                    p0_count += 1

        if not p.allow_p0_uncovered and p0_count > 0:
            breached_rules.append(
                f"存在 {p0_count} 处 P0 阻塞级高危未覆盖分支（涉及资金支付或安全鉴权），触发绝对准入红线"
            )
            suggestions.append("请优先修复并补齐 P0 资金结算与身份鉴权分支的测试覆盖，严禁直接带病上线！")

    # 5. 规则四：最大未覆盖变更行数限制
    if tot_uncovered > p.max_allowed_uncovered_lines:
        breached_rules.append(
            f"未覆盖增量代码行数 ({tot_uncovered} 行) 超过单次发布容许上限 ({p.max_allowed_uncovered_lines} 行)"
        )

    # 6. 确定最终准入动作
    if not breached_rules:
        action = CoverageGateVerdictAction.PASSED_CONFORMANT
        is_passed = True
        suggestions.append("增量代码行覆盖率与分支覆盖率均完全符合准入规范，无高危漏测风险，准予合并与发布。")
    else:
        # 若仅有轻微行覆盖率偏离 (如 80%~85%) 且无 P0 阻塞
        if (
            p0_count == 0
            and line_pct >= (p.min_diff_line_coverage_pct - 5.0)
            and tot_uncovered <= p.max_allowed_uncovered_lines
        ):
            action = CoverageGateVerdictAction.WARNING_CONDITIONAL
            is_passed = True
            suggestions.append("当前增量覆盖率略低于标准线但处于预警容差区间内，无 P0 阻断，允许条件性通过。")
        else:
            action = CoverageGateVerdictAction.BLOCKED_DEFICIT
            is_passed = False

    return IncrementalCoverageGateVerdict(
        verdict_id=verdict_id,
        diff_report_id=diff_coverage_report.diff_report_id,
        is_passed=is_passed,
        action=action,
        actual_diff_line_coverage_pct=line_pct,
        target_min_diff_line_coverage_pct=p.min_diff_line_coverage_pct,
        actual_diff_branch_coverage_pct=br_pct,
        target_min_diff_branch_coverage_pct=p.min_diff_branch_coverage_pct,
        p0_uncovered_count=p0_count,
        uncovered_lines_count=tot_uncovered,
        breached_rules=breached_rules,
        remediation_suggestions=suggestions,
    )
