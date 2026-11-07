from collections import deque
from xml.sax.saxutils import quoteattr

import pytest

from app.services.android_agent.device_adapter import AndroidDeviceAdapter
from app.services.android_agent.strict_replay import (
    StrictReplayEngine,
    StrictStepError,
    parse_selector,
    validate_strict_step,
)

PKG = "test.app"
QUERY = f"{PKG}:id/query"
ENTRY = f"{PKG}:id/entry"
SUGGEST = f"{PKG}:id/suggest"


def node(resource_id="", text="", cls="android.widget.TextView", *, clickable=False, enabled=True, children=""):
    return (
        f"<node resource-id={quoteattr(resource_id)} text={quoteattr(text)} class={quoteattr(cls)} "
        f'content-desc="" clickable="{str(clickable).lower()}" enabled="{str(enabled).lower()}" '
        f'password="false" bounds="[0,0][100,100]">{children}</node>'
    )


def tree(*nodes):
    return "<hierarchy>" + "".join(nodes) + "</hierarchy>"


HOME = tree(node(ENTRY, clickable=True))
SEARCH = tree(node(QUERY, "", "android.widget.EditText", clickable=True))


class FakeTransport:
    def __init__(self, trees, *, count=1, click_result=True):
        self.trees = deque(trees)
        self.last_tree = trees[-1] if trees else HOME
        self.calls = []
        self.package = PKG
        self.count = count
        self.click_result = click_result

    def current_package(self):
        return self.package

    def rpc_once(self, method, params):
        self.calls.append((method, params))
        if method == "dumpWindowHierarchy":
            if self.trees:
                self.last_tree = self.trees.popleft()
            result = self.last_tree
        elif method == "count":
            result = self.count
        elif method == "click":
            result = self.click_result
        else:
            result = True
        if isinstance(result, Exception):
            raise result
        return result


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def engine(transport, clock=None):
    clock = clock or FakeClock()
    adapter = AndroidDeviceAdapter(transport, package=PKG, width=1080, height=1920)
    return StrictReplayEngine(
        adapter,
        build_selector=lambda fields: {"mask": 0, **fields},
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )


def run(eng, action, params, *, gate=None, cancel=None):
    return eng.execute(
        action,
        params,
        assert_write_allowed=gate or (lambda: None),
        check_cancel=cancel or (lambda: None),
    )


def writes(transport, method):
    return [call for call in transport.calls if call[0] == method]


def test_click_unique_target_checks_gate_then_dispatches_once():
    transport = FakeTransport([HOME])
    gate_calls = []
    result = run(engine(transport), "click", {"resourceId": ENTRY}, gate=lambda: gate_calls.append(True))
    assert result["success"] is True and result["data"]["matched"] == 1
    assert gate_calls == [True]
    assert writes(transport, "click") == [("click", [{"mask": 0, "resourceId": ENTRY}])]


def test_click_via_clickable_parent_uses_exact_text_selector():
    child = node(SUGGEST, "晴天")
    transport = FakeTransport([tree(node("", "", "android.widget.LinearLayout", clickable=True, children=child))])
    result = run(engine(transport), "click", {"resourceId": SUGGEST, "text": "晴天"})
    assert result["success"] is True and result["data"]["via_clickable_parent"] is True
    assert writes(transport, "click")[0][1][0] == {"mask": 0, "resourceId": SUGGEST, "text": "晴天"}


@pytest.mark.parametrize(
    ("xml", "code"),
    [
        (tree(node(ENTRY, clickable=True), node(ENTRY, clickable=True)), "target_not_unique"),
        (tree(node("other")), "target_not_found"),
        (tree(node(ENTRY, clickable=True, enabled=False)), "target_not_interactable"),
        (tree(node(ENTRY)), "target_not_clickable"),
    ],
)
def test_click_rejects_ambiguous_missing_or_inert_targets_without_writing(xml, code):
    transport = FakeTransport([xml])
    result = run(engine(transport), "click", {"resourceId": ENTRY, "x": 10, "y": 10})
    assert result["success"] is False and result["data"]["strict_code"] == code
    assert writes(transport, "click") == []


def test_click_never_falls_back_to_coordinates_and_needs_selector():
    transport = FakeTransport([HOME])
    result = run(engine(transport), "click", {"x": 10, "y": 20})
    assert result["success"] is False and result["data"]["strict_code"] == "selector_missing"
    assert transport.calls == []


def test_click_count_drift_blocks_dispatch():
    transport = FakeTransport([HOME], count=2)
    result = run(engine(transport), "click", {"resourceId": ENTRY})
    assert result["data"]["strict_code"] == "selector_count_changed"
    assert writes(transport, "click") == []


def test_click_error_after_dispatch_is_unknown_and_not_retried():
    transport = FakeTransport([HOME], click_result=RuntimeError("socket"))
    result = run(engine(transport), "click", {"resourceId": ENTRY})
    assert result["data"]["strict_code"] == "click_outcome_unknown"
    assert len(writes(transport, "click")) == 1


def test_gate_exception_propagates_and_prevents_write():
    class Cancelled(Exception):
        pass

    def gate():
        raise Cancelled()

    transport = FakeTransport([HOME])
    with pytest.raises(Cancelled):
        run(engine(transport), "click", {"resourceId": ENTRY}, gate=gate)
    assert writes(transport, "click") == []


def test_package_drift_blocks_click():
    transport = FakeTransport([HOME])
    transport.package = "other.app"
    result = run(engine(transport), "click", {"resourceId": ENTRY})
    assert result["success"] is False and result["data"]["strict_code"] == "unexpected_package"


