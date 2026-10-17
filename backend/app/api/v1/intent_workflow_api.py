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
from app.services.vlm_autonomous_explorer import (
    decide_and_step_exploration,
    get_exploration_session,
    list_exploration_sessions,
    perceive_screen_elements,
    start_exploration_session,
)
from app.services.exploration_anomaly_detector import (
    inspect_screen_anomaly,
    list_anomaly_records,
)
from app.services.exploration_to_workflow_converter import (
    convert_exploration_to_workflow,
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


class StartExplorationRequest(BaseModel):
    platform: str = Field("web", description="目标终端平台 (web | ios | android)")
    device_id: str = Field("browser_default", description="设备标识 (如 iOS UDID 或浏览器实例)")
    goal: str = Field("自主探索界面主业务流并捕获异常", description="探索业务目标说明")
    max_steps: int = Field(30, ge=5, le=100, description="最大探索步数")


class StepExplorationRequest(BaseModel):
    session_id: str = Field(..., description="探索会话 ID")
    screenshot_base64: str = Field(..., description="当前屏幕截图 Base64 字符串")
    consecutive_same_state_count: int = Field(0, description="页面连续相同状态计数 (防死锁)")


class ConvertExplorationRequest(BaseModel):
    session_id: str = Field(..., description="探索会话 ID")
    workflow_id: Optional[str] = Field(None, description="工作流 ID")
    workflow_name: Optional[str] = Field(None, description="工作流名称")


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


@router.post("/exploration/start")
def start_exploration_endpoint(
    payload: StartExplorationRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """启动 VLM 多模态自主探索测试会话"""
    sess = start_exploration_session(
        platform=payload.platform,
        device_id=payload.device_id,
        goal=payload.goal,
        max_steps=payload.max_steps,
    )
    return {
        "message": "自主探索会话启动成功",
        "session": sess.to_dict(),
    }


@router.post("/exploration/step")
def step_exploration_endpoint(
    payload: StepExplorationRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """接收屏幕截图，执行一步多模态探索与异常缺陷检测"""
    try:
        session, decided_action = decide_and_step_exploration(
            session_id=payload.session_id,
            current_screenshot_b64=payload.screenshot_base64,
        )
        # 异常检测
        elements = perceive_screen_elements(payload.screenshot_base64, platform=session.platform)
        anomaly = inspect_screen_anomaly(
            session=session,
            screenshot_b64=payload.screenshot_base64,
            elements=elements,
            consecutive_same_state_count=payload.consecutive_same_state_count,
        )

        return {
            "message": "探索单步决策完成",
            "action": decided_action,
            "anomaly": anomaly.to_dict() if anomaly else None,
            "current_step": session.step_count,
            "states_count": len(session.states),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/exploration/{session_id}")
def get_exploration_session_endpoint(
    session_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取探索会话的状态迁移图谱与执行轨迹"""
    sess = get_exploration_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="未找到目标探索会话记录")
    return {"session": sess.to_dict()}


@router.get("/exploration/list/sessions")
def list_exploration_sessions_endpoint(
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询全量自主探索会话列表"""
    items = list_exploration_sessions(limit=limit)
    return {
        "total": len(items),
        "sessions": items,
    }


@router.post("/exploration/convert")
def convert_exploration_endpoint(
    payload: ConvertExplorationRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """将验证通过的探索轨迹一键转换为标准多端低代码自动化工作流"""
    sess = get_exploration_session(payload.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="未找到目标探索会话")

    workflow_draft = convert_exploration_to_workflow(
        session=sess,
        workflow_id=payload.workflow_id,
        workflow_name=payload.workflow_name,
    )
    return {
        "message": "探索轨迹成功固化转换为自动化工作流草稿",
        "workflow_draft": workflow_draft,
    }


@router.get("/exploration/anomalies/list")
def list_anomalies_endpoint(
    session_id: Optional[str] = None,
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询探索中检出的异常白屏、卡死或报错弹窗记录"""
    anomalies = list_anomaly_records(session_id=session_id, limit=limit)
    return {
        "total": len(anomalies),
        "anomalies": anomalies,
    }
