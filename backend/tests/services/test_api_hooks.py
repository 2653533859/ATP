import pytest

from app.services.api_hooks import ApiHookError, execute_api_hooks


def test_hooks_set_delete_assert_and_extract_values():
    context = {"user": "alice", "token": "old"}

    summaries = execute_api_hooks(
        [
            {"action": "set_variable", "variable": "request_id", "value": "{{user}}-1"},
            {"action": "assert", "variable": "request_id", "operator": "eq", "expected": "alice-1"},
            {"action": "extract", "variable": "server_token", "expression": "$.token"},
            {"action": "delete_variable", "variable": "token"},
        ],
        context,
        response_body={"token": "new"},
    )

    assert context == {"user": "alice", "request_id": "alice-1", "server_token": "new"}
    assert [item["action"] for item in summaries] == ["set_variable", "assert", "extract", "delete_variable"]


def test_hooks_support_xml_and_header_extraction():
    context = {}

    execute_api_hooks(
        [
            {"action": "extract", "variable": "user_id", "type": "xpath", "expression": "//user/@id"},
            {"action": "extract", "variable": "request_id", "source": "header", "expression": "x-request-id"},
        ],
        context,
        response_body="<root><user id='u-1'/></root>",
        response_headers={"x-request-id": "r-1"},
    )

    assert context == {"user_id": "u-1", "request_id": "r-1"}


@pytest.mark.parametrize(
    "action",
    [
        {"action": "set_variable", "variable": "bad-name", "value": "x"},
        {"action": "run_python", "variable": "x"},
        {"action": "extract", "variable": "x", "expression": "$.missing"},
    ],
)
def test_hooks_reject_unsafe_or_invalid_actions(action):
    with pytest.raises(ApiHookError):
        execute_api_hooks([action], {}, response_body={"ok": True})
