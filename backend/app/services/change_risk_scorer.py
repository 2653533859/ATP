"""代码变更行数/圈复杂度与核心度多维风险指数模型引擎 (S2.2).

结合 Git Diff 代码变更规模、AST 控制流圈复杂度增量 (Cyclomatic Complexity Delta)
以及核心涉敏资产路径匹配，综合推导代码变更风险指数 (Change Risk Score, 0-100) 与风险等级。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import re
from typing import Any
import uuid

from app.services.git_diff_ast_analyzer import analyze_git_diff_ast

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    CRITICAL = "CRITICAL"  # 极高风险: ≥ 75
    HIGH = "HIGH"  # 高风险: 50 ~ 74
    MEDIUM = "MEDIUM"  # 中等风险: 25 ~ 49
    LOW = "LOW"  # 低风险: < 25


@dataclass
class RiskDimensionBreakdown:
    dimension_name: str
    score: float  # 0.0 ~ 100.0
    weight: float  # 0.0 ~ 1.0
    raw_metrics: dict[str, Any]
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension_name": self.dimension_name,
            "score": round(self.score, 2),
            "weight": self.weight,
            "raw_metrics": self.raw_metrics,
            "description": self.description,
        }


@dataclass
class ChangeRiskReport:
    risk_id: str
    overall_risk_score: float
    risk_level: RiskLevel
    dimensions: dict[str, RiskDimensionBreakdown]
    high_risk_files: list[str]
    risk_factors_summary: list[str]
    recommended_action: str
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "overall_risk_score": round(self.overall_risk_score, 2),
            "risk_level": self.risk_level.value,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "high_risk_files": self.high_risk_files,
            "risk_factors_summary": self.risk_factors_summary,
            "recommended_action": self.recommended_action,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


# 内存报告仓库
_CHANGE_RISK_REPORTS: dict[str, ChangeRiskReport] = {}

# 默认核心高危模块路径正则模式库
DEFAULT_CRITICAL_PATTERNS = [
    r"^backend/app/core/.*",
    r"^backend/app/api/deps\.py",
    r".*/auth.*",
    r".*/pay.*",
    r".*/billing.*",
    r".*/security.*",
    r".*/models/.*",
    r"^alembic/.*",
]


def _calculate_volume_score(
    total_added: int, total_deleted: int, changed_files_count: int
) -> tuple[float, dict[str, Any], str]:
    """维度 1：计算代码变更规模得分。"""
    total_loc = total_added + total_deleted
    raw = {
        "total_added_lines": total_added,
        "total_deleted_lines": total_deleted,
        "total_loc_delta": total_loc,
        "changed_files_count": changed_files_count,
    }

    if total_loc <= 20 and changed_files_count <= 2:
        score = 15.0
        desc = "变更行数极少 (≤20 行)，属于微型安全局部修改"
    elif total_loc <= 100:
        score = 40.0
        desc = f"变更代码规模适中 (共 {total_loc} 行，涉及 {changed_files_count} 个文件)"
    elif total_loc <= 300:
        score = 70.0
        desc = f"变更体量较大 (共 {total_loc} 行)，可能涉及跨文件模块重构"
    else:
        score = 95.0
        desc = f"超大体量代码变更 (共 {total_loc} 行)，存在较高潜在回归风险"

    return score, raw, desc


def _calculate_ast_complexity_delta(source_code: str, changed_line_numbers: list[int]) -> int:
    """遍历 AST 计算变更行所引入的圈复杂度分支增量。"""
    if not source_code or not changed_line_numbers:
        return 0

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return 0

    changed_lines_set = set(changed_line_numbers)
    complexity_delta = 0

    for node in ast.walk(tree):
        node_lineno = getattr(node, "lineno", None)
        if node_lineno is None or node_lineno not in changed_lines_set:
            continue

        # 遇到控制流分支或异常跳转节点增加复杂度
        if isinstance(
            node,
            (
                ast.If,
                ast.For,
                ast.While,
                ast.ExceptHandler,
                ast.With,
                ast.IfExp,
                ast.Assert,
            ),
        ):
            complexity_delta += 1
        elif isinstance(node, ast.BoolOp):
            # 逻辑与/或操作符引入多重判断
            complexity_delta += max(1, len(node.values) - 1)
    return complexity_delta


def _calculate_complexity_score(
    total_complexity_delta: int,
) -> tuple[float, dict[str, Any], str]:
    """维度 2：计算控制流圈复杂度增量得分。"""
    raw = {"complexity_delta_count": total_complexity_delta}

    if total_complexity_delta == 0:
        score = 10.0
        desc = "未引入新的控制流分支或复杂条件嵌套"
    elif total_complexity_delta <= 3:
        score = 35.0
        desc = f"引入轻微控制流分支 (增量: {total_complexity_delta})"
    elif total_complexity_delta <= 8:
        score = 65.0
        desc = f"引入较多控制分支或异常处理逻辑 (增量: {total_complexity_delta})"
    else:
        score = 95.0
        desc = f"高圈复杂度增量 (增量: {total_complexity_delta})，包含大量深层分支嵌套"

    return score, raw, desc


def _calculate_criticality_score(
    file_paths: list[str], critical_patterns: list[str]
) -> tuple[float, dict[str, Any], str, list[str]]:
    """维度 3：计算触及核心模块涉敏度得分。"""
    compiled_patterns = [re.compile(p, re.IGNORECASE) for p in critical_patterns]
    high_risk_files: list[str] = []

    for fpath in file_paths:
        for pat in compiled_patterns:
            if pat.search(fpath):
                high_risk_files.append(fpath)
                break

    raw = {
        "high_risk_files_count": len(high_risk_files),
        "high_risk_files": high_risk_files,
    }

    if not high_risk_files:
        score = 15.0
        desc = "未触及认证鉴权、加密、支付或核心数据模型"
    elif len(high_risk_files) == 1:
        score = 75.0
        desc = f"触及 1 处高危核心服务模块: {high_risk_files[0]}"
    else:
        score = 95.0
        desc = f"触及 {len(high_risk_files)} 处核心服务或涉敏模块，需强化安全把关"

    return score, raw, desc, high_risk_files


def evaluate_change_risk(
    diff_text: str,
    file_sources: dict[str, str] | None = None,
    critical_patterns: list[str] | None = None,
    weight_volume: float = 0.30,
    weight_complexity: float = 0.35,
    weight_criticality: float = 0.35,
) -> ChangeRiskReport:
    """综合计算 Git Diff 的多维代码变更风险指数与等级。"""
    risk_id = f"risk_{uuid.uuid4().hex[:12]}"
    patterns = critical_patterns or DEFAULT_CRITICAL_PATTERNS
    sources = file_sources or {}

    diff_report = analyze_git_diff_ast(diff_text=diff_text, file_sources=sources)

    total_added = diff_report.diff_summary.get("total_added_lines", 0)
    total_deleted = diff_report.diff_summary.get("total_deleted_lines", 0)
    changed_files = [f.file_path for f in diff_report.changed_files]

    # 1. 规模分
    score_vol, raw_vol, desc_vol = _calculate_volume_score(total_added, total_deleted, len(changed_files))

    # 2. 复杂度分
    total_complexity = 0
    for fdiff in diff_report.changed_files:
        if fdiff.file_path.endswith(".py"):
            src = sources.get(fdiff.file_path, "")
            total_complexity += _calculate_ast_complexity_delta(src, fdiff.changed_line_numbers)

    score_comp, raw_comp, desc_comp = _calculate_complexity_score(total_complexity)

    # 3. 核心度分
    score_crit, raw_crit, desc_crit, high_risk_files = _calculate_criticality_score(changed_files, patterns)

    # 加权聚合
    composite_score = (score_vol * weight_volume) + (score_comp * weight_complexity) + (score_crit * weight_criticality)
    composite_score = max(0.0, min(100.0, composite_score))

    # 判定风险等级
    if composite_score >= 75.0:
        level = RiskLevel.CRITICAL
        action = "阻断直接合流：必须执行全量回归用例并要求至少 2 位核心研发专家双人评审 (Reviewer Sign-off)"
    elif composite_score >= 50.0:
        level = RiskLevel.HIGH
        action = "严格门禁卡点：必须通过 S1.3 推导的精准回归测试集并由模块 Owner 签署准入"
    elif composite_score >= 25.0:
        level = RiskLevel.MEDIUM
        action = "常规准入：执行精准测试集且测试通过率达 100% 即可准入"
    else:
        level = RiskLevel.LOW
        action = "快速通道：轻量变更，通过基本语法检查与冒烟用例即可合流"

    # 汇总风险因子
    factors: list[str] = []
    if score_crit >= 70.0:
        factors.append(f"触及涉敏核心代码模块 ({len(high_risk_files)} 个文件)")
    if score_comp >= 60.0:
        factors.append(f"控制分支复杂度显著上升 (+{total_complexity})")
    if score_vol >= 60.0:
        factors.append(f"代码变更体量较大 (+{total_added}/-{total_deleted})")
    if not factors:
        factors.append("变更整体安全受控，未发现显著高危特征")

    dimensions = {
        "volume": RiskDimensionBreakdown(
            dimension_name="变更代码规模",
            score=score_vol,
            weight=weight_volume,
            raw_metrics=raw_vol,
            description=desc_vol,
        ),
        "complexity": RiskDimensionBreakdown(
            dimension_name="圈复杂度增量",
            score=score_comp,
            weight=weight_complexity,
            raw_metrics=raw_comp,
            description=desc_comp,
        ),
        "criticality": RiskDimensionBreakdown(
            dimension_name="核心资产敏感度",
            score=score_crit,
            weight=weight_criticality,
            raw_metrics=raw_crit,
            description=desc_crit,
        ),
    }

    report = ChangeRiskReport(
        risk_id=risk_id,
        overall_risk_score=composite_score,
        risk_level=level,
        dimensions=dimensions,
        high_risk_files=high_risk_files,
        risk_factors_summary=factors,
        recommended_action=action,
    )

    _CHANGE_RISK_REPORTS[risk_id] = report
    logger.info(
        "Evaluated change risk: id=%s score=%.1f level=%s high_risk_files=%d",
        risk_id,
        composite_score,
        level.value,
        len(high_risk_files),
    )
    return report


def get_change_risk_report(risk_id: str) -> ChangeRiskReport | None:
    """获取指定风险评估报告。"""
    return _CHANGE_RISK_REPORTS.get(risk_id)


def list_change_risk_reports() -> list[ChangeRiskReport]:
    """查询历史风险评估报告列表。"""
    return list(_CHANGE_RISK_REPORTS.values())


def reset_change_risk_registry() -> None:
    """单元测试清理状态使用。"""
    _CHANGE_RISK_REPORTS.clear()
