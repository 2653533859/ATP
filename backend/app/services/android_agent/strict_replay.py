"""严格回放步骤：供正式 Android 低代码执行器在 ``strict_replay`` 模式下使用。

与旧路径的区别：
- 所有定位都按 UI 树属性精确相等匹配，目标必须唯一，没有坐标兜底；
- 写操作在发送前调用 ``assert_write_allowed``（取消、租约由调用方实现），
  发送后的任何异常都视为结果未知，不重发；
- 断言与条件等待基于结构化节点，空预期直接拒绝。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.services.android_agent.device_adapter import AndroidDeviceAdapter, DeviceAdapterError
from app.services.android_agent.observation import UiNode

# 严格模式下由本模块接管的动作；其余动作仍走执行器原有 ADB 路径。
STRICT_ACTIONS = frozenset({"click", "input", "wait_until", "assert_element", "assert_text"})
# 严格模式允许继续使用旧路径的动作：没有定位目标，或只读。
STRICT_PASSTHROUGH_ACTIONS = frozenset({"press_key", "start_app", "stop_app", "wait", "screenshot", "swipe"})

MAX_SELECTOR_VALUE = 512
WAIT_TIMEOUT_MS_RANGE = (100, 60000)
WAIT_INTERVAL_MS_RANGE = (200, 5000)

_SELECTOR_FIELDS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    # (节点属性, 参数别名, uiautomator2 选择器键, 报告标签)
    ("resource_id", ("resourceId", "resource_id"), "resourceId", "resourceId"),
    ("text", ("text",), "text", "text"),
    ("class_name", ("className", "class_name"), "className", "className"),
    ("content_desc", ("contentDesc", "content_desc"), "description", "contentDesc"),
)

# 与执行器统一的错误文案；只含稳定原因和选择器描述，不回显输入值。
_MESSAGES = {
    "selector_missing": "缺少定位条件（resourceId/text/className/contentDesc 至少一项）",
    "selector_invalid": "定位条件格式无效",
    "target_not_found": "未找到匹配控件",
    "target_not_unique": "匹配到多个控件，目标不唯一",
    "target_not_interactable": "控件不可用或不在屏幕内",
    "target_not_clickable": "控件及其父节点均不可点击",
    "selector_count_changed": "执行前复核时控件数量发生变化",
    "click_outcome_unknown": "点击已发送但结果未确认，不会自动重试",
    "input_target_required": "严格回放的输入步骤必须指定 resourceId",
    "input_value_invalid": "输入内容无效",
    "input_value_unresolved": "输入内容包含未解析的变量",
    "condition_invalid": "等待条件无效（仅支持 visible/absent）",
    "timeout_invalid": "等待超时必须在 100–60000 毫秒之间",
    "interval_invalid": "轮询间隔必须在 200–5000 毫秒之间",
    "expect_invalid": "断言期望无效（仅支持 present/absent）",
    "count_invalid": "匹配数量必须是非负整数",
    "wait_timeout": "条件等待超时",
    "assert_failed": "断言未通过",
    "assert_text_missing": "文本断言缺少预期文本",
    "unsupported_action": "严格回放不支持该步骤类型",
}


class StrictStepError(Exception):
    def __init__(self, code: str, detail: str | None = None):
        self.code = code
        message = _MESSAGES.get(code, code)
        self.message = f"{message}：{detail}" if detail else message
        super().__init__(self.message)


@dataclass(frozen=True)
class NodeSelector:
    resource_id: str | None = None
    text: str | None = None
    class_name: str | None = None
    content_desc: str | None = None

    def matches(self, node: UiNode) -> bool:
        return all(
            expected is None or getattr(node, attr) == expected
            for attr, expected in (
                ("resource_id", self.resource_id),
                ("text", self.text),
                ("class_name", self.class_name),
                ("content_desc", self.content_desc),
            )
        )

    def u2_fields(self) -> dict[str, str]:
        fields: dict[str, str] = {}
        for attr, _aliases, u2_key, _label in _SELECTOR_FIELDS:
            value = getattr(self, attr)
            if value is not None:
                fields[u2_key] = value
        return fields

    def describe(self) -> str:
        parts = []
        for attr, _aliases, _u2_key, label in _SELECTOR_FIELDS:
            value = getattr(self, attr)
            if value is not None:
                parts.append(f"{label}={value}")
        return ", ".join(parts)


def parse_selector(params: dict[str, Any], *, include_text: bool = True) -> NodeSelector:
    """按精确值解析选择器；空字符串视为未填写，至少需要一项。"""
    values: dict[str, str] = {}
    for attr, aliases, _u2_key, _label in _SELECTOR_FIELDS:
        if attr == "text" and not include_text:
            continue
        raw = next((params[key] for key in aliases if params.get(key) not in (None, "")), None)
        if raw is None:
            continue
        if not isinstance(raw, str) or len(raw) > MAX_SELECTOR_VALUE:
            raise StrictStepError("selector_invalid")
        if not raw.strip():
            continue
        values[attr] = raw
    if not values:
        raise StrictStepError("selector_missing")
    return NodeSelector(**values)


def _int_param(params: dict[str, Any], key: str, default: int, bounds: tuple[int, int], code: str) -> int:
    raw = params.get(key, default)
    if raw in (None, ""):
        raw = default
    if isinstance(raw, bool):
        raise StrictStepError(code)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise StrictStepError(code) from None
    if value != raw and not (isinstance(raw, str) and raw.strip() == str(value)):
        raise StrictStepError(code)
    if not bounds[0] <= value <= bounds[1]:
        raise StrictStepError(code)
    return value


def _optional_count(params: dict[str, Any], key: str) -> int | None:
    raw = params.get(key)
    if raw in (None, ""):
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise StrictStepError("count_invalid")
    return raw


def validate_strict_step(action: str, params: dict[str, Any]) -> None:
    """无设备的参数校验，供执行前预检与执行器复用。"""
    if action in STRICT_PASSTHROUGH_ACTIONS:
        return
    if action not in STRICT_ACTIONS:
        raise StrictStepError("unsupported_action", action or "-")
    if action == "click":
        parse_selector(params)
    elif action == "input":
        resource_id = params.get("resourceId") or params.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id.strip():
            raise StrictStepError("input_target_required")
        value = params.get("text", params.get("value", ""))
        if not isinstance(value, str) or len(value) > MAX_SELECTOR_VALUE:
            raise StrictStepError("input_value_invalid")
    elif action == "wait_until":
        parse_selector(params)
        if str(params.get("condition") or "visible") not in {"visible", "absent"}:
            raise StrictStepError("condition_invalid")
        _int_param(params, "timeout_ms", 10000, WAIT_TIMEOUT_MS_RANGE, "timeout_invalid")
        _int_param(params, "interval_ms", 500, WAIT_INTERVAL_MS_RANGE, "interval_invalid")
    elif action == "assert_element":
        parse_selector(params)
        if str(params.get("expect") or "present") not in {"present", "absent"}:
            raise StrictStepError("expect_invalid")
        _optional_count(params, "count")
        _optional_count(params, "min_count")
    elif action == "assert_text":
        text = params.get("text")
        if not isinstance(text, str) or not text.strip():
            raise StrictStepError("assert_text_missing")


class StrictReplayEngine:
    """在已持有设备租约的前提下执行严格步骤；单个实例只服务一个运行。"""

    def __init__(
        self,
        adapter: AndroidDeviceAdapter,
        *,
        build_selector: Callable[[dict[str, str]], dict[str, Any]],
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.adapter = adapter
        self.transport = adapter.transport
        self._build_selector = build_selector
        self._sleep = sleep
        self._monotonic = monotonic

    def execute(
        self,
        action: str,
        params: dict[str, Any],
        *,
        assert_write_allowed: Callable[[], None],
        check_cancel: Callable[[], None],
    ) -> dict[str, Any]:
        """返回执行器统一的 ``{success, error, data}``；取消/租约异常原样抛出。"""
        try:
            validate_strict_step(action, params)
            if action == "click":
                data = self._click(params, assert_write_allowed)
            elif action == "input":
                data = self._input(params, assert_write_allowed)
            elif action == "wait_until":
                data = self._wait_until(params, check_cancel)
            elif action == "assert_element":
                data = self._assert_element(params)
            else:
                data = self._assert_element({"text": params["text"]})
        except StrictStepError as exc:
            return {"success": False, "error": exc.message, "data": {"strict_code": exc.code}}
        except DeviceAdapterError as exc:
            code = str(exc)
            return {"success": False, "error": f"设备操作失败：{code}", "data": {"strict_code": code}}
        return {"success": True, "data": data}

    def _observe(self) -> list[UiNode]:
        return self.adapter.observe()

    def _click(self, params: dict[str, Any], assert_write_allowed: Callable[[], None]) -> dict[str, Any]:
        selector = parse_selector(params)
        nodes = self._observe()
        matches = [node for node in nodes if selector.matches(node)]
        if not matches:
            raise StrictStepError("target_not_found", selector.describe())
        if len(matches) != 1:
            raise StrictStepError("target_not_unique", f"{selector.describe()}（{len(matches)} 个）")
        target = matches[0]
        if not target.enabled or target.bounds is None:
            raise StrictStepError("target_not_interactable", selector.describe())
        via_parent = False
        if not target.clickable:
            by_id = {node.node_id: node for node in nodes}
            parent = by_id.get(target.parent_id or "")
            while parent is not None and not parent.clickable:
                parent = by_id.get(parent.parent_id or "")
            if parent is None or not parent.enabled:
                raise StrictStepError("target_not_clickable", selector.describe())
            via_parent = True
        rpc_selector = self._build_selector(selector.u2_fields())
        try:
            count = self.transport.rpc_once("count", [rpc_selector])
        except Exception:
            raise StrictStepError("target_not_found", selector.describe()) from None
        if type(count) is not int or count != 1:
            raise StrictStepError("selector_count_changed", selector.describe())
        self.adapter._check_package()
        assert_write_allowed()
        try:
            clicked = self.transport.rpc_once("click", [rpc_selector])
        except Exception:
            raise StrictStepError("click_outcome_unknown", selector.describe()) from None
        if clicked is not True:
            raise StrictStepError("click_outcome_unknown", selector.describe())
        return {"selector": selector.describe(), "matched": 1, "via_clickable_parent": via_parent}

    def _input(self, params: dict[str, Any], assert_write_allowed: Callable[[], None]) -> dict[str, Any]:
        resource_id = str(params.get("resourceId") or params.get("resource_id")).strip()
        value = params.get("text", params.get("value", ""))
        if "{{" in value and "}}" in value:
            raise StrictStepError("input_value_unresolved")
        self.adapter.replace_text(resource_id, value, assert_write_allowed=assert_write_allowed)
        return {"resourceId": resource_id, "verified": True, "length": len(value)}

    def _wait_until(self, params: dict[str, Any], check_cancel: Callable[[], None]) -> dict[str, Any]:
        selector = parse_selector(params)
        condition = str(params.get("condition") or "visible")
        timeout_ms = _int_param(params, "timeout_ms", 10000, WAIT_TIMEOUT_MS_RANGE, "timeout_invalid")
        interval_ms = _int_param(params, "interval_ms", 500, WAIT_INTERVAL_MS_RANGE, "interval_invalid")
        started = self._monotonic()
        deadline = started + timeout_ms / 1000
        attempts = 0
        last_error: str | None = None
        last_count: int | None = None
        while True:
            check_cancel()
            attempts += 1
            try:
                nodes = self._observe()
            except DeviceAdapterError as exc:
                last_error = str(exc)
            else:
                last_error = None
                last_count = sum(1 for node in nodes if selector.matches(node))
                if (condition == "visible" and last_count > 0) or (condition == "absent" and last_count == 0):
                    return {
                        "selector": selector.describe(),
                        "condition": condition,
                        "matched": last_count,
                        "attempts": attempts,
                        "elapsed_ms": int((self._monotonic() - started) * 1000),
                    }
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                detail = f"{selector.describe()} {condition}，{timeout_ms} ms 内 {attempts} 次观察"
                if last_error:
                    detail += f"，最后一次观察失败：{last_error}"
                elif last_count is not None:
                    detail += f"，最后匹配 {last_count} 个"
                raise StrictStepError("wait_timeout", detail)
            self._sleep(min(interval_ms / 1000, remaining))

    def _assert_element(self, params: dict[str, Any]) -> dict[str, Any]:
        selector = parse_selector(params)
        expect = str(params.get("expect") or "present")
        exact = _optional_count(params, "count")
        minimum = _optional_count(params, "min_count")
        nodes = self._observe()
        count = sum(1 for node in nodes if selector.matches(node))
        if expect == "absent":
            passed = count == 0
            expectation = "不存在"
        elif exact is not None:
            passed = count == exact
            expectation = f"恰好 {exact} 个"
        else:
            floor = max(1, minimum or 1)
            passed = count >= floor
            expectation = f"至少 {floor} 个"
        if not passed:
            raise StrictStepError("assert_failed", f"{selector.describe()} 期望{expectation}，实际 {count} 个")
        return {"selector": selector.describe(), "expect": expect, "matched": count}


def connect_strict_engine(serial: str, package: str) -> StrictReplayEngine:
    """显式连接 uiautomator2 服务并构造严格回放引擎（阻塞调用，需在线程中执行）。"""
    import uiautomator2 as u2
    from uiautomator2._selector import Selector

    from app.services.android_agent.device_adapter import UiautomatorTransport

    device = u2.connect(serial)
    transport = UiautomatorTransport(device)
    width, height = device.window_size()
    adapter = AndroidDeviceAdapter(transport, package=package, width=int(width), height=int(height))
    return StrictReplayEngine(adapter, build_selector=lambda fields: dict(Selector(**fields)))
