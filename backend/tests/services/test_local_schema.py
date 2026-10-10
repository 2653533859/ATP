"""SQLite bootstrap and upgrade guards for portable Windows data."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect

from app.core.local_schema import CURRENT_LOCAL_SCHEMA_VERSION, ensure_local_schema
from app.models.base import Base
from app.models.bootstrap import load_all_models

load_all_models()


def _legacy_mapped_schema(engine) -> None:
    """Reconstruct pre-version-7 mapped fields, rather than mislabel current DDL as v1."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        for table in ("group_run_children", "execution_dispatches", "hermes_actions"):
            connection.exec_driver_sql(f"DROP TABLE {table}")
        for table, columns in {
            "test_suites": ["identity_token"],
            "suite_runs": ["identity_token", "cancel_requested_at"],
            "plan_runs": ["identity_token", "cancel_requested_at"],
            "execution_run_leases": ["run_identity"],
        }.items():
            for column in columns:
                connection.exec_driver_sql(f"ALTER TABLE {table} DROP COLUMN {column}")


def test_fresh_local_database_gets_versioned_schema(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.sqlite3'}")

    assert ensure_local_schema(engine) == CURRENT_LOCAL_SCHEMA_VERSION
    assert ensure_local_schema(engine) == CURRENT_LOCAL_SCHEMA_VERSION


def test_existing_unversioned_prototype_is_adopted(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'prototype.sqlite3'}")
    Base.metadata.create_all(bind=engine)

    assert ensure_local_schema(engine) == CURRENT_LOCAL_SCHEMA_VERSION


def test_version_one_database_gets_durable_queue(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'v1.sqlite3'}")
    _legacy_mapped_schema(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA user_version=1")

    assert ensure_local_schema(engine) == CURRENT_LOCAL_SCHEMA_VERSION
    with engine.connect() as connection:
        assert "local_jobs" in inspect(connection).get_table_names()


def test_version_two_queue_upgrade_allows_reused_run_id(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'v2.sqlite3'}")
    _legacy_mapped_schema(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA user_version=2")
        connection.exec_driver_sql(
            "CREATE TABLE local_jobs (id INTEGER PRIMARY KEY, task_name TEXT, run_id INTEGER, "
            "args_json TEXT, status TEXT, error TEXT, created_at TEXT, started_at TEXT, "
            "finished_at TEXT, UNIQUE(task_name, run_id))"
        )

    assert ensure_local_schema(engine) == CURRENT_LOCAL_SCHEMA_VERSION
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO local_jobs(task_name, run_id, run_created_at, args_json, status) "
            "VALUES ('run_test_case', 1, 'first', 'cipher', 'finished')"
        )
        connection.exec_driver_sql(
            "INSERT INTO local_jobs(task_name, run_id, run_created_at, args_json, status) "
            "VALUES ('run_test_case', 1, 'second', 'cipher', 'queued')"
        )


def test_incomplete_unversioned_database_is_rejected(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'incomplete.sqlite3'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")

    with pytest.raises(RuntimeError, match="missing table"):
        ensure_local_schema(engine)


def test_database_from_newer_version_is_rejected(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'future.sqlite3'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(f"PRAGMA user_version={CURRENT_LOCAL_SCHEMA_VERSION + 1}")

    with pytest.raises(RuntimeError, match="newer ATP version"):
        ensure_local_schema(engine)


def test_version_two_queue_interrupts_inflight_jobs_on_identity_upgrade(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'v2-inflight.sqlite3'}")
    _legacy_mapped_schema(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA user_version=2")
        connection.exec_driver_sql(
            "CREATE TABLE local_jobs (id INTEGER PRIMARY KEY, task_name TEXT, run_id INTEGER, "
            "args_json TEXT, status TEXT, error TEXT, created_at TEXT, started_at TEXT, "
            "finished_at TEXT, UNIQUE(task_name, run_id))"
        )
        connection.exec_driver_sql(
            "INSERT INTO local_jobs VALUES (1, 'run_test_case', 11, 'cipher', 'running', NULL, "
            "CURRENT_TIMESTAMP, NULL, NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO local_jobs VALUES (2, 'run_test_suite', 12, 'cipher', 'queued', NULL, "
            "CURRENT_TIMESTAMP, NULL, NULL)"
        )

    assert ensure_local_schema(engine) == CURRENT_LOCAL_SCHEMA_VERSION
    with engine.connect() as connection:
        rows = connection.exec_driver_sql("SELECT status, error FROM local_jobs ORDER BY id").all()
    assert [row[0] for row in rows] == ["interrupted", "interrupted"]
    assert all("重新提交" in row[1] for row in rows)
