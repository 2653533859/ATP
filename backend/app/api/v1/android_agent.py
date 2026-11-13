"""Android Agent REST API router for session lifecycle, control transitions and event stream."""

from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.android_agent import (
    AndroidAgentDraft,
    AndroidAgentCommand,
    AndroidAgentReplay,
    AndroidAgentSession,
)
from app.models.case import CaseStatus, TestCase, TestRun
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.encryption import decrypt
from app.models.ai_llm_config import AILLMConfig
from app.models.device import Device, DeviceStatus
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.android_agent import (
    AgentCompleteRequest,
    AgentControlRequest,
    AgentControlResponse,
    AgentDraftCreateRequest,
    AgentDraftPatchRequest,
    AgentDraftResponse,
    AgentEventItem,
    AgentEventsResponse,
    AgentManualActionRequest,
    AgentPublishResponse,
    AgentReplayHandoffResponse,
    AgentReplayPreviewResponse,
    AgentReplayResponse,
    AgentReplayStartRequest,
    AgentRunResultResponse,
    AgentSessionCreate,
    AgentSessionStatus,
    AgentSessionResponse,
    AgentVisionModelOut,
)
from app.models.audit import AuditLog
from app.services.ai_case.llm_client import LLMRequest
from app.services.android_agent.compiler import compile_session_draft
from app.services.android_agent.coordinator import (
    AgentCoordinator,
    DeviceLeaseUnavailableError,
    InvalidStateTransitionError,
    SessionNotFoundError,
    UnauthorizedControllerError,
)
from app.services.android_agent.loop import AgentLoopError, run_agent_session
from app.services.android_agent.control import ControlRejected, ControlState, DeviceControlGate
from app.services.android_agent.device_adapter import DeviceAdapterError, UiTarget
from app.services.android_agent.replay import (
    build_replay_preview,
    find_published_case,
    find_verified_replay,
    start_replay,
)
from app.services.device_leases import get_active_device_lease, release_device_lease

router = APIRouter(prefix="/projects/{project_id}/android-agent", tags=["Android Agent"])
coordinator = AgentCoordinator()


