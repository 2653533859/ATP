"""Versioned SQLite schema lifecycle for the single-user Windows profile.

Version 1 is the mapped schema first shipped with the local prototype. Existing
unversioned prototype databases are adopted only after their table/column
layout matches that baseline. Every later model change needs an explicit
versioned migration here; ``create_all`` must never silently patch old data.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from sqlalchemy import Engine, inspect
from sqlalchemy.engine import Connection

from app.models.base import Base

CURRENT_LOCAL_SCHEMA_VERSION = 11


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


def _extend_run_id_allocator(connection: Connection) -> None:
    highest = connection.exec_driver_sql(
        "SELECT MAX(value) FROM (SELECT COALESCE(MAX(id), 0) AS value FROM performance_runs "
        "UNION ALL SELECT COALESCE(MAX(id), 0) FROM mobile_special_runs "
        "UNION ALL SELECT COALESCE(MAX(id), 0) FROM local_run_ids)"
    ).scalar_one()
    if highest:
        connection.exec_driver_sql("INSERT OR IGNORE INTO local_run_ids(id) VALUES (?)", (highest,))


LOCAL_MIGRATIONS[5] = _extend_run_id_allocator


def _deprecated_group_cancellations(connection: Connection) -> None:
    """版本 6 曾创建 local_group_cancellations 表；该表与 request_group_cancel 均无调用方，已删除。

    保留空迁移维持版本链连续：老库从版本 5 升级时不会因缺号失败；已建过该表的
    开发库保留一张空表，不影响末尾的 _assert_current_schema 校验（只覆盖映射模型）。
    """


LOCAL_MIGRATIONS[6] = _deprecated_group_cancellations


def _create_hermes_actions(connection: Connection) -> None:
    # Freeze version 7's shape; using current model metadata would add version
    # 8's identity column early and make the following migration fail.
    connection.exec_driver_sql("""CREATE TABLE hermes_actions (
        id INTEGER NOT NULL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        command_id VARCHAR(64) NOT NULL,
        action VARCHAR(32) NOT NULL,
        request_hash VARCHAR(64) NOT NULL,
        resource_id INTEGER NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_hermes_action_command UNIQUE(user_id, command_id)
    )""")


LOCAL_MIGRATIONS[7] = _create_hermes_actions


def _create_command_resource_identities(connection: Connection) -> None:
    for table_name in ("test_suites", "suite_runs"):
        connection.exec_driver_sql(
            f"ALTER TABLE {table_name} ADD COLUMN identity_token VARCHAR(32) NOT NULL DEFAULT ''"
        )
        last_id = -1
        while True:
            ids = (
                connection.exec_driver_sql(
                    f"SELECT id FROM {table_name} WHERE id > ? ORDER BY id LIMIT 1000", (last_id,)
                )
                .scalars()
                .all()
            )
            if not ids:
                break
            for resource_id in ids:
                connection.exec_driver_sql(
                    f"UPDATE {table_name} SET identity_token=? WHERE id=?", (uuid4().hex, resource_id)
                )
            last_id = ids[-1]
    # Old receipts remain unverified; looking up the current ID could bind the wrong resource.
    connection.exec_driver_sql("ALTER TABLE hermes_actions ADD COLUMN resource_identity VARCHAR(32)")


LOCAL_MIGRATIONS[8] = _create_command_resource_identities


def _create_execution_dispatches(connection: Connection) -> None:
    # Freeze version 9's shape so later mapped fields cannot leak into this migration.
    connection.exec_driver_sql("""CREATE TABLE execution_dispatches (
        id VARCHAR(32) NOT NULL PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        run_id INTEGER NOT NULL,
        run_identity VARCHAR(32) NOT NULL,
        task_name VARCHAR(64) NOT NULL,
        queue VARCHAR(128) NOT NULL,
        mode VARCHAR(16) NOT NULL,
        args_ciphertext TEXT NOT NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        attempt_count INTEGER NOT NULL DEFAULT 0,
        claim_token VARCHAR(32),
        claimed_at DATETIME,
        submitted_at DATETIME,
        error_code VARCHAR(64),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_execution_dispatches_task_identity UNIQUE(task_name, run_identity)
    )""")
    connection.exec_driver_sql(
        "CREATE INDEX ix_execution_dispatches_mode_status_created " "ON execution_dispatches(mode, status, created_at)"
    )


LOCAL_MIGRATIONS[9] = _create_execution_dispatches


def _extend_execution_acceptance(connection: Connection) -> None:
    connection.exec_driver_sql("ALTER TABLE execution_dispatches ADD COLUMN execution_token VARCHAR(32)")
    connection.exec_driver_sql("ALTER TABLE execution_dispatches ADD COLUMN accepted_at DATETIME")
    connection.exec_driver_sql("ALTER TABLE execution_run_leases ADD COLUMN run_identity VARCHAR(32)")
    _extend_job_dispatch_identity(connection)


def _extend_job_dispatch_identity(connection: Connection) -> None:
    connection.exec_driver_sql("ALTER TABLE local_jobs ADD COLUMN dispatch_id VARCHAR(32)")
    connection.exec_driver_sql("ALTER TABLE local_jobs ADD COLUMN run_identity VARCHAR(32)")
    # Only bind queue records whose existing timestamp still identifies this run.
    connection.exec_driver_sql("""UPDATE local_jobs SET run_identity=(
        SELECT identity_token FROM suite_runs
        WHERE suite_runs.id=local_jobs.run_id AND suite_runs.created_at=local_jobs.run_created_at
    ) WHERE task_name='run_test_suite'""")
    connection.exec_driver_sql("""UPDATE local_jobs SET dispatch_id=(
        SELECT id FROM execution_dispatches WHERE task_name='run_test_suite'
        AND mode='local' AND run_id=local_jobs.run_id AND run_identity=local_jobs.run_identity
    ) WHERE task_name='run_test_suite' AND run_identity IS NOT NULL""")
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX uq_local_jobs_dispatch ON local_jobs(dispatch_id) WHERE dispatch_id IS NOT NULL"
    )


LOCAL_MIGRATIONS[10] = _extend_execution_acceptance


def _create_group_recovery(connection: Connection) -> None:
    connection.exec_driver_sql("ALTER TABLE suite_runs ADD COLUMN cancel_requested_at DATETIME")
    connection.exec_driver_sql("ALTER TABLE plan_runs ADD COLUMN cancel_requested_at DATETIME")
    connection.exec_driver_sql("ALTER TABLE plan_runs ADD COLUMN identity_token VARCHAR(32) NOT NULL DEFAULT ''")
    last_id = -1
    while True:
        ids = (
            connection.exec_driver_sql("SELECT id FROM plan_runs WHERE id > ? ORDER BY id LIMIT 1000", (last_id,))
            .scalars()
            .all()
        )
        if not ids:
            break
        for run_id in ids:
            connection.exec_driver_sql("UPDATE plan_runs SET identity_token=? WHERE id=?", (uuid4().hex, run_id))
        last_id = ids[-1]
    connection.exec_driver_sql("""UPDATE local_jobs SET run_identity=(
        SELECT identity_token FROM plan_runs WHERE plan_runs.id=local_jobs.run_id
        AND plan_runs.created_at=local_jobs.run_created_at
    ) WHERE task_name='run_test_plan'""")
    connection.exec_driver_sql("""CREATE TABLE group_run_children (
        id INTEGER NOT NULL PRIMARY KEY,
        parent_kind VARCHAR(16) NOT NULL,
        parent_run_id INTEGER NOT NULL,
        parent_identity VARCHAR(32) NOT NULL,
        child_kind VARCHAR(16) NOT NULL,
        child_id INTEGER NOT NULL,
        child_identity VARCHAR(128) NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_group_run_children_identity UNIQUE(parent_kind, parent_identity, child_id, child_identity)
    )""")
    connection.exec_driver_sql(
        "CREATE INDEX ix_group_run_children_parent_identity ON group_run_children(parent_identity)"
    )


LOCAL_MIGRATIONS[11] = _create_group_recovery


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
            _extend_job_dispatch_identity(connection)
            _create_run_id_allocator(connection)
            _extend_run_id_allocator(connection)
            _set_version(connection, CURRENT_LOCAL_SCHEMA_VERSION)
        elif version == 0:
            # Adopt only a complete prototype database. Incomplete databases
            # stay untouched so the user can restore a prior backup.
            _assert_current_schema(connection)
            _create_job_queue(connection)
            _extend_job_dispatch_identity(connection)
            _create_run_id_allocator(connection)
            _extend_run_id_allocator(connection)
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
