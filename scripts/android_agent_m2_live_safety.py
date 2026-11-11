"""M2/M3 真机安全性与草稿链路：设备互斥、写门禁、用户确认完成、草稿编译。"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, "backend")

REPO = Path(".").resolve()
DST_DIR = REPO / ".local-run" / "android-agent-m2-live-20261111" / "data"
SERIAL = "b01ac8cb"
PKG = "com.android.calculator2"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


env = load_env(REPO / ".env")
for key in ("APP_SECRET_KEY", "FIRST_ADMIN_PASSWORD", "FIRST_ADMIN_USERNAME", "FIRST_ADMIN_EMAIL", "ENCRYPTION_KEY"):
    if key in env:
        os.environ[key] = env[key]
os.environ["APP_ENV"] = "local"
os.environ["ATP_LOCAL_MODE"] = "true"
os.environ["ATP_LOCAL_DATA_DIR"] = str(DST_DIR)
os.environ["ADB_SCAN_ENABLED"] = "false"
os.environ["LOCAL_DEVICE_MONITOR_ENABLED"] = "false"

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.android_agent import AndroidAgentEvent, AndroidAgentSession
from app.models.bootstrap import load_all_models
from app.models.device import Device
from app.models.project import Module, Project
from app.schemas.android_agent import AgentManualActionRequest, AgentSessionCreate
from app.services.android_agent.compiler import compile_session_draft
from app.services.android_agent.coordinator import (
    AgentCoordinator,
    DeviceLeaseUnavailableError,
    UnauthorizedControllerError,
)

load_all_models()


async def main() -> int:
    engine = create_async_engine(settings.DATABASE_URL, connect_args={"timeout": 15})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    checks: dict[str, object] = {}
    try:
        coordinator = AgentCoordinator()
        async with factory() as db:
            project = (await db.execute(select(Project).limit(1))).scalar_one()
            module = (await db.execute(select(Module).where(Module.project_id == project.id).limit(1))).scalar_one()
            device = (await db.execute(select(Device).where(Device.serial == SERIAL))).scalar_one()
            # 取真正执行过动作的会话，避免选到互斥测试残留的空会话
            prior = (
                await db.execute(
                    select(AndroidAgentSession)
                    .where(
                        AndroidAgentSession.project_id == project.id,
                        AndroidAgentSession.steps_count > 0,
                    )
                    .order_by(AndroidAgentSession.id.desc())
                    .limit(1)
                )
            ).scalar_one()
            # 清理上一次互斥测试留下的空会话
            strays = (
                (
                    await db.execute(
                        select(AndroidAgentSession).where(
                            AndroidAgentSession.project_id == project.id,
                            AndroidAgentSession.steps_count == 0,
                            AndroidAgentSession.status == "created",
                        )
                    )
                )
                .scalars()
                .all()
            )
            for stray in strays:
                await coordinator.cancel_session(db, stray.id, reason="互斥测试残留清理")
            await db.commit()
            prior_id = prior.id
            print("prior session:", prior_id, prior.status, "| steps:", prior.steps_count)

        # 1) 设备互斥：前一会话仍持租约，第二个必须被拒
        async with factory() as db:
            second = await coordinator.create_session(
                db,
                project_id=project.id,
                payload=AgentSessionCreate(
                    device_id=device.id,
                    package_name=PKG,
                    goal="互斥验证",
                    expected_outcome="不应启动",
                    title="租约互斥验证",
                ),
            )
            await db.commit()
            second_id = second.id
        conflict = False
        detail = ""
        async with factory() as db:
            try:
                await coordinator.start_session(db, second_id)
                await db.commit()
            except DeviceLeaseUnavailableError as exc:
                conflict = True
                detail = str(exc)[:90]
                await db.rollback()
        checks["device_busy_rejected"] = conflict
        checks["device_busy_detail"] = detail

        # 2) 写门禁：未接管时禁止人工写
        async with factory() as db:
            rejected = False
            try:
                await coordinator.manual_action(db, prior_id, AgentManualActionRequest(action="back"))
            except UnauthorizedControllerError:
                rejected = True
            checks["write_requires_manual_control"] = rejected
            await db.rollback()

        # 3) 用户确认终态断言后收敛（paused -> completed）
        async with factory() as db:
            done = await coordinator.complete_session(db, prior_id, summary="7+8=15 真机验证通过", outcome="success")
            await db.commit()
            checks["completed_status"] = str(getattr(done.status, "value", done.status))
            checks["lease_released_after_complete"] = done.lease_token is None

        # 4) 草稿编译（现在应可回放）
        async with factory() as db:
            session = await db.get(AndroidAgentSession, prior_id)
            events = (
                (
                    await db.execute(
                        select(AndroidAgentEvent)
                        .where(AndroidAgentEvent.session_id == prior_id)
                        .order_by(AndroidAgentEvent.seq)
                    )
                )
                .scalars()
                .all()
            )
            compiled = compile_session_draft(
                session_id=session.id,
                package_name=session.package_name,
                goal=session.goal,
                expected_outcome=session.expected_outcome,
                events=events,
            )
            checks["draft_replayable"] = compiled.replayable
            checks["draft_actions"] = [s["action"] for s in compiled.steps]
            checks["draft_source_seqs"] = [s["source_seq"] for s in compiled.steps]
            checks["draft_assertions"] = compiled.assertions
            checks["draft_blocking"] = [i["code"] for i in compiled.blocking_issues]
            checks["draft_hash"] = compiled.content_hash[:16]

        for key, value in checks.items():
            print(f"{key}: {value}")
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
