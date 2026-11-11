from collections import deque
from xml.sax.saxutils import quoteattr

import pytest

from app.services.android_agent.device_adapter import AndroidDeviceAdapter, DeviceAdapterError

RESOURCE = "test.app:id/query"


def tree(text="", *, duplicate=False, enabled=True, password=False, class_name="android.widget.EditText"):
    node = (
        f'<node resource-id="{RESOURCE}" text={quoteattr(text)} class="{class_name}" '
        f'enabled="{str(enabled).lower()}" password="{str(password).lower()}" bounds="[0,0][100,100]" />'
    )
    return "<hierarchy>" + node * (2 if duplicate else 1) + "</hierarchy>"


class FakeTransport:
    def __init__(self, trees):
        self.trees = deque(trees)
        self.calls = []
        self.package = "test.app"
        self.count = 1
        self.write_result = True

    def current_package(self):
        return self.package

    def rpc_once(self, method, params):
        self.calls.append((method, params))
        if method == "dumpWindowHierarchy":
            result = self.trees.popleft()
        elif method == "count":
            result = self.count
        else:
            result = self.write_result
        if isinstance(result, Exception):
            raise result
        return result


def adapter(transport):
    return AndroidDeviceAdapter(transport, package="test.app", width=1080, height=1920)


def writes(transport):
    return [call for call in transport.calls if call[0] == "setText"]


@pytest.mark.parametrize("value", ["晴天", "晴天 & < > ' \" %s 😀", ""])
def test_unicode_replacement_verifies_exact_text_without_shell_or_ime(value):
    transport = FakeTransport([tree("old"), tree(value)])
    gate_calls = []
    adapter(transport).replace_text(RESOURCE, value, assert_write_allowed=lambda: gate_calls.append(True))
    assert gate_calls == [True]
    assert len(writes(transport)) == 1
    assert writes(transport)[0][1][1] == value
    assert {method for method, _ in transport.calls} == {"dumpWindowHierarchy", "count", "setText"}


def test_capture_retries_empty_or_failed_reads_only():
    transport = FakeTransport([RuntimeError("idle"), "<hierarchy />", tree()])
    assert len(adapter(transport).observe()) == 1
    assert len(transport.calls) == 3


def test_capture_stops_after_budget():
    transport = FakeTransport(["<hierarchy />"] * 4)
    with pytest.raises(DeviceAdapterError, match="^observation_unavailable$"):
        adapter(transport).observe()
    assert len(transport.calls) == 3


@pytest.mark.parametrize(
    "xml", [tree(duplicate=True), tree(enabled=False), tree(password=True), tree(class_name="android.widget.TextView")]
)
def test_invalid_target_never_writes(xml):
    transport = FakeTransport([xml])
    with pytest.raises(DeviceAdapterError):
        adapter(transport).replace_text(RESOURCE, "晴天", assert_write_allowed=lambda: None)
    assert not writes(transport)


@pytest.mark.parametrize("result", [TimeoutError("secret input"), False, None])
def test_uncertain_write_never_retries_or_leaks_value(result):
    transport = FakeTransport([tree()])
    transport.write_result = result
    with pytest.raises(DeviceAdapterError, match="^input_outcome_unknown$"):
        adapter(transport).replace_text(RESOURCE, "晴天", assert_write_allowed=lambda: None)
    assert len(writes(transport)) == 1


@pytest.mark.parametrize("after", [tree("晴天 extra"), tree(duplicate=True), "<hierarchy />"])
def test_postcondition_failure_is_unknown_not_retry(after):
    transport = FakeTransport([tree(), after, after, after])
    with pytest.raises(DeviceAdapterError, match="^input_outcome_unknown$"):
        adapter(transport).replace_text(RESOURCE, "晴天", assert_write_allowed=lambda: None)
    assert len(writes(transport)) == 1


def test_lost_lease_prevents_dispatch():
    transport = FakeTransport([tree()])

    def revoked():
        raise DeviceAdapterError("lease_lost")

    with pytest.raises(DeviceAdapterError, match="^lease_lost$"):
        adapter(transport).replace_text(RESOURCE, "晴天", assert_write_allowed=revoked)
    assert not writes(transport)


@pytest.mark.parametrize("count", [0, 2, True])
def test_selector_changed_between_observation_and_write(count):
    transport = FakeTransport([tree()])
    transport.count = count
    with pytest.raises(DeviceAdapterError, match="^input_target_not_unique$"):
        adapter(transport).replace_text(RESOURCE, "晴天", assert_write_allowed=lambda: None)
    assert not writes(transport)


