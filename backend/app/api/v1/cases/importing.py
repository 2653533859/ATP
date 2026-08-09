"""Transactional case import preview and commit endpoints."""

from __future__ import annotations

import copy

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.v1.cases as _cases
from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.case import CaseStatus, TestCase
from app.models.project import Module
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.case_import import CaseImportConflict, CaseImportOut, CaseImportPreviewOut, CaseImportRequest

router = APIRouter(tags=["用例导入"])


async def _preview(
    db: AsyncSession, project_id: int, body: CaseImportRequest
) -> tuple[CaseImportPreviewOut, dict[tuple[int, str], TestCase], dict[int, Module]]:
    modules = {}
    for item in body.cases:
        if item.module_id in modules:
            continue
        module = await db.get(Module, item.module_id)
        if module is not None and module.project_id == project_id:
            modules[item.module_id] = module

    module_ids = list(modules)
    existing: dict[tuple[int, str], TestCase] = {}
    if module_ids:
        result = await db.execute(select(TestCase).where(TestCase.module_id.in_(module_ids)))
        existing = {(item.module_id, item.name.strip()): item for item in result.scalars().all()}

    conflicts: list[CaseImportConflict] = []
    seen: set[tuple[int, str]] = set()
    errors: list[str] = []
    for index, item in enumerate(body.cases):
        key = (item.module_id, item.name.strip())
        if item.module_id not in modules:
            errors.append(f"第 {index + 1} 项模块不属于当前项目: {item.module_id}")
        elif not item.name.strip():
            errors.append(f"第 {index + 1} 项用例名称不能为空")
        elif key in seen:
            conflicts.append(
                CaseImportConflict(index=index, module_id=item.module_id, name=item.name, reason="导入内容重复")
            )
        elif key in existing:
            conflicts.append(
                CaseImportConflict(index=index, module_id=item.module_id, name=item.name, reason="项目中已存在同名用例")
            )
        seen.add(key)
    invalid_count = len(errors) + len(conflicts)
    return (
        CaseImportPreviewOut(
            total=len(body.cases),
            valid_count=max(0, len(body.cases) - invalid_count),
            invalid_count=invalid_count,
            conflicts=conflicts,
            errors=errors,
        ),
        existing,
        modules,
    )


@router.post("/projects/{project_id}/cases/import-preview", response_model=CaseImportPreviewOut)
async def preview_case_import(
    project_id: int,
    body: CaseImportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, project_id, ProjectRole.editor)
    preview, _, _ = await _preview(db, project_id, body)
    return preview


@router.post("/projects/{project_id}/cases/import", response_model=CaseImportOut, status_code=status.HTTP_201_CREATED)
async def import_cases(
    project_id: int,
    body: CaseImportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, project_id, ProjectRole.editor)
    preview, existing, modules = await _preview(db, project_id, body)
    if preview.errors:
        raise HTTPException(status_code=400, detail=preview.errors)
    if preview.conflicts and body.conflict_policy == "fail":
        raise HTTPException(status_code=409, detail={"message": "导入存在冲突", "conflicts": preview.conflicts})

    conflict_keys = {(item.module_id, item.name.strip()) for item in preview.conflicts}
    imported_ids: list[int] = []
    skipped_count = 0
    seen_import_keys: set[tuple[int, str]] = set()
    try:
        for item in body.cases:
            key = (item.module_id, item.name.strip())
            if key in seen_import_keys:
                skipped_count += 1
                continue
            seen_import_keys.add(key)
            target = existing.get(key)
            if target is not None and body.conflict_policy == "skip":
                skipped_count += 1
                continue
            module = modules[item.module_id]
            dataset_id, dataset_version = await _cases._resolve_dataset_binding(
                db, item.dataset_id, item.dataset_version, project_id
            )
            steps_payload = _cases._normalize_steps(item.steps, item.case_type, item.config, item.name)
            if target is not None and body.conflict_policy == "replace":
                target.description = item.description
                target.summary = item.summary or item.description or item.name
                target.priority = item.priority
                target.case_level = item.case_level
                target.tags = list(item.tags)
                target.config = copy.deepcopy(item.config)
                target.dataset_id = dataset_id
                target.dataset_version = dataset_version
                await _cases._replace_case_steps(db, target, steps_payload)
                imported_ids.append(target.id)
                continue
            case = TestCase(
                name=item.name,
                description=item.description,
                case_code=await _cases._generate_case_code(db, module, item.case_type),
                summary=item.summary or item.description or item.name,
                case_type=item.case_type,
                status=CaseStatus.draft,
                priority=item.priority,
                case_level=item.case_level,
                review_status="pending",
                automation_status=item.automation_status,
                tags=list(item.tags),
                module_id=item.module_id,
                creator_id=user.id,
                owner_id=item.owner_id or user.id,
                preconditions=list(item.preconditions),
                postconditions=list(item.postconditions),
                config=copy.deepcopy(item.config),
                dataset_id=dataset_id,
                dataset_version=dataset_version,
            )
            await _cases._replace_case_steps(db, case, steps_payload)
            db.add(case)
            await db.flush()
            imported_ids.append(case.id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    await _cases.invalidate_stats_cache()
    return CaseImportOut(
        imported=len(imported_ids),
        skipped_count=skipped_count,
        case_ids=imported_ids,
        conflicts=preview.conflicts if conflict_keys else [],
    )
