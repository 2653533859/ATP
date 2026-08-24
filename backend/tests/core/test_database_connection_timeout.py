from pathlib import Path

from app.core.config import Settings


def test_infrastructure_connection_timeouts_are_bounded_and_wired() -> None:
    settings = Settings(_env_file=None)
    assert settings.POSTGRES_CONNECT_TIMEOUT_SECONDS == 5
    assert settings.REDIS_CONNECT_TIMEOUT_SECONDS == 5
    assert settings.MINIO_CONNECT_TIMEOUT_SECONDS == 5
    assert settings.MINIO_READ_TIMEOUT_SECONDS == 60
    assert all(
        1 <= value <= 120
        for value in (
            settings.POSTGRES_CONNECT_TIMEOUT_SECONDS,
            settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            settings.MINIO_CONNECT_TIMEOUT_SECONDS,
        )
    )
    assert 1 <= settings.MINIO_READ_TIMEOUT_SECONDS <= 3600

    database_source = Path(__file__).parents[2].joinpath("app", "core", "database.py").read_text(encoding="utf-8")
    assert 'connect_args={"timeout": settings.POSTGRES_CONNECT_TIMEOUT_SECONDS}' in database_source
    assert 'connect_args={"connect_timeout": settings.POSTGRES_CONNECT_TIMEOUT_SECONDS}' in database_source

    redis_source = Path(__file__).parents[2].joinpath("app", "core", "redis_client.py").read_text(encoding="utf-8")
    assert "socket_connect_timeout=timeout" in redis_source
    assert "read_timeout = timeout if socket_timeout is None" in redis_source
    assert "socket_timeout=read_timeout" in redis_source

    minio_source = Path(__file__).parents[2].joinpath("app", "core", "minio_client.py").read_text(encoding="utf-8")
    assert "connect=settings.MINIO_CONNECT_TIMEOUT_SECONDS" in minio_source
    assert "read=settings.MINIO_READ_TIMEOUT_SECONDS" in minio_source
    assert "maxsize=10" in minio_source

    celery_source = Path(__file__).parents[2].joinpath("app", "worker", "celery_app.py").read_text(encoding="utf-8")
    assert '"socket_connect_timeout": settings.REDIS_CONNECT_TIMEOUT_SECONDS' in celery_source
    assert '"socket_timeout": settings.REDIS_CONNECT_TIMEOUT_SECONDS' in celery_source


def test_infrastructure_connection_timeouts_reject_zero_and_large_values() -> None:
    for value in (0, 121):
        for field_name in (
            "POSTGRES_CONNECT_TIMEOUT_SECONDS",
            "REDIS_CONNECT_TIMEOUT_SECONDS",
            "MINIO_CONNECT_TIMEOUT_SECONDS",
        ):
            try:
                Settings(_env_file=None, **{field_name: value})
            except ValueError:
                continue
            raise AssertionError(f"{field_name} value {value} should be rejected")

    for value in (0, 3601):
        try:
            Settings(_env_file=None, MINIO_READ_TIMEOUT_SECONDS=value)
        except ValueError:
            continue
        raise AssertionError("MINIO_READ_TIMEOUT_SECONDS out of range should be rejected")
