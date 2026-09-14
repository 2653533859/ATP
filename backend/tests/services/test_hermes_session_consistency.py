"""Multi-replica consistency contracts for persisted Hermes state."""

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.v1.hermes import _commit_hermes_state
from app.models.hermes import HermesSession


def _session() -> HermesSession:
    return HermesSession(
        project_id=1,
        user_id=7,
        title="并发会话",
        context_filters={},
        messages=[],
        drafts=[],
        metrics={"queries": 0},
    )


def test_hermes_session_optimistic_version_rejects_stale_replica_write():
    engine = create_engine("sqlite://")
    HermesSession.__table__.create(engine)
    with Session(engine) as setup:
        setup.add(_session())
        setup.commit()

    replica_a = Session(engine, expire_on_commit=False)
    replica_b = Session(engine, expire_on_commit=False)
    try:
        state_a = replica_a.get(HermesSession, 1)
        state_b = replica_b.get(HermesSession, 1)
        assert state_a is not None and state_b is not None
        assert state_a.state_version == state_b.state_version == 1

        state_a.metrics = {"queries": 1}
        replica_a.commit()
        assert state_a.state_version == 2

        state_b.metrics = {"queries": 1, "helpful": 1}
        with pytest.raises(StaleDataError):
            replica_b.commit()
        replica_b.rollback()

        replica_b.refresh(state_b)
        assert state_b.metrics == {"queries": 1}
        assert state_b.state_version == 2
    finally:
        replica_a.close()
        replica_b.close()
        engine.dispose()


def test_commit_hermes_state_turns_stale_write_into_retryable_conflict():
    class StaleDB:
        def __init__(self):
            self.rollbacks = 0

        async def commit(self):
            raise StaleDataError("another replica updated the row")

        async def rollback(self):
            self.rollbacks += 1

    db = StaleDB()

    with pytest.raises(HTTPException) as error:
        asyncio.run(_commit_hermes_state(db))  # type: ignore[arg-type]

    assert error.value.status_code == 409
    assert "刷新后重试" in error.value.detail
    assert db.rollbacks == 1
