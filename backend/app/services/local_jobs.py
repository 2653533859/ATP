"""Single-process durable execution queue for the Windows SQLite profile."""

from __future__ import annotations

import json
import logging
from threading import Event, Thread
from typing import Any

from sqlalchemy import text

from app.core.encryption import decrypt, encrypt

logger = logging.getLogger(__name__)
_stop = Event()
_thread: Thread | None = None
_TASKS = {"run_test_case", "run_test_suite", "run_test_plan", "run_mobile_special_task", "run_performance_test"}
_RUN_TABLES = {
    "run_test_case": "test_runs",
    "run_test_suite": "suite_runs",
    "run_test_plan": "plan_runs",
    "run_mobile_special_task": "mobile_special_runs",
    "run_performance_test": "performance_runs",
}
_INTERRUPTED = "本地 ATP 在执行期间退出；请检查副作用后重新运行"


def _engine() -> Any:
    from app.core.database import sync_engine

    return sync_engine


def enqueue_local_job(task: Any, args: tuple[Any, ...]) -> None:
    task_name = str(getattr(task, "name", ""))
    if task_name not in _TASKS:
        raise ValueError(f"unsupported local task: {task_name}")
    if not args or not isinstance(args[0], int):
        raise ValueError("local task requires a run id")
    payload = encrypt(json.dumps(args, ensure_ascii=False))
    with _engine().begin() as connection:
        table = _RUN_TABLES[task_name]
        run_created_at = connection.execute(
            text(f"SELECT created_at FROM {table} WHERE id=:run_id"), {"run_id": args[0]}
        ).scalar_one_or_none()
        if run_created_at is None:
            raise ValueError("local run was removed before enqueue")
        run_identity = None
        if task_name in {"run_test_suite", "run_test_plan"}:
            run_identity = connection.execute(
                text(f"SELECT identity_token FROM {table} WHERE id=:id AND created_at=:created"),
                {"id": args[0], "created": run_created_at},
            ).scalar_one_or_none()
        connection.execute(
            text(
                "INSERT INTO local_jobs(task_name, run_id, run_created_at, args_json, run_identity) "
                "VALUES (:name, :run_id, :created_at, :payload, :identity)"
            ),
            {
                "name": task_name,
                "run_id": args[0],
                "created_at": run_created_at,
                "payload": payload,
                "identity": run_identity,
            },
        )


def _mark_run_error(
    connection: Any, task_name: str, run_id: int, message: str, run_created_at: str | None = None
) -> bool:
    table = _RUN_TABLES[task_name]
    identity_clause = " AND created_at=:created_at" if run_created_at is not None else ""
    if task_name == "run_performance_test":
        statement = (
            f"UPDATE {table} SET status=CASE WHEN status='cancelling' THEN 'cancelled' ELSE 'failed' END, "
            f"error_message=:message, finished_at=CURRENT_TIMESTAMP "
            f"WHERE id=:run_id AND status IN ('pending', 'running', 'cancelling'){identity_clause}"
        )
    elif task_name == "run_mobile_special_task":
        statement = (
            f"UPDATE {table} SET status='failed', summary_json=:message, finished_at=CURRENT_TIMESTAMP "
            f"WHERE id=:run_id AND status IN ('pending', 'running'){identity_clause}"
        )
        message = json.dumps({"error_message": message}, ensure_ascii=False)
    else:
        statement = (
            f"UPDATE {table} SET status='error', error_message=:message "
            f"WHERE id=:run_id AND status IN ('pending', 'running'){identity_clause}"
        )
    result = connection.execute(text(statement), {"run_id": run_id, "message": message, "created_at": run_created_at})
    return bool(result.rowcount)


def recover_interrupted_jobs() -> int:
    """Keep queued jobs, but never repeat a task that may have caused side effects."""
    with _engine().begin() as connection:
        rows = connection.execute(
            text("SELECT id, task_name, run_id, run_created_at, run_identity FROM local_jobs WHERE status='running'")
        ).all()
        for job_id, task_name, run_id, run_created_at, run_identity in rows:
            if run_created_at is not None and _same_suite_identity(connection, task_name, run_id, run_identity):
                _recover_interrupted_run(connection, task_name, run_id, _INTERRUPTED, run_created_at)
            connection.execute(
                text(
                    "UPDATE local_jobs SET status='interrupted', error=:error, "
                    "finished_at=CURRENT_TIMESTAMP WHERE id=:id"
                ),
                {"id": job_id, "error": _INTERRUPTED},
            )
    return len(rows)


def _same_suite_identity(connection: Any, task_name: str, run_id: int, identity: str | None) -> bool:
    if task_name not in {"run_test_suite", "run_test_plan"}:
        return True
    if not identity:
        return False
    return (
        connection.execute(
            text(f"SELECT id FROM {_RUN_TABLES[task_name]} WHERE id=:id AND identity_token=:identity"),
            {"id": run_id, "identity": identity},
        ).scalar_one_or_none()
        is not None
    )


