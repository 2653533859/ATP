"""Versioned SQLite schema lifecycle for the single-user Windows profile.

Version 1 is the mapped schema first shipped with the local prototype. Existing
unversioned prototype databases are adopted only after their table/column
layout matches that baseline. Every later model change needs an explicit
versioned migration here; ``create_all`` must never silently patch old data.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Engine, inspect
from sqlalchemy.engine import Connection

from app.models.base import Base

CURRENT_LOCAL_SCHEMA_VERSION = 4


def _create_job_queue(connection: Connection, table_name: str = "local_jobs") -> None:
    connection.exec_driver_sql(f"""CREATE TABLE {table_name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_name TEXT NOT NULL,
        run_id INTEGER NOT NULL,
        run_created_at TEXT,
        args_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued',
        error TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        started_at TEXT,
        finished_at TEXT,
        UNIQUE(task_name, run_id, run_created_at)
    )""")
    if table_name == "local_jobs":
        connection.exec_driver_sql("CREATE INDEX ix_local_jobs_status_id ON local_jobs(status, id)")


def _upgrade_job_queue_identity(connection: Connection) -> None:
    """Old SQLite run IDs may be reused after a case is deleted."""
    _create_job_queue(connection, "local_jobs_next")
    rows = connection.exec_driver_sql(
        "SELECT id, task_name, run_id, args_json, status, error, created_at, started_at, finished_at " "FROM local_jobs"
    ).all()
    for row in rows:
        job_id, task_name, run_id, payload, status, error, created_at, started_at, finished_at = row
        if status in {"queued", "running"}:
            status, error = "interrupted", "本地队列升级；请检查原运行后重新提交"
            table = {"run_test_case": "test_runs", "run_test_suite": "suite_runs", "run_test_plan": "plan_runs"}.get(
                task_name
            )
            if table:
                connection.exec_driver_sql(
                    f"UPDATE {table} SET status='error', error_message=? "
                    "WHERE id=? AND status IN ('pending', 'running')",
                    (error, run_id),
                )
        connection.exec_driver_sql(
            "INSERT INTO local_jobs_next(id, task_name, run_id, args_json, status, error, "
            "created_at, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, task_name, run_id, payload, status, error, created_at, started_at, finished_at),
        )
    connection.exec_driver_sql("DROP TABLE local_jobs")
    connection.exec_driver_sql("ALTER TABLE local_jobs_next RENAME TO local_jobs")
    connection.exec_driver_sql("CREATE INDEX ix_local_jobs_status_id ON local_jobs(status, id)")


def _create_run_id_allocator(connection: Connection) -> None:
    connection.exec_driver_sql("CREATE TABLE local_run_ids (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    highest = connection.exec_driver_sql(
        "SELECT MAX(value) FROM ("
        "SELECT COALESCE(MAX(id), 0) AS value FROM test_runs UNION ALL "
        "SELECT COALESCE(MAX(id), 0) FROM suite_runs UNION ALL "
        "SELECT COALESCE(MAX(id), 0) FROM plan_runs UNION ALL "
        "SELECT COALESCE(MAX(id), 0) FROM mobile_special_runs UNION ALL "
        "SELECT COALESCE(MAX(run_id), 0) FROM local_jobs UNION ALL "
        "SELECT COALESCE(MAX(run_id), 0) FROM execution_run_leases)"
    ).scalar_one()
    if highest:
        connection.exec_driver_sql("INSERT INTO local_run_ids(id) VALUES (?)", (highest,))


LOCAL_MIGRATIONS: dict[int, Callable[[Connection], None]] = {
    2: _create_job_queue,
    3: _upgrade_job_queue_identity,
    4: _create_run_id_allocator,
}


def _read_version(connection: Connection) -> int:
    return int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())


def _set_version(connection: Connection, version: int) -> None:
    connection.exec_driver_sql(f"PRAGMA user_version={version}")


def _assert_current_schema(connection: Connection) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.tables.values():
        if table.name not in existing_tables:
            raise RuntimeError(f"local SQLite schema is missing table {table.name}; restore a matching backup")
        actual_columns = {column["name"] for column in inspector.get_columns(table.name)}
        expected_columns = {column.name for column in table.columns}
        if actual_columns != expected_columns:
            raise RuntimeError(f"local SQLite schema differs at {table.name}; a versioned migration is required")


def ensure_local_schema(engine: Engine) -> int:
    """Create a fresh local database or apply explicit migrations in order."""
    with engine.begin() as connection:
        if connection.dialect.name != "sqlite":
            raise RuntimeError("local schema manager requires SQLite")

        version = _read_version(connection)
        if version > CURRENT_LOCAL_SCHEMA_VERSION:
            raise RuntimeError("local SQLite database was created by a newer ATP version")

        existing_tables = set(inspect(connection).get_table_names())
        if not existing_tables:
            Base.metadata.create_all(bind=connection)
            _create_job_queue(connection)
            _create_run_id_allocator(connection)
            _set_version(connection, CURRENT_LOCAL_SCHEMA_VERSION)
        elif version == 0:
            # Adopt only a complete prototype database. Incomplete databases
            # stay untouched so the user can restore a prior backup.
            _assert_current_schema(connection)
            _create_job_queue(connection)
            _create_run_id_allocator(connection)
            _set_version(connection, CURRENT_LOCAL_SCHEMA_VERSION)
        else:
            for next_version in range(version + 1, CURRENT_LOCAL_SCHEMA_VERSION + 1):
                migration = LOCAL_MIGRATIONS.get(next_version)
                if migration is None:
                    raise RuntimeError(f"missing local SQLite migration {next_version}")
                migration(connection)
                _set_version(connection, next_version)

        _assert_current_schema(connection)
        if "local_jobs" not in inspect(connection).get_table_names():
            raise RuntimeError("local SQLite job queue is missing")
        if "local_run_ids" not in inspect(connection).get_table_names():
            raise RuntimeError("local SQLite run ID allocator is missing")
        return _read_version(connection)
