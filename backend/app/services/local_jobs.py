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
_TASKS = {"run_test_case", "run_test_suite", "run_test_plan", "run_mobile_special_task"}
_RUN_TABLES = {
    "run_test_case": "test_runs",
    "run_test_suite": "suite_runs",
    "run_test_plan": "plan_runs",
    "run_mobile_special_task": "mobile_special_runs",
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
        connection.execute(
            text(
                "INSERT INTO local_jobs(task_name, run_id, run_created_at, args_json) "
                "VALUES (:name, :run_id, :created_at, :payload)"
            ),
            {"name": task_name, "run_id": args[0], "created_at": run_created_at, "payload": payload},
        )


def _mark_run_error(
    connection: Any, task_name: str, run_id: int, message: str, run_created_at: str | None = None
) -> bool:
    table = _RUN_TABLES[task_name]
    identity_clause = " AND created_at=:created_at" if run_created_at is not None else ""
    if task_name == "run_mobile_special_task":
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
            text("SELECT id, task_name, run_id, run_created_at FROM local_jobs WHERE status='running'")
        ).all()
        for job_id, task_name, run_id, run_created_at in rows:
            _mark_run_error(connection, task_name, run_id, _INTERRUPTED, run_created_at)
            same_mobile_run = (
                task_name == "run_mobile_special_task"
                and connection.execute(
                    text("SELECT id FROM mobile_special_runs WHERE id=:run_id AND created_at=:created_at"),
                    {"run_id": run_id, "created_at": run_created_at},
                ).scalar_one_or_none()
                is not None
            )
            if same_mobile_run:
                connection.execute(
                    text(
                        "DELETE FROM device_leases WHERE owner_label=:label AND device_id=("
                        "SELECT device_id FROM mobile_special_runs WHERE id=:run_id AND created_at=:created_at)"
                    ),
                    {"run_id": run_id, "created_at": run_created_at, "label": f"mobile-run:{run_id}"},
                )
                connection.execute(
                    text(
                        "UPDATE execution_run_leases SET status='released', released_at=CURRENT_TIMESTAMP "
                        "WHERE task_type='android' AND run_id=:run_id AND status='active'"
                    ),
                    {"run_id": run_id},
                )
            connection.execute(
                text(
                    "UPDATE local_jobs SET status='interrupted', error=:error, "
                    "finished_at=CURRENT_TIMESTAMP WHERE id=:id"
                ),
                {"id": job_id, "error": _INTERRUPTED},
            )
    return len(rows)


def _run_next_job() -> bool:
    with _engine().begin() as connection:
        row = connection.execute(
            text(
                "SELECT id, task_name, run_id, run_created_at, args_json FROM local_jobs "
                "WHERE status='queued' ORDER BY id LIMIT 1"
            )
        ).first()
        if row is None:
            return False
        job_id, task_name, run_id, run_created_at, payload = row
        connection.execute(
            text("UPDATE local_jobs SET status='running', started_at=CURRENT_TIMESTAMP WHERE id=:id"),
            {"id": job_id},
        )

    table = _RUN_TABLES[task_name]
    with _engine().begin() as connection:
        current = connection.execute(
            text(f"SELECT created_at, status FROM {table} WHERE id=:run_id"), {"run_id": run_id}
        ).first()
        if current is None or current[0] != run_created_at or current[1] != "pending":
            connection.execute(
                text("UPDATE local_jobs SET status='skipped', finished_at=CURRENT_TIMESTAMP WHERE id=:id"),
                {"id": job_id},
            )
            if task_name == "run_mobile_special_task":
                from app.services.mobile_special_control import clear_cancel_request

                clear_cancel_request(run_id)
            return True

    try:
        if task_name == "run_mobile_special_task":
            from app.worker import tasks_mobile_special

            task = tasks_mobile_special.run_mobile_special_task
        else:
            from app.worker import tasks

            task = getattr(tasks, task_name)

        args = json.loads(decrypt(payload))
        result = task.apply(args=args)
        if result.failed():
            raise RuntimeError(str(result.result))
        table = _RUN_TABLES[task_name]
        with _engine().connect() as connection:
            final_status = connection.execute(
                text(f"SELECT status FROM {table} WHERE id=:run_id AND created_at=:created_at"),
                {"run_id": run_id, "created_at": run_created_at},
            ).scalar_one_or_none()
        if final_status in {"pending", "running"}:
            raise RuntimeError("local task returned without a terminal run state")
    except Exception:
        logger.exception("Local execution job %s failed", job_id)
        with _engine().begin() as connection:
            _mark_run_error(connection, task_name, run_id, "本地执行失败；请查看本地日志", run_created_at)
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
