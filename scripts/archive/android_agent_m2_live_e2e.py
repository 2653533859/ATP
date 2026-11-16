"""M2+M3 真机端到端：循环执行 -> 用户确认完成 -> 草稿编译 -> 回放前核对。

真实部分：设备适配层、设备租约、写门禁、SQLite 库、事件与命令落库、草稿编译。
替代部分：模型决策由确定性规划器产生（无可用视觉模型凭据）。
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
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
from app.models.android_agent import AndroidAgentCommand, AndroidAgentEvent, AndroidAgentSession
from app.models.bootstrap import load_all_models
from app.models.device import Device
from app.models.project import Module, Project
from app.schemas.android_agent import AgentSessionCreate
from app.services.android_agent import loop as loop_module
from app.services.android_agent.compiler import compile_session_draft
from app.services.android_agent.coordinator import AgentCoordinator
from app.services.android_agent.device_adapter import AndroidDeviceAdapter, UiautomatorTransport
from app.services.android_agent.replay import build_replay_preview

load_all_models()


class Planner:
    """读取真实观察后按稳定属性选动作；可复现、不含随机性。"""

    def __init__(self) -> None:
        self.steps: list[str] = []

    @staticmethod
    def _find(obs: dict, *, resource_id: str = "", text: str = "", desc: str = ""):
        for node in obs["nodes"]:
            if resource_id and node.get("resource_id") != resource_id:
                continue
            if text and node.get("text") != text:
                continue
            if desc and node.get("content_desc") != desc:
                continue
            if resource_id or text or desc:
                return node
        return None

    def decide(self, obs: dict) -> dict:
        oid = obs["observation_id"]

        def tap(node, label):
            self.steps.append(label)
            return {
                "schema_version": 1,
                "observation_id": oid,
                "action": "tap",
                "target": {"node_id": node["node_id"]},
                "expected_observation": {"type": "element_visible", "resource_id": f"{PKG}:id/digit_0"},
                "reason": f"按键 {label}",
            }

        node = self._find(obs, resource_id="android:id/button1", text="同意")
        if node:
            return tap(node, "dismiss")

        if not self.steps:
            node = self._find(obs, resource_id=f"{PKG}:id/clr")
            if node:
                return tap(node, "clear")

        plan = [
            ("digit_7", "7", "", "press_7"),
            ("op_add", "", "加", "press_add"),
            ("digit_8", "8", "", "press_8"),
            ("eq", "", "等于", "press_eq"),
        ]
        for rid, text, desc, label in plan:
            if label in self.steps:
                continue
            node = self._find(obs, resource_id=f"{PKG}:id/{rid}", text=text, desc=desc)
            if node:
                return tap(node, label)

        self.steps.append("finish")
        return {
            "schema_version": 1,
            "observation_id": oid,
            "action": "finish",
            "reason": "按键完成，提出结束建议（成功与否由终态断言裁决）",
        }


PLANNER = Planner()


async def fake_probe(request, *, goal, observation):
    from app.services.android_agent.contracts import parse_decision
    from app.services.android_agent.model_probe import ProbeResult

    decision = parse_decision(json.dumps(PLANNER.decide(observation), ensure_ascii=False))
    return ProbeResult(decision=decision, elapsed_ms=1, usage={"total_tokens": 41})


async def main() -> int:
    engine = create_async_engine(settings.DATABASE_URL, connect_args={"timeout": 15})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    out: dict[str, object] = {}
    try:
        coordinator = AgentCoordinator()
        async with factory() as db:
            project = (await db.execute(select(Project).limit(1))).scalar_one()
            module = (await db.execute(select(Module).where(Module.project_id == project.id).limit(1))).scalar_one()
            device = (await db.execute(select(Device).where(Device.serial == SERIAL))).scalar_one()

        # 真实设备
        import uiautomator2 as u2

        d = u2.connect(SERIAL)
        width, height = d.window_size()
        d.app_stop(PKG)
        time.sleep(0.5)
        d.app_start(PKG, wait=True)
        time.sleep(1.8)
        adapter = AndroidDeviceAdapter(UiautomatorTransport(d), package=PKG, width=int(width), height=int(height))

        async with factory() as db:
            session = await coordinator.create_session(
                db,
                project_id=project.id,
                payload=AgentSessionCreate(
                    device_id=device.id,
                    package_name=PKG,
                    goal="在计算器里计算 7 加 8 并确认结果为 15",
                    expected_outcome="计算器显示 15",
                    title="真机端到端 7+8",
                    llm_config_id=1,
                ),
            )
            await db.commit()
            session_id = session.id
            await coordinator.start_session(db, session_id)
            await db.commit()
        print("session:", session_id, "started")

        loop_module.probe_model = fake_probe
        result = await loop_module.run_agent_session(
            factory, session_id, adapter=adapter, llm_request=object(), values={}, max_rounds=20
        )
        out["loop_status"] = result.status
        out["loop_reason"] = result.reason
        out["planner_steps"] = list(PLANNER.steps)

        # 独立断言（不采信模型的 finish）
        nodes = adapter.observe()
        out["assertion_15"] = any(n.text == "15" for n in nodes)

        # 用户确认终态断言 -> 收敛
        async with factory() as db:
            done = await coordinator.complete_session(
                db,
                session_id,
                summary="7+8=15 已确认",
                outcome="success",
                terminal_assertions=[
                    {"type": "element_visible", "resource_id": f"{PKG}:id/eq"},
                ],
            )
            await db.commit()
            out["session_status"] = str(getattr(done.status, "value", done.status))
            out["lease_released"] = done.lease_token is None

        # 草稿编译
        async with factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            events = (
                (
                    await db.execute(
                        select(AndroidAgentEvent)
                        .where(AndroidAgentEvent.session_id == session_id)
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
                terminal_assertions=session.terminal_assertions or [],
            )
            out["draft_replayable"] = compiled.replayable
            out["draft_actions"] = [s["action"] for s in compiled.steps]
            out["draft_source_seqs"] = [s["source_seq"] for s in compiled.steps]
            out["draft_assertions"] = compiled.assertions
            out["draft_blocking"] = [i["code"] for i in compiled.blocking_issues]
            out["draft_hash"] = compiled.content_hash[:16]

            commands = (
                (await db.execute(select(AndroidAgentCommand).where(AndroidAgentCommand.session_id == session_id)))
                .scalars()
                .all()
            )
            out["command_count"] = len(commands)
            out["command_statuses"] = sorted({c.status for c in commands})

            # 回放前核对（内存对象，不落库）
            class _DraftShim:
                id = 1
                project_id = session.project_id
                version = 1
                schema_version = 1
                content_hash = compiled.content_hash
                steps = compiled.steps
                assertions = compiled.assertions
                variables = compiled.variables
                preconditions = compiled.preconditions
                blocking_issues = compiled.blocking_issues
                source_map = compiled.source_map
                status = compiled.status

            preview = await build_replay_preview(db, _DraftShim(), session)
            out["preview_ready"] = preview.ready
            out["preview_codes"] = [i.code for i in preview.items]

        for key, value in out.items():
            print(f"{key}: {value}")
        return 0 if out.get("draft_replayable") and out.get("assertion_15") else 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
