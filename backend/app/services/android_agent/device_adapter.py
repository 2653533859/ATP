"""M0 supervised device adapter; caller must own the device lease before writes.

Not wired to production jobs. No coordinate/IME fallback or write retries.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time
from typing import Any, Protocol

from app.services.android_agent.observation import ObservationRejected, UiNode, parse_hierarchy


class DeviceAdapterError(ValueError):
    """Stable codes only; never expose RPC errors containing entered text."""


@dataclass(frozen=True)
class UiTarget:
    """Exact-match target; never substring-matched against the raw XML."""

    resource_id: str = ""
    text: str = ""

    def __post_init__(self) -> None:
        if not self.resource_id and not self.text:
            raise DeviceAdapterError("empty_target")

    def matches(self, node: UiNode) -> bool:
        if node.text_truncated and self.text:
            return False
        return (not self.resource_id or node.resource_id == self.resource_id) and (
            not self.text or node.text == self.text
        )

    def rpc_selector(self) -> dict[str, Any]:
        # Mask bits match uiautomator2 3.2.1: text=0x01, resourceId=0x200000.
        selector: dict[str, Any] = {"mask": 0, "childOrSibling": [], "childOrSiblingSelector": []}
        if self.text:
            selector["mask"] |= 0x01
            selector["text"] = self.text
        if self.resource_id:
            selector["mask"] |= 0x200000
            selector["resourceId"] = self.resource_id
        return selector


class Transport(Protocol):
    def current_package(self) -> str: ...

    def rpc_once(self, method: str, params: list[Any]) -> Any: ...


class UiautomatorTransport:
    """Pinned 3.2.1 transport, bypassing its implicit RPC restart/retry wrapper.

    Explicit connection may start/install the bundled UIAutomator service. The
    private function is intentional: public jsonrpc_call retries writes after
    HTTPError. Revalidate this adapter before changing the pinned dependency.
    """

    def __init__(self, device: Any):
        from importlib.metadata import version

        if version("uiautomator2") != "3.2.1":
            raise DeviceAdapterError("unsupported_uiautomator_version")
        self.device = device

    def current_package(self) -> str:
        return str(self.device.app_current().get("package", ""))

    def rpc_once(self, method: str, params: list[Any]) -> Any:
        from uiautomator2.core import _jsonrpc_call

        # No debug output: RPC params can include sensitive test values.
        return _jsonrpc_call(self.device._dev, method, params, timeout=5, print_request=False)


class AndroidDeviceAdapter:
    def __init__(self, transport: Transport, *, package: str, width: int, height: int):
        if not package or width <= 0 or height <= 0:
            raise DeviceAdapterError("invalid_device_context")
        self.transport = transport
        self.package = package
        self.width = width
        self.height = height

    def _check_package(self) -> None:
        try:
            actual = self.transport.current_package()
        except Exception:
            raise DeviceAdapterError("device_unavailable") from None
        if actual != self.package:
            raise DeviceAdapterError("unexpected_package")

    def observe(self, *, attempts: int = 3) -> list[UiNode]:
        if type(attempts) is not int or not 1 <= attempts <= 3:
            raise DeviceAdapterError("invalid_capture_budget")
        for _ in range(attempts):
            self._check_package()
            try:
                xml = self.transport.rpc_once("dumpWindowHierarchy", [False, 50])
                if not isinstance(xml, str):
                    raise ObservationRejected("invalid_ui_tree")
                nodes = parse_hierarchy(xml.encode("utf-8"), width=self.width, height=self.height)
            except Exception:
                continue
            self._check_package()
            if nodes:
                return nodes
        raise DeviceAdapterError("observation_unavailable")

    def _input_target(self, nodes: list[UiNode], resource_id: str) -> UiNode:
        matches = [node for node in nodes if node.resource_id == resource_id]
        if len(matches) != 1:
            raise DeviceAdapterError("input_target_not_unique")
        target = matches[0]
        if (
            not target.enabled
            or target.redacted
            or target.bounds is None
            or target.class_name != "android.widget.EditText"
        ):
            raise DeviceAdapterError("input_target_not_editable")
        return target

    def replace_text(self, resource_id: str, value: str, *, assert_write_allowed: Callable[[], None]) -> None:
        """Replace one unique input, then independently verify exact text.

        The callback must validate lease/epoch/cancellation immediately before
        dispatch. This adapter does not implement that production gate itself.
        Any error after dispatch is unknown, never an instruction to resend.
        """
        if not resource_id.startswith(self.package + ":id/") or len(resource_id) >= 512:
            raise DeviceAdapterError("input_target_outside_package")
        if not isinstance(value, str) or len(value) > 512:
            raise DeviceAdapterError("invalid_input_value")
        self._input_target(self.observe(), resource_id)
        # Selector mask matches uiautomator2 3.2.1 className | resourceId.
        selector = {
            "mask": 2097168,
            "childOrSibling": [],
            "childOrSiblingSelector": [],
            "resourceId": resource_id,
            "className": "android.widget.EditText",
        }
        try:
            count = self.transport.rpc_once("count", [selector])
        except Exception:
            raise DeviceAdapterError("input_target_unavailable") from None
        if type(count) is not int or count != 1:
            raise DeviceAdapterError("input_target_not_unique")
        self._check_package()
        assert_write_allowed()
        try:
            # setText replaces content atomically; do not clear first.
            if self.transport.rpc_once("setText", [selector, value]) is not True:
                raise DeviceAdapterError("input_outcome_unknown")
            target = self._input_target(self.observe(), resource_id)
            if target.text_truncated or target.text != value:
                raise DeviceAdapterError("input_outcome_unknown")
        except Exception:
            raise DeviceAdapterError("input_outcome_unknown") from None

    def wait_for(
        self,
        target: UiTarget,
        *,
        timeout_ms: int,
        absent: bool = False,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> list[UiNode]:
        """Poll until an exact condition holds; a timeout is always a failure."""
        if type(timeout_ms) is not int or not 100 <= timeout_ms <= 30000:
            raise DeviceAdapterError("invalid_wait_budget")
        deadline = clock() + timeout_ms / 1000
        while True:
            try:
                nodes = self.observe()
            except DeviceAdapterError as exc:
                if exc.args != ("observation_unavailable",):
                    raise
            else:
                found = any(target.matches(node) for node in nodes)
                if found is not absent:
                    return nodes
            if clock() >= deadline:
                raise DeviceAdapterError("condition_timeout")
            sleep(0.4)

    def tap(self, target: UiTarget, *, assert_write_allowed: Callable[[], None]) -> None:
        """Tap one unique enabled element. No coordinates, no retry after dispatch."""
        nodes = self.observe()
        matches = [node for node in nodes if target.matches(node)]
        if len(matches) != 1:
            raise DeviceAdapterError("target_not_unique")
        node = matches[0]
        if not node.enabled or node.redacted or node.bounds is None:
            raise DeviceAdapterError("target_not_tappable")
        parent = next((item for item in nodes if item.node_id == node.parent_id), None)
        if not node.clickable and not (parent and parent.clickable and parent.enabled):
            raise DeviceAdapterError("target_not_tappable")
        selector = target.rpc_selector()
        try:
            count = self.transport.rpc_once("count", [selector])
        except Exception:
            raise DeviceAdapterError("target_unavailable") from None
        if type(count) is not int or count != 1:
            raise DeviceAdapterError("target_not_unique")
        self._check_package()
        assert_write_allowed()
        try:
            result = self.transport.rpc_once("click", [selector])
        except Exception:
            raise DeviceAdapterError("write_outcome_unknown") from None
        if result is not True:
            raise DeviceAdapterError("write_outcome_unknown")

    def press_back(self, *, assert_write_allowed: Callable[[], None]) -> None:
        self._check_package()
        assert_write_allowed()
        try:
            self.transport.rpc_once("pressKey", ["back"])
        except Exception:
            raise DeviceAdapterError("write_outcome_unknown") from None

    def swipe(
        self,
        direction: str,
        distance_fraction: float,
        *,
        assert_write_allowed: Callable[[], None],
    ) -> None:
        """Bounded screen-center swipe, avoiding edges that trigger system gestures."""
        if direction not in ("up", "down", "left", "right"):
            raise DeviceAdapterError("invalid_swipe_direction")
        if type(distance_fraction) not in (float, int) or not (0.0 < float(distance_fraction) <= 0.8):
            raise DeviceAdapterError("invalid_swipe_distance")

        self._check_package()
        cx = self.width // 2
        cy = self.height // 2
        dx = int(self.width * float(distance_fraction) / 2)
        dy = int(self.height * float(distance_fraction) / 2)

        if direction == "up":
            sx, sy, ex, ey = cx, cy + dy, cx, cy - dy
        elif direction == "down":
            sx, sy, ex, ey = cx, cy - dy, cx, cy + dy
        elif direction == "left":
            sx, sy, ex, ey = cx + dx, cy, cx - dx, cy
        else:  # right
            sx, sy, ex, ey = cx - dx, cy, cx + dx, cy

        min_x, max_x = int(self.width * 0.05), int(self.width * 0.95)
        min_y, max_y = int(self.height * 0.05), int(self.height * 0.95)
        if not (min_x <= sx <= max_x and min_x <= ex <= max_x and min_y <= sy <= max_y and min_y <= ey <= max_y):
            raise DeviceAdapterError("swipe_coordinates_out_of_bounds")

        assert_write_allowed()
        try:
            result = self.transport.rpc_once("swipe", [sx, sy, ex, ey, 50])
        except Exception:
            raise DeviceAdapterError("write_outcome_unknown") from None
        if result is not True:
            raise DeviceAdapterError("write_outcome_unknown")
