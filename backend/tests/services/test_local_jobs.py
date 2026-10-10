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
            "run_created_at TEXT, run_identity TEXT, dispatch_id TEXT, args_json TEXT, status TEXT DEFAULT 'queued')"
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
        connection.exec_driver_sql(
            "CREATE TABLE test_runs (id INTEGER PRIMARY KEY, created_at TEXT, status TEXT, error_message TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE local_jobs (id INTEGER PRIMARY KEY, task_name TEXT, run_id INTEGER, "
            "run_created_at TEXT, run_identity TEXT, dispatch_id TEXT, status TEXT, error TEXT, finished_at TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO test_runs(id, created_at, status) VALUES (7, '2026-09-29 10:00:00', 'running')"
        )
        connection.exec_driver_sql(
            "INSERT INTO local_jobs(id, task_name, run_id, run_created_at, status) "
            "VALUES (1, 'run_test_case', 7, '2026-09-29 10:00:00', 'running')"
        )
    assert local_jobs.recover_interrupted_jobs() == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM test_runs WHERE id=7")).scalar_one() == "error"
        assert connection.execute(text("SELECT status FROM local_jobs WHERE id=1")).scalar_one() == "interrupted"


@pytest.mark.parametrize("initial_status", ["running", "stopped", "completed"])
@pytest.mark.parametrize("same_identity", [True, False])
def test_interrupted_android_special_run_is_failed_without_replay(
    tmp_path, monkeypatch, initial_status, same_identity
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'android-recovery.sqlite3'}")
    monkeypatch.setattr(local_jobs, "_engine", lambda: engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE mobile_special_runs (id INTEGER PRIMARY KEY, created_at TEXT, status TEXT, device_id INTEGER, "
            "summary_json TEXT, finished_at TEXT)"
        )
        connection.exec_driver_sql("CREATE TABLE device_leases (device_id INTEGER, owner_label TEXT)")
        connection.exec_driver_sql(
            "CREATE TABLE execution_run_leases (task_type TEXT, run_id INTEGER, status TEXT, released_at TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE local_jobs (id INTEGER PRIMARY KEY, task_name TEXT, run_id INTEGER, "
            "run_created_at TEXT, run_identity TEXT, dispatch_id TEXT, status TEXT, error TEXT, finished_at TEXT)"
        )
        connection.execute(
            text("INSERT INTO mobile_special_runs VALUES (8, '2026-09-29 10:00:00', :status, 3, '{}', NULL)"),
            {"status": initial_status},
        )
        connection.exec_driver_sql("INSERT INTO device_leases VALUES (3, 'mobile-run:8')")
        connection.exec_driver_sql("INSERT INTO execution_run_leases VALUES ('android', 8, 'active', NULL)")
        connection.exec_driver_sql(
            "INSERT INTO local_jobs(id, task_name, run_id, run_created_at, status) "
            "VALUES (1, 'run_mobile_special_task', 8, :created_at, 'running')",
            {"created_at": "2026-09-29 10:00:00" if same_identity else "2026-09-28 10:00:00"},
        )
    assert local_jobs.recover_interrupted_jobs() == 1
    with engine.connect() as connection:
        status, summary = connection.execute(
            text("SELECT status, summary_json FROM mobile_special_runs WHERE id=8")
        ).one()
        assert status == ("failed" if same_identity and initial_status == "running" else initial_status)
        assert ("error_message" in summary) == (same_identity and initial_status == "running")
        assert connection.execute(text("SELECT status FROM local_jobs WHERE id=1")).scalar_one() == "interrupted"
        assert connection.execute(text("SELECT COUNT(*) FROM device_leases")).scalar_one() == (
            0 if same_identity else 1
        )
        assert connection.execute(text("SELECT status FROM execution_run_leases")).scalar_one() == (
            "released" if same_identity else "active"
        )


def test_local_android_special_job_runs_without_celery_broker(tmp_path, monkeypatch) -> None:
    import app.worker as worker_package

    engine = create_engine(f"sqlite:///{tmp_path / 'android-queue.sqlite3'}")
    monkeypatch.setattr(local_jobs, "_engine", lambda: engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE mobile_special_runs (id INTEGER PRIMARY KEY, created_at TEXT, status TEXT, "
            "summary_json TEXT, finished_at TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE local_jobs (id INTEGER PRIMARY KEY, task_name TEXT, run_id INTEGER, "
            "run_created_at TEXT, run_identity TEXT, dispatch_id TEXT, args_json TEXT, status TEXT DEFAULT 'queued', error TEXT, "
            "started_at TEXT, finished_at TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO mobile_special_runs VALUES (8, '2026-09-29 10:00:00', 'pending', '{}', NULL)"
        )

    def apply(*, args):
        with engine.begin() as connection:
            connection.execute(text("UPDATE mobile_special_runs SET status='completed' WHERE id=:id"), {"id": args[0]})
        return SimpleNamespace(failed=lambda: False, result=None)

    fake_task = SimpleNamespace(name="run_mobile_special_task", apply=apply)
    monkeypatch.setattr(
        worker_package, "tasks_mobile_special", SimpleNamespace(run_mobile_special_task=fake_task), raising=False
    )
    local_jobs.enqueue_local_job(fake_task, (8,))
    assert local_jobs._run_next_job() is True
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM local_jobs")).scalar_one() == "finished"
        assert connection.execute(text("SELECT status FROM mobile_special_runs")).scalar_one() == "completed"


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
            "run_created_at TEXT, run_identity TEXT, dispatch_id TEXT, args_json TEXT, status TEXT DEFAULT 'queued', error TEXT, "
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
            "run_created_at TEXT, run_identity TEXT, dispatch_id TEXT, args_json TEXT, status TEXT DEFAULT 'queued', error TEXT, "
            "started_at TEXT, finished_at TEXT)"
        )
        connection.exec_driver_sql("INSERT INTO test_runs VALUES (7, '2026-09-29 10:00:00', 'pending', NULL)")

    def apply(*, args):
        with engine.begin() as connection:
            connection.execute(text("UPDATE test_runs SET status='passed' WHERE id=:id"), {"id": args[0]})
        return SimpleNamespace(failed=lambda: False, result=None)

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
