from __future__ import annotations

import copy

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.v1.cases as _cases
from app.api.deps import assert_project_access, require_engineer
from app.core.database import get_db
from app.core.encryption import decrypt_env_vars
from app.models.case import RunStatus, TestCase, TestRun
from app.models.environment import Environment, EnvVariable
from app.models.project import Module
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.ai_healing_iter5 import (
    HealingPatchApplyOut,
    HealingPatchApplyRequest,
    HealingPatchPreviewOut,
    HealingPatchPreviewRequest,
)
from app.services.ai_healing_iter5 import (
    StructuredHealingPatch,
    parse_structured_healing_suggestion,
    validate_lowcode_patch,
)

router = APIRouter(prefix="/ai-healing", tags=["AI 自愈 iter5"])


@router.post("/patch-preview", response_model=HealingPatchPreviewOut)
async def preview_healing_patch(
    body: HealingPatchPreviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    """Validate a structured healing patch and return a preview config.

    This endpoint never mutates the test case. It is the safety gate before a
    future human-reviewed apply endpoint.
    """
    case, _module = await _get_case_and_assert_access(db, user, body.case_id)
    try:
        patch = _resolve_patch(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    case_type = case.case_type.value if hasattr(case.case_type, "value") else str(case.case_type)
    result = validate_lowcode_patch(
        case_type=case_type,
        case_config=case.config or {},
        patch=patch,
    )
    normalized_patch = None
    if result.normalized_patch is not None:
        normalized_patch = {
            "case_type": result.normalized_patch.case_type,
            "step_index": result.normalized_patch.step_index,
            "action": result.normalized_patch.action,
            "params": result.normalized_patch.params,
        }
    return HealingPatchPreviewOut(
        accepted=result.accepted,
        reasons=result.reasons,
        normalized_patch=normalized_patch,
        preview_config=result.preview_config,
    )


@router.post("/patch-apply", response_model=HealingPatchApplyOut)
async def apply_healing_patch(
    body: HealingPatchApplyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    """Apply a human-approved structured healing patch.

    This creates a case snapshot before writing, records an audit log, and can
    optionally trigger a regression run for the same case.
    """
    case, module = await _get_case_and_assert_access(db, user, body.case_id)
    try:
        patch = _resolve_patch(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    case_type = case.case_type.value if hasattr(case.case_type, "value") else str(case.case_type)
    result = validate_lowcode_patch(
        case_type=case_type,
        case_config=case.config or {},
        patch=patch,
    )
    normalized_patch = _dump_patch(result.normalized_patch)
    if not result.accepted or result.preview_config is None:
        return HealingPatchApplyOut(
            accepted=False,
            reasons=result.reasons,
            case_id=case.id,
            normalized_patch=normalized_patch,
            preview_config=result.preview_config,
        )

    snapshot_version = await _cases._next_snapshot_version(db, case.id)
    db.add(_cases._build_snapshot(case, snapshot_version, user.id))
    await _cases._enforce_snapshot_retention(db, case.id)

    case.config = copy.deepcopy(result.preview_config)
    await _cases._replace_case_steps(
        db,
        case,
        _cases._normalize_steps([], case.case_type, case.config or {}, case.name),
    )

    await _cases.write_audit_log(
        db,
        action="ai_healing_patch_apply",
        resource_type="test_case",
        resource_id=case.id,
        user_id=user.id,
        username=getattr(user, "username", ""),
        project_id=module.project_id,
        detail=(
            f"AI healing patch applied: case_id={case.id}, "
            f"source_run_id={body.source_run_id}, source_step_id={body.source_step_id}, "
            f"patch={normalized_patch}"
        ),
    )
    await db.commit()
    await _cases.invalidate_stats_cache()

    regression_run_id = None
    if body.trigger_regression:
        regression_run_id = await _trigger_regression_run(db, case, user, body, normalized_patch)

    return HealingPatchApplyOut(
        accepted=True,
        reasons=[],
        case_id=case.id,
        snapshot_version=snapshot_version,
        normalized_patch=normalized_patch,
        regression_run_id=regression_run_id,
        preview_config=result.preview_config,
    )


def _resolve_patch(body: HealingPatchPreviewRequest) -> StructuredHealingPatch | None:
    if body.raw_suggestion:
        suggestion = parse_structured_healing_suggestion(body.raw_suggestion)
        return suggestion.patch
    if body.suggestion is None:
        raise ValueError("structured_healing_suggestion_required")
    if body.suggestion.patch is None:
        return None
    return StructuredHealingPatch(
        case_type=body.suggestion.patch.case_type,
        step_index=body.suggestion.patch.step_index,
        action=body.suggestion.patch.action,
        params=body.suggestion.patch.params,
    )


async def _get_case_and_assert_access(
    db: AsyncSession,
    user: User,
    case_id: int,
) -> tuple[TestCase, Module]:
    case = await db.get(TestCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="用例不存在")
    module = await db.get(Module, case.module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="模块不存在")
    await assert_project_access(db, user, module.project_id, ProjectRole.engineer)
    return case, module


def _dump_patch(patch: StructuredHealingPatch | None) -> dict | None:
    if patch is None:
        return None
    return {
        "case_type": patch.case_type,
        "step_index": patch.step_index,
        "action": patch.action,
        "params": patch.params,
    }


async def _trigger_regression_run(
    db: AsyncSession,
    case: TestCase,
    user: User,
    body: HealingPatchApplyRequest,
    normalized_patch: dict | None,
) -> int:
    env_name: str | None = None
    merged_vars = dict(body.extra_vars)
    if body.env_id is not None:
        env = await db.get(Environment, body.env_id)
        if env is None:
            raise HTTPException(status_code=404, detail="环境不存在")
        env_name = env.name
        result = await db.execute(select(EnvVariable).where(EnvVariable.env_id == env.id))
        env_vars = decrypt_env_vars(result.scalars().all())
        merged_vars = {**env_vars, **body.extra_vars}

    run = TestRun(
        case_id=case.id,
        triggered_by=user.id,
        trace_id=_cases.get_trace_id() or None,
        status=RunStatus.pending,
        environment=env_name,
        result_summary={
            "triggered_by_ai_healing_patch": True,
            "source_run_id": body.source_run_id,
            "source_step_id": body.source_step_id,
            "patch": normalized_patch,
        },
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    _cases.run_test_case.delay(run.id, merged_vars, run.trace_id)
    return run.id
