"""运行时失败拦截与自愈补丁应用器服务 (T1.2)

在自动化用例执行抛出 ElementNotFound 时拦截执行流、现场自愈重定位并生成可复用补丁:
1. 运行时异常拦截与上下文快照提取 (Runtime Failure Interception);
2. 毫秒级弹性重定位器推导与现场热替换重试 (In-Flight Hot Replacement & Resume);
3. 自愈补丁全生命周期管理 (PROPOSED -> APPLIED_IN_FLIGHT -> COMMITTED_PERMANENT);
4. 补丁持久化与用例回写索引。
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.dynamic_locator_self_healer import (
    BrokenLocatorContext,
    CandidateDOMNode,
    HealingStrategyTier,
    derive_self_healing_candidates,
)


class PatchStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"  # 已推导生成自愈补丁，等待确认
    APPLIED_IN_FLIGHT = "APPLIED_IN_FLIGHT"  # 运行时现场热替换执行成功
    COMMITTED_PERMANENT = "COMMITTED_PERMANENT"  # 已永久采纳并回写至用例库
    REJECTED = "REJECTED"  # 人工或策略否决废弃


class RuntimeHealingVerdict(str, enum.Enum):
    HEALED_AND_RESUMED = "HEALED_AND_RESUMED"  # 拦截并自愈成功，任务继续执行
    HEALING_FAILED = "HEALING_FAILED"  # 自愈推导未达置信度或无可用候选，保持失败
    REJECTED_BY_POLICY = "REJECTED_BY_POLICY"  # 安全门禁或黑名单拦截自愈


@dataclass
class SelfHealingPatchRecord:
    patch_id: str
    step_id: str
    case_id: Optional[str]
    source_platform: str  # web | ios | android
    broken_locator: Dict[str, str]  # {"type": "css", "value": "#old_btn"}
    healed_locator: Dict[str, str]  # {"type": "css", "value": "button[data-action='pay']"}
    confidence_score: float
    strategy_tier: HealingStrategyTier
    status: PatchStatus
    explanation: str
    execution_time_saved_ms: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    committed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["strategy_tier"] = self.strategy_tier.value
        d["status"] = self.status.value
        d["confidence_score"] = round(self.confidence_score, 4)
        return d


@dataclass
class RuntimeHealingExecutionResult:
    healing_id: str
    step_id: str
    verdict: RuntimeHealingVerdict
    patch: Optional[SelfHealingPatchRecord]
    elapsed_ms: float
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        d["elapsed_ms"] = round(self.elapsed_ms, 2)
        if self.patch:
            d["patch"] = self.patch.to_dict()
        return d


_PATCH_STORE: Dict[str, SelfHealingPatchRecord] = {}
_STEP_PATCH_INDEX: Dict[str, str] = {}  # step_id -> patch_id


def clear_healing_patches() -> None:
    """清空自愈补丁内存记录（测试夹具使用）"""
    _PATCH_STORE.clear()
    _STEP_PATCH_INDEX.clear()


def intercept_and_heal_step(
    context: BrokenLocatorContext,
    screen_nodes: List[CandidateDOMNode],
    case_id: Optional[str] = None,
    platform: str = "web",
    confidence_threshold: float = 0.65,
) -> RuntimeHealingExecutionResult:
    """在用例步骤发生定位失效时拦截异常，执行实时推导与现场自愈重试

    Returns:
        RuntimeHealingExecutionResult (包含裁决结果与生成的自愈补丁对象)
    """
    start_time = time.perf_counter()
    hid = f"heal_{uuid.uuid4().hex[:10]}"

    # 1. 检查是否存在此前已采纳的有效补丁
    existing_patch_id = _STEP_PATCH_INDEX.get(context.step_id)
    if existing_patch_id and existing_patch_id in _PATCH_STORE:
        patch = _PATCH_STORE[existing_patch_id]
        if patch.status in (PatchStatus.APPLIED_IN_FLIGHT, PatchStatus.COMMITTED_PERMANENT):
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return RuntimeHealingExecutionResult(
                healing_id=hid,
                step_id=context.step_id,
                verdict=RuntimeHealingVerdict.HEALED_AND_RESUMED,
                patch=patch,
                elapsed_ms=elapsed,
                message=f"命中历史自愈补丁 [{patch.patch_id}]，复用新定位器: {patch.healed_locator['value']}",
            )

    # 2. 现场执行多模态自愈推导
    diag_res = derive_self_healing_candidates(context, screen_nodes, confidence_threshold)
    elapsed = (time.perf_counter() - start_time) * 1000.0

    if not diag_res.has_healed_candidate or not diag_res.best_candidate:
        return RuntimeHealingExecutionResult(
            healing_id=hid,
            step_id=context.step_id,
            verdict=RuntimeHealingVerdict.HEALING_FAILED,
            patch=None,
            elapsed_ms=elapsed,
            message=f"视口内未推导出满足置信度门限 (>={confidence_threshold}) 的候选控件，自愈终止，保持用例失败",
        )

    best = diag_res.best_candidate
    patch_id = f"patch_heal_{uuid.uuid4().hex[:10]}"

    new_patch = SelfHealingPatchRecord(
        patch_id=patch_id,
        step_id=context.step_id,
        case_id=case_id,
        source_platform=platform,
        broken_locator={
            "type": context.failed_locator_type,
            "value": context.failed_locator_value,
        },
        healed_locator={
            "type": best.recommended_locator_type,
            "value": best.recommended_locator_value,
        },
        confidence_score=best.confidence_score,
        strategy_tier=best.strategy_tier,
        status=PatchStatus.APPLIED_IN_FLIGHT,
        explanation=best.healing_explanation,
        execution_time_saved_ms=round(elapsed, 2),
    )

    _PATCH_STORE[patch_id] = new_patch
    _STEP_PATCH_INDEX[context.step_id] = patch_id

    return RuntimeHealingExecutionResult(
        healing_id=hid,
        step_id=context.step_id,
        verdict=RuntimeHealingVerdict.HEALED_AND_RESUMED,
        patch=new_patch,
        elapsed_ms=elapsed,
        message=f"运行时现场自愈成功！耗时 {round(elapsed, 2)}ms，新定位器: [{new_patch.healed_locator['type']}] {new_patch.healed_locator['value']}",
    )


def commit_healing_patch(patch_id: str) -> bool:
    """确认采纳并将自愈补丁永久固化至用例库"""
    patch = _PATCH_STORE.get(patch_id)
    if not patch:
        return False
    patch.status = PatchStatus.COMMITTED_PERMANENT
    patch.committed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return True


def reject_healing_patch(patch_id: str) -> bool:
    """人工否决或回滚自愈补丁"""
    patch = _PATCH_STORE.get(patch_id)
    if not patch:
        return False
    patch.status = PatchStatus.REJECTED
    if patch.step_id in _STEP_PATCH_INDEX:
        del _STEP_PATCH_INDEX[patch.step_id]
    return True


def get_healing_patch(patch_id: str) -> Optional[SelfHealingPatchRecord]:
    """查询单张自愈补丁详情"""
    return _PATCH_STORE.get(patch_id)


def list_healing_patches(
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """查询近期生成的自愈补丁历史流水"""
    items = list(_PATCH_STORE.values())
    if status:
        items = [i for i in items if i.status.value == status.upper()]
    items.sort(key=lambda x: x.created_at, reverse=True)
    return [i.to_dict() for i in items[:limit]]
