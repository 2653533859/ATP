from __future__ import annotations

import subprocess

from app.migration_startup import (
    DEFAULT_ATTEMPTS,
    DEFAULT_DELAY_SECONDS,
    MAX_ATTEMPTS,
    MAX_DELAY_SECONDS,
    MigrationRetrySettings,
    is_transient_database_failure,
    migration_retry_settings,
    run_migrations,
)


def _result(returncode: int, *, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["alembic", "upgrade", "head"], returncode, stdout=stdout, stderr=stderr)


def test_transient_database_failure_classification_only_matches_known_readiness_errors():
    assert is_transient_database_failure(_result(1, stderr="could not translate host name 'postgres'"))
    assert is_transient_database_failure(_result(1, stderr="the database system is starting up"))
    assert not is_transient_database_failure(_result(1, stderr="column already exists"))


def test_retry_settings_are_bounded_and_invalid_values_fall_back_to_defaults():
    assert migration_retry_settings(
        {"ATP_MIGRATION_RETRY_ATTEMPTS": "bad", "ATP_MIGRATION_RETRY_DELAY_SECONDS": "bad"}
    ) == (MigrationRetrySettings(DEFAULT_ATTEMPTS, DEFAULT_DELAY_SECONDS))
    assert migration_retry_settings(
        {"ATP_MIGRATION_RETRY_ATTEMPTS": "999", "ATP_MIGRATION_RETRY_DELAY_SECONDS": "999"}
    ) == (MigrationRetrySettings(MAX_ATTEMPTS, MAX_DELAY_SECONDS))
    assert migration_retry_settings({"ATP_MIGRATION_RETRY_DELAY_SECONDS": "NaN"}) == (
        MigrationRetrySettings(DEFAULT_ATTEMPTS, DEFAULT_DELAY_SECONDS)
    )


def test_transient_dns_failure_retries_without_emitting_command_output():
    results = iter(
        [
            _result(1, stderr="temporary failure in name resolution password=not-for-logs"),
            _result(0),
        ]
    )
    messages: list[str] = []
    delays: list[float] = []

    exit_code = run_migrations(
        MigrationRetrySettings(attempts=3, delay_seconds=0.25),
        runner=lambda: next(results),
        sleeper=delays.append,
        emit=messages.append,
    )

    assert exit_code == 0
    assert delays == [0.25]
    assert messages == [
        "database readiness unavailable; retrying migration (1/3)",
        "database migrations completed",
    ]
    assert all("not-for-logs" not in message for message in messages)


def test_programmatic_non_finite_retry_delay_is_normalised_before_sleeping():
    results = iter([_result(1, stderr="connection refused"), _result(0)])
    delays: list[float] = []

    exit_code = run_migrations(
        MigrationRetrySettings(attempts=2, delay_seconds=float("nan")),
        runner=lambda: next(results),
        sleeper=delays.append,
        emit=lambda _message: None,
    )

    assert exit_code == 0
    assert delays == [DEFAULT_DELAY_SECONDS]


def test_non_retryable_failure_exits_without_restarting():
    calls = 0
    messages: list[str] = []

    def runner() -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return _result(2, stderr="column already exists")

    exit_code = run_migrations(MigrationRetrySettings(attempts=3, delay_seconds=0), runner=runner, emit=messages.append)

    assert exit_code == 2
    assert calls == 1
    assert messages == ["migration failed with a non-retryable error; exiting"]


def test_retry_exhaustion_is_finite_and_reports_only_the_safe_summary():
    messages: list[str] = []
    delays: list[float] = []

    exit_code = run_migrations(
        MigrationRetrySettings(attempts=2, delay_seconds=0.5),
        runner=lambda: _result(1, stderr="connection refused secret=not-for-logs"),
        sleeper=delays.append,
        emit=messages.append,
    )

    assert exit_code == 1
    assert delays == [0.5]
    assert messages[-1] == "database readiness did not recover within 2 migration attempts; exiting"
    assert all("not-for-logs" not in message for message in messages)


def test_command_start_failure_is_not_retried_or_echoed():
    messages: list[str] = []

    exit_code = run_migrations(
        MigrationRetrySettings(attempts=3, delay_seconds=0),
        runner=lambda: (_ for _ in ()).throw(OSError("command path contains a secret")),
        emit=messages.append,
    )

    assert exit_code == 1
    assert messages == ["migration command could not be started; exiting"]
