"""Deleted SQLite runs never reuse an ID held by a durable lease or job."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core import local_run_ids
from app.core.local_schema import ensure_local_schema
from app.models.bootstrap import load_all_models
from app.models.case import TestRun

load_all_models()


def test_local_run_ids_continue_after_deleted_run(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'ids.sqlite3'}")
    ensure_local_schema(engine)
    monkeypatch.setattr(local_run_ids, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    local_run_ids.install_local_run_id_allocator()

    with Session(engine) as session:
        first = TestRun(case_id=1, triggered_by=1)
        session.add(first)
        session.commit()
        first_id = first.id
        session.delete(first)
        session.commit()
        second = TestRun(case_id=1, triggered_by=1)
        session.add(second)
        session.commit()
        second_id = second.id
        assert second_id > first_id

    with engine.connect() as connection:
        assert connection.execute(text("SELECT MAX(id) FROM local_run_ids")).scalar_one() == second_id
