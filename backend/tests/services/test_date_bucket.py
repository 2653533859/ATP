"""Cross-dialect calendar grouping used by run statistics."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine, literal, select

from app.services import date_bucket as date_bucket_module


def test_sqlite_daily_and_weekly_buckets(monkeypatch) -> None:
    monkeypatch.setattr(date_bucket_module, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        tuesday = literal("2026-09-29 12:34:56")
        sunday = literal("2026-10-04 23:59:59")
        assert connection.scalar(select(date_bucket_module.date_bucket(tuesday, "daily"))) == "2026-09-29"
        assert connection.scalar(select(date_bucket_module.date_bucket(tuesday, "weekly"))) == "2026-09-28"
        assert connection.scalar(select(date_bucket_module.date_bucket(sunday, "weekly"))) == "2026-09-28"


def test_server_weekly_bucket_keeps_postgres_function(monkeypatch) -> None:
    monkeypatch.setattr(date_bucket_module, "settings", SimpleNamespace(ATP_LOCAL_MODE=False))
    expression = date_bucket_module.date_bucket(literal("2026-09-29"), "weekly")

    assert "date_trunc" in str(expression)
