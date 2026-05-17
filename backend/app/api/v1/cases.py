import copy
import csv
import io
import json
import re
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_engineer
from app.core.database import get_db
from app.core.encryption import decrypt_env_vars
from app.core.tracing import get_trace_id
from app.api.v1.statistics import invalidate_stats_cache
from app.models.case import CaseSnapshot, CaseStatus, CaseStep, CaseType, RunStatus, TestCase, TestRun
from app.models.environment import Environment, EnvVariable
from app.models.project import Module, Project
from app.models.user import User
from app.schemas.case import (
    CaseBatchDeleteIn,
    CaseBatchImportOut,
    CaseBatchMoveIn,
    CaseBatchOpOut,
    CaseSnapshotOut,
    CaseWorkflowRequest,
    PaginatedRunsOut,
    PaginatedSnapshotsOut,
    RunTriggerRequest,
    TestCaseCreate,
    TestCaseDetailOut,
    TestCaseOut,
    TestCaseUpdate,
    TestRunOut,
)
from app.services.audit import write_audit_log
from app.worker.tasks import run_test_case

router = APIRouter(tags=["用例管理"])


def _normalize_code_fragment(name: str, fallback_prefix: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]+", " ", name or "").strip()
    if compact:
        parts = [part[:4].upper() for part in compact.split()[:3]]
        merged = "".join(parts)
        if merged:
            return merged[:12]
    return fallback_prefix


def _type_code(case_type: CaseType) -> str:
    mapping = {
        CaseType.api: "API",
        CaseType.web: "WEB",
        CaseType.android: "AND",
        CaseType.graphql: "GQL",
        CaseType.websocket: "WS",
        CaseType.grpc: "GRPC",
    }
    return mapping[case_type]


def _serialize_steps(steps: list[CaseStep] | list[object]) -> list[dict]:
    ordered = sorted(steps, key=lambda item: getattr(item, "step_no", 0))
    return [
        {
            "step_no": getattr(step, "step_no", index + 1),
            "action": getattr(step, "action", ""),
            "test_data": getattr(step, "test_data", None),
            "expected_result": getattr(step, "expected_result", None),
            "is_key_step": bool(getattr(step, "is_key_step", False)),
            "remarks": getattr(step, "remarks", None),
        }
        for index, step in enumerate(ordered)
    ]


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if item is None:
            continue
        if isinstance(item, str):
            if item:
                normalized.append(item)
            continue
        normalized.append(str(item))
    return normalized


def _normalize_case_legacy_fields(case: TestCase) -> TestCase:
    case.preconditions = _normalize_string_list(case.preconditions)
    case.postconditions = _normalize_string_list(case.postconditions)
    case.tags = _normalize_string_list(case.tags)
    return case


def _serialize_case_snapshot(case: TestCase) -> dict:
    return {
        "case_code": case.case_code,
        "name": case.name,
        "description": case.description,
        "summary": case.summary,
        "case_type": case.case_type.value,
        "status": case.status.value,
        "priority": case.priority,
        "case_level": case.case_level,
        "review_status": case.review_status,
        "automation_status": case.automation_status,
        "module_id": case.module_id,
        "creator_id": case.creator_id,
        "owner_id": case.owner_id,
        "preconditions": _normalize_string_list(case.preconditions),
        "postconditions": _normalize_string_list(case.postconditions),
        "tags": _normalize_string_list(case.tags),
        "config": copy.deepcopy(case.config or {}),
        "steps": _serialize_steps(case.steps or []),
    }


def _build_snapshot(case: TestCase, version: int, updated_by: int) -> CaseSnapshot:
    snapshot_data = _serialize_case_snapshot(case)
    return CaseSnapshot(
        case_id=case.id,
        version=version,
        name=case.name,
        description=case.description,
        tags=_normalize_string_list(case.tags),
        config=copy.deepcopy(case.config or {}),
        snapshot_data=snapshot_data,
        updated_by=updated_by,
    )


