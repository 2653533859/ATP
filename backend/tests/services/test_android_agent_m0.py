import json

import pytest

from app.services.android_agent.contracts import DecisionRejected, Finish, parse_decision, validate_context
from app.services.android_agent.observation import ObservationRejected, parse_dump_output, parse_hierarchy


def action(**overrides):
    return {
        "schema_version": 1,
        "observation_id": "obs-1",
        "action": "tap",
        "target": {"node_id": "n1"},
        "expected_observation": {"type": "element_visible", "resource_id": "test:id/search"},
        "reason": "打开搜索",
        **overrides,
    }


def context(**overrides):
    return {
        "observation_id": "obs-1",
        "observed_package": "test.app",
        "allowed_package": "test.app",
        "captured_epoch": 1,
        "current_epoch": 1,
        "controllable_node_ids": {"n1"},
        "allowed_value_refs": {"product_name"},
        "device_online": True,
        "observation_available": True,
        **overrides,
    }


def test_valid_tap_is_only_a_candidate_not_an_execution():
    decision = parse_decision(json.dumps(action()))
    assert validate_context(decision, **context()) is None
    assert decision.target.node_id == "n1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"action": "shell", "command": "input tap 1 1"},
        {"target": {"node_id": "n1", "x": 10}},
        {"lease_token": "do-not-echo"},
        {"schema_version": "1"},
        {"schema_version": True},
        {"expected_observation": {"type": "element_visible", "resource_id": " "}},
        {"action": "input", "value_ref": "${secret}"},
    ],
)
def test_model_cannot_expand_contract(overrides):
    with pytest.raises(DecisionRejected, match="^invalid_decision$"):
        parse_decision(json.dumps(action(**overrides)))


@pytest.mark.parametrize("raw", ["```json\n{}\n```", "[]", "null", '{"action":"tap","action":"finish"}', "\ud800"])
def test_invalid_envelopes_and_duplicate_keys_are_rejected(raw):
    with pytest.raises(DecisionRejected, match="^invalid_decision$"):
        parse_decision(raw)


def test_model_response_size_is_bounded():
    with pytest.raises(DecisionRejected, match="^response_too_large$"):
        parse_decision("x" * 16385)


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"current_epoch": 2}, "control_epoch_changed"),
        ({"observation_id": "obs-2"}, "observation_stale"),
        ({"observed_package": "another.app"}, "package_out_of_scope"),
        ({"controllable_node_ids": set()}, "target_unavailable"),
        ({"device_online": False}, "device_offline"),
        ({"observation_available": False}, "observation_unavailable"),
    ],
)
def test_delayed_or_out_of_scope_model_decision_cannot_pass_context(overrides, code):
    with pytest.raises(DecisionRejected, match=f"^{code}$"):
        validate_context(parse_decision(json.dumps(action())), **context(**overrides))


def test_input_requires_an_explicitly_allowed_variable_reference():
    decision = parse_decision(json.dumps(action(action="input", value_ref="password")))
    with pytest.raises(DecisionRejected, match="^value_ref_forbidden$"):
        validate_context(decision, **context())


def test_finish_is_a_proposal_with_no_success_field():
    data = {"schema_version": 1, "observation_id": "obs-1", "action": "finish", "reason": "检查完成"}
    assert isinstance(parse_decision(json.dumps(data)), Finish)
    with pytest.raises(DecisionRejected):
        parse_decision(json.dumps({**data, "success": True}))


@pytest.mark.parametrize("timeout", [0, 15001, "100", True])
def test_wait_requires_strict_bounded_timeout(timeout):
    data = action(action="wait", timeout_ms=timeout)
    del data["target"]
    with pytest.raises(DecisionRejected):
        parse_decision(json.dumps(data))


@pytest.mark.parametrize("kind", ["input", "swipe", "back", "wait", "request_help"])
def test_each_supported_action_has_a_valid_contract(kind):
    data = action(action=kind)
    if kind == "input":
        data["value_ref"] = "product_name"
    else:
        del data["target"]
    if kind == "swipe":
        data.update(direction="up", distance_fraction=0.5)
    if kind == "wait":
        data["timeout_ms"] = 1000
    if kind == "request_help":
        del data["expected_observation"]
        data["code"] = "cannot_progress"
    decision = parse_decision(json.dumps(data))
    assert validate_context(decision, **context()) is None


