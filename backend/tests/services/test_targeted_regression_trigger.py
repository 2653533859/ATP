"""Unit tests for C2.3 Targeted Regression TestSuite Synthesis & Automated Trigger.

Tests:
1. Targeted regression suite composition with deduplication and sorting
2. Breaking change auto-derives P0 priority and triggers adaptive preemption
3. Non-breaking change auto-derives P1 priority
4. Validation fails on empty case IDs
5. Database persistence creates TestSuite asset
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest
from app.models import load_all_models

load_all_models()

from app.services.adaptive_queue_preemptor import _TASKS
from app.services.cluster_load_balancer import (
    _CLUSTER_NODES,
    register_worker_heartbeat,
)
from app.services.targeted_regression_trigger import (
    synthesize_and_trigger_targeted_regression,
)


@pytest.fixture(autouse=True)
def clean_state():
    _CLUSTER_NODES.clear()
    _TASKS.clear()
    yield
    _CLUSTER_NODES.clear()
    _TASKS.clear()


@pytest.mark.asyncio
async def test_synthesize_breaking_change_triggers_p0():
    # Setup alive worker
    register_worker_heartbeat(
        worker_id="w_reg_01",
        hostname="reg-worker",
        ip_address="10.0.0.1",
        queues=["default"],
        current_concurrency=0,
        max_concurrency=5,
    )

    # Input duplicate cases: [102, 101, 102] -> deduplicated to [101, 102]
    res = await synthesize_and_trigger_targeted_regression(
        impacted_case_ids=[102, 101, 102],
        project_id=1,
        owner_id=10,
        suite_name="订单核心接口破坏性变更回归",
        is_breaking_change=True,
        persist=False,
        auto_trigger=True,
    )

    assert res.total_cases_count == 2
    assert res.included_case_ids == [101, 102]
    assert res.task_priority == "P0"  # Breaking change elevated to P0!
    assert res.dispatched is True
    assert res.task_id is not None
    assert "精准回归" in res.message


@pytest.mark.asyncio
async def test_synthesize_warning_change_triggers_p1():
    res = await synthesize_and_trigger_targeted_regression(
        impacted_case_ids=[101, 103],
        project_id=1,
        owner_id=10,
        is_breaking_change=False,
        persist=False,
        auto_trigger=True,
    )

    assert res.total_cases_count == 2
    assert res.task_priority == "P1"
    assert res.dispatched is True


@pytest.mark.asyncio
async def test_synthesize_validation_empty_cases():
    with pytest.raises(ValueError, match="至少包含 1 个"):
        await synthesize_and_trigger_targeted_regression(
            impacted_case_ids=[],
            project_id=1,
            owner_id=10,
        )


@pytest.mark.asyncio
async def test_synthesize_database_persistence():
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Capture added suite
    added_objects = []

    def fake_add(obj):
        added_objects.append(obj)
        obj.id = 501  # Mock generated ID

    mock_db.add = MagicMock(side_effect=fake_add)

    res = await synthesize_and_trigger_targeted_regression(
        impacted_case_ids=[201, 202],
        project_id=1,
        owner_id=10,
        suite_name="持久化入库回归套件",
        persist=True,
        auto_trigger=False,
        db=mock_db,
    )

    assert res.persisted is True
    assert res.suite_id == 501
    assert len(added_objects) == 1
    suite_record = added_objects[0]
    assert suite_record.name == "持久化入库回归套件"
    assert len(suite_record.case_ids) == 2
    assert suite_record.case_ids[0]["case_id"] == 201