async def _lock_agent_session(db: AsyncSession, session_id: int) -> AndroidAgentSession:
    # SQLite ignores FOR UPDATE. A no-op write serializes manual dispatch with
    # resume/cancel/complete there; PostgreSQL holds the row lock until commit.
    await db.execute(
        update(AndroidAgentSession)
        .where(AndroidAgentSession.id == session_id)
        .values(version=AndroidAgentSession.version, updated_at=AndroidAgentSession.updated_at)
        .execution_options(synchronize_session=False)
    )
    return (
        await db.execute(
            select(AndroidAgentSession)
            .where(AndroidAgentSession.id == session_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


def _require_android_agent_enabled() -> None:
    if not settings.ANDROID_AGENT_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="android_agent_disabled: Android Agent 功能已停用，现有会话仍可查看或取消",
        )


async def _record_agent_audit(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: int | None,
    user: User,
    project_id: int,
    detail: str | None = None,
) -> None:
    """审计与业务变更同事务提交；写入失败时由调用方回滚。"""
    db.add(
        AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=getattr(user, "id", None),
            username=getattr(user, "username", ""),
            detail=detail,
            project_id=project_id,
        )
    )
    await db.flush()


def _enqueue_replay_run(run: TestRun, case: TestCase, session: AndroidAgentSession) -> None:
    """把回放运行投递到 Android 执行队列；测试可替换该函数。"""
    import app.api.v1.cases as _cases
    from app.services.execution_routing import enqueue_case_run

    enqueue_case_run(
        _cases.run_test_case,
        run.id,
        dict(session.context_values or {}),
        run.trace_id,
        case.case_type,
    )


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


@router.get(
    "/sessions",
    response_model=list[AgentSessionResponse],
    summary="分页查询项目下的 Android Agent 会话列表",
)
async def list_agent_sessions(
    project_id: int = Path(..., ge=1),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AndroidAgentSession]:
    await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    stmt = (
        select(AndroidAgentSession)
        .where(AndroidAgentSession.project_id == project_id)
        .order_by(AndroidAgentSession.id.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


@router.get(
    "/models",
    response_model=list[AgentVisionModelOut],
    summary="列出项目可用的已启用模型配置（脱敏，不含密钥）",
)
async def list_agent_models(
    project_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AILLMConfig]:
    await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    stmt = (
        select(AILLMConfig)
        .where(AILLMConfig.enabled.is_(True))
        .order_by(AILLMConfig.supports_vision.desc(), AILLMConfig.id.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


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
    _require_android_agent_enabled()
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
    _require_android_agent_enabled()
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
    await _get_project_session(db, project_id, session_id)
    session = await _lock_agent_session(db, session_id)
    if payload.action.value == "resume":
        _require_android_agent_enabled()
    if payload.action.value == "resume":
        await _require_no_manual_dispatch(db, session_id)

    # 乐观并发版本检查
    if payload.expected_version is not None and payload.expected_version != session.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session version conflict: expected {payload.expected_version}, actual {session.version}",
        )

    try:
        inflight = await _manual_dispatch_inflight(db, session_id) if payload.action.value == "cancel" else False
        if inflight:
            # 作废后续写入，但不能在正在进行的设备 RPC 结束前把租约交给其他人。
            updated = await coordinator.cancel_session(db, session_id, reason=payload.reason or "", retain_lease=True)
        else:
            updated = await coordinator.control_session(
                db,
                session_id,
                action=payload.action,
                reason=payload.reason or "",
            )
        await _record_agent_audit(
            db,
            action=f"android_agent_session_{payload.action.value}",
            resource_type="android_agent_session",
            resource_id=updated.id,
            user=current_user,
            project_id=project_id,
            detail=(
                f"status={updated.status}; controller={updated.controller}; "
                f"control_epoch={updated.control_epoch}; reason={payload.reason or ''}"
            ),
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
    _require_android_agent_enabled()
    await _get_project_session(db, project_id, session_id)
    try:
        # Serialize manual dispatches on the session row. An in-flight or
        # interrupted command must never be silently sent a second time.
        session = await _lock_agent_session(db, session_id)
        if payload.idempotency_key:
            existing = (
                await db.execute(
                    select(AndroidAgentCommand).where(
                        AndroidAgentCommand.session_id == session_id,
                        AndroidAgentCommand.idempotency_key == payload.idempotency_key,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return _manual_response(existing)
        inflight = await db.scalar(
            select(AndroidAgentCommand.id)
            .where(AndroidAgentCommand.session_id == session_id, AndroidAgentCommand.status == "dispatching")
            .limit(1)
        )
        if inflight is not None:
            raise HTTPException(status_code=409, detail="manual_command_in_progress: 请先核实前一指令结果")
        raw_params = dict(payload.params)
        params = {key: raw_params[key] for key in ("resource_id", "direction", "duration_ms") if key in raw_params}
        safe_payload = payload.model_copy(update={"params": params})
        cmd = await coordinator.manual_action(db, session_id, safe_payload)
        cmd.status = "dispatching"
        command_id, epoch = cmd.id, session.control_epoch
        device_id, lease_token, package_name = session.device_id, session.lease_token, session.package_name
        await _record_agent_audit(
            db,
            action="android_agent_manual_action",
            resource_type="android_agent_session",
            resource_id=session_id,
            user=current_user,
            project_id=project_id,
            detail=f"command_id={cmd.id}; seq={cmd.seq}; control_epoch={cmd.control_epoch}; action={cmd.action}",
        )
        await db.commit()
        result, error = await _execute_manual_action(
            session_id, device_id, lease_token, epoch, package_name, payload.action, raw_params
        )
        cmd = await db.get(AndroidAgentCommand, command_id)
        assert cmd is not None
        cmd.status, cmd.error_message = result, error
        current = await _lock_agent_session(db, session_id)
        if current.status == "cancelled" and current.device_id == device_id and current.lease_token == lease_token:
            if device_id and lease_token:
                await release_device_lease(db, device_id, lease_token)
            current.lease_token = None
        await coordinator.append_event(
            db,
            session_id,
            event_type="step_executed",
            payload={
                "command_id": command_id,
                "action": payload.action,
                "action_status": result,
                "control_epoch": epoch,
                "node": {"resource_id": params.get("resource_id", "")},
                "params": params,
                "error_code": error,
                "controller": "manual",
            },
        )
        await db.commit()
        await db.refresh(cmd)
        return _manual_response(cmd)
    except UnauthorizedControllerError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _manual_response(cmd: AndroidAgentCommand) -> dict[str, Any]:
    return {
        "command_id": cmd.id,
        "session_id": cmd.session_id,
        "seq": cmd.seq,
        "control_epoch": cmd.control_epoch,
        "action": cmd.action,
        "status": cmd.status,
        "idempotency_key": cmd.idempotency_key,
        "error_code": cmd.error_message,
    }


async def _manual_dispatch_inflight(db: AsyncSession, session_id: int) -> bool:
    inflight = await db.scalar(
        select(AndroidAgentCommand.id)
        .where(AndroidAgentCommand.session_id == session_id, AndroidAgentCommand.status == "dispatching")
        .limit(1)
    )
    return inflight is not None


async def _require_no_manual_dispatch(db: AsyncSession, session_id: int) -> None:
    if await _manual_dispatch_inflight(db, session_id):
        raise HTTPException(status_code=409, detail="manual_command_in_progress: 请先核实前一指令结果")


async def _execute_manual_action(
    session_id: int,
    device_id: int | None,
    lease_token: str | None,
    epoch: int,
    package_name: str,
    action: str,
    params: dict[str, Any],
) -> tuple[str, str | None]:
    """设备写入前复核持有人和代次；异常结果不自动重试。"""
    if device_id is None or not lease_token:
        return "cancelled", "lease_missing"

    class ManualGate(DeviceControlGate):
        async def check(self, captured_epoch: int) -> None:
            if not settings.ANDROID_AGENT_ENABLED:
                raise ControlRejected("android_agent_disabled")
            await super().check(captured_epoch)
            async with self.session_factory() as check_db:
                current = await check_db.get(AndroidAgentSession, session_id)
                if (
                    current is None
                    or current.status != "paused"
                    or current.controller not in ("manual", "human")
                    or current.control_epoch != captured_epoch
                ):
                    raise ControlRejected("manual_control_changed")

    gate = ManualGate(AsyncSessionLocal, device_id=device_id, lease_token=lease_token, state=ControlState(epoch))
    try:
        await gate.check(epoch)
        async with AsyncSessionLocal() as lookup_db:
            device = await lookup_db.get(Device, device_id)
            if device is None or device.status == DeviceStatus.offline:
                return "failed", "device_unavailable"
            adapter = await asyncio.to_thread(_build_device_adapter, device, package_name)
        allow = gate.sync_check(epoch, asyncio.get_running_loop())
        resource_id = params.get("resource_id")
        if action in ("tap", "input") and (not isinstance(resource_id, str) or not resource_id):
            return "failed", "resource_id_required"
        if action == "tap":
            await asyncio.to_thread(adapter.tap, UiTarget(resource_id=resource_id), assert_write_allowed=allow)
        elif action == "input":
            value = params.get("text")
            if not isinstance(value, str) or not value:
                return "failed", "input_value_required"
            await asyncio.to_thread(adapter.replace_text, resource_id, value, assert_write_allowed=allow)
        elif action == "swipe":
            await asyncio.to_thread(adapter.swipe, params.get("direction", "up"), 0.5, assert_write_allowed=allow)
        elif action == "back":
            await asyncio.to_thread(adapter.press_back, assert_write_allowed=allow)
        elif action == "wait":
            duration = params.get("duration_ms", 1000)
            if type(duration) is not int or not 100 <= duration <= 30000:
                return "failed", "invalid_wait_budget"
            await asyncio.sleep(duration / 1000)
            await gate.check(epoch)
        return "succeeded", None
    except ControlRejected as exc:
        return "cancelled", str(exc)
    except DeviceAdapterError as exc:
        code = str(exc).split(":", 1)[0]
        return ("outcome_unknown" if code in {"write_outcome_unknown", "input_outcome_unknown"} else "failed"), code
    except Exception:
        return "outcome_unknown", "manual_action_outcome_unknown"


async def _build_llm_request(db: AsyncSession, session: AndroidAgentSession) -> LLMRequest:
    """按会话绑定的模型配置构造请求；未配置或模型不支持视觉时只暴露稳定错误码。"""
    if session.llm_config_id is None:
        raise HTTPException(status_code=409, detail="model_capability_missing: 会话未绑定视觉模型")
    config = await db.get(AILLMConfig, session.llm_config_id)
    if config is None or not config.enabled:
        raise HTTPException(status_code=409, detail="model_capability_missing: 模型配置不存在或已停用")
    if not config.supports_vision:
        raise HTTPException(status_code=409, detail="model_capability_missing: 所选模型未声明视觉能力")
    api_key = "" if config.provider == "ollama" and not config.api_key_encrypted else decrypt(config.api_key_encrypted)
    return LLMRequest(
        provider=config.provider,
        api_key=api_key,
        model_name=config.model_name,
        prompt="",
        endpoint=config.endpoint,
    )


def _build_device_adapter(device: Device, package_name: str) -> Any:
    """构造受监督的设备适配层；连接失败只暴露稳定错误码。"""
    from app.services.android_agent.strict_replay import connect_strict_engine

    try:
        engine = connect_strict_engine(device.serial, package_name)
    except Exception:
        raise HTTPException(status_code=503, detail="device_unavailable: 无法连接设备 UIAutomator 服务") from None
    return engine.adapter


@router.post(
    "/sessions/{session_id}/complete",
    response_model=AgentSessionResponse,
    summary="用户确认终态断言后收敛会话（finish 建议不自动等于成功）",
)
async def complete_agent_session(
    payload: AgentCompleteRequest,
    project_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AndroidAgentSession:
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    await _get_project_session(db, project_id, session_id)
    session = await _lock_agent_session(db, session_id)
    await _require_no_manual_dispatch(db, session_id)
    if not payload.terminal_assertion_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="必须确认终态断言（成功条件已在设备上验证）后才能收敛会话",
        )
    if not payload.terminal_assertions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="terminal_assertions_required: 至少提供一条结构化终态断言",
        )
    if session.status not in (
        AgentSessionStatus.paused.value,
        AgentSessionStatus.running.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"agent_complete_rejected: 会话状态 {session.status} 不可收敛",
        )
    try:
        completed = await coordinator.complete_session(
            db,
            session_id,
            summary=payload.summary or "用户确认终态断言",
            outcome=payload.outcome,
            terminal_assertions=[item.model_dump() for item in payload.terminal_assertions],
        )
        await _record_agent_audit(
            db,
            action="android_agent_session_complete",
            resource_type="android_agent_session",
            resource_id=completed.id,
            user=current_user,
            project_id=project_id,
            detail=(
                f"outcome={payload.outcome}; assertions={len(payload.terminal_assertions)}; "
                f"summary={payload.summary or ''}"
            ),
        )
        await db.commit()
        await db.refresh(completed)
        return completed
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/run",
    response_model=AgentRunResultResponse,
    summary="驱动模型循环执行一轮会话（阻塞至收敛）",
)
async def run_agent_session_endpoint(
    project_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    max_rounds: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentRunResultResponse:
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    _require_android_agent_enabled()
    session = await _get_project_session(db, project_id, session_id)
    if session.status != AgentSessionStatus.running.value:
        raise HTTPException(
            status_code=409,
            detail=f"agent_loop_rejected: 会话状态 {session.status}，只有 running 会话可以驱动",
        )
    if session.device_id is None:
        raise HTTPException(status_code=409, detail="device_unavailable: 会话未绑定设备")
    device = await db.get(Device, session.device_id)
    if device is None or device.status == DeviceStatus.offline:
        raise HTTPException(status_code=409, detail="device_offline: 所选设备不在线")

    llm_request = await _build_llm_request(db, session)
    if not session.lease_token or not await get_active_device_lease(db, device.id, session.lease_token):
        raise HTTPException(status_code=409, detail="lease_lost: 会话未持有有效的设备租约")
    adapter = _build_device_adapter(device, session.package_name)
    values = {key: str(value) for key, value in (session.context_values or {}).items()}

    try:
        result = await run_agent_session(
            AsyncSessionLocal,
            session_id,
            adapter=adapter,
            llm_request=llm_request,
            values=values,
            max_rounds=max_rounds,
        )
    except AgentLoopError as exc:
        raise HTTPException(status_code=409, detail=f"agent_loop_rejected: {exc}") from None
    return AgentRunResultResponse(
        status=result.status,
        reason=result.reason,
        steps=result.steps,
        model_calls=result.model_calls,
        tokens=result.tokens,
    )


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


# ---------------- M3: 草稿 / 回放 / 保存（A30–A33） ----------------


async def _get_project_draft(db: AsyncSession, project_id: int, draft_id: int) -> AndroidAgentDraft:
    draft = await db.get(AndroidAgentDraft, draft_id)
    if draft is None or draft.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"草稿 {draft_id} 不存在或不属于项目 {project_id}",
        )
    return draft


def _serialize_draft(draft: AndroidAgentDraft) -> AgentDraftResponse:
    return AgentDraftResponse.model_validate(draft)


async def _next_draft_version(db: AsyncSession, session_id: int) -> int:
    current = (
        await db.execute(
            select(func.coalesce(func.max(AndroidAgentDraft.version), 0)).where(
                AndroidAgentDraft.session_id == session_id
            )
        )
    ).scalar_one()
    return int(current) + 1


def _hash_draft_payload(
    *,
    session_id: int,
    steps: list[Any],
    assertions: list[Any],
    preconditions: list[Any],
    variables: list[Any],
    schema_version: int,
) -> str:
    canonical = json.dumps(
        {
            "schema_version": schema_version,
            "session_id": session_id,
            "steps": steps,
            "assertions": assertions,
            "preconditions": preconditions,
            "variables": variables,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@router.get(
    "/sessions/{session_id}/drafts",
    response_model=list[AgentDraftResponse],
    summary="查询指定会话的所有草稿版本（按版本号降序）",
)
async def list_agent_session_drafts(
    project_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AgentDraftResponse]:
    await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    await _get_project_session(db, project_id, session_id)
    stmt = (
        select(AndroidAgentDraft)
        .where(
            AndroidAgentDraft.project_id == project_id,
            AndroidAgentDraft.session_id == session_id,
        )
        .order_by(AndroidAgentDraft.version.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_serialize_draft(row) for row in rows]


@router.post(
    "/sessions/{session_id}/drafts",
    response_model=AgentDraftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="从会话轨迹编译草稿新版本",
)
async def create_agent_draft(
    project_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    payload: AgentDraftCreateRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentDraftResponse:
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    session = await _get_project_session(db, project_id, session_id)
    request = payload or AgentDraftCreateRequest()

    events = await coordinator.list_events(db, session_id, after_seq=0, limit=1000)
    compiled = compile_session_draft(
        session_id=session.id,
        package_name=session.package_name,
        goal=session.goal,
        expected_outcome=session.expected_outcome,
        events=events,
        terminal_assertions=session.terminal_assertions or [],
        restored_initial_state=request.restored_initial_state,
    )

    version = await _next_draft_version(db, session_id)
    existing_hash = (
        await db.execute(
            select(AndroidAgentDraft).where(
                AndroidAgentDraft.session_id == session_id,
                AndroidAgentDraft.content_hash == compiled.content_hash,
            )
        )
    ).scalar_one_or_none()
    if existing_hash is not None:
        # 内容未变化：返回既有版本，避免重复版本号
        return _serialize_draft(existing_hash)

    draft = AndroidAgentDraft(
        project_id=project_id,
        session_id=session_id,
        version=version,
        schema_version=compiled.schema_version,
        status=compiled.status,
        content_hash=compiled.content_hash,
        steps=compiled.steps,
        assertions=compiled.assertions,
        variables=compiled.variables,
        preconditions=compiled.preconditions,
        blocking_issues=compiled.blocking_issues,
        source_map=compiled.source_map,
        environment_snapshot={
            "package_name": session.package_name,
            "device_id": session.device_id,
            "goal": session.goal,
            "expected_outcome": session.expected_outcome,
        },
        created_by=current_user.id,
    )
    db.add(draft)
    await db.flush()
    await coordinator.append_event(
        db,
        session_id,
        event_type="draft_compiled",
        payload={
            "draft_id": draft.id,
            "version": draft.version,
            "status": draft.status,
            "blocking_issues": [issue.get("code") for issue in draft.blocking_issues],
        },
    )
    await db.commit()
    await db.refresh(draft)
    return _serialize_draft(draft)


@router.get(
    "/drafts/{draft_id}",
    response_model=AgentDraftResponse,
    summary="读取草稿版本",
)
async def get_agent_draft(
    project_id: int = Path(..., ge=1),
    draft_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentDraftResponse:
    await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    draft = await _get_project_draft(db, project_id, draft_id)
    return _serialize_draft(draft)


@router.patch(
    "/drafts/{draft_id}",
    response_model=AgentDraftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="编辑草稿生成新版本（旧版本与验证资格作废）",
)
async def update_agent_draft(
    payload: AgentDraftPatchRequest,
    project_id: int = Path(..., ge=1),
    draft_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentDraftResponse:
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    base = await _get_project_draft(db, project_id, draft_id)

    latest_version = await _next_draft_version(db, base.session_id) - 1
    if payload.expected_version != latest_version or base.version != latest_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"version_conflict: 当前最新版本 {latest_version}，请求基于 {payload.expected_version}",
        )

    steps = payload.steps if payload.steps is not None else list(base.steps or [])
    assertions = payload.assertions if payload.assertions is not None else list(base.assertions or [])
    preconditions = payload.preconditions if payload.preconditions is not None else list(base.preconditions or [])
    variables = list(base.variables or [])
    blocking_issues = list(base.blocking_issues or [])
    if payload.steps is not None:
        # 手工编辑的步骤视为已整理，阻断项只保留与断言相关的项
        blocking_issues = [issue for issue in blocking_issues if issue.get("code") == "missing_final_assertion"]
    if payload.assertions is not None:
        blocking_issues = [issue for issue in blocking_issues if issue.get("code") != "missing_final_assertion"]
    if not assertions:
        blocking_issues.append({"code": "missing_final_assertion", "message": "缺少用户确认的终态断言，不能自动回放"})

    content_hash = _hash_draft_payload(
        session_id=base.session_id,
        steps=steps,
        assertions=assertions,
        preconditions=preconditions,
        variables=variables,
        schema_version=base.schema_version,
    )
    edited = AndroidAgentDraft(
        project_id=project_id,
        session_id=base.session_id,
        version=payload.expected_version + 1,
        schema_version=base.schema_version,
        status="blocked" if blocking_issues else "pending_replay",
        content_hash=content_hash,
        steps=steps,
        assertions=assertions,
        variables=variables,
        preconditions=preconditions,
        blocking_issues=blocking_issues,
        source_map=base.source_map,
        environment_snapshot=base.environment_snapshot,
        created_by=current_user.id,
    )
    db.add(edited)
    await db.flush()
    await coordinator.append_event(
        db,
        base.session_id,
        event_type="draft_edited",
        payload={
            "base_draft_id": base.id,
            "draft_id": edited.id,
            "version": edited.version,
            "status": edited.status,
        },
    )
    await db.commit()
    await db.refresh(edited)
    return _serialize_draft(edited)


@router.get(
    "/drafts/{draft_id}/replay-preview",
    response_model=AgentReplayPreviewResponse,
    summary="回放前核对草稿与初始状态",
)
async def preview_agent_draft_replay(
    project_id: int = Path(..., ge=1),
    draft_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentReplayPreviewResponse:
    await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    draft = await _get_project_draft(db, project_id, draft_id)
    session = await _get_project_session(db, project_id, draft.session_id)
    return await build_replay_preview(db, draft, session)


@router.post(
    "/drafts/{draft_id}/replays",
    response_model=AgentReplayHandoffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="发起独立回放（固定草稿快照，同幂等键复用）",
)
async def start_agent_draft_replay(
    payload: AgentReplayStartRequest,
    project_id: int = Path(..., ge=1),
    draft_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentReplayHandoffResponse:
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    draft = await _get_project_draft(db, project_id, draft_id)
    session = await _get_project_session(db, project_id, draft.session_id)

    device_serial = None
    if payload.device_id:
        device = await db.get(Device, payload.device_id)
        if device is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
        device_serial = device.serial

    replay, case, run = await start_replay(
        db,
        draft=draft,
        session=session,
        user=current_user,
        module_id=payload.module_id,
        idempotency_key=payload.idempotency_key,
        initial_state_confirmed=payload.initial_state_confirmed,
        device_serial=device_serial,
    )
    await coordinator.append_event(
        db,
        session.id,
        event_type="replay_queued",
        payload={
            "replay_id": replay.id,
            "draft_id": draft.id,
            "draft_version": replay.draft_version,
            "case_id": replay.case_id,
            "run_id": replay.run_id,
        },
    )
    await db.commit()
    await db.refresh(replay)

    try:
        # 回放与正式执行走同一条 Android 低代码派发链路，Agent 决策已关闭
        _enqueue_replay_run(run, case, session)
    except Exception:
        # 回放记录已持久化；派发失败不伪造通过，由调用方按 run 状态重试
        replay.status = "dispatch_failed"
        replay.error_code = "dispatch_failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="回放已创建但执行派发失败，请稍后重试",
        ) from None
    await db.commit()

    return AgentReplayHandoffResponse(
        replay=AgentReplayResponse.model_validate(replay),
        case_id=case.id,
        run_id=run.id,
        frozen_snapshot=replay.environment_snapshot,
    )


@router.get(
    "/replays/{replay_id}",
    response_model=AgentReplayResponse,
    summary="查询回放状态与关联运行",
)
async def get_agent_replay(
    project_id: int = Path(..., ge=1),
    replay_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentReplayResponse:
    await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    replay = await db.get(AndroidAgentReplay, replay_id)
    if replay is None or replay.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"回放 {replay_id} 不存在或不属于项目 {project_id}",
        )
    if replay.run_id:
        run = await db.get(TestRun, replay.run_id)
        if run is not None:
            run_status = str(getattr(run.status, "value", run.status))
            if run_status in ("passed", "failed", "error", "stopped"):
                replay.status = run_status
            elif run_status in ("running", "pending"):
                replay.status = "running"
    return AgentReplayResponse.model_validate(replay)


@router.post(
    "/drafts/{draft_id}/publish",
    response_model=AgentPublishResponse,
    summary="把当前验证通过的草稿版本保存为正式用例（幂等）",
)
async def publish_agent_draft(
    project_id: int = Path(..., ge=1),
    draft_id: int = Path(..., ge=1),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentPublishResponse:
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    draft = await _get_project_draft(db, project_id, draft_id)

    published = await find_published_case(db, draft)
    if published is not None:
        verified_id = (await find_verified_replay(db, draft)).id if await find_verified_replay(db, draft) else 0
        return AgentPublishResponse(
            draft_id=draft.id,
            draft_version=draft.version,
            case_id=published.id,
            verified_replay_id=verified_id,
            published=True,
            idempotent_replay=True,
        )
    del idempotency_key

    verified = await find_verified_replay(db, draft)
    if verified is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="draft_not_replayable: 当前草稿版本没有通过的独立回放，不能保存为正式用例",
        )
    if draft.blocking_issues:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="draft_not_replayable: 草稿仍有阻断项，需人工整理后重新回放",
        )
    if verified.case_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="verified_replay_missing_case: 通过的回放缺少用例，请重新发起回放",
        )

    replay_case = await db.get(TestCase, verified.case_id)
    if replay_case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="verified_replay_missing_case: 通过回放的用例已被删除",
        )
    # 保存的是回放用例本身：校验通过、可进入正常调度，配置固定为草稿快照
    replay_case.status = CaseStatus.active
    replay_case.review_status = "approved"
    replay_case.reviewed_at = datetime.now(timezone.utc)
    replay_case.reviewed_by = current_user.id

    draft.published_case_id = replay_case.id
    draft.published_at = datetime.now(timezone.utc)
    draft.status = "verified" if draft.status == "verified" else "verified"
    await coordinator.append_event(
        db,
        draft.session_id,
        event_type="draft_published",
        payload={
            "draft_id": draft.id,
            "version": draft.version,
            "case_id": replay_case.id,
            "verified_replay_id": verified.id,
        },
    )
    await _record_agent_audit(
        db,
        action="android_agent_draft_publish",
        resource_type="android_agent_draft",
        resource_id=draft.id,
        user=current_user,
        project_id=project_id,
        detail=(
            f"session_id={draft.session_id}; draft_version={draft.version}; "
            f"case_id={replay_case.id}; replay_id={verified.id}"
        ),
    )
    await db.commit()
    return AgentPublishResponse(
        draft_id=draft.id,
        draft_version=draft.version,
        case_id=replay_case.id,
        verified_replay_id=verified.id,
        published=True,
    )
