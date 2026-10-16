"""CI/CD 流水线 Checkpoint 检查点通用集成引擎 (S4.3).

为 Jenkins、GitHub Actions、GitLab CI/CD 流水线提供无侵入一键集成的检查点服务，
一键端到端编排代码差异 AST 解析、精准测试推荐、风险评估、Flaky 抑制与门禁裁决，
输出标准化流水线退出码 (Exit Code 0/1/2) 与高保真控制台日志。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import time
from typing import Any
import uuid

from app.services.change_risk_scorer import evaluate_change_risk
from app.services.flaky_test_suppression_filter import filter_flaky_tests_for_ci
from app.services.pr_quality_gatekeeper import (
    MergeGateVerdict,
    evaluate_pr_quality_gate,
)
from app.services.smart_test_selection_engine import (
    SelectionStrategy,
    select_tests_from_diff,
)

logger = logging.getLogger(__name__)


class PipelineStageStatus(str, Enum):
    PASSED = "PASSED"  # 退出码 0: 成功放行
    BLOCKED = "BLOCKED"  # 退出码 1: 门禁硬阻断，流水线失败中断
    WARNING = "WARNING"  # 退出码 2: 次要风险告警，非致命提示


@dataclass
class CheckpointStageResult:
    stage_name: str
    status: PipelineStageStatus
    duration_ms: float
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 2),
            "summary": self.summary,
            "details": self.details,
        }


@dataclass
class CheckpointExecutionReport:
    checkpoint_id: str
    pipeline_name: str
    commit_sha: str
    pr_id: str
    exit_code: int  # 0: PASS, 1: BLOCK, 2: WARN
    overall_status: PipelineStageStatus
    stages: list[CheckpointStageResult]
    remediation_summary: list[str]
    console_log_output: str
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "pipeline_name": self.pipeline_name,
            "commit_sha": self.commit_sha,
            "pr_id": self.pr_id,
            "exit_code": self.exit_code,
            "overall_status": self.overall_status.value,
            "stages": [s.to_dict() for s in self.stages],
            "remediation_summary": self.remediation_summary,
            "console_log_output": self.console_log_output,
            "executed_at": self.executed_at.isoformat(),
        }


# 内存报告仓库
_CHECKPOINT_REPORTS: dict[str, CheckpointExecutionReport] = {}


def execute_ci_pipeline_checkpoint(
    diff_text: str,
    pipeline_name: str = "GitHub-Actions-CI",
    commit_sha: str = "HEAD",
    pr_id: str = "0",
    author: str = "developer",
    target_branch: str = "main",
    file_sources: dict[str, str] | None = None,
    selection_strategy: SelectionStrategy = SelectionStrategy.BALANCED,
    mock_test_pass_rate_pct: float = 100.0,
    mock_test_failed_cases_count: int = 0,
    mutation_score_pct: float | None = 85.0,
    has_dual_approvals: bool = False,
) -> CheckpointExecutionReport:
    """端到端编排执行 CI 检查点并计算退出码与格式化控制台日志。"""
    checkpoint_id = f"chk_{uuid.uuid4().hex[:12]}"
    stages: list[CheckpointStageResult] = []
    log_lines: list[str] = [
        "================================================================================",
        f"🚀 [ATP CI Checkpoint] 开始执行全要素代码质量与准入检查点: {pipeline_name}",
        f"   Commit SHA: {commit_sha} | PR: #{pr_id} | Author: @{author} | Target: {target_branch}",
        "================================================================================",
    ]

    # --- Stage 1: TIA 精准测试推荐与差异解析 ---
    s1_start = time.perf_counter()
    sel_report = select_tests_from_diff(
        diff_text=diff_text,
        file_sources=file_sources,
        strategy=selection_strategy,
    )
    s1_duration = (time.perf_counter() - s1_start) * 1000.0

    stages.append(
        CheckpointStageResult(
            stage_name="Test Impact Analysis (TIA)",
            status=PipelineStageStatus.PASSED,
            duration_ms=s1_duration,
            summary=f"已筛选出 {sel_report.selected_cases_count} 个必要用例，自动裁剪 {sel_report.pruning_ratio_pct:.1f}% 冗余",
            details={
                "selected_cases_count": sel_report.selected_cases_count,
                "pruned_cases_count": sel_report.pruned_cases_count,
                "pruning_ratio_pct": sel_report.pruning_ratio_pct,
            },
        )
    )
    log_lines.append(
        f"[STAGE 1] 精准测试集分析完成: 推荐 {sel_report.selected_cases_count} 个用例 (冗余裁剪率: {sel_report.pruning_ratio_pct:.1f}%)"
    )

    # --- Stage 2: 代码变更风险指数评估 ---
    s2_start = time.perf_counter()
    risk_report = evaluate_change_risk(
        diff_text=diff_text,
        file_sources=file_sources,
    )
    s2_duration = (time.perf_counter() - s2_start) * 1000.0

    risk_status = (
        PipelineStageStatus.WARNING if risk_report.risk_level.value == "CRITICAL" else PipelineStageStatus.PASSED
    )
    stages.append(
        CheckpointStageResult(
            stage_name="Change Risk Scoring",
            status=risk_status,
            duration_ms=s2_duration,
            summary=f"代码变更风险分 {risk_report.overall_risk_score:.1f} ({risk_report.risk_level.value})",
            details={
                "risk_score": risk_report.overall_risk_score,
                "risk_level": risk_report.risk_level.value,
                "high_risk_files": risk_report.high_risk_files,
            },
        )
    )
    log_lines.append(
        f"[STAGE 2] 变更风险指数评估: {risk_report.overall_risk_score:.1f} 分 ({risk_report.risk_level.value}) - {risk_report.recommended_action}"
    )

    # --- Stage 3: Flaky 抖动用例自适应抑制 ---
    s3_start = time.perf_counter()
    candidate_cases = [{"case_id": c.case_id, "case_name": c.case_name} for c in sel_report.selected_cases]
    flaky_report = filter_flaky_tests_for_ci(cases_to_evaluate=candidate_cases)
    s3_duration = (time.perf_counter() - s3_start) * 1000.0

    stages.append(
        CheckpointStageResult(
            stage_name="Flaky Test Suppression",
            status=PipelineStageStatus.PASSED,
            duration_ms=s3_duration,
            summary=f"主干阻塞用例 {len(flaky_report.actionable_case_ids)} 个，隔离观察用例 {len(flaky_report.quarantined_case_ids)} 个",
            details={
                "actionable_count": len(flaky_report.actionable_case_ids),
                "quarantined_count": len(flaky_report.quarantined_case_ids),
            },
        )
    )
    log_lines.append(
        f"[STAGE 3] 抖动用例自适应隔离: 移出主干隔离 {len(flaky_report.quarantined_case_ids)} 个，放行主干 {len(flaky_report.actionable_case_ids)} 个"
    )

    # --- Stage 4: PR 全要素门禁综合仲裁 ---
    s4_start = time.perf_counter()
    gate_report = evaluate_pr_quality_gate(
        pr_id=pr_id,
        commit_sha=commit_sha,
        author=author,
        target_branch=target_branch,
        test_pass_rate_pct=mock_test_pass_rate_pct,
        test_failed_cases_count=mock_test_failed_cases_count,
        risk_score=risk_report.overall_risk_score,
        risk_level=risk_report.risk_level.value,
        mutation_score_pct=mutation_score_pct,
        has_dual_approvals=has_dual_approvals,
    )
    s4_duration = (time.perf_counter() - s4_start) * 1000.0

    # 根据门禁仲裁决议映射最终流水线退出码
    if gate_report.verdict == MergeGateVerdict.MERGE_APPROVED:
        overall_status = PipelineStageStatus.PASSED
        exit_code = 0
        gate_status = PipelineStageStatus.PASSED
    elif gate_report.verdict == MergeGateVerdict.MERGE_BLOCKED:
        overall_status = PipelineStageStatus.BLOCKED
        exit_code = 1
        gate_status = PipelineStageStatus.BLOCKED
    else:
        overall_status = PipelineStageStatus.WARNING
        exit_code = 2
        gate_status = PipelineStageStatus.WARNING

    stages.append(
        CheckpointStageResult(
            stage_name="PR Quality Gatekeeper",
            status=gate_status,
            duration_ms=s4_duration,
            summary=f"准入决议: {gate_report.verdict.value} (合规分 {gate_report.overall_compliance_score:.1f})",
            details={
                "verdict": gate_report.verdict.value,
                "is_mergeable": gate_report.is_mergeable,
                "blocking_reasons": gate_report.blocking_reasons,
            },
        )
    )

    log_lines.append("--------------------------------------------------------------------------------")
    if exit_code == 0:
        log_lines.append(f"✅ [ATP CI 门禁检查点通过] 决议: {gate_report.verdict.value} | 退出码: {exit_code}")
    elif exit_code == 1:
        log_lines.append(f"❌ [ATP CI 门禁硬性阻断] 决议: {gate_report.verdict.value} | 退出码: {exit_code}")
        for reason in gate_report.blocking_reasons:
            log_lines.append(f"   [BLOCK REASON] {reason}")
    else:
        log_lines.append(f"⚠️ [ATP CI 门禁警告放行] 决议: {gate_report.verdict.value} | 退出码: {exit_code}")
        for warn in gate_report.warning_reasons:
            log_lines.append(f"   [WARNING] {warn}")

    if gate_report.remediation_steps:
        log_lines.append("🛠️ 解除阻断指引:")
        for idx, step in enumerate(gate_report.remediation_steps, 1):
            log_lines.append(f"   {idx}. {step}")
    log_lines.append("================================================================================")

    console_log = "\n".join(log_lines)

    report = CheckpointExecutionReport(
        checkpoint_id=checkpoint_id,
        pipeline_name=pipeline_name,
        commit_sha=commit_sha,
        pr_id=str(pr_id),
        exit_code=exit_code,
        overall_status=overall_status,
        stages=stages,
        remediation_summary=gate_report.remediation_steps,
        console_log_output=console_log,
    )

    _CHECKPOINT_REPORTS[checkpoint_id] = report
    logger.info(
        "CI Checkpoint executed: id=%s pipeline=%s exit_code=%d status=%s",
        checkpoint_id,
        pipeline_name,
        exit_code,
        overall_status.value,
    )
    return report


def get_checkpoint_report(checkpoint_id: str) -> CheckpointExecutionReport | None:
    """获取指定检查点执行报告。"""
    return _CHECKPOINT_REPORTS.get(checkpoint_id)


def list_checkpoint_reports() -> list[CheckpointExecutionReport]:
    """查询历史检查点执行报告列表。"""
    return list(_CHECKPOINT_REPORTS.values())


def reset_checkpoint_registry() -> None:
    """单元测试清理状态使用。"""
    _CHECKPOINT_REPORTS.clear()