def _derive_steps_from_config(case_type: CaseType, config: dict, fallback_name: str) -> list[dict]:
    config = config or {}
    raw_steps = config.get("steps")
    if isinstance(raw_steps, list) and raw_steps:
        derived_steps: list[dict] = []
        for index, step in enumerate(raw_steps, start=1):
            params = step.get("params") if isinstance(step, dict) else None
            test_data = params if params is not None else step
            expected = step.get("assertions") if isinstance(step, dict) else None
            if not expected and isinstance(step, dict):
                expected = step.get("expected_result") or step.get("text")
            derived_steps.append(
                {
                    "step_no": index,
                    "action": step.get("name") or step.get("action") or f"{fallback_name} step {index}",
                    "test_data": json.dumps(test_data, ensure_ascii=False) if test_data is not None else None,
                    "expected_result": (
                        json.dumps(expected, ensure_ascii=False)
                        if isinstance(expected, (dict, list))
                        else (str(expected) if expected not in (None, "") else None)
                    ),
                    "is_key_step": index == 1,
                    "remarks": None,
                }
            )
        return derived_steps

    if config.get("script_path"):
        return [
            {
                "step_no": 1,
                "action": f"Execute {case_type.value} automation script",
                "test_data": config.get("script_path"),
                "expected_result": "Script completes successfully",
                "is_key_step": True,
                "remarks": None,
            }
        ]

    return [
        {
            "step_no": 1,
            "action": f"Execute {fallback_name}",
            "test_data": None,
            "expected_result": None,
            "is_key_step": True,
            "remarks": None,
        }
    ]


def _normalize_steps(body_steps: list[object], case_type: CaseType, config: dict, fallback_name: str) -> list[dict]:
    source = body_steps or _derive_steps_from_config(case_type, config, fallback_name)
    normalized: list[dict] = []
    for index, step in enumerate(source, start=1):
        if hasattr(step, "model_dump"):
            payload = step.model_dump()
        else:
            payload = dict(step)
        normalized.append(
            {
                "step_no": payload.get("step_no") or index,
                "action": payload.get("action") or f"Step {index}",
                "test_data": payload.get("test_data"),
                "expected_result": payload.get("expected_result"),
                "is_key_step": bool(payload.get("is_key_step", False)),
                "remarks": payload.get("remarks"),
            }
        )
    normalized.sort(key=lambda item: item["step_no"])
    for index, item in enumerate(normalized, start=1):
        item["step_no"] = index
    return normalized


async def _replace_case_steps(db: AsyncSession, case: TestCase, steps_payload: list[dict]) -> None:
    if case.id is not None and case.steps:
        case.steps.clear()
        await db.flush()

    case.steps.extend(
        [
            CaseStep(
                step_no=step["step_no"],
                action=step["action"],
                test_data=step.get("test_data"),
                expected_result=step.get("expected_result"),
                is_key_step=step.get("is_key_step", False),
                remarks=step.get("remarks"),
            )
            for step in steps_payload
        ]
    )


async def _next_snapshot_version(db: AsyncSession, case_id: int) -> int:
    await db.execute(select(TestCase.id).where(TestCase.id == case_id).with_for_update())
    max_ver = await db.scalar(
        select(func.coalesce(func.max(CaseSnapshot.version), 0)).where(CaseSnapshot.case_id == case_id)
    )
    return (max_ver or 0) + 1


async def _get_case_detail_or_404(db: AsyncSession, case_id: int) -> TestCase:
    result = await db.execute(
        select(TestCase)
        .where(TestCase.id == case_id)
        .options(selectinload(TestCase.steps))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    return _normalize_case_legacy_fields(case)


async def _get_module_for_case_code(db: AsyncSession, module_id: int) -> Module:
    result = await db.execute(
        select(Module)
        .where(Module.id == module_id)
        .options(selectinload(Module.project))
    )
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="模块不存在")
    project = module.project
    if project is None:
        raise HTTPException(status_code=400, detail="模块缺少所属项目")
    if not project.project_code:
        project.project_code = _normalize_code_fragment(project.name, f"P{project.id}")
    if not module.module_code:
        module.module_code = _normalize_code_fragment(module.name, f"M{module.id}")
    return module


