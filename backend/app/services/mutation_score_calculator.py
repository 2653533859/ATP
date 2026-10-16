"""用例断言有效性量化与变异得分 (Mutation Score) 计算器引擎 (S3.3).

依据变异体执行检验的 Killed / Survived 统计，
按照国际软件测试标准公式计算变异得分 (Mutation Score %)，
评定测试用例集断言充分性等级 (EXCELLENT / ADEQUATE / INSUFFICIENT / WEAK)，
精准定位“只跑过无实质断言”的脆弱用例与盲区代码行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

from app.services.code_mutation_operator_engine import get_mutant_by_id
from app.services.mutation_execution_runner import (
    MutantExecutionResult,
    MutantStatus,
    get_mutation_execution_report,
)

logger = logging.getLogger(__name__)


class AssertionAdequacyLevel(str, Enum):
    EXCELLENT = "EXCELLENT"  # 卓越断言: Mutation Score ≥ 85%
    ADEQUATE = "ADEQUATE"  # 充分合格: 70% ~ 84.9%
    INSUFFICIENT = "INSUFFICIENT"  # 欠缺改进: 50% ~ 69.9%
    WEAK = "WEAK"  # 脆弱虚设: < 50% (大量存活变异体)


@dataclass
class OperatorScoreBreakdown:
    operator_type: str
    total_mutants: int
    killed_mutants: int
    survived_mutants: int
    operator_mutation_score_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_type": self.operator_type,
            "total_mutants": self.total_mutants,
            "killed_mutants": self.killed_mutants,
            "survived_mutants": self.survived_mutants,
            "operator_mutation_score_pct": round(self.operator_mutation_score_pct, 2),
        }


@dataclass
class AssertionBlindspotItem:
    mutant_id: str
    file_path: str
    line_number: int
    operator_type: str
    original_line: str
    mutated_line: str
    description: str
    suggested_assertion_fix: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutant_id": self.mutant_id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "operator_type": self.operator_type,
            "original_line": self.original_line,
            "mutated_line": self.mutated_line,
            "description": self.description,
            "suggested_assertion_fix": self.suggested_assertion_fix,
        }


@dataclass
class MutationScoreReport:
    score_id: str
    execution_run_id: str
    mutation_score_pct: float
    adequacy_level: AssertionAdequacyLevel
    total_mutants: int
    killed_count: int
    survived_count: int
    timed_out_count: int
    operator_breakdowns: dict[str, OperatorScoreBreakdown]
    blindspots: list[AssertionBlindspotItem]
    summary_verdict: str
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "score_id": self.score_id,
            "execution_run_id": self.execution_run_id,
            "mutation_score_pct": round(self.mutation_score_pct, 2),
            "adequacy_level": self.adequacy_level.value,
            "total_mutants": self.total_mutants,
            "killed_count": self.killed_count,
            "survived_count": self.survived_count,
            "timed_out_count": self.timed_out_count,
            "operator_breakdowns": {k: v.to_dict() for k, v in self.operator_breakdowns.items()},
            "blindspots": [b.to_dict() for b in self.blindspots],
            "summary_verdict": self.summary_verdict,
            "calculated_at": self.calculated_at.isoformat(),
        }


# 内存报告仓库
_MUTATION_SCORE_REPORTS: dict[str, MutationScoreReport] = {}


def _rate_adequacy_level(score: float) -> tuple[AssertionAdequacyLevel, str]:
    """根据变异得分评定测试集断言充分度等级。"""
    if score >= 85.0:
        return (
            AssertionAdequacyLevel.EXCELLENT,
            "测试用例断言极其严密 (变异得分 ≥ 85%)，成功捕获了绝大多数代码篡改与故障分支，达到卓越质量交付水准。",
        )
    elif score >= 70.0:
        return (
            AssertionAdequacyLevel.ADEQUATE,
            "测试用例断言基本合格 (变异得分 70%~85%)，满足标准发版质量门禁，但仍存在少量边界值断言盲区。",
        )
    elif score >= 50.0:
        return (
            AssertionAdequacyLevel.INSUFFICIENT,
            "测试用例断言欠缺 (变异得分 50%~70%)，半数左右代码变异未被现有测试发现，需针对盲区补充断言。",
        )
    else:
        return (
            AssertionAdequacyLevel.WEAK,
            "测试用例断言严重脆弱虚设 (变异得分 < 50%)，存在大量'仅调用函数、无状态断言'的假阳性用例，无法有效拦截代码缺陷！",
        )


def _suggest_fix_for_operator(operator_type: str, orig_line: str, mut_line: str) -> str:
    """针对具体存活变异算子生成建议补充的测试断言。"""
    if operator_type == "ROR":
        return f"当前条件反转 ({orig_line} -> {mut_line}) 未引发用例报错，建议补充对边界临界值与否定分支的显式 assert 断言。"
    elif operator_type == "LCR":
        return "逻辑连接符 and/or 替换后用例依然 PASS，说明缺少对复合条件两端独立成立与否的单元组合覆盖用例。"
    elif operator_type == "RVO":
        return f"函数返回值被篡改后用例未拦截，强烈建议增加对返回数据结构、特定数值或状态码的严格断言 assert res == expected。"
    elif operator_type == "BVO":
        return f"常数边界偏移 ±1 未被捕获，建议增加针对边界上下界点（如 0, 1, max-1, max）的极值参数化测试。"
    elif operator_type == "AOR":
        return "算术运算符变异未报错，建议校验计算产出的中间值与最终累计值。"
    return "建议检查调用该函数的测试用例，补齐针对业务实际输出的校验断言。"


def calculate_mutation_score(
    execution_results: list[MutantExecutionResult] | None = None,
    execution_run_id: str | None = None,
) -> MutationScoreReport:
    """计算变异得分并分析断言盲区。"""
    score_id = f"mut_score_{uuid.uuid4().hex[:12]}"

    # 若传入了 execution_run_id，优先从历史报告加载
    results: list[MutantExecutionResult] = []
    run_id_val = execution_run_id or "adhoc_run"

    if execution_run_id:
        rep = get_mutation_execution_report(execution_run_id)
        if rep:
            results = rep.results

    if not results and execution_results:
        results = execution_results

    total = len(results)
    if total == 0:
        report = MutationScoreReport(
            score_id=score_id,
            execution_run_id=run_id_val,
            mutation_score_pct=100.0,
            adequacy_level=AssertionAdequacyLevel.EXCELLENT,
            total_mutants=0,
            killed_count=0,
            survived_count=0,
            timed_out_count=0,
            operator_breakdowns={},
            blindspots=[],
            summary_verdict="未提供变异体验证结果，默认评定为稳固。",
        )
        _MUTATION_SCORE_REPORTS[score_id] = report
        return report

    killed_count = sum(1 for r in results if r.status == MutantStatus.KILLED)
    timed_out_count = sum(1 for r in results if r.status == MutantStatus.TIMED_OUT)
    survived_count = sum(1 for r in results if r.status == MutantStatus.SURVIVED)

    # 变异得分公式 = (KILLED + TIMED_OUT) / TOTAL * 100%
    effective_killed = killed_count + timed_out_count
    score_pct = (float(effective_killed) / float(total)) * 100.0

    level, verdict = _rate_adequacy_level(score_pct)

    # 各算子层面的捕获统计
    op_stats: dict[str, dict[str, int]] = {}
    blindspots: list[AssertionBlindspotItem] = []

    for r in results:
        op = r.operator_type
        if op not in op_stats:
            op_stats[op] = {"total": 0, "killed": 0, "survived": 0}
        op_stats[op]["total"] += 1

        if r.status in (MutantStatus.KILLED, MutantStatus.TIMED_OUT):
            op_stats[op]["killed"] += 1
        else:
            op_stats[op]["survived"] += 1

            # 存活变异体构成断言盲区
            mut_detail = get_mutant_by_id(r.mutant_id)
            orig_line = mut_detail.original_line if mut_detail else ""
            mut_line = mut_detail.mutated_line if mut_detail else ""
            fpath = mut_detail.file_path if mut_detail else "unknown.py"

            fix_advice = _suggest_fix_for_operator(r.operator_type, orig_line, mut_line)
            blindspots.append(
                AssertionBlindspotItem(
                    mutant_id=r.mutant_id,
                    file_path=fpath,
                    line_number=r.line_number,
                    operator_type=r.operator_type,
                    original_line=orig_line,
                    mutated_line=mut_line,
                    description=r.description,
                    suggested_assertion_fix=fix_advice,
                )
            )

    breakdowns: dict[str, OperatorScoreBreakdown] = {}
    for op, counts in op_stats.items():
        op_total = counts["total"]
        op_killed = counts["killed"]
        op_score = (float(op_killed) / float(op_total) * 100.0) if op_total > 0 else 0.0
        breakdowns[op] = OperatorScoreBreakdown(
            operator_type=op,
            total_mutants=op_total,
            killed_mutants=op_killed,
            survived_mutants=counts["survived"],
            operator_mutation_score_pct=op_score,
        )

    report = MutationScoreReport(
        score_id=score_id,
        execution_run_id=run_id_val,
        mutation_score_pct=score_pct,
        adequacy_level=level,
        total_mutants=total,
        killed_count=killed_count,
        survived_count=survived_count,
        timed_out_count=timed_out_count,
        operator_breakdowns=breakdowns,
        blindspots=blindspots,
        summary_verdict=verdict,
    )

    _MUTATION_SCORE_REPORTS[score_id] = report
    logger.info(
        "Calculated mutation score: id=%s score=%.2f%% level=%s blindspots=%d",
        score_id,
        score_pct,
        level.value,
        len(blindspots),
    )
    return report


def get_mutation_score_report(score_id: str) -> MutationScoreReport | None:
    """按 ID 查询变异得分报告。"""
    return _MUTATION_SCORE_REPORTS.get(score_id)


def list_mutation_score_reports() -> list[MutationScoreReport]:
    """查询历史变异得分报告列表。"""
    return list(_MUTATION_SCORE_REPORTS.values())


def reset_mutation_score_registry() -> None:
    """单元测试清理状态使用。"""
    _MUTATION_SCORE_REPORTS.clear()