def test_input_sets_unicode_text_and_verifies():
    filled = tree(node(QUERY, "晴天", "android.widget.EditText", clickable=True))
    transport = FakeTransport([SEARCH, filled])
    gate_calls = []
    result = run(engine(transport), "input", {"resourceId": QUERY, "text": "晴天"}, gate=lambda: gate_calls.append(1))
    assert result == {"success": True, "data": {"resourceId": QUERY, "verified": True, "length": 2}}
    assert gate_calls == [1] and writes(transport, "setText")[0][1][1] == "晴天"


def test_input_requires_resource_id_and_resolved_value():
    transport = FakeTransport([SEARCH])
    assert run(engine(transport), "input", {"text": "x"})["data"]["strict_code"] == "input_target_required"
    result = run(engine(transport), "input", {"resourceId": QUERY, "text": "{{missing}}"})
    assert result["data"]["strict_code"] == "input_value_unresolved"
    assert writes(transport, "setText") == []


def test_input_verification_mismatch_is_unknown_outcome():
    transport = FakeTransport([SEARCH, SEARCH])
    result = run(engine(transport), "input", {"resourceId": QUERY, "text": "晴天"})
    assert result["success"] is False and result["data"]["strict_code"] == "input_outcome_unknown"
    assert len(writes(transport, "setText")) == 1


def test_wait_until_visible_polls_until_match():
    clock = FakeClock()
    transport = FakeTransport([HOME, HOME, SEARCH])
    result = run(engine(transport, clock), "wait_until", {"resourceId": QUERY, "timeout_ms": 5000, "interval_ms": 500})
    assert result["success"] is True and result["data"]["attempts"] == 3
    assert clock.sleeps == [0.5, 0.5]


def test_wait_until_absent_and_timeout_failure():
    clock = FakeClock()
    transport = FakeTransport([SEARCH])
    result = run(
        engine(transport, clock), "wait_until", {"resourceId": QUERY, "condition": "absent", "timeout_ms": 1000}
    )
    assert result["success"] is False and result["data"]["strict_code"] == "wait_timeout"
    assert "最后匹配 1 个" in result["error"]
    assert clock.now <= 1.0 + 1e-9


def test_wait_until_checks_cancel_each_attempt():
    class Cancelled(Exception):
        pass

    checks = []

    def cancel():
        checks.append(1)
        if len(checks) == 2:
            raise Cancelled()

    transport = FakeTransport([HOME])
    with pytest.raises(Cancelled):
        run(engine(transport), "wait_until", {"resourceId": QUERY, "timeout_ms": 5000}, cancel=cancel)
    assert len(checks) == 2


def test_wait_until_tolerates_transient_observation_failure():
    transport = FakeTransport(["<hierarchy />"] * 3 + [SEARCH])
    result = run(engine(transport), "wait_until", {"resourceId": QUERY, "timeout_ms": 5000})
    assert result["success"] is True and result["data"]["attempts"] == 2


def test_assert_element_exact_count_presence_and_absence():
    results = tree(
        node(QUERY, "晴天", "android.widget.EditText"),
        node("", "晴天"),
        node("", "综合"),
        node(f"{PKG}:id/tab", "歌曲"),
    )
    transport = FakeTransport([results])
    eng = engine(transport)
    assert run(eng, "assert_element", {"resourceId": QUERY, "text": "晴天", "count": 1})["success"] is True
    assert run(eng, "assert_element", {"className": "android.widget.TextView", "text": "晴天"})["success"] is True
    assert run(eng, "assert_element", {"resourceId": SUGGEST, "expect": "absent"})["success"] is True
    failed = run(eng, "assert_element", {"text": "晴天", "count": 1})
    assert failed["success"] is False and "实际 2 个" in failed["error"]
    # 精确匹配：子串不能通过。
    assert run(eng, "assert_element", {"text": "晴"})["success"] is False
    assert run(eng, "assert_text", {"text": "综合"})["success"] is True
    assert run(eng, "assert_text", {"text": "综"})["success"] is False


@pytest.mark.parametrize(
    ("action", "params", "code"),
    [
        ("assert_text", {"text": "  "}, "assert_text_missing"),
        ("assert_element", {}, "selector_missing"),
        ("assert_element", {"resourceId": QUERY, "expect": "maybe"}, "expect_invalid"),
        ("assert_element", {"resourceId": QUERY, "count": -1}, "count_invalid"),
        ("assert_element", {"resourceId": QUERY, "count": True}, "count_invalid"),
        ("wait_until", {"resourceId": QUERY, "condition": "gone"}, "condition_invalid"),
        ("wait_until", {"resourceId": QUERY, "timeout_ms": 99}, "timeout_invalid"),
        ("wait_until", {"resourceId": QUERY, "timeout_ms": 1.5}, "timeout_invalid"),
        ("wait_until", {"resourceId": QUERY, "interval_ms": 100}, "interval_invalid"),
        ("long_click", {"resourceId": QUERY}, "unsupported_action"),
        ("click", {"resourceId": 3}, "selector_invalid"),
    ],
)
def test_invalid_params_rejected_before_device_access(action, params, code):
    with pytest.raises(StrictStepError) as caught:
        validate_strict_step(action, params)
    assert caught.value.code == code
    transport = FakeTransport([HOME])
    result = run(engine(transport), action, params)
    assert result["success"] is False and result["data"]["strict_code"] == code
    assert transport.calls == []


def test_passthrough_actions_validate_without_rules():
    for action in ("press_key", "start_app", "wait", "screenshot", "swipe", "stop_app"):
        validate_strict_step(action, {})


def test_selector_aliases_and_blank_fields():
    selector = parse_selector({"resource_id": QUERY, "text": "", "content_desc": "搜索", "class_name": " "})
    assert selector.u2_fields() == {"resourceId": QUERY, "description": "搜索"}
    assert selector.describe() == f"resourceId={QUERY}, contentDesc=搜索"
