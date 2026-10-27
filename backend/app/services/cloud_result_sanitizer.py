"""Sanitize test results into lightweight, PII-redacted cloud summary contracts (D2)."""

from __future__ import annotations

from typing import Any
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.local_machine_identity import get_machine_id, get_machine_name
from app.schemas.cloud_sync import CloudRunSummary, CloudStepSummary
from app.services.sensitive_data_redactor import mask_pii_text


def _clean_text(val: Any, max_len: int = 1024) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    masked = mask_pii_text(s)
    return masked[:max_len]


def _clean_error_summary(val: Any) -> str | None:
    """Never export free-form execution errors, which can contain credentials or bodies."""
    return "执行失败；详细错误仅保存在本机报告" if val else None


def sanitize_queued_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip legacy free-form errors from outbox entries created before this fix."""
    safe = dict(payload)
    safe["error_summary"] = _clean_error_summary(payload.get("error_summary"))
    safe["steps"] = [
        {**step, "error_summary": _clean_error_summary(step.get("error_summary"))} for step in payload.get("steps", [])
    ]
    return safe


def _query_first(connection: Connection, query: str, params: dict[str, Any]) -> Any:
    result = connection.execute(text(query), params)
    if result is None:
        return None
    return result.mappings().first()


def _query_all(connection: Connection, query: str, params: dict[str, Any]) -> list[Any]:
    result = connection.execute(text(query), params)
    if result is None:
        return []
    return list(result.mappings().all())


def _map_task_to_run_type(task_name: str) -> str:
    mapping = {
        "run_test_case": "case",
        "run_test_suite": "suite",
        "run_test_plan": "plan",
        "run_mobile_special_task": "mobile_special",
        "run_performance_test": "performance",
    }
    return mapping.get(task_name, task_name)


def build_cloud_run_summary(
    connection: Connection,
    task_name: str,
    run_id: int,
    client_id: str | None = None,
    machine_name: str | None = None,
) -> CloudRunSummary:
    """Build a versioned, PII-redacted CloudRunSummary from local SQLite run tables."""
    cid = client_id or get_machine_id()
    mname = machine_name or get_machine_name()
    run_type = _map_task_to_run_type(task_name)
    unique_key = f"{cid}:{run_type}:{run_id}"

    if run_type == "case":
        return _build_case_summary(connection, cid, mname, unique_key, run_id)
    elif run_type == "suite":
        return _build_suite_summary(connection, cid, mname, unique_key, run_id)
    elif run_type == "plan":
        return _build_plan_summary(connection, cid, mname, unique_key, run_id)
    elif run_type == "mobile_special":
        return _build_mobile_summary(connection, cid, mname, unique_key, run_id)
    elif run_type == "performance":
        return _build_performance_summary(connection, cid, mname, unique_key, run_id)
    else:
        return _build_generic_summary(cid, mname, unique_key, run_type, run_id)


def _build_case_summary(
    connection: Connection, client_id: str, machine_name: str, unique_key: str, run_id: int
) -> CloudRunSummary:
    row = _query_first(
        connection,
        """
        SELECT r.id, r.status, r.created_at, r.updated_at, r.duration_ms, r.error_message, r.environment,
               c.name as case_name, p.name as project_name, p.project_code, u.username
        FROM test_runs r
        LEFT JOIN test_cases c ON r.case_id = c.id
        LEFT JOIN modules m ON c.module_id = m.id
        LEFT JOIN projects p ON m.project_id = p.id
        LEFT JOIN users u ON r.triggered_by = u.id
        WHERE r.id = :run_id
        """,
        {"run_id": run_id},
    )

    if row is None:
        return _fallback_summary(client_id, machine_name, unique_key, "case", run_id)

    step_rows = _query_all(
        connection,
        """
        SELECT step_index, name, status, duration_ms, error_message
        FROM step_results
        WHERE run_id = :run_id
        ORDER BY step_index ASC
        """,
        {"run_id": run_id},
    )

    steps = [
        CloudStepSummary(
            step_index=s["step_index"],
            name=_clean_text(s["name"], 256) or f"Step {s['step_index']}",
            status=str(s["status"] or "unknown"),
            duration_ms=s["duration_ms"],
            error_summary=_clean_error_summary(s["error_message"]),
        )
        for s in step_rows
    ]

    total_steps = len(steps)
    passed_steps = sum(1 for s in steps if s.status == "passed")

    return CloudRunSummary(
        schema_version=1,
        client_id=client_id,
        machine_name=machine_name,
        unique_key=unique_key,
        run_type="case",
        run_id=run_id,
        project_name=_clean_text(row["project_name"], 128) or "Local Project",
        project_code=_clean_text(row["project_code"], 64) or "LOCAL",
        title=_clean_text(row["case_name"], 256) or f"Case Run #{run_id}",
        status=str(row["status"] or "unknown"),
        started_at=row["created_at"],
        finished_at=row["updated_at"],
        duration_ms=row["duration_ms"],
        triggered_by=_clean_text(row["username"], 64) or "admin",
        environment=_clean_text(row["environment"], 64),
        metrics={"total_steps": total_steps, "passed_steps": passed_steps},
        error_summary=_clean_error_summary(row["error_message"]),
        steps=steps,
    )


def _build_suite_summary(
    connection: Connection, client_id: str, machine_name: str, unique_key: str, run_id: int
) -> CloudRunSummary:
    row = _query_first(
        connection,
        """
        SELECT r.id, r.status, r.created_at, r.updated_at, r.duration_ms, r.error_message,
               r.total_cases, r.passed_cases, r.failed_cases, r.error_cases, r.skipped_cases,
               s.name as suite_name, p.name as project_name, p.project_code, u.username
        FROM suite_runs r
        LEFT JOIN test_suites s ON r.suite_id = s.id
        LEFT JOIN projects p ON s.project_id = p.id
        LEFT JOIN users u ON r.triggered_by = u.id
        WHERE r.id = :run_id
        """,
        {"run_id": run_id},
    )

    if row is None:
        return _fallback_summary(client_id, machine_name, unique_key, "suite", run_id)

    total = row["total_cases"] or 0
    passed = row["passed_cases"] or 0
    failed = row["failed_cases"] or 0
    error_cnt = row["error_cases"] or 0
    skipped = row["skipped_cases"] or 0
    pass_rate = round((passed / total * 100), 2) if total > 0 else 0.0

    return CloudRunSummary(
        schema_version=1,
        client_id=client_id,
        machine_name=machine_name,
        unique_key=unique_key,
        run_type="suite",
        run_id=run_id,
        project_name=_clean_text(row["project_name"], 128) or "Local Project",
        project_code=_clean_text(row["project_code"], 64) or "LOCAL",
        title=_clean_text(row["suite_name"], 256) or f"Suite Run #{run_id}",
        status=str(row["status"] or "unknown"),
        started_at=row["created_at"],
        finished_at=row["updated_at"],
        duration_ms=row["duration_ms"],
        triggered_by=_clean_text(row["username"], 64) or "admin",
        metrics={
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": failed,
            "error_cases": error_cnt,
            "skipped_cases": skipped,
            "pass_rate": pass_rate,
        },
        error_summary=_clean_error_summary(row["error_message"]),
        steps=[],
    )


def _build_plan_summary(
    connection: Connection, client_id: str, machine_name: str, unique_key: str, run_id: int
) -> CloudRunSummary:
    row = _query_first(
        connection,
        """
        SELECT r.id, r.status, r.created_at, r.updated_at, r.duration_ms, r.error_message,
               r.total_cases, r.passed_cases, r.failed_cases, r.error_cases, r.skipped_cases,
               pl.name as plan_name, p.name as project_name, p.project_code, u.username
        FROM plan_runs r
        LEFT JOIN test_plans pl ON r.plan_id = pl.id
        LEFT JOIN projects p ON pl.project_id = p.id
        LEFT JOIN users u ON r.triggered_by = u.id
        WHERE r.id = :run_id
        """,
        {"run_id": run_id},
    )

    if row is None:
        return _fallback_summary(client_id, machine_name, unique_key, "plan", run_id)

    total = row["total_cases"] or 0
    passed = row["passed_cases"] or 0
    failed = row["failed_cases"] or 0
    pass_rate = round((passed / total * 100), 2) if total > 0 else 0.0

    return CloudRunSummary(
        schema_version=1,
        client_id=client_id,
        machine_name=machine_name,
        unique_key=unique_key,
        run_type="plan",
        run_id=run_id,
        project_name=_clean_text(row["project_name"], 128) or "Local Project",
        project_code=_clean_text(row["project_code"], 64) or "LOCAL",
        title=_clean_text(row["plan_name"], 256) or f"Plan Run #{run_id}",
        status=str(row["status"] or "unknown"),
        started_at=row["created_at"],
        finished_at=row["updated_at"],
        duration_ms=row["duration_ms"],
        triggered_by=_clean_text(row["username"], 64) or "admin",
        metrics={
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": failed,
            "error_cases": row["error_cases"] or 0,
            "skipped_cases": row["skipped_cases"] or 0,
            "pass_rate": pass_rate,
        },
        error_summary=_clean_error_summary(row["error_message"]),
        steps=[],
    )


def _build_mobile_summary(
    connection: Connection, client_id: str, machine_name: str, unique_key: str, run_id: int
) -> CloudRunSummary:
    row = _query_first(
        connection,
        """
        SELECT r.id, r.status, r.created_at, r.updated_at, r.duration_ms,
               t.name as task_name, t.task_type, t.package_name,
               p.name as project_name, p.project_code, u.username
        FROM mobile_special_runs r
        LEFT JOIN mobile_special_tasks t ON r.task_id = t.id
        LEFT JOIN projects p ON t.project_id = p.id
        LEFT JOIN users u ON r.triggered_by = u.id
        WHERE r.id = :run_id
        """,
        {"run_id": run_id},
    )

    if row is None:
        return _fallback_summary(client_id, machine_name, unique_key, "mobile_special", run_id)

    return CloudRunSummary(
        schema_version=1,
        client_id=client_id,
        machine_name=machine_name,
        unique_key=unique_key,
        run_type="mobile_special",
        run_id=run_id,
        project_name=_clean_text(row["project_name"], 128) or "Local Project",
        project_code=_clean_text(row["project_code"], 64) or "LOCAL",
        title=_clean_text(row["task_name"], 256) or f"Mobile Run #{run_id}",
        status=str(row["status"] or "unknown"),
        started_at=row["created_at"],
        finished_at=row["updated_at"],
        duration_ms=row["duration_ms"],
        triggered_by=_clean_text(row["username"], 64) or "admin",
        metrics={"package_name": row["package_name"], "task_type": row["task_type"]},
        error_summary=None,
        steps=[],
    )


def _build_performance_summary(
    connection: Connection, client_id: str, machine_name: str, unique_key: str, run_id: int
) -> CloudRunSummary:
    row = _query_first(
        connection,
        """
        SELECT r.id, r.status, r.created_at, r.updated_at, r.error_message,
               t.name as test_name, p.name as project_name, p.project_code, u.username
        FROM performance_runs r
        LEFT JOIN performance_tests t ON r.performance_test_id = t.id
        LEFT JOIN projects p ON t.project_id = p.id
        LEFT JOIN users u ON r.triggered_by = u.id
        WHERE r.id = :run_id
        """,
        {"run_id": run_id},
    )

    if row is None:
        return _fallback_summary(client_id, machine_name, unique_key, "performance", run_id)

    return CloudRunSummary(
        schema_version=1,
        client_id=client_id,
        machine_name=machine_name,
        unique_key=unique_key,
        run_type="performance",
        run_id=run_id,
        project_name=_clean_text(row["project_name"], 128) or "Local Project",
        project_code=_clean_text(row["project_code"], 64) or "LOCAL",
        title=_clean_text(row["test_name"], 256) or f"Performance Run #{run_id}",
        status=str(row["status"] or "unknown"),
        started_at=row["created_at"],
        finished_at=row["updated_at"],
        duration_ms=None,
        triggered_by=_clean_text(row["username"], 64) or "admin",
        metrics={},
        error_summary=_clean_error_summary(row["error_message"]),
        steps=[],
    )


def _build_generic_summary(
    client_id: str, machine_name: str, unique_key: str, run_type: str, run_id: int
) -> CloudRunSummary:
    return _fallback_summary(client_id, machine_name, unique_key, run_type, run_id)


def _fallback_summary(
    client_id: str, machine_name: str, unique_key: str, run_type: str, run_id: int
) -> CloudRunSummary:
    return CloudRunSummary(
        schema_version=1,
        client_id=client_id,
        machine_name=machine_name,
        unique_key=unique_key,
        run_type=run_type,
        run_id=run_id,
        project_name="Local Project",
        project_code="LOCAL",
        title=f"{run_type.capitalize()} Run #{run_id}",
        status="completed",
        metrics={},
        error_summary=None,
        steps=[],
    )