def _recover_interrupted_run(
    connection: Any,
    task_name: str,
    run_id: int,
    message: str,
    run_created_at: str,
    visited: set[tuple[str, int]] | None = None,
) -> None:
    """Preserve terminal results, but clean leases after confirming run identity."""
    visited = visited if visited is not None else set()
    key = (task_name, run_id)
    if key in visited:
        return
    table = _RUN_TABLES[task_name]
    same_run = connection.execute(
        text(f"SELECT id FROM {table} WHERE id=:id AND created_at=:created_at"),
        {"id": run_id, "created_at": run_created_at},
    ).scalar_one_or_none()
    if same_run is None:
        return
    visited.add(key)
    _mark_run_error(connection, task_name, run_id, message, run_created_at)
    _release_interrupted_run(connection, task_name, run_id, message, visited)


def _release_interrupted_run(
    connection: Any, task_name: str, run_id: int, message: str, visited: set[tuple[str, int]]
) -> None:
    """Release only this interrupted run and its persisted inline children."""
    from sqlalchemy import inspect

    tables = set(inspect(connection).get_table_names())
    lease_type = {
        "run_test_case": "case",
        "run_test_suite": "suite",
        "run_test_plan": "plan",
        "run_performance_test": "performance",
        "run_mobile_special_task": "android",
    }[task_name]
    if "execution_run_leases" in tables:
        run_identity = None
        if task_name in {"run_test_suite", "run_test_plan"}:
            run_identity = connection.execute(
                text(f"SELECT identity_token FROM {_RUN_TABLES[task_name]} WHERE id=:id"), {"id": run_id}
            ).scalar_one_or_none()
        identity_clause = " AND run_identity=:identity" if task_name in {"run_test_suite", "run_test_plan"} else ""
        connection.execute(
            text(
                "UPDATE execution_run_leases SET status='released', released_at=CURRENT_TIMESTAMP "
                f"WHERE task_type=:type AND run_id=:id AND status='active'{identity_clause}"
            ),
            {"type": lease_type, "id": run_id, "identity": run_identity},
        )
    if task_name in {"run_test_case", "run_mobile_special_task"} and "device_leases" in tables:
        label = f"case-run:{run_id}" if task_name == "run_test_case" else f"mobile-run:{run_id}"
        device_clause = (
            " AND device_id=(SELECT device_id FROM mobile_special_runs WHERE id=:id)"
            if task_name == "run_mobile_special_task"
            else ""
        )
        device_ids = (
            connection.execute(
                text(f"SELECT device_id FROM device_leases WHERE owner_label=:label{device_clause}"),
                {"label": label, "id": run_id},
            )
            .scalars()
            .all()
        )
        connection.execute(
            text(f"DELETE FROM device_leases WHERE owner_label=:label{device_clause}"),
            {"label": label, "id": run_id},
        )
        if "devices" in tables:
            for device_id in device_ids:
                connection.execute(
                    text(
                        "UPDATE devices SET status='online' WHERE id=:id AND status='busy' "
                        "AND NOT EXISTS (SELECT 1 FROM device_leases WHERE device_id=:id)"
                    ),
                    {"id": device_id},
                )
    if task_name == "run_test_case":
        columns = {item["name"] for item in inspect(connection).get_columns("test_runs")}
        if "parent_run_id" in columns:
            children = connection.execute(
                text("SELECT id, created_at FROM test_runs WHERE parent_run_id=:id"), {"id": run_id}
            ).all()
            for child_id, child_created_at in children:
                _recover_interrupted_run(connection, task_name, child_id, message, child_created_at, visited)
    group = {
        "run_test_suite": ("case_run_ids", "run_id", "run_test_case"),
        "run_test_plan": ("suite_run_ids", "suite_run_id", "run_test_suite"),
    }.get(task_name)
    if group is None:
        return
    _column, _child_key, child_task = group
    table = _RUN_TABLES[task_name]
    identity = connection.execute(text(f"SELECT identity_token FROM {table} WHERE id=:id"), {"id": run_id}).scalar()
    kind = "suite" if task_name == "run_test_suite" else "plan"
    # Never infer an old child's identity from a reused numeric ID in JSON.
    children = connection.execute(
        text(
            "SELECT child_id, child_identity FROM group_run_children "
            "WHERE parent_kind=:kind AND parent_run_id=:id AND parent_identity=:identity"
        ),
        {"kind": kind, "id": run_id, "identity": identity},
    ).all()
    for child_id, child_identity in children:
        child_table = _RUN_TABLES[child_task]
        if child_task == "run_test_suite":
            child_created_at = connection.execute(
                text("SELECT created_at FROM suite_runs WHERE id=:id AND identity_token=:identity"),
                {"id": child_id, "identity": child_identity},
            ).scalar_one_or_none()
        else:
            child_created_at = connection.execute(
                text(f"SELECT created_at FROM {child_table} WHERE id=:id AND created_at=:identity"),
                {"id": child_id, "identity": child_identity},
            ).scalar_one_or_none()
        if child_created_at is not None:
            _recover_interrupted_run(connection, child_task, child_id, message, child_created_at, visited)


