"""Idempotency and audit helpers for unified execution commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.execution_command import ExecutionCommand
from app.services.audit import write_audit_log

INDETERMINATE_COMMAND_DETAIL = "命令处理进程在确认结果前中断，副作用状态不确定；禁止自动重放，请核对源任务和审计日志"


@dataclass(frozen=True)
class ExecutionCommandClaim:
    command: ExecutionCommand
    replay_response: dict | None = None


def normalize_execution_command_id(value: str | None, *, action: str, task_type: str, run_id: int) -> str:
    """Return a bounded command ID; omitted IDs use a stable workbench key."""
    normalized = value.strip() if value is not None else f"workbench:{action}:{task_type}:{run_id}"
    if not normalized:
        raise HTTPException(status_code=422, detail="命令 ID 不能为空")
    if len(normalized) > 128:
        raise HTTPException(status_code=422, detail="命令 ID 不能超过 128 个字符")
    return normalized


def _assert_same_command(command: ExecutionCommand, *, action: str, task_type: str, run_id: int) -> None:
    if (command.action, command.task_type, command.run_id) != (action, task_type, run_id):
        raise HTTPException(status_code=409, detail="命令 ID 已被其他任务操作使用")


def _resolve_existing(command: ExecutionCommand, *, action: str, task_type: str, run_id: int) -> ExecutionCommandClaim:
    _assert_same_command(command, action=action, task_type=task_type, run_id=run_id)
    if command.status == "succeeded":
        return ExecutionCommandClaim(command=command, replay_response=dict(command.response_json or {}))
    if command.status == "processing":
        raise HTTPException(status_code=409, detail="相同命令正在处理中，请勿重复提交")
    raise HTTPException(
        status_code=command.error_status_code or 409,
        detail=command.error_detail or "相同命令此前执行失败，请使用新的命令 ID 重试",
    )


async def _find_command(db: AsyncSession, *, user_id: int, command_id: str) -> ExecutionCommand | None:
    result = await db.execute(
        select(ExecutionCommand).where(
            ExecutionCommand.user_id == user_id,
            ExecutionCommand.command_id == command_id,
        )
    )
    return result.scalar_one_or_none()


async def _find_target_command(
    db: AsyncSession,
    *,
    action: str,
    task_type: str,
    run_id: int,
    for_update: bool = False,
) -> ExecutionCommand | None:
    statement = select(ExecutionCommand).where(
        ExecutionCommand.action == action,
        ExecutionCommand.task_type == task_type,
        ExecutionCommand.run_id == run_id,
        ExecutionCommand.status.in_(("processing", "succeeded", "indeterminate")),
    )
    if for_update:
        statement = statement.with_for_update()
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def claim_execution_command(
    db: AsyncSession,
    *,
    user_id: int,
    command_id: str,
    action: str,
    task_type: str,
    run_id: int,
    project_id: int | None,
    source_status: str,
) -> ExecutionCommandClaim:
    """Claim a command, or return its completed response for an exact replay."""
    existing = await _find_command(db, user_id=user_id, command_id=command_id)
    if existing is not None:
        return _resolve_existing(existing, action=action, task_type=task_type, run_id=run_id)

    command = ExecutionCommand(
        user_id=user_id,
        command_id=command_id,
        action=action,
        task_type=task_type,
        run_id=run_id,
        project_id=project_id,
        source_status=source_status,
        status="processing",
    )
    db.add(command)
    try:
        await db.commit()
        await db.refresh(command)
        return ExecutionCommandClaim(command=command)
    except IntegrityError:
        await db.rollback()
        existing = await _find_command(db, user_id=user_id, command_id=command_id)
        if existing is None:
            existing = await _find_target_command(
                db,
                action=action,
                task_type=task_type,
                run_id=run_id,
                for_update=True,
            )
        if existing is None:
            raise
        return _resolve_existing(existing, action=action, task_type=task_type, run_id=run_id)


async def complete_execution_command(
    db: AsyncSession,
    command: ExecutionCommand,
    *,
    response: dict,
    username: str,
) -> None:
    command.status = "succeeded"
    command.response_json = response
    command.result_status = str(response.get("status") or "") or None
    await write_audit_log(
        db,
        action=f"execution.{command.action}.succeeded",
        resource_type=f"{command.task_type}_run",
        resource_id=command.run_id,
        user_id=command.user_id,
        username=username,
        project_id=command.project_id,
        detail=json.dumps(
            {
                "command_id": command.command_id,
                "source_status": command.source_status,
                "result_status": command.result_status,
                "response": response,
            },
            ensure_ascii=False,
            default=str,
        ),
    )
    await db.commit()


async def fail_execution_command(
    db: AsyncSession,
    command: ExecutionCommand,
    *,
    status_code: int,
    detail: str,
    username: str,
) -> None:
    command_pk = command.id
    await db.rollback()
    reloaded_command = await db.get(ExecutionCommand, command_pk)
    if reloaded_command is None:
        return
    command = reloaded_command
    command.status = "failed"
    command.result_status = command.source_status
    command.error_status_code = status_code
    command.error_detail = detail
    await write_audit_log(
        db,
        action=f"execution.{command.action}.failed",
        resource_type=f"{command.task_type}_run",
        resource_id=command.run_id,
        user_id=command.user_id,
        username=username,
        project_id=command.project_id,
        detail=json.dumps(
            {
                "command_id": command.command_id,
                "source_status": command.source_status,
                "result_status": command.result_status,
                "status_code": status_code,
                "detail": detail,
            },
            ensure_ascii=False,
        ),
    )
    await db.commit()


async def mark_execution_command_indeterminate(
    db: AsyncSession,
    command: ExecutionCommand,
    *,
    username: str,
    detail: str = INDETERMINATE_COMMAND_DETAIL,
) -> None:
    """Persist an uncertain outcome when dispatch may have produced a side effect."""
    command_pk = command.id
    await db.rollback()
    reloaded_command = await db.get(ExecutionCommand, command_pk)
    if reloaded_command is None:
        return
    reloaded_command.status = "indeterminate"
    reloaded_command.error_status_code = 409
    reloaded_command.error_detail = detail
    await write_audit_log(
        db,
        action=f"execution.{reloaded_command.action}.indeterminate",
        resource_type=f"{reloaded_command.task_type}_run",
        resource_id=reloaded_command.run_id,
        user_id=reloaded_command.user_id,
        username=username,
        project_id=reloaded_command.project_id,
        detail=json.dumps(
            {
                "command_id": reloaded_command.command_id,
                "source_status": reloaded_command.source_status,
                "result_status": reloaded_command.result_status,
                "reason": "dispatch_exception",
            },
            ensure_ascii=False,
        ),
    )
    await db.commit()


def reconcile_stale_execution_commands(
    session: Session,
    *,
    now: datetime,
    timeout_minutes: int,
    limit: int = 500,
) -> int:
    """Close abandoned command claims without replaying uncertain side effects."""
    cutoff = now - timedelta(minutes=timeout_minutes)
    result = session.execute(
        select(ExecutionCommand)
        .where(
            ExecutionCommand.status == "processing",
            ExecutionCommand.updated_at < cutoff,
        )
        .order_by(ExecutionCommand.id.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    commands = result.scalars().all()
    for command in commands:
        command.status = "indeterminate"
        command.error_status_code = 409
        command.error_detail = INDETERMINATE_COMMAND_DETAIL
        session.add(
            AuditLog(
                action=f"execution.{command.action}.indeterminate",
                resource_type=f"{command.task_type}_run",
                resource_id=command.run_id,
                user_id=command.user_id,
                username="system",
                project_id=command.project_id,
                detail=json.dumps(
                    {
                        "command_id": command.command_id,
                        "source_status": command.source_status,
                        "result_status": command.result_status,
                        "reason": "processing_timeout",
                        "timeout_minutes": timeout_minutes,
                    },
                    ensure_ascii=False,
                ),
            )
        )
    return len(commands)