async def _generate_case_code(db: AsyncSession, module: Module, case_type: CaseType) -> str:
    prefix = f"{module.project.project_code}-{module.module_code}-{_type_code(case_type)}"
    result = await db.execute(
        select(TestCase.case_code)
        .where(TestCase.module_id == module.id, TestCase.case_type == case_type)
        .order_by(TestCase.id.desc())
    )
    max_sequence = 0
    for case_code in result.scalars().all():
        if not case_code or not case_code.startswith(prefix):
            continue
        suffix = case_code.rsplit("-", 1)[-1]
        if suffix.isdigit():
            max_sequence = max(max_sequence, int(suffix))
    return f"{prefix}-{max_sequence + 1:04d}"


def _reset_review_after_edit(case: TestCase) -> None:
    case.status = CaseStatus.draft
    case.review_status = "pending"
    case.submitted_at = None
    case.reviewed_at = None
    case.reviewed_by = None
    case.review_comment = None


def _assert_can_trigger_run(case: TestCase) -> None:
    if case.status != CaseStatus.active:
        raise HTTPException(status_code=409, detail="仅 active 状态用例可执行")
    if case.review_status != "approved":
        raise HTTPException(status_code=409, detail="仅审核通过的用例可执行")
    if case.automation_status not in {"auto", "semi_auto"}:
        raise HTTPException(status_code=409, detail="当前用例未配置为可自动执行")


