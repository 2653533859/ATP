"""大规模测试套件智能动态分片与跨节点负载均衡 REST API (T1.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.test_suite_dynamic_sharding_scheduler import (
    TestCaseShardingInput,
    calculate_dynamic_sharding,
    clear_sharding_plans,
    detect_straggler_shards,
    get_sharding_plan,
    list_sharding_plans,
)

router = APIRouter(prefix="/cluster/sharding", tags=["测试套件动态分片调度器 (T1.2)"])


class TestCaseItemIn(BaseModel):
    case_id: str = Field(..., description="用例唯一标识")
    case_name: str = Field(..., description="用例名称")
    historical_duration_ms: float = Field(default=1000.0, ge=1.0, description="历史耗时(ms)")
    priority: str = Field(default="P1", description="用例优先级 (P0~P3)")
    tags: list[str] = Field(default_factory=list, description="用例标签列表")


class CalculateShardingPlanIn(BaseModel):
    cases: list[TestCaseItemIn] = Field(..., min_length=0, description="待分片测试用例列表")
    total_shards: int = Field(default=3, ge=1, le=50, description="目标切分分片数")
    node_ids: list[str] | None = Field(default=None, description="指定执行节点标识列表")


class ShardProgressItemIn(BaseModel):
    shard_index: int = Field(..., ge=0)
    node_id: str = Field(...)
    elapsed_ms: float = Field(default=0.0, ge=0.0)
    remaining_cases: int = Field(default=0, ge=0)
    total_cases: int = Field(default=1, ge=1)


class DetectStragglerIn(BaseModel):
    shard_progress: list[ShardProgressItemIn] = Field(..., description="各分片运行状态数据")


@router.post("/plan")
async def calculate_sharding_endpoint(
    body: CalculateShardingPlanIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """生成基于 LPT 贪心装箱算法的测试套件多节点分片调度方案。"""
    _ = _user
    case_inputs = [
        TestCaseShardingInput(
            case_id=c.case_id,
            case_name=c.case_name,
            historical_duration_ms=c.historical_duration_ms,
            priority=c.priority,
            tags=c.tags,
        )
        for c in body.cases
    ]
    plan = calculate_dynamic_sharding(
        cases=case_inputs,
        total_shards=body.total_shards,
        node_ids=body.node_ids,
    )
    return {"message": "动态分片调度方案生成成功", "plan": plan.to_dict()}


@router.post("/rebalance-detect")
async def detect_straggler_endpoint(
    body: DetectStragglerIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """检测各分片运行进度并输出掉队节点与再平衡建议。"""
    _ = _user
    progress_dicts = [p.model_dump() for p in body.shard_progress]
    res = detect_straggler_shards(progress_dicts)
    return res


@router.get("/plans")
async def list_plans_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史分片调度方案列表。"""
    _ = _user
    plans = list_sharding_plans(limit=limit)
    return {"total": len(plans), "plans": plans}


@router.get("/plans/{plan_id}")
async def get_plan_endpoint(
    plan_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询分片调度方案详情。"""
    _ = _user
    plan = get_sharding_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"分片方案 [{plan_id}] 不存在")
    return {"plan": plan.to_dict()}


@router.delete("/plans")
async def clear_plans_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空所有历史分片方案（需工程师权限）。"""
    _ = _user
    clear_sharding_plans()
    return {"message": "已清空所有分片方案"}
