"""Tests for Android Agent ORM models, relationships and integrity constraints."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.android_agent import AndroidAgentCommand, AndroidAgentEvent, AndroidAgentSession
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.project import Project
from app.models.user import User

load_all_models()


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'test_models.sqlite').as_posix()}")

    @event.listens_for(engine, "connect")
    def _set_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    needed_tables = [
        Base.metadata.tables["users"],
        Base.metadata.tables["ai_llm_configs"],
        Base.metadata.tables["devices"],
        Base.metadata.tables["projects"],
        AndroidAgentSession.__table__,
        AndroidAgentEvent.__table__,
        AndroidAgentCommand.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=needed_tables)

    with Session(engine) as session:
        user = User(username="test_admin", email="admin@example.com", hashed_password="pw", role="admin")
        session.add(user)
        session.commit()
        project = Project(name="Test Project", description="Test Project Description", owner_id=user.id)
        session.add(project)
        session.commit()
        session.refresh(project)
        yield session
    engine.dispose()


def test_android_agent_session_defaults_and_attributes(db_session: Session):
    session_obj = AndroidAgentSession(
        project_id=1,
        title="Search item flow",
        goal="Search for sneakers",
        expected_outcome="Detail page is displayed",
        package_name="com.test.shop",
        context_values={"item_name": "sneakers"},
    )
    db_session.add(session_obj)
    db_session.commit()
    db_session.refresh(session_obj)

    assert session_obj.id is not None
    assert session_obj.status == "created"
    assert session_obj.controller == "agent"
    assert session_obj.version == 1
    assert session_obj.control_epoch == 0
    assert session_obj.budget_max_steps == 30
    assert session_obj.budget_max_calls == 40
    assert session_obj.steps_count == 0
    assert session_obj.model_calls_count == 0
    assert session_obj.total_tokens == 0
    assert session_obj.lease_token is None
    assert session_obj.error_code is None
    assert session_obj.context_values == {"item_name": "sneakers"}
    assert session_obj.created_at is not None
    assert session_obj.updated_at is not None


def test_android_agent_event_unique_seq_constraint(db_session: Session):
    session_obj = AndroidAgentSession(
        project_id=1,
        goal="Goal",
        expected_outcome="Outcome",
        package_name="com.test.shop",
    )
    db_session.add(session_obj)
    db_session.commit()

    ev1 = AndroidAgentEvent(
        session_id=session_obj.id,
        seq=1,
        event_type="session_created",
        payload={"note": "init"},
    )
    db_session.add(ev1)
    db_session.commit()

    # 重复 seq=1 在同一个 session 下必须触发唯一约束冲突
    ev2 = AndroidAgentEvent(
        session_id=session_obj.id,
        seq=1,
        event_type="observation_captured",
        payload={"note": "conflict"},
    )
    db_session.add(ev2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_android_agent_command_idempotency_constraint(db_session: Session):
    session_obj = AndroidAgentSession(
        project_id=1,
        goal="Goal",
        expected_outcome="Outcome",
        package_name="com.test.shop",
    )
    db_session.add(session_obj)
    db_session.commit()

    cmd1 = AndroidAgentCommand(
        session_id=session_obj.id,
        seq=1,
        control_epoch=0,
        observation_id="obs-1",
        idempotency_key="idem-key-100",
        action="tap",
        params={"target": "n1"},
    )
    db_session.add(cmd1)
    db_session.commit()

    # 重复 idempotency_key 在同一个 session 下必须触发唯一约束冲突
    cmd2 = AndroidAgentCommand(
        session_id=session_obj.id,
        seq=2,
        control_epoch=0,
        observation_id="obs-2",
        idempotency_key="idem-key-100",
        action="tap",
        params={"target": "n2"},
    )
    db_session.add(cmd2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_android_agent_session_cascade_delete(db_session: Session):
    session_obj = AndroidAgentSession(
        project_id=1,
        goal="Goal",
        expected_outcome="Outcome",
        package_name="com.test.shop",
    )
    db_session.add(session_obj)
    db_session.commit()

    ev = AndroidAgentEvent(
        session_id=session_obj.id,
        seq=1,
        event_type="session_created",
    )
    cmd = AndroidAgentCommand(
        session_id=session_obj.id,
        seq=1,
        control_epoch=0,
        observation_id="obs-1",
        idempotency_key="idem-key-1",
        action="tap",
    )
    db_session.add_all([ev, cmd])
    db_session.commit()

    ev_id = ev.id
    cmd_id = cmd.id

    # 删除 session，关联的 event 和 command 应该被级联删除
    db_session.delete(session_obj)
    db_session.commit()

    assert db_session.get(AndroidAgentEvent, ev_id) is None
    assert db_session.get(AndroidAgentCommand, cmd_id) is None
