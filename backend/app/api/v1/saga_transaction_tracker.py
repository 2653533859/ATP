"""Sagas/TCC 分布式事务流转跟踪与悬挂事务探测 REST API (T2.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.saga_transaction_state_tracker import (
    audit_global_tx,
    clear_saga_store,
    list_active_and_hanging_transactions,
    record_branch_tx,
    record_global_tx,
    simulate_saga_scenario,
)

router = APIRouter(prefix="/consistency/saga", tags=["分布式事务跟踪与悬挂探测 (T2.1)"])


class CreateGlobalTxIn(BaseModel):
    global_tx_id: str | None = Field(default=None, description="全局事务 ID (选填，留空自动生成)")
    business_key: str = Field(..., description="业务主键 (如订单号/交易流水号)")
    pattern: str = Field(default="TCC", description="事务模式: TCC | SAGA")
    timeout_seconds: float = Field(default=30.0, ge=1.0, description="事务超时时间 (秒)")


class RecordBranchTxIn(BaseModel):
    global_tx_id: str = Field(..., description="所属全局事务 ID")
    service_name: str = Field(..., description="微服务名称")
    action_name: str = Field(..., description="事务动作名称")
    stage: str = Field(default="TRY", description="阶段: TRY | CONFIRM | CANCEL | FORWARD | COMPENSATE")
    status: str = Field(default="SUCCESS", description="状态: PENDING | SUCCESS | FAILED | TIMEOUT")
    duration_ms: float = Field(default=0.0, ge=0.0, description="执行耗时 (毫秒)")
    error_message: str = Field(default="", description="错误信息")
    retry_count: int = Field(default=0, ge=0, description="重试次数")
    payload: dict[str, Any] = Field(default_factory=dict, description="业务载荷数据")


class SimulateSagaIn(BaseModel):
    scenario_key: str = Field(
        default="hanging",
        description="仿真场景: hanging (悬挂事务) | empty_compensation (空补偿) | timeout (超时未决) | normal (正常提交)",
    )


@router.post("/transactions")
async def create_global_tx_endpoint(
    body: CreateGlobalTxIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """创建或注册全局事务追踪上下文。"""
    _ = _user
    tx = record_global_tx(
        global_tx_id=body.global_tx_id,
        business_key=body.business_key,
        pattern=body.pattern,
        timeout_seconds=body.timeout_seconds,
    )
    return {"message": "全局事务已注册", "transaction": tx.to_dict()}


@router.post("/branches")
async def record_branch_tx_endpoint(
    body: RecordBranchTxIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """上报微服务分支事务阶段与执行结果。"""
    _ = _user
    branch = record_branch_tx(
        global_tx_id=body.global_tx_id,
        service_name=body.service_name,
        action_name=body.action_name,
        stage=body.stage,
        status=body.status,
        duration_ms=body.duration_ms,
        error_message=body.error_message,
        retry_count=body.retry_count,
        payload=body.payload,
    )
    return {"message": "分支事务记录成功", "branch": branch.to_dict()}


@router.get("/transactions/{global_tx_id}/audit")
async def audit_global_tx_endpoint(
    global_tx_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对指定全局事务执行最终一致性、悬挂事务与空补偿深度稽核。"""
    _ = _user
    audit = audit_global_tx(global_tx_id)
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到该全局事务: {global_tx_id}",
        )
    return audit.to_dict()


@router.get("/hanging")
async def list_hanging_transactions_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """探测查询全网未决、悬挂或一致性撕裂事务列表。"""
    _ = _user
    txs = list_active_and_hanging_transactions()
    return {"total": len(txs), "transactions": txs}


@router.post("/simulate")
async def simulate_saga_endpoint(
    body: SimulateSagaIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """仿真执行典型分布式长事务场景并出具一致性稽核报告。"""
    _ = _user
    report = simulate_saga_scenario(body.scenario_key)
    return {"message": "分布式事务场景仿真完成", "report": report.to_dict()}


@router.delete("/transactions")
async def clear_saga_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空分布式事务缓存仓库 (需工程师权限)。"""
    _ = _user
    c = clear_saga_store()
    return {"message": f"已清空 {c} 条全局事务记录", "cleared_count": c}
