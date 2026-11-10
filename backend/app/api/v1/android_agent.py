"""Android Agent REST API router for session lifecycle, control transitions and event stream."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.android_agent import AndroidAgentSession
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.android_agent import (
    AgentControlRequest,
    AgentControlResponse,
    AgentEventItem,
    AgentEventsResponse,
    AgentManualActionRequest,
    AgentSessionCreate,
    AgentSessionResponse,
)
from app.services.android_agent.coordinator import (
    AgentCoordinator,
    DeviceLeaseUnavailableError,
    InvalidStateTransitionError,
    SessionNotFoundError,
    UnauthorizedControllerError,
)

router = APIRouter(prefix="/projects/{project_id}/android-agent", tags=["Android Agent"])
coordinator = AgentCoordinator()


async def _get_project_session(
    db: AsyncSession,
    project_id: int,
    session_id: int,
) -> AndroidAgentSession:
    try:
        session = await coordinator.get_session(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent session {session_id} not found",
        ) from None
    if session.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent session {session_id} does not belong to project {project_id}",
        )
    return session


@router.post(
    "/sessions",
    response_model=AgentSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建 Android Agent 会话",
)
async def create_agent_session(
    payload: AgentSessionCreate,
    project_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AndroidAgentSession:
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    session = await coordinator.create_session(db, project_id, payload)
    await db.commit()
    await db.refresh(session)
    return session


@router.post(
    "/sessions/{session_id}/start",
    response_model=AgentSessionResponse,
    summary="启动 Agent 会话并锁定设备租约",
)
async def start_agent_session(
    project_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AndroidAgentSession:
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    await _get_project_session(db, project_id, session_id)
    try:
        session = await coordinator.start_session(db, session_id)
        await db.commit()
        await db.refresh(session)
        return session
    except DeviceLeaseUnavailableError as exc:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device lease unavailable: {exc}",
        ) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/sessions/{session_id}",
    response_model=AgentSessionResponse,
    summary="查询 Agent 会话详情",
)
async def get_agent_session(
    project_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AndroidAgentSession:
    await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    session = await _get_project_session(db, project_id, session_id)
    return session


@router.post(
    "/sessions/{session_id}/control",
    response_model=AgentControlResponse,
    summary="发送会话控制指令 (pause/takeover/resume/cancel)",
)
async def control_agent_session(
    payload: AgentControlRequest,
    project_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentControlResponse:
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    session = await _get_project_session(db, project_id, session_id)

    # 乐观并发版本检查
    if payload.expected_version is not None and payload.expected_version != session.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session version conflict: expected {payload.expected_version}, actual {session.version}",
        )

    try:
        updated = await coordinator.control_session(
            db,
            session_id,
            action=payload.action,
            reason=payload.reason or "",
        )
        await db.commit()
        await db.refresh(updated)
        return AgentControlResponse(
            session_id=updated.id,
            status=updated.status,
            controller=updated.controller,
            control_epoch=updated.control_epoch,
            version=updated.version,
            message=f"Action '{payload.action.value}' executed successfully",
        )
    except DeviceLeaseUnavailableError as exc:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device lease unavailable: {exc}",
        ) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/sessions/{session_id}/manual-action",
    response_model=dict[str, Any],
    summary="人工接管状态下执行单步动作",
)
async def manual_action_agent_session(
    payload: AgentManualActionRequest,
    project_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    await _get_project_session(db, project_id, session_id)
    try:
        cmd = await coordinator.manual_action(db, session_id, payload)
        await db.commit()
        await db.refresh(cmd)
        return {
            "command_id": cmd.id,
            "session_id": cmd.session_id,
            "seq": cmd.seq,
            "control_epoch": cmd.control_epoch,
            "action": cmd.action,
            "status": cmd.status,
            "idempotency_key": cmd.idempotency_key,
        }
    except UnauthorizedControllerError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/sessions/{session_id}/events",
    response_model=AgentEventsResponse,
    summary="增量分页获取 Agent 事件流",
)
async def get_agent_session_events(
    project_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    after_seq: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentEventsResponse:
    await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    await _get_project_session(db, project_id, session_id)

    # 读取 limit + 1 条判断是否有更多事件
    events = await coordinator.list_events(db, session_id, after_seq=after_seq, limit=limit + 1)
    has_more = len(events) > limit
    page_events = events[:limit]

    items = [
        AgentEventItem(
            id=ev.id,
            session_id=ev.session_id,
            seq=ev.seq,
            event_type=ev.event_type,
            payload=ev.payload,
            artifact_refs=ev.artifact_refs,
            created_at=ev.created_at,
        )
        for ev in page_events
    ]
    next_seq = page_events[-1].seq if page_events else after_seq
    return AgentEventsResponse(items=items, next_seq=next_seq, has_more=has_more)
