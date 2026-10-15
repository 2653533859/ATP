"""Targeted Regression TestSuite Synthesis & Automated Execution Trigger Service (C2.3).

Provides:
1. Automated composition of minimal targeted regression test suites from contract change impact cases.
2. Smart priority derivation (Breaking changes -> P0 preemption, Warnings -> P1/P2).
3. Optional atomic database persistence to TestSuite assets.
4. Seamless automated dispatching into the adaptive priority queue preemptor engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.suite import SuiteStatus, TestSuite
from app.models.project import Project  # noqa: F401
from app.services.adaptive_queue_preemptor import enqueue_task

logger = logging.getLogger(__name__)


@dataclass
class TargetedRegressionResult:
    synthesis_id: str
    suite_id: int | None
    suite_name: str
    project_id: int
    total_cases_count: int
    included_case_ids: list[int]
    persisted: bool
    dispatched: bool
    task_id: str | None
    task_priority: str
    was_preempted: bool
    triggered_at: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "synthesis_id": self.synthesis_id,
            "suite_id": self.suite_id,
            "suite_name": self.suite_name,
            "project_id": self.project_id,
            "total_cases_count": self.total_cases_count,
            "included_case_ids": self.included_case_ids,
            "persisted": self.persisted,
            "dispatched": self.dispatched,
            "task_id": self.task_id,
            "task_priority": self.task_priority,
            "was_preempted": self.was_preempted,
            "triggered_at": self.triggered_at,
            "message": self.message,
        }


async def synthesize_and_trigger_targeted_regression(
    impacted_case_ids: list[int],
    *,
    project_id: int,
    owner_id: int,
    suite_name: str | None = None,
    priority: str | None = None,
    is_breaking_change: bool = False,
    persist: bool = True,
    auto_trigger: bool = True,
    queue_name: str = "default",
    db: AsyncSession | None = None,
) -> TargetedRegressionResult:
    """Compose minimal targeted regression suite from impacted cases and dispatch into queue."""
    synthesis_id = f"synth_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Deduplicate and sort cases
    unique_case_ids = sorted(list(set(impacted_case_ids)))
    if not unique_case_ids:
        raise ValueError("合成精准回归套件需要至少包含 1 个受影响的测试用例")

    # Name and priority derivation
    effective_name = (
        suite_name.strip()
        if suite_name and suite_name.strip()
        else f"契约变更影响精准回归套件_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    )

    if priority in {"P0", "P1", "P2", "P3"}:
        task_priority = priority
    elif is_breaking_change:
        task_priority = "P0"  # Breaking change triggers P0 emergency preemption
    else:
        task_priority = "P1"

    # Formatted case_ids JSON payload for TestSuite
    ordered_case_ids = [{"case_id": cid, "sort": idx} for idx, cid in enumerate(unique_case_ids)]

    persisted_suite_id: int | None = None

    # 1. Database Persistence if requested
    if persist and db is not None:
        suite = TestSuite(
            name=effective_name,
            description=f"由接口契约变更影响面分析引擎自动重组合成的精准回归套件 (包含 {len(unique_case_ids)} 个受损用例)",
            project_id=project_id,
            creator_id=owner_id,
            case_ids=ordered_case_ids,
            status=SuiteStatus.active,
        )
        db.add(suite)
        await db.commit()
        await db.refresh(suite)
        persisted_suite_id = suite.id
        logger.info("Persisted targeted regression suite #%s: %s", suite.id, suite.name)

    # 2. Automated Dispatch into Preemptive Queue if requested
    dispatched_task_id: str | None = None
    was_preempted = False

    if auto_trigger:
        task_name = f"精准回归自动化执行: {effective_name}"
        task, was_preempted = enqueue_task(
            task_name=task_name,
            queue_name=queue_name,
            priority=task_priority,
            estimated_duration_sec=float(len(unique_case_ids) * 15.0),
            allow_preemption=True,
        )
        dispatched_task_id = task.task_id
        logger.info(
            "Targeted regression suite dispatched into queue: task_id=%s, priority=%s, preempted=%s",
            task.task_id,
            task_priority,
            was_preempted,
        )

    msg = f"已成功合成包含 {len(unique_case_ids)} 个用例的精准回归套件"
    if persisted_suite_id:
        msg += f" (Suite ID: #{persisted_suite_id})"
    if dispatched_task_id:
        msg += f"，已下发执行任务 {dispatched_task_id} (优先级: {task_priority})"
        if was_preempted:
            msg += "，并触发弹性抢占插队！"

    return TargetedRegressionResult(
        synthesis_id=synthesis_id,
        suite_id=persisted_suite_id,
        suite_name=effective_name,
        project_id=project_id,
        total_cases_count=len(unique_case_ids),
        included_case_ids=unique_case_ids,
        persisted=persist and persisted_suite_id is not None,
        dispatched=auto_trigger and dispatched_task_id is not None,
        task_id=dispatched_task_id,
        task_priority=task_priority,
        was_preempted=was_preempted,
        triggered_at=now_iso,
        message=msg,
    )
