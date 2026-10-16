"""接口契约与业务 Spec 驱动的端到端用例智能生成 REST API (T3.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.llm_spec_to_e2e_case_synthesizer import (
    clear_synthesized_cases_store,
    get_synthesized_case,
    list_synthesized_cases,
    synthesize_e2e_test_flow,
)

router = APIRouter(prefix="/llm-testing/synthesize-cases", tags=["LLM 端到端测试用例智能生成 (T3.1)"])


class EndpointItemIn(BaseModel):
    path: str = Field(...)
    method: str = Field(default="POST")
    summary: str = Field(default="")
    request_schema: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] = Field(default_factory=dict)


class SynthesizeCaseIn(BaseModel):
    spec_title: str = Field(..., description="业务场景标题 (如 电商用户登录下单闭环)")
    business_flow_description: str = Field(default="", description="自然语言业务流或 PRD 描述")
    endpoints: list[EndpointItemIn] | None = Field(default=None, description="涉及的微服务接口契约列表（选填）")


@router.post("/generate")
async def generate_e2e_case_endpoint(
    body: SynthesizeCaseIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """根据业务 Spec 与接口契约智能推导上下文并合成端到端测试用例。"""
    _ = _user
    eps_dicts = [ep.model_dump() for ep in body.endpoints] if body.endpoints is not None else None
    test_case = synthesize_e2e_test_flow(
        spec_title=body.spec_title,
        business_flow_description=body.business_flow_description,
        endpoints=eps_dicts,
    )
    return {"message": "端到端业务测试用例流智能合成完成", "case": test_case.to_dict()}


@router.get("/cases")
async def list_cases_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史生成的端到端用例列表。"""
    _ = _user
    cases = list_synthesized_cases(limit=limit)
    return {"total": len(cases), "cases": cases}


@router.get("/cases/{case_id}")
async def get_case_endpoint(
    case_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单条生成的用例详情与 Python 测试脚本。"""
    _ = _user
    case = get_synthesized_case(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"用例 [{case_id}] 不存在")
    return {"case": case.to_dict()}


@router.delete("/cases")
async def clear_cases_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空所有生成的用例（需工程师权限）。"""
    _ = _user
    clear_synthesized_cases_store()
    return {"message": "已清空所有合成端到端测试用例"}
