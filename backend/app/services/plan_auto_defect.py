"""测试计划失败后自动创建平台内部缺陷的回退逻辑。

当项目未启用外部缺陷跟踪器（Jira/禅道/GitLab 等）时，测试计划开启
``auto_create_bugs`` 后会回退在平台内部 ``defects`` 表中自动创建或去重关联缺陷。
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bootstrap import load_all_models
from app.models.case import RunStatus, StepResult, TestCase, TestRun
from app.models.defect import Defect, DefectRunLink
from app.models.suite import SuiteRun

_ACTIVE_DUPLICATE_STATUSES = {"open", "in_progress", "reopened"}
_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|cookie|set-cookie|password|passwd|token|secret|api[_-]?key)\s*[:=]\s*(?:bearer\s+)?[^,;\n]+"
)


def _safe_text(value: Any, limit: int = 2_000) -> str | None:
    if value is None:
        return None
    text = str(value)
    text = _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return text[:limit]


def _fingerprint(project_id: int, title: str, error_message: str | None) -> str:
    normalized = " ".join((error_message or "").lower().split())[:1_000]
    return hashlib.sha256(f"{project_id}|{title.lower().strip()}|{normalized}".encode("utf-8")).hexdigest()


async def _resolve_case_run_error(
    db: AsyncSession,
    case_run: TestRun,
    case_result: dict[str, Any],
) -> str | None:
    direct = getattr(case_run, "error_message", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    from_summary = case_result.get("error")
    if isinstance(from_summary, str) and from_summary.strip():
        return from_summary.strip()

    step_stmt = (
        select(StepResult.error_message)
        .where(StepResult.run_id == case_run.id, StepResult.error_message.isnot(None))
        .order_by(StepResult.step_index.asc())
        .limit(1)
    )
    step_err = (await db.execute(step_stmt)).scalar_one_or_none()
    if isinstance(step_err, str) and step_err.strip():
        return step_err.strip()

    child_stmt = (
        select(TestRun.id, TestRun.error_message)
        .where(
            TestRun.parent_run_id == case_run.id,
            TestRun.status.in_([RunStatus.failed, RunStatus.error]),
        )
        .order_by(TestRun.iteration_index.asc(), TestRun.id.asc())
        .limit(1)
    )
    child_row = (await db.execute(child_stmt)).first()
    if child_row is not None:
        child_id, child_err = child_row[0], child_row[1]
        if isinstance(child_err, str) and child_err.strip():
            return child_err.strip()
        child_step_stmt = (
            select(StepResult.error_message)
            .where(StepResult.run_id == child_id, StepResult.error_message.isnot(None))
            .order_by(StepResult.step_index.asc())
            .limit(1)
        )
        child_step_err = (await db.execute(child_step_stmt)).scalar_one_or_none()
        if isinstance(child_step_err, str) and child_step_err.strip():
            return child_step_err.strip()
    return None


async def _find_active_duplicate(db: AsyncSession, project_id: int, fingerprint: str) -> Defect | None:
    stmt = (
        select(Defect)
        .where(
            Defect.project_id == project_id,
            Defect.fingerprint == fingerprint,
            Defect.status.in_(_ACTIVE_DUPLICATE_STATUSES),
        )
        .order_by(Defect.updated_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _ensure_run_link(
    db: AsyncSession,
    *,
    defect: Defect,
    case_run: TestRun,
    case: TestCase,
    error_message: str | None,
    linked_by: int | None,
) -> bool:
    stmt = (
        select(DefectRunLink)
        .where(
            DefectRunLink.defect_id == defect.id,
            DefectRunLink.run_type == "case",
            DefectRunLink.run_id == case_run.id,
        )
        .limit(1)
    )
    existing_link = (await db.execute(stmt)).scalar_one_or_none()
    evidence = {
        "status": getattr(getattr(case_run, "status", None), "value", getattr(case_run, "status", None)),
        "case_id": case.id,
        "case_name": _safe_text(case.name, 256),
        "environment": _safe_text(getattr(case_run, "environment", None), 128),
        "trace_id": _safe_text(getattr(case_run, "trace_id", None), 128),
        "error_message": _safe_text(error_message),
    }
    if existing_link is None:
        db.add(
            DefectRunLink(
                defect_id=defect.id,
                run_type="case",
                run_id=case_run.id,
                case_id=case.id,
                evidence=evidence,
                linked_by=linked_by,
            )
        )
        return True
    existing_link.case_id = case.id
    existing_link.evidence = evidence
    existing_link.linked_by = linked_by
    return False


async def auto_create_internal_defects_for_plan_run(
    db: AsyncSession,
    *,
    plan: Any,
    plan_run: Any,
    suite_run_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """无外部 BugTracker 时，为测试计划中的失败/异常用例创建或关联内部缺陷。"""
    load_all_models()
    bug_results: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    linked_by = getattr(plan_run, "triggered_by", None)

    for suite_result in suite_run_results:
        suite_run_id = suite_result.get("suite_run_id")
        if not suite_run_id:
            continue
        suite_run = await db.get(SuiteRun, suite_run_id)
        if not suite_run:
            continue

        for case_result in suite_run.case_run_ids or []:
            if case_result.get("status") not in {"failed", "error"}:
                continue
            case_run_id = case_result.get("run_id")
            case_run = await db.get(TestRun, case_run_id) if case_run_id else None
            if not case_run:
                continue
            case = await db.get(TestCase, case_result.get("case_id") or case_run.case_id)
            if not case:
                continue

            error_message = await _resolve_case_run_error(db, case_run, case_result)
            title = f"[ATP] {case.name} 执行失败"[:256]
            fingerprint = _fingerprint(plan.project_id, title, error_message)
            existing = await _find_active_duplicate(db, plan.project_id, fingerprint)
            if existing is not None:
                created_link = await _ensure_run_link(
                    db,
                    defect=existing,
                    case_run=case_run,
                    case=case,
                    error_message=error_message,
                    linked_by=linked_by,
                )
                if created_link:
                    existing.occurrence_count = (existing.occurrence_count or 0) + 1
                existing.last_seen_at = now
                bug_results.append(
                    {
                        "case_id": case.id,
                        "run_id": case_run.id,
                        "defect_id": existing.id,
                        "bug_id": f"DEF-{existing.id}",
                        "source": "internal",
                        "duplicate": True,
                    }
                )
                continue

            description = _safe_text(
                error_message or f"测试计划 #{plan.id}（运行 #{getattr(plan_run, 'id', '')}）执行失败",
                20_000,
            )
            defect = Defect(
                project_id=plan.project_id,
                case_id=case.id,
                title=title,
                description=description,
                status="open",
                priority="P2",
                severity="major",
                fingerprint=fingerprint,
                labels=["auto-plan"],
                occurrence_count=1,
                last_seen_at=now,
                creator_id=linked_by,
            )
            db.add(defect)
            await db.flush()
            await _ensure_run_link(
                db,
                defect=defect,
                case_run=case_run,
                case=case,
                error_message=error_message,
                linked_by=linked_by,
            )
            bug_results.append(
                {
                    "case_id": case.id,
                    "run_id": case_run.id,
                    "defect_id": defect.id,
                    "bug_id": f"DEF-{defect.id}",
                    "source": "internal",
                    "duplicate": False,
                }
            )

    return bug_results
