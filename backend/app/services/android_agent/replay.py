"""草稿快照、独立回放与幂等保存正式用例（实施清单 A32/A33）。

回放与保存都不重新调用模型：回放把草稿固定成快照，交给现有 Android 低代码
执行器执行；保存只在"当前草稿版本的独立回放通过"时创建正式用例，并且同一
幂等键重复请求返回同一用例。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.android_agent import AndroidAgentDraft, AndroidAgentReplay, AndroidAgentSession
from app.models.case import CaseType, RunStatus, TestCase, TestRun
from app.models.project import Module
from app.models.user import User
from app.schemas.android_agent import (
    AgentReplayPreviewItem,
    AgentReplayPreviewResponse,
    AgentReplayResponse,
)
from app.services.android_agent.compiler import DRAFT_SCHEMA_VERSION
from app.core.tracing import get_trace_id

REPLAYABLE_DRAFT_STATUSES = frozenset({"replayable", "pending_replay", "verified"})
PASSED_REPLAY_STATUSES = frozenset({"passed"})
_ANDROID_CASE_CONFIG_KEYS = ("package_name", "device_serial", "app_package", "strict_replay", "auto_launch")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=detail)


def frozen_snapshot(draft: AndroidAgentDraft, session: AndroidAgentSession) -> dict[str, Any]:
    """把草稿固定成不可变快照；回放只按快照执行，后续编辑不影响进行中的回放。"""
    return {
        "schema_version": draft.schema_version or DRAFT_SCHEMA_VERSION,
        "draft_id": draft.id,
        "draft_version": draft.version,
        "content_hash": draft.content_hash,
        "session_id": session.id,
        "package_name": session.package_name,
        "goal": session.goal,
        "expected_outcome": session.expected_outcome,
        "steps": draft.steps,
        "assertions": draft.assertions,
        "variables": draft.variables,
        "preconditions": draft.preconditions,
        "device_id": session.device_id,
        "context_values": dict(session.context_values or {}),
        "source_map": draft.source_map,
    }


def build_case_config(snapshot: dict[str, Any], *, module_id: int, device_serial: str | None) -> dict[str, Any]:
    """草稿快照 -> Android 低代码用例 config；Agent 回放不允许坐标兜底。"""
    config: dict[str, Any] = {
        "steps": snapshot["steps"],
        "assertions": snapshot["assertions"],
        "strict_replay": True,
        "android_agent": {
            "draft_id": snapshot["draft_id"],
            "draft_version": snapshot["draft_version"],
            "content_hash": snapshot["content_hash"],
            "expected_outcome": snapshot["expected_outcome"],
            "variables": snapshot["variables"],
            "agent_replay": True,
        },
    }
    if snapshot.get("package_name"):
        config["package_name"] = snapshot["package_name"]
        config["app_package"] = snapshot["package_name"]
    if device_serial:
        config["device_serial"] = device_serial
    config["_internal"] = {"module_id": module_id}
    return config


async def get_module_or_404(db: AsyncSession, module_id: int, project_id: int) -> Module:
    module = await db.get(Module, module_id)
    if module is None or module.project_id != project_id:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="模块不存在或不属于该项目")
    return module


async def build_replay_preview(
    db: AsyncSession,
    draft: AndroidAgentDraft,
    session: AndroidAgentSession,
) -> AgentReplayPreviewResponse:
    """回放前核对：草稿状态、阻断项、用例模块绑定与设备；未确认项不显示就绪。"""
    items: list[AgentReplayPreviewItem] = []

    if draft.status == "blocked" or draft.blocking_issues:
        items.append(
            AgentReplayPreviewItem(
                code="DRAFT_BLOCKED",
                status="fail",
                message=f"草稿存在 {len(draft.blocking_issues or [])} 个阻断项，需人工整理后才能回放",
            )
        )
    else:
        items.append(AgentReplayPreviewItem(code="DRAFT_READY", status="pass", message="草稿无可回放阻断项"))

    modules = (
        (await db.execute(select(Module.id).where(Module.project_id == draft.project_id).limit(1))).scalars().all()
    )
    if modules:
        items.append(
            AgentReplayPreviewItem(
                code="CASE_MODULE_BINDING",
                status="pass",
                message="项目内存在可绑定模块，发起回放时需显式指定 module_id",
            )
        )
    else:
        items.append(
            AgentReplayPreviewItem(
                code="CASE_MODULE_BINDING",
                status="fail",
                message="项目尚未创建模块，回放无法绑定用例归属，请先创建模块",
            )
        )

    if draft.variables:
        items.append(
            AgentReplayPreviewItem(
                code="VARIABLES_REQUIRED",
                status="warn",
                message="回放前需提供变量：" + ", ".join(sorted(draft.variables)),
            )
        )

    if session.device_id is None:
        items.append(
            AgentReplayPreviewItem(
                code="DEVICE_MISSING",
                status="fail",
                message="会话未绑定设备，无法发起独立回放",
            )
        )
    else:
        items.append(
            AgentReplayPreviewItem(
                code="DEVICE_BOUND",
                status="pass",
                message=f"回放设备 ID：{session.device_id}（回放时重新获取租约）",
            )
        )

    snapshot = frozen_snapshot(draft, session)
    return AgentReplayPreviewResponse(
        draft_id=draft.id,
        draft_version=draft.version,
        content_hash=draft.content_hash,
        ready=all(item.status != "fail" for item in items),
        frozen_snapshot=snapshot,
        items=items,
    )


def _replay_out(replay: AndroidAgentReplay) -> AgentReplayResponse:
    return AgentReplayResponse.model_validate(replay)


async def find_replay_by_idempotency(
    db: AsyncSession, draft_id: int, idempotency_key: str
) -> AndroidAgentReplay | None:
    return (
        await db.execute(
            select(AndroidAgentReplay).where(
                AndroidAgentReplay.draft_id == draft_id,
                AndroidAgentReplay.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()


async def start_replay(
    db: AsyncSession,
    *,
    draft: AndroidAgentDraft,
    session: AndroidAgentSession,
    user: User,
    module_id: int,
    idempotency_key: str,
    initial_state_confirmed: bool,
    device_serial: str | None = None,
) -> tuple[AndroidAgentReplay, TestCase, TestRun]:
    """发起独立回放：先查幂等键，再原子创建回放用例与运行记录。"""
    existing = await find_replay_by_idempotency(db, draft.id, idempotency_key)
    if existing is not None:
        case = await db.get(TestCase, existing.case_id) if existing.case_id else None
        run = await db.get(TestRun, existing.run_id) if existing.run_id else None
        if case is None or run is None:
            raise _conflict("回放记录已存在但关联用例或运行丢失，请重新发起")
        return existing, case, run

    if not initial_state_confirmed:
        raise HTTPException(
            # 使用新的常量名，避免 Starlette 弃用告警
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="必须确认初始状态（App 版本、登录状态、页面位置、测试数据）后才能回放",
        )
    if draft.status not in REPLAYABLE_DRAFT_STATUSES or draft.blocking_issues:
        raise _conflict(f"draft_not_replayable: 草稿状态 {draft.status} 存在阻断项，不能发起回放")

    module = await get_module_or_404(db, module_id, draft.project_id)
    snapshot = frozen_snapshot(draft, session)
    config = build_case_config(snapshot, module_id=module.id, device_serial=device_serial)

    replay = AndroidAgentReplay(
        project_id=draft.project_id,
        session_id=session.id,
        draft_id=draft.id,
        draft_version=draft.version,
        content_hash=draft.content_hash,
        idempotency_key=idempotency_key,
        status="queued",
        initial_state_confirmed=True,
        module_id=module.id,
        environment_snapshot=snapshot,
        started_at=_now(),
    )
    db.add(replay)
    await db.flush()

    case = TestCase(
        name=f"[Agent 回放] {session.title} v{draft.version}",
        description=session.goal,
        case_code=f"AGENT-REPLAY-{replay.id}",
        summary=session.expected_outcome[:500],
        case_type=CaseType.android,
        module_id=module.id,
        creator_id=user.id,
        owner_id=user.id,
        config=config,
        preconditions=list(draft.preconditions or []),
        tags=["android-agent-replay"],
        automation_status="auto",
    )
    db.add(case)
    await db.flush()

    run = TestRun(
        case_id=case.id,
        status=RunStatus.pending,
        triggered_by=user.id,
        trace_id=get_trace_id() or None,
    )
    db.add(run)
    await db.flush()

    replay.case_id = case.id
    replay.run_id = run.id
    await db.flush()
    return replay, case, run


def completed_case_steps(snapshot: dict[str, Any], *, auto_approve: bool) -> list[dict[str, Any]]:
    """把快照步骤转换成正式用例步骤；保存时补齐步骤序号。"""
    steps: list[dict[str, Any]] = []
    for index, raw in enumerate(snapshot.get("steps") or []):
        if not isinstance(raw, dict):
            continue
        step = dict(raw)
        step["step_no"] = index + 1
        step.setdefault("status", "converted")
        steps.append(step)
    if not steps:
        raise _conflict("draft_not_replayable: 草稿没有可保存的步骤")
    if not auto_approve:
        for step in steps:
            step.pop("verified", None)
    return steps


async def find_verified_replay(db: AsyncSession, draft: AndroidAgentDraft) -> AndroidAgentReplay | None:
    """当前版本、当前内容哈希下通过的回放；编辑或重新编译后自动失效。"""
    return (
        await db.execute(
            select(AndroidAgentReplay)
            .where(
                AndroidAgentReplay.draft_id == draft.id,
                AndroidAgentReplay.draft_version == draft.version,
                AndroidAgentReplay.content_hash == draft.content_hash,
                AndroidAgentReplay.status.in_(PASSED_REPLAY_STATUSES),
            )
            .order_by(AndroidAgentReplay.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def find_published_case(db: AsyncSession, draft: AndroidAgentDraft) -> TestCase | None:
    if draft.published_case_id is None:
        return None
    return await db.get(TestCase, draft.published_case_id)


def mark_verified(draft: AndroidAgentDraft) -> None:
    """有通过回放时标记验证资格；只是状态提示，不代替回放证据。"""
    if draft.status == "pending_replay":
        draft.status = "verified"


__all__ = [
    "REPLAYABLE_DRAFT_STATUSES",
    "build_case_config",
    "build_replay_preview",
    "completed_case_steps",
    "find_published_case",
    "find_replay_by_idempotency",
    "find_verified_replay",
    "frozen_snapshot",
    "get_module_or_404",
    "mark_verified",
    "start_replay",
]
