"""Durable queue recovery does not replay a possibly side-effectful run."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sqlalchemy import create_engine, text

from app.services import local_jobs


def test_local_job_payload_is_encrypted_and_queued(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.sqlite3'}")
    monkeypatch.setattr(local_jobs, "_engine", lambda: engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE local_jobs (id INTEGER PRIMARY KEY, task_name TEXT, run_id INTEGER, "
            "run_created_at TEXT, args_json TEXT, status TEXT DEFAULT 'queued')"
        )
        connection.exec_driver_sql("CREATE TABLE test_runs (id INTEGER PRIMARY KEY, created_at TEXT)")
        connection.exec_driver_sql("INSERT INTO test_runs VALUES (7, '2026-09-29 10:00:00')")

    local_jobs.enqueue_local_job(SimpleNamespace(name="run_test_case"), (7, {"api_token": "private-value"}, None))
    with engine.connect() as connection:
        payload, status = connection.execute(text("SELECT args_json, status FROM local_jobs")).one()
    assert "private-value" not in payload
    assert status == "queued"


def test_interrupted_run_is_marked_error_without_replay(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'recovery.sqlite3'}")
    monkeypatch.setattr(local_jobs, "_engine", lambda: engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE test_runs (id INTEGER PRIMARY KEY, status TEXT, error_message TEXT)")
        connection.exec_driver_sql(
            "CREATE TABLE local_jobs (id INTEGER PRIMARY KEY, task_name TEXT, run_id INTEGER, "
            "run_created_at TEXT, status TEXT, error TEXT, finished_at TEXT)"
        )
        connection.exec_driver_sql("INSERT INTO test_runs(id, status) VALUES (7, 'running')")
        connection.exec_driver_sql(
            "INSERT INTO local_jobs(id, task_name, run_id, status) VALUES (1, 'run_test_case', 7, 'running')"
        )
    assert local_jobs.recover_interrupted_jobs() == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM test_runs WHERE id=7")).scalar_one() == "error"
        assert connection.execute(text("SELECT status FROM local_jobs WHERE id=1")).scalar_one() == "interrupted"


@pytest.mark.parametrize("task_failed", [False, True])
def test_task_that_returns_without_final_state_is_failed(tmp_path, monkeypatch, task_failed) -> None:
    import app.worker as worker_package

    engine = create_engine(f"sqlite:///{tmp_path / 'stuck.sqlite3'}")
    monkeypatch.setattr(local_jobs, "_engine", lambda: engine)
    fake_result = SimpleNamespace(failed=lambda: task_failed, result="worker failed")
    fake_task = SimpleNamespace(name="run_test_case", apply=lambda **_kwargs: fake_result)
    monkeypatch.setattr(worker_package, "tasks", SimpleNamespace(run_test_case=fake_task), raising=False)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE test_runs (id INTEGER PRIMARY KEY, created_at TEXT, status TEXT, error_message TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE local_jobs (id INTEGER PRIMARY KEY, task_name TEXT, run_id INTEGER, "
            "run_created_at TEXT, args_json TEXT, status TEXT DEFAULT 'queued', error TEXT, "
            "started_at TEXT, finished_at TEXT)"
        )
        connection.exec_driver_sql("INSERT INTO test_runs VALUES (7, '2026-09-29 10:00:00', 'pending', NULL)")
    local_jobs.enqueue_local_job(fake_task, (7, {}, None))

    assert local_jobs._run_next_job() is True
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM test_runs WHERE id=7")).scalar_one() == "error"
        assert connection.execute(text("SELECT status FROM local_jobs")).scalar_one() == "failed"


def test_local_queue_rejects_unknown_or_missing_runs(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'invalid.sqlite3'}")
    monkeypatch.setattr(local_jobs, "_engine", lambda: engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE test_runs (id INTEGER PRIMARY KEY, created_at TEXT)")

    with pytest.raises(ValueError, match="unsupported local task"):
        local_jobs.enqueue_local_job(SimpleNamespace(name="other"), (1,))
    with pytest.raises(ValueError, match="requires a run id"):
        local_jobs.enqueue_local_job(SimpleNamespace(name="run_test_case"), ())
    with pytest.raises(ValueError, match="removed before enqueue"):
        local_jobs.enqueue_local_job(SimpleNamespace(name="run_test_case"), (99,))


def test_local_queue_skips_deleted_run_and_finishes_valid_run(tmp_path, monkeypatch) -> None:
    import app.worker as worker_package

    engine = create_engine(f"sqlite:///{tmp_path / 'queue.sqlite3'}")
    monkeypatch.setattr(local_jobs, "_engine", lambda: engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE test_runs (id INTEGER PRIMARY KEY, created_at TEXT, status TEXT, error_message TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE local_jobs (id INTEGER PRIMARY KEY, task_name TEXT, run_id INTEGER, "
            "run_created_at TEXT, args_json TEXT, status TEXT DEFAULT 'queued', error TEXT, "
            "started_at TEXT, finished_at TEXT)"
        )
        connection.exec_driver_sql("INSERT INTO test_runs VALUES (7, '2026-09-29 10:00:00', 'pending', NULL)")

    def apply(*, args):
        with engine.begin() as connection:
            connection.execute(text("UPDATE test_runs SET status='passed' WHERE id=:id"), {"id": args[0]})
        return SimpleNamespace(failed=lambda: False)

    fake_task = SimpleNamespace(name="run_test_case", apply=apply)
    monkeypatch.setattr(worker_package, "tasks", SimpleNamespace(run_test_case=fake_task), raising=False)
    local_jobs.enqueue_local_job(fake_task, (7,))
    assert local_jobs._run_next_job()
    assert not local_jobs._run_next_job()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM local_jobs")).scalar_one() == "finished"

    with engine.begin() as connection:
        connection.execute(text("UPDATE test_runs SET status='pending' WHERE id=7"))
    local_jobs.enqueue_local_job(fake_task, (7,))
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM test_runs WHERE id=7"))
    assert local_jobs._run_next_job()
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT status FROM local_jobs ORDER BY id DESC LIMIT 1")).scalar_one() == "skipped"
        )


def test_local_runner_starts_once_and_stops(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(local_jobs, "recover_interrupted_jobs", lambda: calls.append("recover"))
    monkeypatch.setattr(local_jobs, "_run_next_job", lambda: False)

    local_jobs.start_local_runner()
    try:
        local_jobs.start_local_runner()
        assert calls == ["recover"]
        assert local_jobs._thread is not None and local_jobs._thread.is_alive()
    finally:
        local_jobs.stop_local_runner()
    assert not local_jobs._thread.is_alive()


def test_local_runner_poll_records_error_and_continues(monkeypatch) -> None:
    calls = []

    def fail_once():
        calls.append("poll")
        local_jobs._stop.set()
        raise RuntimeError("temporary poll error")

    monkeypatch.setattr(local_jobs, "_run_next_job", fail_once)
    local_jobs._stop.clear()
    try:
        local_jobs._loop()
        assert calls == ["poll"]
    finally:
        local_jobs._stop.clear()