def test_wrong_foreground_app_never_writes():
    transport = FakeTransport([tree()])
    transport.package = "other.app"
    with pytest.raises(DeviceAdapterError, match="^unexpected_package$"):
        adapter(transport).replace_text(RESOURCE, "晴天", assert_write_allowed=lambda: None)
    assert not transport.calls


@pytest.mark.parametrize("budget", [0, 4, True])
def test_capture_budget_is_bounded(budget):
    with pytest.raises(DeviceAdapterError, match="^invalid_capture_budget$"):
        adapter(FakeTransport([])).observe(attempts=budget)


def test_truncated_text_cannot_falsely_pass_exact_verification():
    value = "x" * 512
    transport = FakeTransport([tree(), tree(value + "unexpected")])
    with pytest.raises(DeviceAdapterError, match="^input_outcome_unknown$"):
        adapter(transport).replace_text(RESOURCE, value, assert_write_allowed=lambda: None)
    assert len(writes(transport)) == 1


def test_offscreen_target_never_writes():
    transport = FakeTransport([tree().replace("[0,0][100,100]", "[0,0][0,0]")])
    with pytest.raises(DeviceAdapterError, match="^input_target_not_editable$"):
        adapter(transport).replace_text(RESOURCE, "晴天", assert_write_allowed=lambda: None)
    assert not writes(transport)


def test_pinned_transport_bypasses_library_write_retry(monkeypatch):
    import importlib.metadata
    from types import SimpleNamespace

    import uiautomator2.core

    from app.services.android_agent.device_adapter import UiautomatorTransport

    monkeypatch.setattr(importlib.metadata, "version", lambda name: "3.2.1")
    calls = []

    def fail(*args, **kwargs):
        calls.append((args, kwargs))
        raise TimeoutError("uncertain")

    monkeypatch.setattr(uiautomator2.core, "_jsonrpc_call", fail)
    transport = UiautomatorTransport(SimpleNamespace(_dev=object()))
    with pytest.raises(TimeoutError):
        transport.rpc_once("setText", [{}, "test"])
    assert len(calls) == 1
    assert calls[0][1] == {"timeout": 5, "print_request": False}


def test_unreviewed_dependency_version_is_rejected(monkeypatch):
    import importlib.metadata

    from app.services.android_agent.device_adapter import UiautomatorTransport

    monkeypatch.setattr(importlib.metadata, "version", lambda name: "3.3.0")
    with pytest.raises(DeviceAdapterError, match="^unsupported_uiautomator_version$"):
        UiautomatorTransport(object())


def test_ui_target_supports_content_desc_locator():
    """真机图标按钮常常只有 content-desc，定位器必须支持它。"""
    from app.services.android_agent.device_adapter import UiTarget
    from app.services.android_agent.observation import UiNode

    node = UiNode(
        node_id="n1",
        parent_id=None,
        resource_id="com.demo:id/op_add",
        text="",
        content_desc="加",
        class_name="android.widget.Button",
        bounds=(0, 0, 10, 10),
        enabled=True,
        clickable=True,
        redacted=False,
    )
    target = UiTarget(resource_id="com.demo:id/op_add", content_desc="加")
    assert target.matches(node) is True

    # 描述不一致时不得匹配
    assert UiTarget(resource_id="com.demo:id/op_add", content_desc="减").matches(node) is False
    # 截断的描述不得用于精确匹配
    truncated = UiNode(
        node_id="n2",
        parent_id=None,
        resource_id="com.demo:id/op_add",
        text="",
        content_desc="加",
        class_name="android.widget.Button",
        bounds=(0, 0, 10, 10),
        enabled=True,
        clickable=True,
        redacted=False,
        desc_truncated=True,
    )
    assert target.matches(truncated) is False


def test_ui_target_selector_mask_includes_description():
    """mask 必须包含 description(0x40)，否则 RPC 会按纯 resourceId 匹配到多个节点。"""
    from app.services.android_agent.device_adapter import UiTarget

    selector = UiTarget(resource_id="com.demo:id/op_add", content_desc="加").rpc_selector()
    assert selector["mask"] & 0x40
    assert selector["mask"] & 0x200000
    assert selector["description"] == "加"
    assert selector["resourceId"] == "com.demo:id/op_add"


def test_ui_target_rejects_empty_and_describes_itself():
    from app.services.android_agent.device_adapter import DeviceAdapterError, UiTarget

    with pytest.raises(DeviceAdapterError):
        UiTarget()
    described = UiTarget(content_desc="等于").describe()
    assert "content_desc=等于" in described
