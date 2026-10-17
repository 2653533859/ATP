"""自然语言意图驱动工作流生成与优化 REST API (T1.3)"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.deps import require_engineer
from app.models.user import User

from app.services.intent_workflow_synthesizer import (
    get_synthesis_result,
    list_synthesis_history,
    refine_workflow_with_intent,
    synthesize_workflow_from_intent,
)

router = APIRouter(prefix="/workflow/intent", tags=["Intent-Driven Workflow Synthesizer"])


class GenerateWorkflowFromIntentRequest(BaseModel):
    prompt: str = Field(
        ..., description="自然语言业务测试意图 (例如: '创建订单后用Web登录加购，在iOS支付并在数据库对账')"
    )
    workflow_id: Optional[str] = Field(None, description="期望的工作流 ID")
    workflow_name: Optional[str] = Field(None, description="期望的工作流名称")


class RefineWorkflowIntentRequest(BaseModel):
    synthesis_id: str = Field(..., description="上一次合成的会话 ID")
    refinement_prompt: str = Field(..., description="微调与增补指令 (例如: '在支付前加一个延时等待 500ms')")


@router.post("/generate")
def generate_workflow_endpoint(
    payload: GenerateWorkflowFromIntentRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """基于自然语言业务意图智能逆向推导合成多端多协议工作流 DAG 拓扑"""
    dag = synthesize_workflow_from_intent(
        prompt=payload.prompt,
        workflow_id=payload.workflow_id,
        workflow_name=payload.workflow_name,
    )
    return {
        "message": "工作流拓扑 DAG 意图合成成功",
        "synthesis": dag.to_dict(),
    }


@router.post("/refine")
def refine_workflow_endpoint(
    payload: RefineWorkflowIntentRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """根据自然语言指令对话式微调扩充已有工作流拓扑"""
    try:
        refined = refine_workflow_with_intent(
            synthesis_id=payload.synthesis_id,
            refinement_prompt=payload.refinement_prompt,
        )
        return {
            "message": "工作流拓扑微调更新成功",
            "synthesis": refined.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{synthesis_id}")
def get_synthesis_endpoint(
    synthesis_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询单次意图合成的工作流拓扑详情"""
    dag = get_synthesis_result(synthesis_id)
    if not dag:
        raise HTTPException(status_code=404, detail="未找到目标意图合成记录")
    return {"synthesis": dag.to_dict()}


@router.get("/history/list")
def list_synthesis_history_endpoint(
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取近期意图驱动合成的工作流历史列表"""
    items = list_synthesis_history(limit=limit)
    return {
        "total": len(items),
        "history": items,
    }
