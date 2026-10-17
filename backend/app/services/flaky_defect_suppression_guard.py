"""偶发抖动缺陷提单防击穿安全沙箱看门狗服务 (T4.1)

识别偶发网络抖动与 Flaky 假失败，防范误建无效垃圾工单与开发团队警报疲劳:
1. 即时重试自愈校验门禁 (重试通过即判定为 FLAKY 抖动，强行抑制自动提单);
2. 历史震荡率分析与隔离池机制 (Flaky Flipping Frequency > 30% 标记隔离观察);
3. 瞬态网络特征模式过滤 (DNS/TCP握手瞬态重置安全识别);
4. 确定性缺陷放行提单与结构化安全裁决 (FlakyEvaluationDecision & DefectSuppressionAction)。
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DefectSuppressionAction(str, enum.Enum):
    DISPATCH_GENUINE_DEFECT = "DISPATCH_GENUINE_DEFECT"  # 确定性真实缺陷，放行提单
    SUPPRESS_FLAKY_RECOVERED = "SUPPRESS_FLAKY_RECOVERED"  # 重试自愈通过，抑制提单
    SUPPRESS_QUARANTINED_FLAKY = "SUPPRESS_QUARANTINED_FLAKY"  # 历史高频抖动用例，入隔离池抑制提单
    SUPPRESS_TRANSIENT_NETWORK = "SUPPRESS_TRANSIENT_NETWORK"  # 瞬态网络偶发丢包，抑制提单


TRANSIENT_NETWORK_PATTERNS = [
    r".*temporary failure in name resolution.*",
    r".*name or service not known.*",
    r".*dns.*timeout.*",
    r".*connection reset by peer.*",
    r".*handshake timed out.*",
    r".*broken pipe.*",
    r".*connection pool exhausted briefly.*",
]


@dataclass
class FlakyEvaluationDecision:
    decision_id: str
    case_id: str
    is_suppressed: bool
    action: DefectSuppressionAction
    retries_attempted: int
    historical_flaky_score: float  # 历史抖动率 0.0 ~ 1.0
    justification: str
    quarantined: bool
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "case_id": self.case_id,
            "is_suppressed": self.is_suppressed,
            "action": self.action.value,
            "retries_attempted": self.retries_attempted,
            "historical_flaky_score": round(self.historical_flaky_score, 2),
            "justification": self.justification,
            "quarantined": self.quarantined,
            "evaluated_at": self.evaluated_at,
        }


def _calculate_historical_flaky_score(history: List[bool]) -> float:
    """计算用例在历史执行中的通过/失败翻转震荡频率 (Flipping Frequency)"""
    if not history or len(history) < 2:
        return 0.0
    flips = 0
    for i in range(1, len(history)):
        if history[i] != history[i - 1]:
            flips += 1
    return flips / (len(history) - 1)


def _is_transient_network_error(error_message: str, stack_trace: str) -> bool:
    """检查是否属于偶发网络瞬态波动"""
    text = f"{error_message}\n{stack_trace}".lower()
    for pat in TRANSIENT_NETWORK_PATTERNS:
        if re.search(pat, text):
            return True
    return False


def evaluate_defect_suppression_guard(
    case_id: str,
    error_message: str,
    stack_trace: str,
    retry_success: bool = False,
    retry_count: int = 0,
    historical_execution_results: Optional[List[bool]] = None,
    flaky_threshold: float = 0.30,
) -> FlakyEvaluationDecision:
    """评估失败用例是否属于偶发抖动或需提单抑制"""
    decision_id = f"fdec_{uuid.uuid4().hex[:10]}"
    history = historical_execution_results or []
    flaky_score = _calculate_historical_flaky_score(history)

    # 1. 第一防线: 即时重试自愈通过
    if retry_success:
        return FlakyEvaluationDecision(
            decision_id=decision_id,
            case_id=case_id,
            is_suppressed=True,
            action=DefectSuppressionAction.SUPPRESS_FLAKY_RECOVERED,
            retries_attempted=retry_count,
            historical_flaky_score=flaky_score,
            justification=f"用例在重试 {retry_count} 次后自愈通过，判定为偶发环境抖动 (Flaky)，安全沙箱已拦截自动提单。",
            quarantined=False,
        )

    # 2. 第二防线: 历史高频震荡用例隔离保护
    if flaky_score >= flaky_threshold:
        return FlakyEvaluationDecision(
            decision_id=decision_id,
            case_id=case_id,
            is_suppressed=True,
            action=DefectSuppressionAction.SUPPRESS_QUARANTINED_FLAKY,
            retries_attempted=retry_count,
            historical_flaky_score=flaky_score,
            justification=f"用例历史震荡率高达 {round(flaky_score * 100, 1)}% (阈值 {round(flaky_threshold * 100, 1)}%)，已列入隔离观察池，抑制提单并通知自动化维护人员。",
            quarantined=True,
        )

    # 3. 第三防线: 瞬态网络特征过滤 (且只重试了一次或以下)
    if _is_transient_network_error(error_message, stack_trace) and retry_count <= 1:
        return FlakyEvaluationDecision(
            decision_id=decision_id,
            case_id=case_id,
            is_suppressed=True,
            action=DefectSuppressionAction.SUPPRESS_TRANSIENT_NETWORK,
            retries_attempted=retry_count,
            historical_flaky_score=flaky_score,
            justification="报错命中瞬态网络抖动特征 (DNS超时/连接重置)，重试未达上限，暂时抑制提单。",
            quarantined=False,
        )

    # 4. 确定性真实缺陷，放行提单
    return FlakyEvaluationDecision(
        decision_id=decision_id,
        case_id=case_id,
        is_suppressed=False,
        action=DefectSuppressionAction.DISPATCH_GENUINE_DEFECT,
        retries_attempted=retry_count,
        historical_flaky_score=flaky_score,
        justification="经重试多次持续失败，且无瞬态抖动模式，确认属于确定性业务或系统真实缺陷，准予自动创建工单。",
        quarantined=False,
    )