@router.get("/cases", response_model=list[TestCaseOut])
async def list_cases(
    project_id: int | None = None,
    module_id: int | None = None,
    case_type: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    review_status: str | None = None,
    owner_id: int | None = None,
    automation_status: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    query = select(TestCase)
    if project_id:
        query = query.join(Module, TestCase.module_id == Module.id).where(Module.project_id == project_id)
    if module_id:
        query = query.where(TestCase.module_id == module_id)
    if case_type:
        query = query.where(TestCase.case_type == case_type)
    if priority:
        query = query.where(TestCase.priority == priority)
    if status:
        query = query.where(TestCase.status == status)
    if review_status:
        query = query.where(TestCase.review_status == review_status)
    if owner_id:
        query = query.where(TestCase.owner_id == owner_id)
    if automation_status:
        query = query.where(TestCase.automation_status == automation_status)
    if keyword:
        like_keyword = f"%{keyword.strip()}%"
        query = query.where(
            or_(
                TestCase.name.ilike(like_keyword),
                TestCase.summary.ilike(like_keyword),
                TestCase.case_code.ilike(like_keyword),
            )
        )
    result = await db.execute(query.order_by(TestCase.updated_at.desc(), TestCase.created_at.desc()))
    items = result.scalars().all()
    if tag:
        items = [case for case in items if tag in (case.tags or [])]
    return items


@router.post("/cases", response_model=TestCaseDetailOut, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = await _get_module_for_case_code(db, body.module_id)
    steps_payload = _normalize_steps(body.steps, body.case_type, body.config, body.name)
    case = TestCase(
        name=body.name,
        description=body.description,
        case_code=await _generate_case_code(db, module, body.case_type),
        summary=body.summary or body.description or body.name,
        case_type=body.case_type,
        status=CaseStatus.draft,
        priority=body.priority,
        case_level=body.case_level,
        review_status="pending",
        automation_status=body.automation_status,
        tags=list(body.tags),
        module_id=body.module_id,
        creator_id=current_user.id,
        owner_id=body.owner_id or current_user.id,
        preconditions=list(body.preconditions),
        postconditions=list(body.postconditions),
        config=copy.deepcopy(body.config),
    )
    await _replace_case_steps(db, case, steps_payload)
    db.add(case)
    await db.commit()
    await invalidate_stats_cache()
    case = await _get_case_detail_or_404(db, case.id)
    await write_audit_log(
        db,
        action="create",
        resource_type="test_case",
        resource_id=case.id,
        user_id=current_user.id,
        username=getattr(current_user, "username", ""),
        detail=f"创建用例: {case.name}",
    )
    await db.commit()
    return case


@router.get("/cases/{case_id}", response_model=TestCaseDetailOut)
async def get_case(case_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    return await _get_case_detail_or_404(db, case_id)


@router.patch("/cases/{case_id}", response_model=TestCaseDetailOut)
async def update_case(
    case_id: int,
    body: TestCaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _get_case_detail_or_404(db, case_id)
    db.add(_build_snapshot(case, await _next_snapshot_version(db, case_id), current_user.id))

    payload = body.model_dump(exclude_none=True)
    if "name" in payload:
        case.name = payload["name"]
    if "description" in payload:
        case.description = payload["description"]
    if "summary" in payload:
        case.summary = payload["summary"] or case.name
    if "tags" in payload:
        case.tags = list(payload["tags"])
    if "preconditions" in payload:
        case.preconditions = list(payload["preconditions"])
    if "postconditions" in payload:
        case.postconditions = list(payload["postconditions"])
    if "priority" in payload:
        case.priority = payload["priority"]
    if "case_level" in payload:
        case.case_level = payload["case_level"]
    if "owner_id" in payload:
        case.owner_id = payload["owner_id"]
    if "automation_status" in payload:
        case.automation_status = payload["automation_status"]
    if "config" in payload:
        case.config = copy.deepcopy(payload["config"])

    if "steps" in payload:
        await _replace_case_steps(
            db,
            case,
            _normalize_steps(payload["steps"] or [], case.case_type, case.config or {}, payload.get("name") or case.name),
        )
    elif "config" in payload:
        await _replace_case_steps(db, case, _normalize_steps([], case.case_type, case.config or {}, case.name))

    if case.review_status == "approved":
        _reset_review_after_edit(case)

    await db.commit()
    return await _get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/copy", response_model=TestCaseDetailOut, status_code=status.HTTP_201_CREATED)
async def copy_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = await _get_case_detail_or_404(db, case_id)
    module = await _get_module_for_case_code(db, source.module_id)
    cloned = TestCase(
        name=f"{source.name} Copy",
        description=source.description,
        case_code=await _generate_case_code(db, module, source.case_type),
        summary=source.summary,
        case_type=source.case_type,
        status=CaseStatus.draft,
        priority=source.priority,
        case_level=source.case_level,
        review_status="pending",
        automation_status=source.automation_status,
        tags=_normalize_string_list(source.tags),
        module_id=source.module_id,
        creator_id=current_user.id,
        owner_id=current_user.id,
        preconditions=_normalize_string_list(source.preconditions),
        postconditions=_normalize_string_list(source.postconditions),
        config=copy.deepcopy(source.config or {}),
    )
    await _replace_case_steps(db, cloned, _serialize_steps(source.steps or []))
    db.add(cloned)
    await db.commit()
    await invalidate_stats_cache()
    return await _get_case_detail_or_404(db, cloned.id)


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    case_name = case.name
    await db.delete(case)
    await write_audit_log(
        db,
        action="delete",
        resource_type="test_case",
        resource_id=case_id,
        user_id=current_user.id,
        username=getattr(current_user, "username", ""),
        detail=f"删除用例: {case_name}",
    )
    await db.commit()
    await invalidate_stats_cache()


@router.post("/cases/batch/delete", response_model=CaseBatchOpOut)
async def batch_delete_cases(
    body: CaseBatchDeleteIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    requested_ids = list(dict.fromkeys(body.case_ids))
    rows = (
        (await db.execute(select(TestCase).where(TestCase.id.in_(requested_ids))))
        .scalars()
        .all()
    )
    found_ids = {row.id for row in rows}
    skipped_ids = [cid for cid in requested_ids if cid not in found_ids]

    for case in rows:
        await db.delete(case)

    if rows:
        await write_audit_log(
            db,
            action="batch_delete",
            resource_type="test_case",
            resource_id=0,
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
            detail=f"批量删除用例 {len(rows)} 个: {[case.id for case in rows]}",
        )
    await db.commit()
    if rows:
        await invalidate_stats_cache()

    return CaseBatchOpOut(
        requested=len(requested_ids),
        processed=len(rows),
        skipped_ids=skipped_ids,
    )


@router.post("/cases/batch/move", response_model=CaseBatchOpOut)
async def batch_move_cases(
    body: CaseBatchMoveIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    target_module = await db.get(Module, body.target_module_id)
    if not target_module:
        raise HTTPException(status_code=404, detail="目标模块不存在")

    requested_ids = list(dict.fromkeys(body.case_ids))
    rows = (
        (await db.execute(select(TestCase).where(TestCase.id.in_(requested_ids))))
        .scalars()
        .all()
    )
    found_ids = {row.id for row in rows}
    skipped_ids = [cid for cid in requested_ids if cid not in found_ids]

    moved: list[int] = []
    for case in rows:
        if case.module_id == target_module.id:
            skipped_ids.append(case.id)
            continue
        case.module_id = target_module.id
        moved.append(case.id)

    if moved:
        await write_audit_log(
            db,
            action="batch_move",
            resource_type="test_case",
            resource_id=target_module.id,
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
            detail=f"批量移动用例 {len(moved)} 个到模块 {target_module.id}: {moved}",
        )
    await db.commit()
    if moved:
        await invalidate_stats_cache()

    return CaseBatchOpOut(
        requested=len(requested_ids),
        processed=len(moved),
        skipped_ids=skipped_ids,
    )


@router.get("/cases/batch/export")
async def batch_export_cases(
    case_ids: str = Query(..., description="逗号分隔的用例 ID"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        id_values = [int(s.strip()) for s in case_ids.split(",") if s.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="case_ids 必须为逗号分隔的整数")
    if not id_values:
        raise HTTPException(status_code=400, detail="case_ids 不能为空")
    if len(id_values) > 1000:
        raise HTTPException(status_code=400, detail="单次导出最多 1000 个用例")

    rows = (
        (await db.execute(select(TestCase).where(TestCase.id.in_(id_values))))
        .scalars()
        .all()
    )
    rows_by_id = {row.id: row for row in rows}
    ordered = [rows_by_id[cid] for cid in id_values if cid in rows_by_id]

    buffer = io.StringIO()
    buffer.write("﻿")  # Excel 友好 BOM
    writer = csv.writer(buffer)
    writer.writerow([
        "id", "case_code", "name", "summary", "case_type", "status",
        "priority", "case_level", "review_status", "automation_status",
        "module_id", "tags", "created_at",
    ])
    for case in ordered:
        writer.writerow([
            case.id,
            case.case_code,
            case.name,
            case.summary or "",
            case.case_type.value if hasattr(case.case_type, "value") else str(case.case_type),
            case.status.value if hasattr(case.status, "value") else str(case.status),
            case.priority,
            case.case_level,
            case.review_status,
            case.automation_status,
            case.module_id,
            ",".join(case.tags or []),
            case.created_at.isoformat() if case.created_at else "",
        ])

    filename = f"cases-export-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.csv"
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_ZIP_MANIFEST_NAME = "manifest.json"
_ZIP_CASES_NAME = "cases.json"
_ZIP_SCHEMA_VERSION = 1
_ZIP_IMPORT_MAX_DECOMPRESSED_BYTES = 50 * 1024 * 1024  # 50MB 防 zip bomb


def _serialize_case_for_zip(case: TestCase) -> dict:
    return {
        "case_code": case.case_code,
        "name": case.name,
        "description": case.description,
        "summary": case.summary,
        "case_type": case.case_type.value if hasattr(case.case_type, "value") else str(case.case_type),
        "priority": case.priority,
        "case_level": case.case_level,
        "automation_status": case.automation_status,
        "tags": list(case.tags or []),
        "preconditions": list(case.preconditions or []),
        "postconditions": list(case.postconditions or []),
        "config": case.config or {},
        "steps": _serialize_steps(case.steps or []),
        "source_module_id": case.module_id,
    }


@router.get("/cases/batch/export-zip")
async def batch_export_cases_zip(
    case_ids: str = Query(..., description="逗号分隔的用例 ID"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        id_values = [int(s.strip()) for s in case_ids.split(",") if s.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="case_ids 必须为逗号分隔的整数")
    if not id_values:
        raise HTTPException(status_code=400, detail="case_ids 不能为空")
    if len(id_values) > 500:
        raise HTTPException(status_code=400, detail="单次 ZIP 导出最多 500 个用例")

    rows = (
        (
            await db.execute(
                select(TestCase)
                .options(selectinload(TestCase.steps))
                .where(TestCase.id.in_(id_values))
            )
        )
        .scalars()
        .all()
    )
    rows_by_id = {row.id: row for row in rows}
    ordered = [rows_by_id[cid] for cid in id_values if cid in rows_by_id]

    serialized = [_serialize_case_for_zip(case) for case in ordered]
    manifest = {
        "schema_version": _ZIP_SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(serialized),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_ZIP_MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(_ZIP_CASES_NAME, json.dumps(serialized, ensure_ascii=False, indent=2))

    filename = f"cases-export-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.zip"
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/cases/batch/import-zip", response_model=CaseBatchImportOut)
async def batch_import_cases_zip(
    target_module_id: int = Query(..., description="目标模块 ID"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    module = await db.get(Module, target_module_id)
    if not module:
        raise HTTPException(status_code=404, detail="目标模块不存在")

    payload_bytes = await file.read()
    if not payload_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空")
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload_bytes))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="文件不是合法的 ZIP")

    try:
        info = archive.getinfo(_ZIP_CASES_NAME)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"ZIP 缺少 {_ZIP_CASES_NAME}")
    if info.file_size > _ZIP_IMPORT_MAX_DECOMPRESSED_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"{_ZIP_CASES_NAME} 解压后大小超过 {_ZIP_IMPORT_MAX_DECOMPRESSED_BYTES // (1024 * 1024)} MB 限制",
        )

    try:
        with archive.open(_ZIP_CASES_NAME) as fh:
            cases_data = json.loads(fh.read().decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail=f"{_ZIP_CASES_NAME} 不是合法 JSON")

    if not isinstance(cases_data, list):
        raise HTTPException(status_code=400, detail=f"{_ZIP_CASES_NAME} 必须是数组")

    created_ids: list[int] = []
    errors: list[str] = []
    skipped = 0
    target_module = await _get_module_for_case_code(db, target_module_id)

    for index, entry in enumerate(cases_data):
        try:
            if not isinstance(entry, dict):
                raise ValueError("条目不是对象")
            case_type_raw = entry.get("case_type")
            try:
                case_type = CaseType(case_type_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"无效的 case_type: {case_type_raw}") from exc

            name = (entry.get("name") or "").strip()
            if not name:
                raise ValueError("name 不能为空")

            steps_payload = entry.get("steps") or []
            new_case = TestCase(
                name=name,
                description=entry.get("description"),
                case_code=await _generate_case_code(db, target_module, case_type),
                summary=entry.get("summary") or entry.get("description") or name,
                case_type=case_type,
                status=CaseStatus.draft,
                priority=entry.get("priority") or "P2",
                case_level=entry.get("case_level") or "regression",
                review_status="pending",
                automation_status=entry.get("automation_status") or "auto",
                tags=list(entry.get("tags") or []),
                module_id=target_module_id,
                creator_id=current_user.id,
                owner_id=current_user.id,
                preconditions=list(entry.get("preconditions") or []),
                postconditions=list(entry.get("postconditions") or []),
                config=entry.get("config") or {},
            )
            db.add(new_case)
            await db.flush()
            for step_no, step in enumerate(steps_payload, start=1):
                if not isinstance(step, dict):
                    continue
                db.add(
                    CaseStep(
                        case_id=new_case.id,
                        step_no=int(step.get("step_no") or step_no),
                        action=str(step.get("action") or ""),
                        test_data=step.get("test_data"),
                        expected_result=step.get("expected_result"),
                        is_key_step=bool(step.get("is_key_step", False)),
                        remarks=step.get("remarks"),
                    )
                )
            created_ids.append(new_case.id)
        except Exception as exc:
            skipped += 1
            errors.append(f"第 {index + 1} 条: {exc}")
            continue

    await db.commit()
    if created_ids:
        await invalidate_stats_cache()

    return CaseBatchImportOut(
        imported=len(created_ids),
        skipped_count=skipped,
        target_module_id=target_module_id,
        created_ids=created_ids,
        errors=errors[:50],
    )


@router.post("/cases/{case_id}/submit-review", response_model=TestCaseDetailOut)
async def submit_review(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    case = await _get_case_detail_or_404(db, case_id)
    if case.status == CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="废弃用例不能提交审核")
    case.review_status = "pending"
    case.submitted_at = datetime.now(timezone.utc)
    case.reviewed_at = None
    case.reviewed_by = None
    case.review_comment = body.comment
    await db.commit()
    return await _get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/approve", response_model=TestCaseDetailOut)
async def approve_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _get_case_detail_or_404(db, case_id)
    if case.review_status != "pending":
        raise HTTPException(status_code=409, detail="只有待审核用例可批准")
    if case.status == CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="废弃用例不能批准")
    case.review_status = "approved"
    case.status = CaseStatus.active
    case.reviewed_at = datetime.now(timezone.utc)
    case.reviewed_by = current_user.id
    case.review_comment = body.comment
    await db.commit()
    return await _get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/reject", response_model=TestCaseDetailOut)
async def reject_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _get_case_detail_or_404(db, case_id)
    if case.review_status != "pending":
        raise HTTPException(status_code=409, detail="只有待审核用例可驳回")
    case.review_status = "rejected"
    case.status = CaseStatus.draft
    case.reviewed_at = datetime.now(timezone.utc)
    case.reviewed_by = current_user.id
    case.review_comment = body.comment
    await db.commit()
    return await _get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/deprecate", response_model=TestCaseDetailOut)
async def deprecate_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    case = await _get_case_detail_or_404(db, case_id)
    if case.status == CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="用例已经废弃")
    case.status = CaseStatus.deprecated
    case.review_comment = body.comment or case.review_comment
    await db.commit()
    return await _get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/reactivate", response_model=TestCaseDetailOut)
async def reactivate_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    case = await _get_case_detail_or_404(db, case_id)
    if case.status != CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="只有废弃用例可重新激活")
    if case.review_status != "approved":
        raise HTTPException(status_code=409, detail="仅审核通过的用例可重新激活")
    case.status = CaseStatus.active
    case.review_comment = body.comment or case.review_comment
    await db.commit()
    return await _get_case_detail_or_404(db, case_id)


@router.get("/cases/{case_id}/snapshots", response_model=PaginatedSnapshotsOut)
async def list_snapshots(
    case_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    await _get_case_detail_or_404(db, case_id)
    total = await db.scalar(
        select(func.count()).select_from(
            select(CaseSnapshot.id).where(CaseSnapshot.case_id == case_id).subquery()
        )
    )
    result = await db.execute(
        select(CaseSnapshot, User.username)
        .outerjoin(User, CaseSnapshot.updated_by == User.id)
        .where(CaseSnapshot.case_id == case_id)
        .order_by(CaseSnapshot.version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for snapshot, username in result.all():
        out = CaseSnapshotOut.model_validate(snapshot)
        out.updated_by_name = username or ""
        items.append(out)
    return PaginatedSnapshotsOut(items=items, total=total or 0, page=page, page_size=page_size)


@router.get("/cases/{case_id}/snapshots/{snapshot_id}", response_model=CaseSnapshotOut)
async def get_snapshot(
    case_id: int,
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    snapshot = await db.get(CaseSnapshot, snapshot_id)
    if not snapshot or snapshot.case_id != case_id:
        raise HTTPException(status_code=404, detail="快照不存在")
    return snapshot


@router.post("/cases/{case_id}/rollback/{snapshot_id}", response_model=TestCaseDetailOut)
async def rollback_case(
    case_id: int,
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _get_case_detail_or_404(db, case_id)
    snapshot = await db.get(CaseSnapshot, snapshot_id)
    if not snapshot or snapshot.case_id != case_id:
        raise HTTPException(status_code=404, detail="快照不存在")

    db.add(_build_snapshot(case, await _next_snapshot_version(db, case_id), current_user.id))

    data = snapshot.snapshot_data or {}
    case.name = data.get("name", snapshot.name)
    case.description = data.get("description", snapshot.description)
    case.summary = data.get("summary", case.name)
    case.case_type = CaseType(data.get("case_type", case.case_type.value))
    case.status = CaseStatus(data.get("status", case.status.value))
    case.priority = data.get("priority", case.priority)
    case.case_level = data.get("case_level", case.case_level)
    case.review_status = data.get("review_status", case.review_status)
    case.automation_status = data.get("automation_status", case.automation_status)
    case.owner_id = data.get("owner_id", case.owner_id)
    case.preconditions = _normalize_string_list(data.get("preconditions", []))
    case.postconditions = _normalize_string_list(data.get("postconditions", []))
    case.tags = _normalize_string_list(data.get("tags", snapshot.tags or []))
    case.config = copy.deepcopy(data.get("config", snapshot.config or {}))
    await _replace_case_steps(
        db,
        case,
        data.get("steps") or _derive_steps_from_config(case.case_type, case.config, case.name),
    )
    await db.commit()
    return await _get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/run", response_model=TestRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    case_id: int,
    body: RunTriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    _assert_can_trigger_run(case)

    env_name: str | None = None
    merged_vars = dict(body.extra_vars)
    if body.env_id is not None:
        env = await db.get(Environment, body.env_id)
        if not env:
            raise HTTPException(status_code=404, detail="环境不存在")
        env_name = env.name
        result = await db.execute(select(EnvVariable).where(EnvVariable.env_id == env.id))
        env_vars = decrypt_env_vars(result.scalars().all())
        merged_vars = {**env_vars, **body.extra_vars}

    run = TestRun(
        case_id=case_id,
        triggered_by=current_user.id,
        trace_id=get_trace_id() or None,
        status=RunStatus.pending,
        environment=env_name,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    run_test_case.delay(run.id, merged_vars, run.trace_id)
    result = await db.execute(select(TestRun).where(TestRun.id == run.id).options(selectinload(TestRun.steps)))
    return TestRunOut.model_validate(result.scalar_one())


@router.get("/runs", response_model=PaginatedRunsOut)
async def list_runs(
    case_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    base = select(TestRun)
    if case_id:
        base = base.where(TestRun.case_id == case_id)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    query = base.options(selectinload(TestRun.steps)).order_by(TestRun.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return PaginatedRunsOut(
        items=result.scalars().all(),
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}", response_model=TestRunOut)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(TestRun).where(TestRun.id == run_id).options(selectinload(TestRun.steps)))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return run
