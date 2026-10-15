"""AI Autonomous Exploration and Case Synthesis API (Phase 2)."""

from __future__ import annotations

import threading
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_engineer
from app.core.database import get_db
from app.models.user import User
from app.services.autonomous_exploration_engine import AutonomousExplorationGraph
from app.services.exploration_case_synthesizer import synthesize_test_case_payload

router = APIRouter(prefix="/exploration", tags=["智能探索遍历与用例生成"])

_LOCK = threading.Lock()
_GRAPHS: dict[str, AutonomousExplorationGraph] = {}


class ExplorationStepIn(BaseModel):
    elements: list[dict[str, Any]] = Field(default_factory=list, description="当前屏幕交互元素列表")
    screen_name: str = Field(default="MainScreen", description="当前页面 URL 或 Activity 名称")
    session_id: str | None = None
    strategy: str = "bfs"
    max_depth: int = 6


class ExplorationStepOut(BaseModel):
    session_id: str
    next_action: dict[str, Any] | None
    current_state_id: str
    metrics: dict[str, Any]


@router.post("/step", response_model=ExplorationStepOut)
async def exploration_step_endpoint(
    body: ExplorationStepIn,
    _user: User = Depends(get_current_user),
):
    """接收当前屏幕状态树元素，更新探索有限状态机图模型并返回下一步探索动作。"""
    sid = body.session_id or f"exp_{uuid.uuid4().hex[:12]}"

    with _LOCK:
        if sid not in _GRAPHS:
            _GRAPHS[sid] = AutonomousExplorationGraph(strategy=body.strategy, max_depth=body.max_depth)
        graph = _GRAPHS[sid]

    state = graph.update_state(body.elements, body.screen_name)
    next_action = graph.select_next_action()
    metrics = graph.get_coverage_metrics()

    return ExplorationStepOut(
        session_id=sid,
        next_action=next_action,
        current_state_id=state.state_id,
        metrics=metrics,
    )


@router.get("/sessions/{session_id}")
async def get_exploration_session_endpoint(
    session_id: str,
    _user: User = Depends(get_current_user),
):
    """查询指定智能探索会话的图模型指标与遍历覆盖率。"""
    with _LOCK:
        graph = _GRAPHS.get(session_id)
    if not graph:
        raise HTTPException(status_code=404, detail="探索会话不存在")
    return graph.get_coverage_metrics()


class SynthesizeCaseIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    module_id: int = Field(ge=1)
    case_type: str = "android"  # android | web | ios
    events: list[dict[str, Any]] = Field(default_factory=list)
    description: str | None = None
    persist: bool = False


@router.post("/synthesize-case", status_code=status.HTTP_200_OK)
async def synthesize_case_endpoint(
    body: SynthesizeCaseIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    """将探索遍历沉淀的有效事件流自动去噪、压缩并合成为 TestCase 用例资产。"""
    payload = synthesize_test_case_payload(
        name=body.name,
        module_id=body.module_id,
        events=body.events,
        case_type=body.case_type,
        description=body.description,
        platform=body.case_type,
    )
    if not body.persist:
        return payload

    from app.api.v1.cases import create_case

    created = await create_case(payload, db=db, current_user=current_user)
    return created
