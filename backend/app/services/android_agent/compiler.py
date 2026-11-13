"""轨迹到 Android 低代码草稿的可追溯转换（实施清单 A30/A31）。

编译只读取会话事件，不执行设备操作，也不把模型文本当作可执行代码：

- 每个步骤保留来源事件序号，纠错尝试不会被静默删除；
- 无法证明可自动转换的步骤进入"待人工整理"，并给出阻断项，
  含阻断项的草稿不可回放，也不能继承通过状态；
- 输入参数只保留运行变量引用，不写入敏感明文；
- 终态断言来自用户确认的成功条件，模型 `finish` 不生成操作步骤。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

DRAFT_SCHEMA_VERSION = 1

# 模型动作到低代码步骤动作的映射；wait 直接映射条件等待，不冒充旧能力。
_ACTION_MAP: dict[str, str] = {
    "tap": "click",
    "input": "input",
    "swipe": "swipe",
    "back": "press_key",
    "wait": "wait_until",
    "launch_app": "start_app",
    "start_app": "start_app",
}

_TERMINAL_EVENT_TYPES = {"session_completed", "session_failed", "session_cancelled"}


class DraftCompileError(ValueError):
    """编译失败时只暴露稳定错误码，不泄露事件内容。"""


@dataclass
class CompiledDraft:
    """编译结果；`replayable` 为 False 时 `blocking_issues` 必不为空。"""

    schema_version: int
    steps: list[dict[str, Any]]
    assertions: list[dict[str, Any]]
    variables: list[str]
    preconditions: list[str]
    blocking_issues: list[dict[str, Any]]
    source_map: dict[str, Any]
    content_hash: str = ""

    @property
    def replayable(self) -> bool:
        return not self.blocking_issues

    @property
    def status(self) -> str:
        return "replayable" if self.replayable else "blocked"


def _issue(code: str, message: str, *, source_seq: int | None = None, step_index: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if source_seq is not None:
        payload["source_seq"] = source_seq
    if step_index is not None:
        payload["step_index"] = step_index
    return payload


def _normalize_expected(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    expected_type = raw.get("type")
    resource_id = raw.get("resource_id")
    if (
        expected_type not in ("element_visible", "element_absent")
        or not isinstance(resource_id, str)
        or not resource_id
    ):
        return None
    return {"type": expected_type, "resource_id": resource_id}


def _node_params(node: Any) -> dict[str, Any]:
    if not isinstance(node, Mapping):
        return {}
    params: dict[str, Any] = {}
    resource_id = node.get("resource_id")
    text = node.get("text")
    desc = node.get("content_desc")
    if isinstance(resource_id, str) and resource_id:
        params["resource_id"] = resource_id
    if isinstance(text, str) and text:
        params["locator"] = {"text": text, "strategy": "text_exact"}
    elif isinstance(desc, str) and desc:
        # 真机图标按钮常只有 content-desc，草稿需要保留这个稳定属性
        params["locator"] = {"content_desc": desc, "strategy": "desc_exact"}
    return params


def _compile_step(payload: Mapping[str, Any], *, step_index: int) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """单步转换；返回 (步骤, 该步骤的阻断项)。"""
    source_seq = payload.get("source_seq")
    raw_action = str(payload.get("action") or "").strip().lower()
    action = _ACTION_MAP.get(raw_action)
    issues: list[dict[str, Any]] = []
    if action is None:
        # 未知动作（如 request_help / finish）不生成步骤，进入待人工整理
        return None, [
            _issue(
                "step_needs_manual_review",
                f"动作 {raw_action or '<empty>'} 无法自动转换为低代码步骤",
                source_seq=source_seq if isinstance(source_seq, int) else None,
                step_index=step_index,
            )
        ]

    params: dict[str, Any] = {}
    if action == "start_app":
        package_name = (
            (payload.get("params") or {}).get("package_name") if isinstance(payload.get("params"), Mapping) else None
        )
        if not isinstance(package_name, str) or not package_name:
            issues.append(
                _issue("step_missing_field", "启动应用步骤缺少包名", source_seq=source_seq, step_index=step_index)
            )
        else:
            params["package_name"] = package_name
    elif action in ("click", "input"):
        node_params = _node_params(payload.get("node"))
        if not node_params:
            issues.append(
                _issue(
                    "step_unstable_locator",
                    "目标缺少稳定 resource_id / 完整文本，不能生成可回放步骤",
                    source_seq=source_seq,
                    step_index=step_index,
                )
            )
        params.update(node_params)
        if action == "input":
            value_ref = (
                (payload.get("params") or {}).get("value_ref") if isinstance(payload.get("params"), Mapping) else None
            )
            if not isinstance(value_ref, str) or not value_ref.isidentifier():
                issues.append(
                    _issue(
                        "step_unsafe_input",
                        "输入步骤缺少合法变量引用，禁止写入明文",
                        source_seq=source_seq,
                        step_index=step_index,
                    )
                )
            else:
                params["value"] = "${" + value_ref + "}"
                params["value_ref"] = value_ref
    elif action == "swipe":
        raw_mapping = payload.get("params")
        raw_params: Mapping[str, Any] = raw_mapping if isinstance(raw_mapping, Mapping) else {}
        direction = raw_params.get("direction")
        if direction not in ("up", "down", "left", "right"):
            issues.append(
                _issue("step_missing_field", "滑动步骤缺少合法方向", source_seq=source_seq, step_index=step_index)
            )
        else:
            params["direction"] = direction
            fraction = raw_params.get("distance_fraction") or raw_params.get("distance")
            if isinstance(fraction, (int, float)) and 0 < float(fraction) <= 0.8:
                params["distance_fraction"] = float(fraction)
    elif action == "press_key":
        params["key"] = "back"
    elif action == "wait_until":
        timeout_ms = (
            (payload.get("params") or {}).get("timeout_ms") if isinstance(payload.get("params"), Mapping) else None
        )
        params["timeout_ms"] = int(timeout_ms) if isinstance(timeout_ms, int) and 100 <= timeout_ms <= 15000 else 15000

    step: dict[str, Any] = {"action": action, "params": params, "source_seq": source_seq, "status": "converted"}
    if issues:
        step["status"] = "needs_manual_review"
        step["needs_manual_review"] = True
    return step, issues


def _content_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def compile_session_draft(
    *,
    session_id: int,
    package_name: str,
    goal: str,
    expected_outcome: str,
    events: Iterable[Any],
    terminal_assertions: Iterable[Mapping[str, Any]] | None = None,
    restored_initial_state: bool = True,
) -> CompiledDraft:
    """把一个会话的事件序列编译成草稿版本（纯函数，可重复执行得到同一哈希）。"""
    ordered = sorted(events, key=lambda event: int(getattr(event, "seq", 0)))
    issues: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    assertions: list[dict[str, Any]] = []
    variables: list[str] = []
    source_events: list[dict[str, Any]] = []
    terminal_type: str | None = None
    finish_expected: dict[str, Any] | None = None

    if not ordered:
        issues.append(_issue("empty_trajectory", "会话没有任何事件，无法生成草稿"))

    for event in ordered:
        event_type = str(getattr(event, "event_type", ""))
        payload: Mapping[str, Any] = getattr(event, "payload", None) or {}
        if event_type in _TERMINAL_EVENT_TYPES:
            terminal_type = event_type
            continue
        if event_type != "step_executed":
            continue

        seq = int(getattr(event, "seq", 0))
        action_name = str(payload.get("action") or "").lower()
        if payload.get("controller") == "manual" and action_name == "wait":
            issues.append(_issue("step_needs_manual_review", "人工固定等待需要整理为可验证的条件等待", source_seq=seq))
        source_events.append({"seq": seq, "action": payload.get("action")})

        # 终止建议轮（finish / request_help）不执行设备动作，action_status 记为
        # not_executed 是正常的，不能据此判成失败步骤
        if action_name in ("finish", "request_help"):
            if action_name == "finish":
                finish_expected = _normalize_expected(payload.get("expected"))
            continue

        action_status = str(payload.get("action_status") or payload.get("status") or "succeeded")
        if action_status not in ("succeeded", "acted"):
            issues.append(
                _issue("step_failed", f"步骤执行结果为 {action_status}", source_seq=seq, step_index=len(steps))
            )

        step, step_issues = _compile_step({**dict(payload), "source_seq": seq}, step_index=len(steps))
        issues.extend(step_issues)
        if step is not None:
            if "value_ref" in step["params"] and step["params"]["value_ref"] not in variables:
                variables.append(step["params"]["value_ref"])
            steps.append(step)

    if terminal_type in (None, "session_failed", "session_cancelled"):
        issues.append(
            _issue(
                "session_not_completed",
                "会话未以成功状态结束，草稿不能继承通过状态",
            )
        )

    # 终态断言只认用户确认的成功条件：模型提出的 finish 仅是建议，不能当通过依据
    for raw in terminal_assertions or []:
        normalized = _normalize_expected(raw)
        if normalized is not None:
            assertions.append(normalized)
    if not assertions and finish_expected is not None:
        # 兼容旧轨迹：没有任何用户确认时，退回轨迹里记录的建议值并明确标注
        assertions.append(finish_expected)
        issues.append(
            _issue(
                "assertion_not_user_confirmed",
                "终态断言取自轨迹建议值，未经用户确认，回放通过不计为验证",
            )
        )
    if not assertions:
        issues.append(_issue("missing_final_assertion", "缺少用户确认的终态断言，不能自动回放"))

    # 无条件：启动应用固定为第一步，由任务配置决定，不由模型选择
    launch_step = {
        "action": "start_app",
        "params": {"package_name": package_name},
        "source_seq": None,
        "status": "injected",
    }
    if any(step["action"] == "start_app" for step in steps):
        steps = [step for step in steps if step["action"] != "start_app"]
    steps.insert(0, launch_step)

    preconditions = [
        f"目标 App 已安装：{package_name}",
        f"用户确认的成功条件：{expected_outcome}",
    ]
    if not restored_initial_state:
        issues.append(_issue("initial_state_unconfirmed", "未确认初始状态，回放结果不可作为验证"))

    body = {
        "schema_version": DRAFT_SCHEMA_VERSION,
        "session_id": session_id,
        "package_name": package_name,
        "goal": goal,
        "expected_outcome": expected_outcome,
        "steps": steps,
        "assertions": assertions,
        "variables": variables,
        "preconditions": preconditions,
        "blocking_issues": issues,
        "source_events": source_events,
    }
    return CompiledDraft(
        schema_version=DRAFT_SCHEMA_VERSION,
        steps=steps,
        assertions=assertions,
        variables=variables,
        preconditions=preconditions,
        blocking_issues=issues,
        source_map={"session_id": session_id, "events": source_events},
        content_hash=_content_hash(body),
    )
