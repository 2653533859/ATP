"""Common response, extraction and assertion records for API-family executors."""

from __future__ import annotations

from typing import Any


EXECUTION_CONTRACT_VERSION = 1


def response_contract(
    protocol: str,
    *,
    duration_ms: int | None = None,
    status_code: int | None = None,
    headers: dict[str, Any] | None = None,
    body: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the protocol-neutral response envelope while retaining legacy fields."""

    result: dict[str, Any] = {
        "contract_version": EXECUTION_CONTRACT_VERSION,
        "protocol": protocol,
        "duration_ms": duration_ms,
        "body": body,
        "headers": headers or {},
        "metadata": metadata or {},
        "assertions": [],
        "extractions": [],
    }
    if status_code is not None:
        result["status_code"] = status_code
    return result


def extraction_result(
    extraction: dict[str, Any],
    *,
    value: Any = None,
    success: bool,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "variable": extraction.get("variable"),
        "type": extraction.get("type", "jsonpath"),
        "expression": extraction.get("expression", ""),
        "success": success,
        "value": value if success else None,
        "error": error,
    }


def assertion_result(
    assertion: dict[str, Any],
    *,
    passed: bool,
    message: str = "",
    actual: Any = None,
) -> dict[str, Any]:
    return {
        "target": assertion.get("target"),
        "operator": assertion.get("operator"),
        "expected": assertion.get("expected"),
        "expression": assertion.get("expression", ""),
        "passed": passed,
        "actual": actual,
        "message": message,
    }
