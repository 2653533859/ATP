"""自主探索式 API 模糊变异与隐蔽缺陷探查 REST API (T3.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.autonomous_api_fuzzing_explorer import (
    FuzzMutationStrategy,
    clear_fuzzing_store,
    execute_fuzzing_exploration,
    get_fuzzing_session,
    list_fuzzing_sessions,
)

router = APIRouter(prefix="/llm-testing/fuzzing-explore", tags=["自主 API 变异探查 (T3.3)"])


class RunFuzzingIn(BaseModel):
    endpoint: str = Field(..., description="目标 API 接口 URL 或路径 (如 /api/v1/orders/checkout)")
    method: str = Field(default="POST", description="请求方法")
    base_payload: dict[str, Any] | None = Field(default=None, description="基准合法请求体")
    strategies: list[str] | None = Field(default=None, description="启用的变异策略列表")


@router.post("/run")
async def run_fuzzing_endpoint(
    body: RunFuzzingIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对目标接口发起多轮自主模糊变异测试，输出隐蔽缺陷与健壮性报告。"""
    _ = _user
    session = execute_fuzzing_exploration(
        endpoint=body.endpoint,
        method=body.method,
        base_payload=body.base_payload,
        strategies=body.strategies,
    )
    return {"message": "API 模糊变异探索测试完成", "session": session.to_dict()}


@router.get("/strategies")
async def list_strategies_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询支持的模糊变异探查策略列表。"""
    _ = _user
    return {"strategies": [{"strategy": s.value, "name": s.name} for s in FuzzMutationStrategy]}


@router.get("/sessions")
async def list_sessions_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史探索测试会话列表。"""
    _ = _user
    sessions = list_fuzzing_sessions(limit=limit)
    return {"total": len(sessions), "sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session_endpoint(
    session_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次变异探查会话详情与漏洞复现命令。"""
    _ = _user
    session = get_fuzzing_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"会话 [{session_id}] 不存在")
    return {"session": session.to_dict()}


@router.delete("/sessions")
async def clear_sessions_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空所有变异测试会话记录（需工程师权限）。"""
    _ = _user
    clear_fuzzing_store()
    return {"message": "已清空所有 API 模糊变异探索会话"}
