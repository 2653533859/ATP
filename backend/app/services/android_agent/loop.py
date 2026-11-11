"""持久协调器驱动的模型循环（实施清单 A21/A22）。

每轮严格按"读状态与预算 → 取观察 → 请求模型 → 校验动作 → 再查代次与租约 →
串行执行 → 采集后状态 → 独立验证 → 事务写事件"执行，并且：

- 不持有数据库事务等待模型或 ADB；
- 每次写入前同步复核租约、控制代次与取消标志（`DeviceControlGate`）；
- 未知执行结果（`*_outcome_unknown`）只标记待核查，绝不重发；
- 后端重启后非终态会话由 `recover_orphaned_sessions` 收敛，不自动继续设备操作。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import asyncio
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.tracing import get_trace_id
from app.models.android_agent import AndroidAgentCommand, AndroidAgentSession
from app.schemas.android_agent import AgentErrorCode, AgentSessionStatus
from app.services.ai_case.llm_client import LLMRequest
from app.services.android_agent.contracts import (
    Back,
    Decision,
    DecisionRejected,
    Finish,
    Input,
    RequestHelp,
    Swipe,
    Tap,
    Wait,
    validate_context,
)
from app.services.android_agent.control import ControlRejected, ControlState, DeviceControlGate
from app.services.android_agent.coordinator import AgentCoordinator, InvalidStateTransitionError
from app.services.android_agent.device_adapter import AndroidDeviceAdapter, DeviceAdapterError, UiTarget
from app.services.android_agent.model_probe import probe_model
from app.services.android_agent.observation import ObservationRejected

# 未知结果：设备可能已经执行，只允许标记待核查，不允许重发
UNKNOWN_OUTCOME_CODES = frozenset(
    {
        "write_outcome_unknown",
        "input_outcome_unknown",
        "device_unavailable",
        "control_check_timeout",
    }
)
# 暂停类终止：保留有效租约等待人工恢复；其余终止释放租约
PAUSING_REASONS = frozenset(
    {
        "finish_proposed",
        "target_ambiguous",
        "sensitive_page",
        "unsupported_page",
        "cannot_progress",
        "observation_unavailable",
        "num_actions_limit",
    }
)
_ACTION_TIMEOUT_SECONDS = 120


class AgentLoopError(RuntimeError):
    """循环前置条件不满足时只暴露稳定错误码。"""


def stable_code(error: object) -> str:
    """把适配层/校验层的错误收敛成稳定错误码，不泄露输入内容。"""
    text = str(error)
    code = text.split(":", 1)[0].strip()
    return code or "agent_loop_error"


async def _record_model_usage(
    session_factory: Any,
    session_id: int,
    *,
    coordinator: AgentCoordinator,
    observation_id: str,
    model_calls: int,
    tokens: int,
    outcome: str,
) -> None:
    """未执行设备动作的终止轮次也要记账，否则用量与成本报告会偏低。"""
    async with session_factory() as db:
        await coordinator.record_step_progress(
            db,
            session_id,
            model_calls=model_calls,
            tokens=tokens,
            actions=0,
            event_payload={
                "observation_id": observation_id,
                "action": outcome,
                "action_status": "not_executed",
            },
        )
        await db.commit()


class LoopAdapter(Protocol):
    package: str

    def observe(self, *, attempts: int = 3) -> list[Any]: ...

    def tap(self, target: UiTarget, *, assert_write_allowed: Any) -> None: ...

    def replace_text(self, resource_id: str, value: str, *, assert_write_allowed: Any) -> None: ...

    def press_back(self, *, assert_write_allowed: Any) -> None: ...

    def swipe(self, direction: str, distance_fraction: float, *, assert_write_allowed: Any) -> None: ...

    def wait_for(self, target: UiTarget, *, timeout_ms: int, absent: bool = False) -> list[Any]: ...


def _normalize_status(value: Any) -> str:
    """SQLAlchemy 枚举列可能返回枚举成员，统一按字符串比较。"""
    return str(getattr(value, "value", value))


def _target_node(decision: Decision, by_id: dict[str, Any]) -> Any:
    target = getattr(decision, "target", None)
    node_id = getattr(target, "node_id", None)
    return by_id.get(node_id) if node_id else None


@dataclass
class LoopResult:
    status: str  # needs_review | halted | completed
    reason: str
    steps: int = 0
    model_calls: int = 0
    tokens: int = 0
    last_observation_id: str | None = None
    events: list[int] = field(default_factory=list)


def _target_for(node: Any) -> UiTarget:
    """文本只在完整且可辨识时进入选择器，绝不使用坐标兜底。"""
    text = node.text if getattr(node, "text", "") and not getattr(node, "text_truncated", False) else ""
    return UiTarget(getattr(node, "resource_id", ""), text)


def _budget_exhausted(session: AndroidAgentSession) -> bool:
    """只按已落库用量判断，避免把"本轮还没执行的动作"提前算进额度。

    计数随 `record_step_progress` 与状态同事务提交，这里读到的就是权威值。
    """
    return session.steps_count >= session.budget_max_steps or session.model_calls_count >= session.budget_max_calls


def _wait_budget(decision: Wait) -> int:
    return int(getattr(decision, "timeout_ms", 15000))


def _expectation_timeout(decision: Decision) -> int:
    return _wait_budget(decision) if isinstance(decision, Wait) else 15000


async def _check_expectation(adapter: LoopAdapter, decision: Decision) -> None:
    expected = getattr(decision, "expected_observation", None)
    if expected is None:
        return
    target = UiTarget(resource_id=expected.resource_id)
    await asyncio.to_thread(
        adapter.wait_for,
        target,
        timeout_ms=_expectation_timeout(decision),
        absent=getattr(expected, "type", "") == "element_absent",
    )


async def _dispatch_action(
    adapter: LoopAdapter,
    decision: Decision,
    by_id: dict[str, Any],
    values: dict[str, str],
    allow: Any,
) -> None:
    if isinstance(decision, Tap):
        await asyncio.to_thread(adapter.tap, _target_for(by_id[decision.target.node_id]), assert_write_allowed=allow)
    elif isinstance(decision, Input):
        await asyncio.to_thread(
            adapter.replace_text,
            by_id[decision.target.node_id].resource_id,
            values[decision.value_ref],
            assert_write_allowed=allow,
        )
    elif isinstance(decision, Swipe):
        await asyncio.to_thread(
            adapter.swipe, decision.direction, decision.distance_fraction, assert_write_allowed=allow
        )
    elif isinstance(decision, Back):
        await asyncio.to_thread(adapter.press_back, assert_write_allowed=allow)


def _action_name(decision: Decision) -> str:
    return str(getattr(decision, "action", "unknown"))


def _command_params(decision: Decision, by_id: dict[str, Any], values: dict[str, str]) -> dict[str, Any]:
    node = None
    target = getattr(decision, "target", None)
    if target is not None:
        node = by_id.get(target.node_id)
    params: dict[str, Any] = {
        "reason": decision.reason,
        "observation_id": decision.observation_id,
    }
    if node is not None:
        params["resource_id"] = node.resource_id
    if isinstance(decision, Input):
        # 只记录变量引用，不落库明文
        params["value_ref"] = decision.value_ref
        params["has_value"] = bool(values.get(decision.value_ref))
    if isinstance(decision, Swipe):
        params["direction"] = decision.direction
        params["distance_fraction"] = decision.distance_fraction
    return params


class _SessionScopedGate(DeviceControlGate):
    """在门禁里额外核对会话当前控制代次，避免只依赖进程内状态。"""

    def __init__(self, session_factory: Any, *, session_id: int, **kwargs: Any):
        super().__init__(session_factory, **kwargs)
        self.session_id = session_id

    async def check(self, captured_epoch: int) -> None:
        await super().check(captured_epoch)
        async with self.session_factory() as db:
            session = await db.get(AndroidAgentSession, self.session_id)
            if session is None:
                raise ControlRejected("session_missing")
            if _normalize_status(session.status) != AgentSessionStatus.running.value:
                raise ControlRejected("write_cancelled")
            if session.control_epoch != captured_epoch:
                raise ControlRejected("control_epoch_changed")
            if session.controller != "agent":
                raise ControlRejected("manual_control_active")


async def _finish(
    code: str, session_id: int, factory: Any, coordinator: AgentCoordinator, result: LoopResult
) -> LoopResult:
    """按语义收敛会话：暂停保留租约等待人工恢复，其余终止释放租约。"""
    async with factory() as db:
        if code in PAUSING_REASONS:
            try:
                await coordinator.control_session(db, session_id, "pause", reason=code)
            except InvalidStateTransitionError:
                pass
        else:
            await coordinator.fail_session(db, session_id, error_code=code, reason=code)
        await db.commit()
    return result


async def run_agent_session(
    session_factory: sessionmaker | Any,
    session_id: int,
    *,
    adapter: LoopAdapter,
    llm_request: LLMRequest | None,
    values: dict[str, str] | None = None,
    max_rounds: int = 30,
) -> LoopResult:
    """驱动一次 Agent 会话直到收敛；返回稳定状态而不是抛业务异常。

    `max_rounds` 只是单次调用的安全上限（默认等于默认步数预算），真正的额度
    由会话的 `budget_max_steps`/`budget_max_calls` 决定。
    """
    coordinator = AgentCoordinator()
    values = values or {}
    result = LoopResult(status="halted", reason="not_started")

    async with session_factory() as db:
        session = await db.get(AndroidAgentSession, session_id)
        if session is None:
            raise AgentLoopError("session_not_found")
        if session.status != AgentSessionStatus.running.value:
            raise AgentLoopError("session_not_running")
        if session.device_id is None or not session.lease_token:
            raise AgentLoopError("lease_missing")
        device_id = session.device_id
        lease_token = session.lease_token
        captured_epoch = session.control_epoch
        package = session.package_name
        goal = session.goal

    # DeviceControlGate 依赖 ControlState；循环用同构的轻量状态表达"进程内无取消"，
    # 真正的权威代次来自数据库里的会话行
    gate = _SessionScopedGate(
        session_factory,
        session_id=session_id,
        device_id=device_id,
        lease_token=lease_token,
        state=_LoopControlState(captured_epoch),
    )

    local_steps = 0
    for _ in range(max_rounds):
        async with session_factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            if session is None:
                raise AgentLoopError("session_not_found")
            current_status = _normalize_status(session.status)
            if current_status != AgentSessionStatus.running.value:
                result.steps = session.steps_count
                result.model_calls = session.model_calls_count
                result.tokens = session.total_tokens
                result.status = "halted"
                result.reason = f"session_{current_status}"
                return result
            result.steps = session.steps_count
            result.model_calls = session.model_calls_count
            result.tokens = session.total_tokens
            if _budget_exhausted(session):
                result.status = "halted"
                result.reason = AgentErrorCode.budget_exceeded.value
                return await _finish(result.reason, session_id, session_factory, coordinator, result)
            epoch = session.control_epoch

        try:
            nodes = await asyncio.to_thread(adapter.observe)
        except (DeviceAdapterError, ObservationRejected) as exc:
            # 观察失败不消耗模型额度，也不重发任何设备动作
            code = stable_code(exc)
            return await _finish(code, session_id, session_factory, coordinator, LoopResult("needs_review", code))

        observation_id = f"obs-{session_id}-{local_steps + 1}-{len(nodes)}-{epoch}"
        observation = {
            "observation_id": observation_id,
            "package_name": package,
            "allowed_value_refs": sorted(values),
            "nodes": [
                {
                    "node_id": node.node_id,
                    "resource_id": node.resource_id,
                    "text": node.text,
                    "content_desc": node.content_desc,
                    "class_name": node.class_name,
                    "bounds": list(node.bounds) if node.bounds else None,
                    "enabled": node.enabled,
                    "clickable": node.clickable,
                }
                for node in nodes
                if not node.redacted
            ],
        }

        decision_calls = 1
        if llm_request is None:
            raise AgentLoopError("llm_request_required")
        try:
            probe = await probe_model(llm_request, goal=goal, observation=observation)
        except DecisionRejected as exc:
            # 模型超时/协议错误同样要记账，否则成本统计会漏掉失败请求
            reason = stable_code(exc)
            await _record_model_usage(
                session_factory,
                session_id,
                coordinator=coordinator,
                observation_id=observation_id,
                model_calls=decision_calls,
                tokens=0,
                outcome="model_rejected",
            )
            return await _finish(
                reason,
                session_id,
                session_factory,
                coordinator,
                LoopResult("needs_review", reason, model_calls=decision_calls),
            )

        decision = probe.decision
        decision = _with_observation_id(decision, observation_id)
        tokens = int(probe.usage.get("total_tokens", 0))

        by_id = {node.node_id: node for node in nodes}
        try:
            validate_context(
                decision,
                observation_id=observation_id,
                observed_package=package,
                allowed_package=package,
                captured_epoch=epoch,
                current_epoch=epoch,
                controllable_node_ids={
                    node.node_id for node in nodes if node.enabled and node.bounds and not node.redacted
                },
                allowed_value_refs=set(values),
                device_online=True,
                observation_available=True,
            )
        except DecisionRejected as exc:
            reason = stable_code(exc)
            await _record_model_usage(
                session_factory,
                session_id,
                coordinator=coordinator,
                observation_id=observation_id,
                model_calls=decision_calls,
                tokens=tokens,
                outcome="decision_rejected",
            )
            return await _finish(
                reason,
                session_id,
                session_factory,
                coordinator,
                LoopResult("halted", reason, model_calls=decision_calls, tokens=tokens),
            )

        if isinstance(decision, (Finish, RequestHelp)):
            reason = "finish_proposed" if isinstance(decision, Finish) else stable_code(decision.code)
            await _record_model_usage(
                session_factory,
                session_id,
                coordinator=coordinator,
                observation_id=observation_id,
                model_calls=decision_calls,
                tokens=tokens,
                outcome=_action_name(decision),
            )
            return await _finish(
                reason,
                session_id,
                session_factory,
                coordinator,
                LoopResult(
                    "needs_review",
                    reason,
                    model_calls=decision_calls,
                    tokens=tokens,
                    last_observation_id=observation_id,
                ),
            )

        command_id = await _record_command(
            session_factory,
            session_id=session_id,
            epoch=epoch,
            observation_id=observation_id,
            decision=decision,
            params=_command_params(decision, by_id, values),
        )

        allow = gate.sync_check(epoch, asyncio.get_running_loop())
        try:
            await _dispatch_action(adapter, decision, by_id, values, allow)
            await _check_expectation(adapter, decision)
            action_status, error_code = "succeeded", None
        except ControlRejected as exc:
            await _mark_command(session_factory, command_id, status="cancelled", error_message=stable_code(exc))
            reason = stable_code(exc)
            return await _finish(reason, session_id, session_factory, coordinator, LoopResult("halted", reason))
        except (asyncio.TimeoutError, TimeoutError):
            action_status, error_code = "outcome_unknown", "control_check_timeout"
        except DeviceAdapterError as exc:
            code = stable_code(exc)
            action_status = "outcome_unknown" if code in UNKNOWN_OUTCOME_CODES else "failed"
            error_code = code
        except Exception:
            action_status, error_code = "outcome_unknown", "unexpected_adapter_error"

        await _mark_command(session_factory, command_id, status=action_status, error_message=error_code)

        async with session_factory() as db:
            event = await coordinator.record_step_progress(
                db,
                session_id,
                model_calls=decision_calls,
                tokens=tokens,
                actions=1 if action_status == "succeeded" else 0,
                event_payload={
                    "observation_id": observation_id,
                    "action": _action_name(decision),
                    "action_status": action_status,
                    "control_epoch": epoch,
                    "command_id": command_id,
                    "node": {"resource_id": (getattr(_target_node(decision, by_id), "resource_id", "") or "")},
                    "params": _command_params(decision, by_id, values),
                    "expected": _expected_payload(decision),
                    "error_code": error_code,
                },
            )
            result.events.append(event.id)
            await db.commit()
            session = await db.get(AndroidAgentSession, session_id)
            if session is not None and _normalize_status(session.status) == AgentSessionStatus.failed.value:
                result.status = "halted"
                result.reason = session.error_code or "budget_exceeded"
                result.steps = session.steps_count
                result.model_calls = session.model_calls_count
                result.tokens = session.total_tokens
                return result

        local_steps += 1
        result.steps = local_steps
        result.model_calls += decision_calls
        result.tokens += tokens
        result.last_observation_id = observation_id
        if action_status != "succeeded":
            reason = error_code or "action_failed"
            status = "needs_review" if action_status == "outcome_unknown" else "halted"
            return await _finish(reason, session_id, session_factory, coordinator, LoopResult(status, reason))

    return await _finish(
        "num_actions_limit", session_id, session_factory, coordinator, LoopResult("needs_review", "num_actions_limit")
    )


class _LoopControlState(ControlState):
    """与 `ControlState` 同构：进程内暂停/取消都会推进代次，代次变化即作废旧决策。"""

    def __init__(self, epoch: int):
        super().__init__(epoch=epoch)


def _with_observation_id(decision: Decision, observation_id: str) -> Decision:
    """模型返回的 observation_id 只作参考，服务端始终回填本次观察的真实编号。"""
    try:
        return decision.model_copy(update={"observation_id": observation_id})  # type: ignore[attr-defined]
    except Exception:
        return decision


def _expected_payload(decision: Decision) -> dict[str, Any]:
    expected = getattr(decision, "expected_observation", None)
    if expected is None:
        return {}
    return {"type": expected.type, "resource_id": expected.resource_id}


async def _record_command(
    session_factory: Any,
    *,
    session_id: int,
    epoch: int,
    observation_id: str,
    decision: Decision,
    params: dict[str, Any],
) -> int:
    import secrets

    from sqlalchemy import func

    async with session_factory() as db:
        max_seq = (
            await db.execute(
                select(func.coalesce(func.max(AndroidAgentCommand.seq), 0)).where(
                    AndroidAgentCommand.session_id == session_id
                )
            )
        ).scalar_one()
        command = AndroidAgentCommand(
            session_id=session_id,
            seq=int(max_seq) + 1,
            control_epoch=epoch,
            observation_id=observation_id,
            idempotency_key=f"agent:{session_id}:{epoch}:{int(max_seq) + 1}:{secrets.token_hex(4)}",
            action=_action_name(decision),
            status="prepared",
            params=params,
        )
        db.add(command)
        await db.commit()
        return command.id


async def _mark_command(session_factory: Any, command_id: int, *, status: str, error_message: str | None) -> None:
    async with session_factory() as db:
        command = await db.get(AndroidAgentCommand, command_id)
        if command is None:
            return
        command.status = status
        command.error_message = (error_message or "")[:256] or None
        await db.commit()