def test_oversized_integer_in_bounds_cannot_crash_parser():
    xml = ('<hierarchy><node bounds="[0,0][' + "9" * 5000 + ',10]"/></hierarchy>').encode()
    assert parse_hierarchy(xml, width=100, height=100)[0].bounds is None


def test_parser_keeps_structure_and_redacts_password_descendants():
    xml = b"""<hierarchy><node resource-id="input" text="secret" password="true"
      content-desc="secret" bounds="[0,0][100,100]" enabled="true">
      <node text="nested secret" bounds="[1,1][2,2]"/>
      </node><node text="public" bounds="[0,0][10,10]" clickable="true" enabled="true"/></hierarchy>"""
    nodes = parse_hierarchy(xml, width=100, height=100)
    assert [n.node_id for n in nodes] == ["n1", "n2", "n3"]
    assert nodes[1].parent_id == "n1"
    assert nodes[0].text == nodes[0].content_desc == nodes[1].text == ""
    assert nodes[1].redacted
    assert nodes[2].text == "public"
    assert nodes[2].bounds == (0, 0, 10, 10)


@pytest.mark.parametrize("bounds", ["[-1,0][2,2]", "[0,0][101,20]", "[2,2][1,1]", "junk", "[1,1][1,1]"])
def test_bad_bounds_do_not_become_clickable_coordinates(bounds):
    xml = f'<hierarchy><node bounds="{bounds}"/></hierarchy>'.encode()
    assert parse_hierarchy(xml, width=100, height=100)[0].bounds is None


@pytest.mark.parametrize(
    "xml",
    [
        b"<broken",
        b"<other/>",
        b"<hierarchy><script/></hierarchy>",
        b'<!DOCTYPE hierarchy [<!ENTITY x SYSTEM "file:///etc/passwd">]><hierarchy>&x;</hierarchy>',
    ],
)
def test_malformed_or_external_entity_xml_is_rejected(xml):
    with pytest.raises(ObservationRejected):
        parse_hierarchy(xml, width=100, height=100)


@pytest.mark.parametrize(
    "xml,code",
    [
        (b"x" * (1024 * 1024 + 1), "ui_tree_too_large"),
        (b"<hierarchy>" + b"<node>" * 65 + b"</node>" * 65 + b"</hierarchy>", "ui_tree_complexity_limit"),
        (b"<hierarchy>" + b"<node/>" * 2001 + b"</hierarchy>", "ui_tree_complexity_limit"),
    ],
    ids=["bytes_limit", "depth_limit", "node_limit"],
)
def test_observation_resource_limits(xml, code):
    with pytest.raises(ObservationRejected, match=f"^{code}$"):
        parse_hierarchy(xml, width=100, height=100)


@pytest.mark.parametrize(
    "output,returncode,code",
    [
        (b"ERROR: could not get idle state.\r\n", 0, "ui_idle_timeout"),
        (b"ERROR: null root node returned by UiTestAutomationBridge.\r\n", 0, "ui_root_unavailable"),
        (b"", 1, "adb_capture_failed"),
        (b"<hierarchy></hierarchy>unexpected", 0, "invalid_ui_dump_envelope"),
    ],
)
def test_actual_device_error_envelopes_are_not_false_success(output, returncode, code):
    with pytest.raises(ObservationRejected, match=f"^{code}$"):
        parse_dump_output(output, returncode=returncode, width=100, height=100)


def test_adb_dump_footer_is_separated_from_xml():
    output = b'<hierarchy><node bounds="[0,0][1,1]"/></hierarchy>UI hierchary dumped to: /dev/tty\r\n'
    assert len(parse_dump_output(output, returncode=0, width=100, height=100)) == 1


def test_only_help_proposal_is_allowed_when_device_is_offline():
    data = {
        "schema_version": 1,
        "observation_id": "obs-1",
        "action": "request_help",
        "reason": "device disconnected",
        "code": "cannot_progress",
    }
    assert validate_context(parse_decision(json.dumps(data)), **context(device_online=False)) is None
    data = {"schema_version": 1, "observation_id": "obs-1", "action": "finish", "reason": "done"}
    with pytest.raises(DecisionRejected, match="^device_offline$"):
        validate_context(parse_decision(json.dumps(data)), **context(device_online=False))
