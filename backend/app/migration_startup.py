"""Bounded, secret-safe Alembic startup retries for Compose deployments."""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite


DEFAULT_ATTEMPTS = 12
DEFAULT_DELAY_SECONDS = 5.0
MAX_ATTEMPTS = 24
MAX_DELAY_SECONDS = 30.0

_TRANSIENT_DATABASE_MARKERS = (
    "temporary failure in name resolution",
    "name or service not known",
    "could not translate host name",
    "connection refused",
    "connection timed out",
    "timeout expired",
    "server closed the connection unexpectedly",
    "the database system is starting up",
    "database system is starting up",
)


@dataclass(frozen=True)
class MigrationRetrySettings:
    attempts: int
    delay_seconds: float


def _bounded_attempts(raw: str | None) -> int:
    try:
        value = int(raw) if raw is not None else DEFAULT_ATTEMPTS
    except ValueError:
        return DEFAULT_ATTEMPTS
    return min(max(value, 1), MAX_ATTEMPTS)


def _bounded_delay_seconds(raw: str | None) -> float:
    try:
        value = float(raw) if raw is not None else DEFAULT_DELAY_SECONDS
    except ValueError:
        return DEFAULT_DELAY_SECONDS
    if not isfinite(value):
        return DEFAULT_DELAY_SECONDS
    return min(max(value, 0.0), MAX_DELAY_SECONDS)


def migration_retry_settings(environ: Mapping[str, str] | None = None) -> MigrationRetrySettings:
    """Read bounded retry settings without importing application configuration."""
    values = os.environ if environ is None else environ
    return MigrationRetrySettings(
        attempts=_bounded_attempts(values.get("ATP_MIGRATION_RETRY_ATTEMPTS")),
        delay_seconds=_bounded_delay_seconds(values.get("ATP_MIGRATION_RETRY_DELAY_SECONDS")),
    )


def is_transient_database_failure(result: subprocess.CompletedProcess[str]) -> bool:
    """Classify only known connection/readiness failures; never expose command output."""
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).lower()
    return any(marker in output for marker in _TRANSIENT_DATABASE_MARKERS)


def _run_alembic_upgrade() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        check=False,
        text=True,
    )


def _normalise_settings(settings: MigrationRetrySettings) -> MigrationRetrySettings:
    delay_seconds = settings.delay_seconds if isfinite(settings.delay_seconds) else DEFAULT_DELAY_SECONDS
    return MigrationRetrySettings(
        attempts=min(max(settings.attempts, 1), MAX_ATTEMPTS),
        delay_seconds=min(max(delay_seconds, 0.0), MAX_DELAY_SECONDS),
    )


def run_migrations(
    settings: MigrationRetrySettings | None = None,
    *,
    runner: Callable[[], subprocess.CompletedProcess[str]] = _run_alembic_upgrade,
    sleeper: Callable[[float], None] = time.sleep,
    emit: Callable[[str], None] = print,
) -> int:
    """Run migrations with finite retries for known transient database failures."""
    retry_settings = _normalise_settings(settings or migration_retry_settings())

    for attempt in range(1, retry_settings.attempts + 1):
        try:
            result = runner()
        except OSError:
            emit("migration command could not be started; exiting")
            return 1

        if result.returncode == 0:
            emit("database migrations completed")
            return 0

        if not is_transient_database_failure(result):
            emit("migration failed with a non-retryable error; exiting")
            return result.returncode if result.returncode > 0 else 1

        if attempt == retry_settings.attempts:
            emit(f"database readiness did not recover within {retry_settings.attempts} migration attempts; exiting")
            return result.returncode if result.returncode > 0 else 1

        emit(f"database readiness unavailable; retrying migration ({attempt}/{retry_settings.attempts})")
        sleeper(retry_settings.delay_seconds)

    raise AssertionError("bounded migration retry loop must return")


def main() -> int:
    return run_migrations()


if __name__ == "__main__":
    raise SystemExit(main())
