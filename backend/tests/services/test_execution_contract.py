from app.services.execution_contract import assertion_result, extraction_result, response_contract


def test_response_contract_has_common_protocol_neutral_shape():
    result = response_contract("http", status_code=200, headers={"x-id": "1"}, body={"ok": True}, duration_ms=8)

    assert result["contract_version"] == 1
    assert result["protocol"] == "http"
    assert result["status_code"] == 200
    assert result["assertions"] == []
    assert result["extractions"] == []


def test_assertion_and_extraction_records_keep_actionable_context():
    assertion = assertion_result(
        {"target": "body", "operator": "eq", "expected": "ok", "expression": "$.status"},
        passed=False,
        actual="failed",
        message="断言失败",
    )
    extraction = extraction_result(
        {"variable": "token", "type": "jsonpath", "expression": "$.token"},
        success=True,
        value="t-1",
    )

    assert assertion["passed"] is False
    assert assertion["actual"] == "failed"
    assert extraction["variable"] == "token"
    assert extraction["value"] == "t-1"
