"""The SQLite profile creates real engines with local connection pragmas."""

import runpy
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core import config


@pytest.mark.asyncio
async def test_local_database_engines_use_sqlite_wal_and_foreign_keys(tmp_path, monkeypatch):
    local_settings = config.Settings(
        _env_file=None,
        ATP_LOCAL_MODE=True,
        ATP_LOCAL_DATA_DIR=str(tmp_path),
        APP_ENV="local",
        APP_SECRET_KEY="unit-test-private-secret",
        FIRST_ADMIN_PASSWORD="unit-test-private-password",
        SLOW_QUERY_LOG_ENABLED=False,
    )
    monkeypatch.setattr(config, "settings", local_settings)
    source = Path(__file__).parents[2] / "app" / "core" / "database.py"
    database = runpy.run_path(str(source))
    async_engine = database["engine"]
    sync_engine = database["sync_engine"]

    try:
        assert local_settings.LOCAL_DATA_PATH.is_dir()
        assert async_engine.url.drivername == "sqlite+aiosqlite"
        assert sync_engine.url.drivername == "sqlite+pysqlite"
        with sync_engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            assert connection.execute(text("PRAGMA journal_mode")).scalar_one().lower() == "wal"
        async with async_engine.connect() as connection:
            assert (await connection.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1
    finally:
        await async_engine.dispose()
        sync_engine.dispose()


@pytest.mark.asyncio
async def test_server_database_engines_keep_postgres_dialect(monkeypatch):
    server_settings = config.Settings(_env_file=None, ATP_LOCAL_MODE=False, APP_ENV="production")
    monkeypatch.setattr(config, "settings", server_settings)
    source = Path(__file__).parents[2] / "app" / "core" / "database.py"
    database = runpy.run_path(str(source))
    async_engine = database["engine"]
    sync_engine = database["sync_engine"]

    try:
        assert async_engine.url.drivername == "postgresql+asyncpg"
        assert sync_engine.url.drivername == "postgresql+psycopg2"
        session_factory = database["AsyncSessionLocal"]
        async with session_factory() as session:
            assert session.bind is async_engine
    finally:
        await async_engine.dispose()
        sync_engine.dispose()
