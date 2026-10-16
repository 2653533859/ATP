"""CI 选定测试集高频抖动 Flaky 用例自适应抑制隔离过滤器 (S2.3).

联动历史用例执行抖动库与治理白名单，对选定测试集进行抖动率探测，
自动将偶发性超时/异步网络抖动的非致命 Flaky 用例进行自适应抑制隔离或附加重试保护，
杜绝假阳性偶发失败阻断主干 CI 交付流水线。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class SuppressionAction(str, Enum):
    NORMAL_PASSTHROUGH = "normal_passthrough"  # 稳固用例正常放行
    RETRY_ATTACHED = "retry_attached"  # 附加自动重试保护 (建议重试 2 次)
    ISOLATED_TO_QUARANTINE = "isolated_to_quarantine"  # 隔离至次级异步观察队列 (不阻断主干 CI)
    TAGGED_OBSERVATION = "tagged_observation"  # 正常执行但打标告警


class FlakyFilterMode(str, Enum):
    AUTO_ADAPTIVE = "auto_adaptive"  # 自动自适应：轻度抖动附加重试，高危重度抖动隔离
    QUARANTINE_STRICT = "quarantine_strict"  # 严格隔离：只要检测到抖动一律移出主干队列
    RETRY_ONLY = "retry_only"  # 仅重试：全部保留在主干并附加重试


@dataclass
class CaseSuppressionEvaluation:
    case_id: int
    case_name: str
    is_flaky: bool
    flakiness_score: float  # 0.0 ~ 1.0 (不稳定抖动指数)
    failure_rate: float  # 历史失败率
    total_runs_analyzed: int
    action: SuppressionAction
    suppression_reason: str
    retry_count_recommended: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "is_flaky": self.is_flaky,
            "flakiness_score": round(self.flakiness_score, 2),
            "failure_rate": round(self.failure_rate, 2),
            "total_runs_analyzed": self.total_runs_analyzed,
            "action": self.action.value,
            "suppression_reason": self.suppression_reason,
            "retry_count_recommended": self.retry_count_recommended,
        }


@dataclass
class FlakySuppressionReport:
    filter_id: str
    mode: FlakyFilterMode
    total_cases_evaluated: int
    stable_cases_count: int
    flaky_cases_count: int
    isolated_cases_count: int
    retried_cases_count: int
    suppression_ratio_pct: float
    actionable_case_ids: list[int]  # 主干流水线实际应阻塞执行的用例列表
    quarantined_case_ids: list[int]  # 被隔离移出主干的用例列表
    evaluations: list[CaseSuppressionEvaluation]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "filter_id": self.filter_id,
            "mode": self.mode.value,
            "total_cases_evaluated": self.total_cases_evaluated,
            "stable_cases_count": self.stable_cases_count,
            "flaky_cases_count": self.flaky_cases_count,
            "isolated_cases_count": self.isolated_cases_count,
            "retried_cases_count": self.retried_cases_count,
            "suppression_ratio_pct": round(self.suppression_ratio_pct, 2),
            "actionable_case_ids": self.actionable_case_ids,
            "quarantined_case_ids": self.quarantined_case_ids,
            "evaluations": [e.to_dict() for e in self.evaluations],
            "created_at": self.created_at.isoformat(),
        }


# 内存隔离报告仓库与治理规则库
_FLAKY_FILTER_REPORTS: dict[str, FlakySuppressionReport] = {}
_GOVERNANCE_OVERRIDES: dict[int, dict[str, Any]] = {}


def register_flaky_governance_override(
    case_id: int,
    action: SuppressionAction,
    reason: str,
    ticket_id: str | None = None,
) -> None:
    """注册用例级人工治理覆盖策略 (如来自 docs/flaky-governance.md)."""
    _GOVERNANCE_OVERRIDES[case_id] = {
        "action": action,
        "reason": reason,
        "ticket_id": ticket_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def filter_flaky_tests_for_ci(
    cases_to_evaluate: list[dict[str, Any]],
    mode: FlakyFilterMode = FlakyFilterMode.AUTO_ADAPTIVE,
    flakiness_threshold: float = 0.20,
    historical_stats: dict[int, dict[str, Any]] | None = None,
) -> FlakySuppressionReport:
    """对 CI 候选测试集执行高频抖动 Flaky 用例探测与自适应抑制隔离。"""
    filter_id = f"flaky_flt_{uuid.uuid4().hex[:12]}"
    stats_map = historical_stats or {}

    evaluations: list[CaseSuppressionEvaluation] = []
    actionable_ids: list[int] = []
    quarantined_ids: list[int] = []

    for item in cases_to_evaluate:
        cid = int(item["case_id"])
        cname = str(item.get("case_name", f"Case #{cid}"))

        # 检查是否有人工治理策略强制覆盖
        override = _GOVERNANCE_OVERRIDES.get(cid)
        if override:
            action = override["action"]
            reason = f"人工治理策略生效: {override['reason']} (工单: {override.get('ticket_id') or '无'})"
            eval_item = CaseSuppressionEvaluation(
                case_id=cid,
                case_name=cname,
                is_flaky=True,
                flakiness_score=1.0,
                failure_rate=0.5,
                total_runs_analyzed=10,
                action=action,
                suppression_reason=reason,
                retry_count_recommended=2 if action == SuppressionAction.RETRY_ATTACHED else 0,
            )
            evaluations.append(eval_item)
            if action == SuppressionAction.ISOLATED_TO_QUARANTINE:
                quarantined_ids.append(cid)
            else:
                actionable_ids.append(cid)
            continue

        # 提取历史统计
        cstats = stats_map.get(cid, {})
        total_runs = int(cstats.get("total_runs", 0))
        failed_runs = int(cstats.get("failed_runs", 0))
        passed_runs = int(cstats.get("passed_runs", 0))

        # 计算抖动指数: 在至少 4 次运行中，失败率在 [15%, 85%] 之间表示高度不稳定抖动
        fail_rate = (failed_runs / float(total_runs)) if total_runs > 0 else 0.0
        # 判定是否同时存在成功与失败
        is_flaky = total_runs >= 4 and failed_runs > 0 and passed_runs > 0
        # 抖动指数：距离 50% 失败率越近，不确定性与抖动度越高
        flakiness_score = max(0.0, 1.0 - abs(fail_rate - 0.5) * 2.0) if is_flaky else 0.0

        if not is_flaky or flakiness_score < flakiness_threshold:
            # 稳固用例正常放行
            eval_item = CaseSuppressionEvaluation(
                case_id=cid,
                case_name=cname,
                is_flaky=False,
                flakiness_score=flakiness_score,
                failure_rate=fail_rate,
                total_runs_analyzed=total_runs,
                action=SuppressionAction.NORMAL_PASSTHROUGH,
                suppression_reason="测试用例历史执行稳固，未检出显著统计性抖动",
                retry_count_recommended=0,
            )
            actionable_ids.append(cid)
        else:
            # 检出 Flaky 抖动，依据模式决策处置动作
            if mode == FlakyFilterMode.QUARANTINE_STRICT:
                action = SuppressionAction.ISOLATED_TO_QUARANTINE
                reason = f"严格模式隔离：检测到用例存在显著偶发抖动 (指数: {flakiness_score:.2f})，移出主干 CI"
                retries = 0
                quarantined_ids.append(cid)
            elif mode == FlakyFilterMode.RETRY_ONLY:
                action = SuppressionAction.RETRY_ATTACHED
                reason = f"重试放行：检测到轻度偶发抖动 (指数: {flakiness_score:.2f})，附加 2 次退避重试保护"
                retries = 2
                actionable_ids.append(cid)
            else:
                # AUTO_ADAPTIVE: 超高抖动 (>0.75) 隔离，轻度抖动附加重试
                if flakiness_score >= 0.75:
                    action = SuppressionAction.ISOLATED_TO_QUARANTINE
                    reason = f"自适应隔离：用例历史高频随机抖动 (指数: {flakiness_score:.2f})，移至异步观察队列"
                    retries = 0
                    quarantined_ids.append(cid)
                else:
                    action = SuppressionAction.RETRY_ATTACHED
                    reason = f"自适应重试：用例存在中度抖动 (指数: {flakiness_score:.2f})，附加自动重试"
                    retries = 2
                    actionable_ids.append(cid)

            eval_item = CaseSuppressionEvaluation(
                case_id=cid,
                case_name=cname,
                is_flaky=True,
                flakiness_score=flakiness_score,
                failure_rate=fail_rate,
                total_runs_analyzed=total_runs,
                action=action,
                suppression_reason=reason,
                retry_count_recommended=retries,
            )

        evaluations.append(eval_item)

    total_count = len(cases_to_evaluate)
    flaky_count = sum(1 for e in evaluations if e.is_flaky)
    stable_count = total_count - flaky_count
    isolated_count = len(quarantined_ids)
    retried_count = sum(1 for e in evaluations if e.action == SuppressionAction.RETRY_ATTACHED)
    suppression_ratio = (float(flaky_count) / float(total_count) * 100.0) if total_count > 0 else 0.0

    report = FlakySuppressionReport(
        filter_id=filter_id,
        mode=mode,
        total_cases_evaluated=total_count,
        stable_cases_count=stable_count,
        flaky_cases_count=flaky_count,
        isolated_cases_count=isolated_count,
        retried_cases_count=retried_count,
        suppression_ratio_pct=suppression_ratio,
        actionable_case_ids=actionable_ids,
        quarantined_case_ids=quarantined_ids,
        evaluations=evaluations,
    )

    _FLAKY_FILTER_REPORTS[filter_id] = report
    logger.info(
        "Flaky suppression filter complete: id=%s total=%d flaky=%d isolated=%d retried=%d",
        filter_id,
        total_count,
        flaky_count,
        isolated_count,
        retried_count,
    )
    return report


def get_flaky_filter_report(filter_id: str) -> FlakySuppressionReport | None:
    """获取指定抖动隔离报告。"""
    return _FLAKY_FILTER_REPORTS.get(filter_id)


def list_flaky_filter_reports() -> list[FlakySuppressionReport]:
    """查询历史抖动隔离报告列表。"""
    return list(_FLAKY_FILTER_REPORTS.values())


def reset_flaky_filter_registry() -> None:
    """单元测试清理状态使用。"""
    _FLAKY_FILTER_REPORTS.clear()
    _GOVERNANCE_OVERRIDES.clear()
