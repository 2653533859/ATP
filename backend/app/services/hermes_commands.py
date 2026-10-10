"""Persistent command receipts; callers check current project permissions first.

Resources and receipts are flushed/committed by the caller's transaction.
Command replay never creates a new resource or dispatches an execution.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hermes_action import HermesAction
from app.models.suite import SuiteRun, TestSuite

CommandAction = Literal["create_suite", "run_suite"]
ResourceState = Literal["available", "missing", "replaced", "unverified"]


class CommandConflict(ValueError):
    """An existing command cannot safely be replayed."""


def command_request_hash(payload: dict[str, Any]) -> str:
    # Preserve the established create-suite digest format for existing clients.
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def find_command(db: AsyncSession, *, user_id: int, command_id: str) -> HermesAction | None:
    return await db.scalar(
        select(HermesAction).where(HermesAction.user_id == user_id, HermesAction.command_id == command_id)
    )


async def command_resource(
    db: AsyncSession, command: HermesAction
) -> tuple[TestSuite | SuiteRun | None, ResourceState]:
    if not command.resource_identity:
        return None, "unverified"
    if command.action == "create_suite":
        resource = await db.get(TestSuite, command.resource_id)
        if resource is None:
            return None, "missing"
        if resource.identity_token != command.resource_identity or resource.project_id != command.project_id:
            return None, "replaced"
        return resource, "available"
    if command.action == "run_suite":
        run = await db.get(SuiteRun, command.resource_id)
        if run is None:
            return None, "missing"
        suite = await db.get(TestSuite, run.suite_id)
        if run.identity_token != command.resource_identity or suite is None or suite.project_id != command.project_id:
            return None, "replaced"
        return run, "available"
    return None, "unverified"


async def replay_command(
    db: AsyncSession,
    *,
    user_id: int,
    project_id: int,
    command_id: str | None,
    action: CommandAction,
    request_hash: str,
) -> TestSuite | SuiteRun | None:
    if command_id is None:
        return None
    command = await find_command(db, user_id=user_id, command_id=command_id)
    if command is None:
        return None
    if command.project_id != project_id or command.action != action or command.request_hash != request_hash:
        raise CommandConflict("操作编号已用于其他项目、动作或内容")
    resource, state = await command_resource(db, command)
    if state == "unverified":
        raise CommandConflict("历史操作缺少资源身份，请核对处理记录；不会自动重建或执行")
    if resource is None:
        raise CommandConflict("原操作资源已删除或身份已变化；不会自动重建或执行")
    return resource


def record_command(
    db: AsyncSession,
    *,
    user_id: int,
    project_id: int,
    command_id: str | None,
    action: CommandAction,
    request_hash: str,
    resource: TestSuite | SuiteRun,
) -> None:
    if command_id is None:
        return
    if not resource.identity_token:
        raise ValueError("command resource must be flushed before recording")
    if (action == "create_suite" and not isinstance(resource, TestSuite)) or (
        action == "run_suite" and not isinstance(resource, SuiteRun)
    ):
        raise ValueError("command action does not match resource type")
    db.add(
        HermesAction(
            user_id=user_id,
            project_id=project_id,
            command_id=command_id,
            action=action,
            request_hash=request_hash,
            resource_id=resource.id,
            resource_identity=resource.identity_token,
        )
    )
