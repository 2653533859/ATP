"""Android Agent persistent coordinator, lifecycle state machine, lease watchdog and crash recovery."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import json
import secrets
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.android_agent import AndroidAgentCommand, AndroidAgentEvent, AndroidAgentSession
from app.schemas.android_agent import (
    AgentControlAction,
    AgentController,
    AgentErrorCode,
    AgentManualActionRequest,
    AgentSessionCreate,
    AgentSessionStatus,
)
from app.services.device_leases import (
    DeviceLeaseConflict,
    acquire_device_lease,
    get_active_device_lease,
    heartbeat_device_lease,
    release_device_lease,
)


class AgentCoordinatorError(RuntimeError):
    """Base error for Android Agent coordinator operations."""


class SessionNotFoundError(AgentCoordinatorError):
    """Session ID does not exist."""


class InvalidStateTransitionError(AgentCoordinatorError):
    """Invalid session status transition."""


class DeviceLeaseUnavailableError(AgentCoordinatorError):
    """Target device cannot be leased or is busy."""


class UnauthorizedControllerError(AgentCoordinatorError):
    """Operation rejected due to mismatched controller (agent vs human)."""


VALID_TRANSITIONS: dict[str, set[str]] = {
    AgentSessionStatus.created.value: {
        AgentSessionStatus.prechecking.value,
        AgentSessionStatus.cancelled.value,
        AgentSessionStatus.failed.value,
    },
    AgentSessionStatus.prechecking.value: {
        AgentSessionStatus.running.value,
        AgentSessionStatus.failed.value,
        AgentSessionStatus.cancelled.value,
    },
    AgentSessionStatus.running.value: {
        AgentSessionStatus.pause_requested.value,
        AgentSessionStatus.paused.value,
        AgentSessionStatus.completed.value,
        AgentSessionStatus.failed.value,
        AgentSessionStatus.cancelled.value,
    },
    AgentSessionStatus.pause_requested.value: {
        AgentSessionStatus.paused.value,
        AgentSessionStatus.failed.value,
        AgentSessionStatus.cancelled.value,
    },
    AgentSessionStatus.paused.value: {
        AgentSessionStatus.running.value,
        AgentSessionStatus.failed.value,
        AgentSessionStatus.cancelled.value,
    },
    AgentSessionStatus.completed.value: set(),
    AgentSessionStatus.failed.value: set(),
    AgentSessionStatus.cancelled.value: set(),
}

# 兼容早期写入的 "human"；新数据统一写 "manual"
MANUAL_CONTROLLERS = frozenset({"manual", "human"})

TERMINAL_STATUSES = frozenset(
    {
        AgentSessionStatus.completed.value,
        AgentSessionStatus.failed.value,
        AgentSessionStatus.cancelled.value,
    }
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _safe_publish_agent_event(session_id: int, event_dict: dict[str, Any]) -> None:
    try:
        from app.core.config import settings

        if getattr(settings, "ATP_LOCAL_MODE", False):
            return
        from app.core.redis_client import close_async_redis, get_async_redis

        r = get_async_redis(db=2)
        try:
            await r.publish(f"atp:agent:session:{session_id}", json.dumps(event_dict, ensure_ascii=False, default=str))
        finally:
            await close_async_redis(r)
    except Exception:
        # Best-effort notification: Redis connection failure must never abort DB transaction
        pass


class AgentCoordinator:
    """Coordinates lifecycle, state machine, control transitions and event logging for Android Agent sessions."""

    async def get_session(self, db: AsyncSession, session_id: int) -> AndroidAgentSession:
        session = await db.get(AndroidAgentSession, session_id)
        if session is None:
            raise SessionNotFoundError(f"Agent session {session_id} not found")
        return session

    def validate_transition(self, current_status: str, target_status: str) -> None:
        allowed = VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition agent session from '{current_status}' to '{target_status}'"
            )

    async def append_event(
        self,
        db: AsyncSession,
        session_id: int,
        event_type: str,
        payload: dict[str, Any],
        artifact_refs: list[str] | None = None,
    ) -> AndroidAgentEvent:
        max_seq = (
            await db.execute(
                select(func.coalesce(func.max(AndroidAgentEvent.seq), 0)).where(
                    AndroidAgentEvent.session_id == session_id
                )
            )
        ).scalar_one()

        event = AndroidAgentEvent(
            session_id=session_id,
            seq=int(max_seq) + 1,
            event_type=event_type,
            payload=payload,
            artifact_refs=artifact_refs or [],
        )
        db.add(event)  # type: ignore[attr-defined]
        await db.flush()

        event_dict = {
            "id": event.id,
            "session_id": event.session_id,
            "seq": event.seq,
            "event_type": event.event_type,
            "payload": event.payload,
            "artifact_refs": event.artifact_refs,
            "created_at": event.created_at.isoformat() if event.created_at else _now().isoformat(),
        }
        await _safe_publish_agent_event(session_id, event_dict)
        return event

    async def create_session(
        self,
        db: AsyncSession,
        project_id: int,
        payload: AgentSessionCreate,
    ) -> AndroidAgentSession:
        session = AndroidAgentSession(
            project_id=project_id,
            device_id=payload.device_id,
            title=payload.title or "Android Agent Session",
            goal=payload.goal,
            expected_outcome=payload.expected_outcome,
            package_name=payload.package_name,
            llm_config_id=payload.llm_config_id,
            status=AgentSessionStatus.created.value,
            controller="agent",
            version=1,
            control_epoch=0,
            budget_max_steps=payload.budget.max_steps,
            budget_max_calls=payload.budget.max_calls,
            context_values=payload.context_values,
        )
        db.add(session)  # type: ignore[attr-defined]
        await db.flush()

        await self.append_event(
            db,
            session.id,
            event_type="session_created",
            payload={
                "project_id": project_id,
                "device_id": session.device_id,
                "goal": session.goal,
                "package_name": session.package_name,
                "budget_max_steps": session.budget_max_steps,
                "budget_max_calls": session.budget_max_calls,
            },
        )
        return session

    async def start_session(self, db: AsyncSession, session_id: int) -> AndroidAgentSession:
        session = await self.get_session(db, session_id)
        self.validate_transition(session.status, AgentSessionStatus.prechecking.value)

        if session.device_id is None:
            raise AgentCoordinatorError("Session does not have an assigned device_id")

        ttl = max(900, session.budget_max_steps * 30 + 300)
        try:
            lease = await acquire_device_lease(
                db,
                session.device_id,
                owner_id=None,
                owner_label=f"android_agent:session:{session.id}",
                ttl_seconds=ttl,
            )
            session.lease_token = lease.lease_token
        except DeviceLeaseConflict as exc:
            await self.fail_session(db, session_id, error_code=AgentErrorCode.device_busy.value, reason=str(exc))
            raise DeviceLeaseUnavailableError(str(exc)) from exc

        session.status = AgentSessionStatus.prechecking.value
        session.version += 1
        await db.flush()
        await self.append_event(
            db,
            session.id,
            event_type="session_prechecking",
            payload={"device_id": session.device_id, "ttl_seconds": ttl},
        )

        now = _now()
        session.started_at = now
        self.validate_transition(session.status, AgentSessionStatus.running.value)
        session.status = AgentSessionStatus.running.value
        session.version += 1
        await db.flush()
        await self.append_event(
            db,
            session.id,
            event_type="session_running",
            payload={"started_at": now.isoformat()},
        )
        return session

    async def control_session(
        self,
        db: AsyncSession,
        session_id: int,
        action: AgentControlAction | str,
        reason: str = "",
    ) -> AndroidAgentSession:
        action_val = action.value if isinstance(action, AgentControlAction) else action
        session = await self.get_session(db, session_id)

        if action_val == AgentControlAction.pause.value:
            if session.status in TERMINAL_STATUSES:
                raise InvalidStateTransitionError(f"Cannot pause session in terminal state '{session.status}'")
            if session.status == AgentSessionStatus.paused.value:
                return session

            self.validate_transition(session.status, AgentSessionStatus.paused.value)
            session.status = AgentSessionStatus.paused.value
            session.control_epoch += 1
            session.version += 1
            await db.flush()
            await self.append_event(
                db,
                session.id,
                event_type="session_paused",
                payload={"reason": reason, "control_epoch": session.control_epoch},
            )
            return session

        elif action_val == AgentControlAction.takeover.value:
            if session.status in TERMINAL_STATUSES:
                raise InvalidStateTransitionError(f"Cannot takeover session in terminal state '{session.status}'")

            session.controller = AgentController.manual.value
            session.status = AgentSessionStatus.paused.value
            session.control_epoch += 1
            session.version += 1
            await db.flush()
            await self.append_event(
                db,
                session.id,
                event_type="human_takeover_started",
                payload={"reason": reason, "control_epoch": session.control_epoch},
            )
            return session

        elif action_val == AgentControlAction.resume.value:
            if session.status != AgentSessionStatus.paused.value:
                raise InvalidStateTransitionError(
                    f"Can only resume session from 'paused' state, current: '{session.status}'"
                )

            # 恢复前验证租约依然有效
            if session.device_id and session.lease_token:
                active_lease = await get_active_device_lease(db, session.device_id, session.lease_token)
                if active_lease is None:
                    await self.fail_session(
                        db,
                        session_id,
                        error_code=AgentErrorCode.lease_lost.value,
                        reason="Device lease lost during pause",
                    )
                    raise DeviceLeaseUnavailableError("Device lease was lost while session was paused")

            session.controller = "agent"
            self.validate_transition(session.status, AgentSessionStatus.running.value)
            session.status = AgentSessionStatus.running.value
            session.control_epoch += 1
            session.version += 1
            await db.flush()
            await self.append_event(
                db,
                session.id,
                event_type="session_resumed",
                payload={"reason": reason, "control_epoch": session.control_epoch},
            )
            return session

        elif action_val == AgentControlAction.cancel.value:
            return await self.cancel_session(db, session_id, reason=reason)

        else:
            raise AgentCoordinatorError(f"Unsupported control action: '{action_val}'")

    async def manual_action(
        self,
        db: AsyncSession,
        session_id: int,
        request: AgentManualActionRequest,
    ) -> AndroidAgentCommand:
        session = await self.get_session(db, session_id)
        # 接管后控制器统一记为 manual（与 AgentController.manual 一致）；早期记录写过 human，读取时兼容
        if session.controller not in MANUAL_CONTROLLERS or session.status != AgentSessionStatus.paused.value:
            raise UnauthorizedControllerError(
                f"Manual actions require a manual controller and status='paused' "
                f"(current: {session.controller}/{session.status})"
            )

        idempotency_key = request.idempotency_key or secrets.token_hex(16)
        stmt = select(AndroidAgentCommand).where(
            AndroidAgentCommand.session_id == session_id,
            AndroidAgentCommand.idempotency_key == idempotency_key,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        max_cmd_seq = (
            await db.execute(
                select(func.coalesce(func.max(AndroidAgentCommand.seq), 0)).where(
                    AndroidAgentCommand.session_id == session_id
                )
            )
        ).scalar_one()

        cmd = AndroidAgentCommand(
            session_id=session_id,
            seq=int(max_cmd_seq) + 1,
            control_epoch=session.control_epoch,
            observation_id=str(request.params.get("observation_id") or "manual"),
            action=request.action,
            params=request.params,
            idempotency_key=idempotency_key,
            # 只登记"已准备"：真正写设备前必须由 dispatch_prepared_command 复核控制权
            status="prepared",
        )
        db.add(cmd)  # type: ignore[attr-defined]
        await db.flush()

        await self.append_event(
            db,
            session_id,
            event_type="manual_action_prepared",
            payload={
                "command_id": cmd.id,
                "action": cmd.action,
                "params": cmd.params,
                "idempotency_key": idempotency_key,
            },
        )
        return cmd

    async def dispatch_prepared_command(
        self,
        db: AsyncSession,
        session_id: int,
        command_id: int,
        *,
        execute: Callable[[AsyncSession, AndroidAgentSession, AndroidAgentCommand], None],
    ) -> AndroidAgentCommand:
        """人工动作的执行闸门：只有 controller=manual 且非终态时才允许落设备。

        门禁内的任何拒绝都只把命令留在 prepared 并返回 409，不产生设备写入。
        """
        session = await self.get_session(db, session_id)
        command = await db.get(AndroidAgentCommand, command_id)
        if command is None or command.session_id != session_id:
            raise AgentCoordinatorError(f"Command {command_id} not found for session {session_id}")
        if command.status != "prepared":
            return command
        if session.status in TERMINAL_STATUSES or session.controller != "manual":
            raise HTTPException(
                status_code=409,
                detail=f"manual_control_required: controller={session.controller}, status={session.status}",
            )

        execute(db, session, command)
        command.status = "succeeded"
        await db.flush()
        await self.append_event(
            db,
            session_id,
            event_type="manual_action_executed",
            payload={
                "command_id": command.id,
                "action": command.action,
                "control_epoch": session.control_epoch,
            },
        )
        return command

    async def complete_session(
        self,
        db: AsyncSession,
        session_id: int,
        summary: str = "",
        outcome: str = "success",
    ) -> AndroidAgentSession:
        session = await self.get_session(db, session_id)
        if session.status in TERMINAL_STATUSES:
            return session

        self.validate_transition(session.status, AgentSessionStatus.completed.value)
        session.status = AgentSessionStatus.completed.value
        session.finished_at = _now()
        session.version += 1

        if session.device_id and session.lease_token:
            await release_device_lease(db, session.device_id, session.lease_token)
            session.lease_token = None

        await db.flush()
        await self.append_event(
            db,
            session.id,
            event_type="session_completed",
            payload={"summary": summary, "outcome": outcome},
        )
        return session

    async def fail_session(
        self,
        db: AsyncSession,
        session_id: int,
        error_code: str,
        reason: str = "",
    ) -> AndroidAgentSession:
        session = await self.get_session(db, session_id)
        if session.status in TERMINAL_STATUSES:
            return session

        self.validate_transition(session.status, AgentSessionStatus.failed.value)
        session.status = AgentSessionStatus.failed.value
        session.error_code = error_code
        session.finished_at = _now()
        session.version += 1

        if session.device_id and session.lease_token:
            try:
                await release_device_lease(db, session.device_id, session.lease_token)
            except Exception:
                pass
            session.lease_token = None

        await db.flush()
        await self.append_event(
            db,
            session.id,
            event_type="session_failed",
            payload={"error_code": error_code, "reason": reason},
        )
        return session

    async def cancel_session(
        self,
        db: AsyncSession,
        session_id: int,
        reason: str = "",
    ) -> AndroidAgentSession:
        session = await self.get_session(db, session_id)
        if session.status in TERMINAL_STATUSES:
            return session

        self.validate_transition(session.status, AgentSessionStatus.cancelled.value)
        session.status = AgentSessionStatus.cancelled.value
        session.finished_at = _now()
        session.control_epoch += 1
        session.version += 1

        if session.device_id and session.lease_token:
            try:
                await release_device_lease(db, session.device_id, session.lease_token)
            except Exception:
                pass
            session.lease_token = None

        await db.flush()
        await self.append_event(
            db,
            session.id,
            event_type="session_cancelled",
            payload={"reason": reason, "control_epoch": session.control_epoch},
        )
        return session

    async def record_step_progress(
        self,
        db: AsyncSession,
        session_id: int,
        *,
        model_calls: int = 1,
        tokens: int = 0,
        actions: int = 1,
        event_payload: dict[str, Any] | None = None,
    ) -> AndroidAgentEvent:
        session = await self.get_session(db, session_id)
        session.steps_count += actions
        session.model_calls_count += model_calls
        session.total_tokens += tokens
        session.version += 1

        # 检查预算耗尽
        if session.steps_count >= session.budget_max_steps or session.model_calls_count >= session.budget_max_calls:
            await self.fail_session(
                db,
                session_id,
                error_code=AgentErrorCode.budget_exceeded.value,
                reason=f"Budget exceeded (steps: {session.steps_count}/{session.budget_max_steps}, calls: {session.model_calls_count}/{session.budget_max_calls})",
            )

        payload = event_payload or {}
        payload.update(
            {
                "steps_count": session.steps_count,
                "model_calls_count": session.model_calls_count,
                "total_tokens": session.total_tokens,
            }
        )
        return await self.append_event(
            db,
            session_id,
            event_type="step_executed",
            payload=payload,
        )

    async def renew_session_lease(self, db: AsyncSession, session_id: int, ttl_seconds: int = 900) -> bool:
        session = await self.get_session(db, session_id)
        if session.status in TERMINAL_STATUSES:
            return False
        if not session.device_id or not session.lease_token:
            return False

        try:
            await heartbeat_device_lease(db, session.device_id, session.lease_token, ttl_seconds=ttl_seconds)
            return True
        except Exception:
            return False

    async def recover_orphaned_sessions(
        self,
        db: AsyncSession,
        inactive_threshold_seconds: int = 180,
    ) -> list[int]:
        """Scan and recover orphaned or crashed non-terminal sessions (A22 crash recovery)."""
        stmt = select(AndroidAgentSession).where(
            AndroidAgentSession.status.in_(
                [
                    AgentSessionStatus.prechecking.value,
                    AgentSessionStatus.running.value,
                    AgentSessionStatus.pause_requested.value,
                ]
            )
        )
        candidates = (await db.execute(stmt)).scalars().all()
        recovered_ids: list[int] = []
        now = _now()
        threshold = now - timedelta(seconds=inactive_threshold_seconds)

        for session in candidates:
            # 1. 检查租约有效性
            lease_active = False
            if session.device_id and session.lease_token:
                active_lease = await get_active_device_lease(db, session.device_id, session.lease_token)
                lease_active = active_lease is not None

            # 2. 检查最后事件活跃时间
            last_event_time = (
                await db.execute(
                    select(func.max(AndroidAgentEvent.created_at)).where(AndroidAgentEvent.session_id == session.id)
                )
            ).scalar_one_or_none()
            if last_event_time and last_event_time.tzinfo is None:
                last_event_time = last_event_time.replace(tzinfo=timezone.utc)

            is_inactive = last_event_time is None or last_event_time < threshold

            if not lease_active or is_inactive:
                reason = "Device lease expired or lost" if not lease_active else "Session heartbeat inactivity timeout"
                await self.fail_session(
                    db,
                    session.id,
                    error_code=AgentErrorCode.system_restarted_needs_review.value,
                    reason=reason,
                )
                recovered_ids.append(session.id)

        return recovered_ids

    async def list_events(
        self,
        db: AsyncSession,
        session_id: int,
        after_seq: int = 0,
        limit: int = 50,
    ) -> list[AndroidAgentEvent]:
        stmt = (
            select(AndroidAgentEvent)
            .where(
                AndroidAgentEvent.session_id == session_id,
                AndroidAgentEvent.seq > after_seq,
            )
            .order_by(AndroidAgentEvent.seq.asc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())
