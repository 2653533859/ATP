"""异常失败根因智能聚类与自愈执行流水审计 API (D2.3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.healing_audit_trail_service import (
    HealingActionType,
    HealingVerificationStatus,
    calculate_healing_metrics,
    cluster_error_event,
    get_fault_cluster,
    list_fault_clusters,
    list_healing_audit_entries,
    record_healing_action,
)

router = APIRouter(prefix="/ai-healing/audit", tags=["AI 异常聚类与自愈执行流水审计"])


class ClusterErrorIn(BaseModel):
    case_id: int = Field(ge=1, description="失败用例 ID")
    run_id: int = Field(ge=1, description="执行批次 Run ID")
    exception_type: str = Field(min_length=1, max_length=128, description="异常类型如 NoSuchElementException")
    error_message: str = Field(min_length=1, description="错误详细报错文本")
    stack_trace: str | None = Field(default=None, description="错误堆栈信息")
    root_cause_hint: str | None = Field(default=None, description="业务根因提示")


class RecordHealingActionIn(BaseModel):
    case_id: int = Field(ge=1, description="用例 ID")
    step_name: str = Field(min_length=1, max_length=128, description="步骤名称")
    action_type: str = Field(
        default="locator_replaced",
        description="自愈动作类型: locator_replaced | schema_autofixed | assertion_tolerated | retry_with_backoff",
    )
    original_value: Any = Field(description="自愈前失效值")
    healed_value: Any = Field(description="自愈后替换值")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="自愈置信度得分")
    verification_status: str = Field(
        default="verified_success",
        description="二次验证状态: verified_success | verified_failure | pending_verify | auto_accepted",
    )
    cluster_id: str | None = Field(default=None, description="关联故障簇 ID")
    duration_ms: float = Field(default=0.0, ge=0.0, description="自愈算法执行耗时 (ms)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


@router.post("/cluster")
async def cluster_error_endpoint(
    body: ClusterErrorIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """对单次失败异常执行特征归一化与故障簇智能聚类 (需工程师权限)。"""
    _ = _user
    cluster = cluster_error_event(
        case_id=body.case_id,
        run_id=body.run_id,
        exception_type=body.exception_type,
        error_message=body.error_message,
        stack_trace=body.stack_trace,
        root_cause_hint=body.root_cause_hint,
    )
    return {"message": "异常事件已成功聚类归因", "cluster": cluster.to_dict()}


@router.get("/clusters")
async def list_fault_clusters_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询当前聚合的全部异常故障簇清单。"""
    _ = _user
    clusters = list_fault_clusters()
    return {"total": len(clusters), "clusters": [c.to_dict() for c in clusters]}


@router.get("/clusters/{cluster_id}")
async def get_fault_cluster_endpoint(
    cluster_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定故障簇详情与波及用例分布。"""
    _ = _user
    cluster = get_fault_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"故障簇不存在: {cluster_id}")
    return cluster.to_dict()


@router.post("/record-action")
async def record_healing_action_endpoint(
    body: RecordHealingActionIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """记录一次用例自愈执行动作流水。"""
    _ = _user
    try:
        act_enum = HealingActionType(body.action_type.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效的自愈动作类型: {body.action_type}")

    try:
        verif_enum = HealingVerificationStatus(body.verification_status.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效的验证状态: {body.verification_status}"
        )

    entry = record_healing_action(
        case_id=body.case_id,
        step_name=body.step_name,
        action_type=act_enum,
        original_value=body.original_value,
        healed_value=body.healed_value,
        confidence_score=body.confidence_score,
        verification_status=verif_enum,
        cluster_id=body.cluster_id,
        duration_ms=body.duration_ms,
        metadata=body.metadata,
    )
    return {"message": "自愈流水记录成功", "entry": entry.to_dict()}


@router.get("/entries")
async def list_healing_entries_endpoint(
    case_id: int | None = Query(default=None, description="按用例 ID 过滤"),
    action_type_str: str | None = Query(default=None, alias="action_type", description="按动作类型过滤"),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询自愈执行流水审计记录。"""
    _ = _user
    act_enum = None
    if action_type_str:
        try:
            act_enum = HealingActionType(action_type_str.lower())
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效的动作类型: {action_type_str}")

    entries = list_healing_audit_entries(case_id=case_id, action_type=act_enum)
    return {"total": len(entries), "entries": [e.to_dict() for e in entries]}


@router.get("/metrics")
async def get_healing_metrics_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取全生命周期自愈成效、二次验证成功率与估算节省工时。"""
    _ = _user
    metrics = calculate_healing_metrics()
    return metrics