def _run_next_job() -> bool:
    with _engine().begin() as connection:
        row = connection.execute(
            text(
                "SELECT id, task_name, run_id, run_created_at, args_json, dispatch_id, run_identity FROM local_jobs "
                "WHERE status='queued' ORDER BY id LIMIT 1"
            )
        ).first()
        if row is None:
            return False
        job_id, task_name, run_id, run_created_at, payload, dispatch_id, run_identity = row
        claimed = connection.execute(
            text(
                "UPDATE local_jobs SET status='running', started_at=CURRENT_TIMESTAMP WHERE id=:id AND status='queued'"
            ),
            {"id": job_id},
        )
        if claimed.rowcount != 1:
            return False

    table = _RUN_TABLES[task_name]
    with _engine().begin() as connection:
        current = connection.execute(
            text(f"SELECT created_at, status FROM {table} WHERE id=:run_id"), {"run_id": run_id}
        ).first()
        if (
            current is None
            or current[0] != run_created_at
            or current[1] != "pending"
            or not _same_suite_identity(connection, task_name, run_id, run_identity)
        ):
            connection.execute(
                text("UPDATE local_jobs SET status='skipped', finished_at=CURRENT_TIMESTAMP WHERE id=:id"),
                {"id": job_id},
            )
            if task_name == "run_mobile_special_task":
                from app.services.mobile_special_control import clear_cancel_request

                clear_cancel_request(run_id)
            elif task_name == "run_performance_test":
                from app.services.performance_control import clear_cancel_request as clear_perf_cancel

                clear_perf_cancel(run_id)
            # 已判定跳过：不得继续派发，否则任务会真的执行并把 skipped 覆盖成终态。
            return True

    try:
        if task_name == "run_mobile_special_task":
            from app.worker import tasks_mobile_special

            task = tasks_mobile_special.run_mobile_special_task
        elif task_name == "run_performance_test":
            from app.worker import tasks_performance

            task = tasks_performance.run_performance_test
        else:
            from app.worker import tasks

            task = getattr(tasks, task_name)

        args = json.loads(decrypt(payload))
        if not isinstance(args, list) or not args or type(args[0]) is not int or args[0] != run_id:
            raise ValueError("local queue payload does not match run")
        options = {}
        if dispatch_id:
            if task_name != "run_test_suite" or not run_identity:
                raise ValueError("invalid local dispatch identity")
            options = {
                "task_id": dispatch_id,
                "headers": {"atp_dispatch_id": dispatch_id, "atp_run_identity": run_identity},
            }
        result = task.apply(args=args, **options)
        if result.failed():
            raise RuntimeError(str(result.result))
        if task_name == "run_test_suite":
            from app.services.suite_delivery import SUITE_DELIVERY_SKIPPED

            if result.result == SUITE_DELIVERY_SKIPPED:
                with _engine().begin() as connection:
                    connection.execute(
                        text("UPDATE local_jobs SET status='skipped', finished_at=CURRENT_TIMESTAMP WHERE id=:id"),
                        {"id": job_id},
                    )
                return True
        table = _RUN_TABLES[task_name]
        with _engine().connect() as connection:
            final_status = connection.execute(
                text(f"SELECT status FROM {table} WHERE id=:run_id AND created_at=:created_at"),
                {"run_id": run_id, "created_at": run_created_at},
            ).scalar_one_or_none()
        if final_status in {"pending", "running", "cancelling"}:
            raise RuntimeError("local task returned without a terminal run state")
    except Exception:
        logger.warning("Local execution job %s failed; inspect its run and dispatch state", job_id)
        with _engine().begin() as connection:
            if _same_suite_identity(connection, task_name, run_id, run_identity):
                _recover_interrupted_run(connection, task_name, run_id, "本地执行失败；请查看本地日志", run_created_at)
            connection.execute(
                text(
                    "UPDATE local_jobs SET status='failed', error=:error, " "finished_at=CURRENT_TIMESTAMP WHERE id=:id"
                ),
                {"id": job_id, "error": "执行失败；详情见本地日志"},
            )
    else:
        with _engine().begin() as connection:
            connection.execute(
                text("UPDATE local_jobs SET status='finished', finished_at=CURRENT_TIMESTAMP WHERE id=:id"),
                {"id": job_id},
            )
    return True


def _loop() -> None:
    while not _stop.is_set():
        try:
            if _run_next_job():
                continue
        except Exception:
            logger.exception("Local execution queue polling failed")
        _stop.wait(0.5)


def start_local_runner() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    recover_interrupted_jobs()
    _stop.clear()
    _thread = Thread(target=_loop, name="atp-local-jobs", daemon=True)
    _thread.start()


def stop_local_runner() -> None:
    _stop.set()
    if _thread:
        _thread.join(timeout=2)
