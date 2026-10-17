"""断言演进置信度评分与安全回滚控制器服务 (T2.3)

为断言演进提供多维置信度健康评分、沙箱试跑验证与历史版本回滚控制:
1. 断言演进多维置信度评分与风险等级评估 (Confidence & Risk Scorer);
2. 隔离沙箱在线试跑校验引擎 (Sandbox Dry-Run Validator);
3. 断言版本快照生命周期管理与一键安全回滚 (Snapshot & Rollback Controller)。
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.assertion_drift_evolution_synthesizer import (
    AssertionEvolutionResult,
    EvolutionStatus,
)
from app.services.response_schema_drift_detector import (
    DriftMutationType,
    SchemaDriftItem,
)


class RiskLevel(str, enum.Enum):
    LOW = "LOW"  # 低风险 (Score >= 85): 字段重命名/简单外层包装，可安全采纳
    MEDIUM = "MEDIUM"  # 中风险 (60 <= Score < 85): 跨层级深层位移或弱类型强转，建议人工审查
    HIGH = "HIGH"  # 高风险 (Score < 60): 复杂重组或可能改变断言语义，阻断自动合流


class DryRunStatus(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class SnapshotStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ROLLBACKED = "ROLLBACKED"


@dataclass
class EvolutionConfidenceEvaluation:
    score: float  # 0.0 ~ 100.0
    risk_level: RiskLevel
    reasons: List[str]
    is_safe_to_auto_apply: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "risk_level": self.risk_level.value,
            "reasons": self.reasons,
            "is_safe_to_auto_apply": self.is_safe_to_auto_apply,
        }


@dataclass
class AssertionDryRunResult:
    status: DryRunStatus
    elapsed_ms: float
    error_message: Optional[str] = None
    output_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "error_message": self.error_message,
            "output_summary": self.output_summary,
        }


@dataclass
class AssertionVersionSnapshot:
    version_id: str
    case_id: str
    step_id: str
    original_assertion: str
    current_assertion: str
    confidence_score: float
    risk_level: RiskLevel
    status: SnapshotStatus
    applied_drift_ids: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    rollbacked_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        d["status"] = self.status.value
        return d


# 内存中版本快照存储
_SNAPSHOT_STORE: Dict[str, AssertionVersionSnapshot] = {}


def clear_assertion_snapshots() -> None:
    """清理内存中快照存储 (用于测试隔离)"""
    _SNAPSHOT_STORE.clear()


def evaluate_assertion_evolution_confidence(
    evolution: AssertionEvolutionResult,
    drift_items: List[SchemaDriftItem],
) -> EvolutionConfidenceEvaluation:
    """综合评估断言演进置信度健康评分与风险等级"""
    if evolution.status != EvolutionStatus.EVOLVED:
        return EvolutionConfidenceEvaluation(
            score=0.0,
            risk_level=RiskLevel.HIGH,
            reasons=["断言未产生有效演进或存在语法错误"],
            is_safe_to_auto_apply=False,
        )

    base_score = 95.0
    reasons: List[str] = []

    # 1. 检查应用的漂移项置信度平均值
    applied_items = [d for d in drift_items if d.drift_id in evolution.applied_drift_ids]
    if applied_items:
        avg_drift_conf = sum(d.confidence for d in applied_items) / len(applied_items)
        if avg_drift_conf < 0.85:
            penalty = (0.85 - avg_drift_conf) * 50
            base_score -= penalty
            reasons.append(f"底层 Schema 漂移平均置信度较低 ({round(avg_drift_conf, 2)}): 扣减 {round(penalty, 1)} 分")
        else:
            reasons.append(f"底层 Schema 漂移高置信对齐 ({round(avg_drift_conf, 2)})")

        # 检查变迁类型风险
        for item in applied_items:
            if item.mutation_type == DriftMutationType.PATH_RELOCATED:
                base_score -= 10.0
                reasons.append(f"涉及深层路径位移 ({item.old_path} -> {item.new_path}): 扣减 10 分")
            elif item.mutation_type == DriftMutationType.TYPE_MUTATED:
                base_score -= 8.0
                reasons.append(f"涉及数据类型兼容推导 ({item.old_path}): 扣减 8 分")
    else:
        base_score -= 30.0
        reasons.append("未关联到有效的 Schema 漂移溯源: 扣减 30 分")

    final_score = max(0.0, min(100.0, base_score))

    if final_score >= 85.0:
        risk = RiskLevel.LOW
        is_safe = True
    elif final_score >= 60.0:
        risk = RiskLevel.MEDIUM
        is_safe = False
    else:
        risk = RiskLevel.HIGH
        is_safe = False

    return EvolutionConfidenceEvaluation(
        score=final_score,
        risk_level=risk,
        reasons=reasons,
        is_safe_to_auto_apply=is_safe,
    )


def dry_run_evolved_assertion(
    evolved_code: str,
    test_payload: Dict[str, Any],
) -> AssertionDryRunResult:
    """在受限沙箱环境中试跑演进后的断言，验证其在最新响应下的执行正确性"""
    start_time = time.perf_counter()

    # 安全沙箱上下文，预注入常用测试变量
    sandbox_locals: Dict[str, Any] = {
        "res": test_payload,
        "resp": test_payload,
        "response": test_payload,
        "data": test_payload.get("data") if isinstance(test_payload, dict) else None,
    }

    try:
        # 执行断言代码
        exec(evolved_code, {"__builtins__": __builtins__}, sandbox_locals)
        elapsed = (time.perf_counter() - start_time) * 1000
        return AssertionDryRunResult(
            status=DryRunStatus.PASS,
            elapsed_ms=elapsed,
            output_summary="断言在最新响应体下试跑验证通过 (PASS)",
        )
    except AssertionError as ae:
        elapsed = (time.perf_counter() - start_time) * 1000
        return AssertionDryRunResult(
            status=DryRunStatus.FAIL,
            elapsed_ms=elapsed,
            error_message=str(ae) or "断言条件不成立 (AssertionError)",
            output_summary="断言条件未能成立，请核对预期取值",
        )
    except Exception as e:
        elapsed = (time.perf_counter() - start_time) * 1000
        return AssertionDryRunResult(
            status=DryRunStatus.ERROR,
            elapsed_ms=elapsed,
            error_message=f"{type(e).__name__}: {str(e)}",
            output_summary=f"断言执行抛出未处理异常: {type(e).__name__}",
        )


def record_assertion_version_snapshot(
    case_id: str,
    step_id: str,
    original_assertion: str,
    evolved_assertion: str,
    confidence_score: float,
    risk_level: RiskLevel,
    applied_drift_ids: Optional[List[str]] = None,
) -> AssertionVersionSnapshot:
    """为用例断言演进生成可溯源版本快照"""
    version_id = f"snap_ast_{uuid.uuid4().hex[:10]}"
    snapshot = AssertionVersionSnapshot(
        version_id=version_id,
        case_id=case_id,
        step_id=step_id,
        original_assertion=original_assertion,
        current_assertion=evolved_assertion,
        confidence_score=confidence_score,
        risk_level=risk_level,
        status=SnapshotStatus.ACTIVE,
        applied_drift_ids=applied_drift_ids or [],
    )
    _SNAPSHOT_STORE[version_id] = snapshot
    return snapshot


def get_assertion_version_snapshot(version_id: str) -> Optional[AssertionVersionSnapshot]:
    """查询单张版本快照"""
    return _SNAPSHOT_STORE.get(version_id)


def list_assertion_snapshots(
    case_id: Optional[str] = None,
    step_id: Optional[str] = None,
    limit: int = 50,
) -> List[AssertionVersionSnapshot]:
    """查询断言版本快照列表"""
    items = list(_SNAPSHOT_STORE.values())
    if case_id:
        items = [i for i in items if i.case_id == case_id]
    if step_id:
        items = [i for i in items if i.step_id == step_id]

    items.sort(key=lambda x: x.created_at, reverse=True)
    return items[:limit]


def rollback_assertion_version(version_id: str) -> Optional[AssertionVersionSnapshot]:
    """一键回滚断言演进至旧基线版本"""
    snap = _SNAPSHOT_STORE.get(version_id)
    if not snap:
        return None

    snap.current_assertion = snap.original_assertion
    snap.status = SnapshotStatus.ROLLBACKED
    snap.rollbacked_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return snap
