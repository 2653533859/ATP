"""cases 包 - 批量操作（删除 / 移动 / 导出 CSV / 导出 ZIP / 导入 ZIP）。"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone

import app.api.v1.cases as _cases
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_engineer
from app.core.database import get_db
from app.models.case import CaseStatus, CaseStep, CaseType, TestCase
from app.models.project import Module
from app.models.user import User
from app.schemas.case import (
    CaseBatchDeleteIn,
    CaseBatchImportOut,
    CaseBatchImportPreviewItem,
    CaseBatchImportPreviewOut,
    CaseBatchMoveIn,
    CaseBatchOpOut,
)

router = APIRouter(tags=["用例管理"])


_ZIP_MANIFEST_NAME = "manifest.json"
_ZIP_CASES_NAME = "cases.json"
_ZIP_SCHEMA_VERSION = 1
_ZIP_IMPORT_MAX_DECOMPRESSED_BYTES = 50 * 1024 * 1024  # 50MB 防 zip bomb
_ZIP_TEMPLATE_CASES = [
    {
        "name": "示例 API 用例",
        "description": "验证登录接口返回成功",
        "summary": "登录成功",
        "case_type": "api",
        "priority": "P2",
        "case_level": "regression",
        "automation_status": "auto",
        "tags": ["import-template"],
        "preconditions": ["测试账号已存在"],
        "postconditions": [],
        "config": {
            "method": "POST",
            "url": "/api/login",
            "headers": {"Content-Type": "application/json"},
            "body": {"username": "tester", "password": "password"},
        },
        "steps": [
            {
                "step_no": 1,
                "action": "发送登录请求",
                "test_data": {"username": "tester"},
                "expected_result": "返回 200 且包含 token",
                "is_key_step": True,
            }
        ],
    }
]


@router.post("/cases/batch/delete", response_model=CaseBatchOpOut)
async def batch_delete_cases(
    body: CaseBatchDeleteIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    requested_ids = list(dict.fromkeys(body.case_ids))
    rows = (await db.execute(select(TestCase).where(TestCase.id.in_(requested_ids)))).scalars().all()
    found_ids = {row.id for row in rows}
    skipped_ids = [cid for cid in requested_ids if cid not in found_ids]

    for case in rows:
        await db.delete(case)

    if rows:
        await _cases.write_audit_log(
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
        await _cases.invalidate_stats_cache()

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
    rows = (await db.execute(select(TestCase).where(TestCase.id.in_(requested_ids)))).scalars().all()
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
        await _cases.write_audit_log(
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
        await _cases.invalidate_stats_cache()

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

    rows = (await db.execute(select(TestCase).where(TestCase.id.in_(id_values)))).scalars().all()
    rows_by_id = {row.id: row for row in rows}
    ordered = [rows_by_id[cid] for cid in id_values if cid in rows_by_id]

    buffer = io.StringIO()
    buffer.write("﻿")  # Excel 友好 BOM
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "case_code",
            "name",
            "summary",
            "case_type",
            "status",
            "priority",
            "case_level",
            "review_status",
            "automation_status",
            "module_id",
            "tags",
            "created_at",
        ]
    )
    for case in ordered:
        writer.writerow(
            [
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
            ]
        )

    filename = f"cases-export-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.csv"
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
        "steps": _cases._serialize_steps(case.steps or []),
        "source_module_id": case.module_id,
    }


def _read_cases_from_import_zip(payload_bytes: bytes) -> list[dict]:
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
    return cases_data


def _validate_import_cases(cases_data: list[dict]) -> tuple[list[dict], list[str], list[CaseBatchImportPreviewItem]]:
    valid_entries: list[dict] = []
    errors: list[str] = []
    preview_cases: list[CaseBatchImportPreviewItem] = []

    for index, entry in enumerate(cases_data):
        row = index + 1
        try:
            if not isinstance(entry, dict):
                raise ValueError("条目不是对象")

            case_type_raw = entry.get("case_type")
            try:
                CaseType(case_type_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"无效的 case_type: {case_type_raw}") from exc

            name = (entry.get("name") or "").strip()
            if not name:
                raise ValueError("name 不能为空")

            steps_payload = entry.get("steps") or []
            if not isinstance(steps_payload, list):
                raise ValueError("steps 必须是数组")

            valid_entries.append(entry)
            if len(preview_cases) < 20:
                preview_cases.append(
                    CaseBatchImportPreviewItem(
                        row=row,
                        name=name,
                        case_type=str(case_type_raw),
                        priority=str(entry.get("priority") or "P2"),
                        step_count=len(steps_payload),
                    )
                )
        except Exception as exc:
            errors.append(f"第 {row} 条: {exc}")
    return valid_entries, errors, preview_cases


@router.get("/cases/batch/import-template")
async def download_case_import_template(_: User = Depends(require_engineer)):
    manifest = {
        "schema_version": _ZIP_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(_ZIP_TEMPLATE_CASES),
        "notes": "编辑 cases.json 后保持 ZIP 内文件名不变，再通过用例管理页导入。",
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_ZIP_MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(_ZIP_CASES_NAME, json.dumps(_ZIP_TEMPLATE_CASES, ensure_ascii=False, indent=2))

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="case-import-template.zip"'},
    )


@router.post("/cases/batch/import-preview", response_model=CaseBatchImportPreviewOut)
async def preview_case_import_zip(
    file: UploadFile = File(...),
    _: User = Depends(require_engineer),
):
    cases_data = _read_cases_from_import_zip(await file.read())
    valid_entries, errors, preview_cases = _validate_import_cases(cases_data)
    return CaseBatchImportPreviewOut(
        total=len(cases_data),
        valid_count=len(valid_entries),
        invalid_count=len(errors),
        preview_cases=preview_cases,
        errors=errors[:50],
    )


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
        (await db.execute(select(TestCase).options(selectinload(TestCase.steps)).where(TestCase.id.in_(id_values))))
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

    cases_data = _read_cases_from_import_zip(await file.read())
    valid_entries, validation_errors, _ = _validate_import_cases(cases_data)

    created_ids: list[int] = []
    errors: list[str] = list(validation_errors)
    skipped = 0
    target_module = await _cases._get_module_for_case_code(db, target_module_id)

    for entry in valid_entries:
        try:
            case_type = CaseType(entry.get("case_type"))
            name = (entry.get("name") or "").strip()
            steps_payload = entry.get("steps") or []
            new_case = TestCase(
                name=name,
                description=entry.get("description"),
                case_code=await _cases._generate_case_code(db, target_module, case_type),
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
            errors.append(str(exc))
            continue

    await db.commit()
    if created_ids:
        await _cases.invalidate_stats_cache()

    return CaseBatchImportOut(
        imported=len(created_ids),
        skipped_count=len(validation_errors) + skipped,
        target_module_id=target_module_id,
        created_ids=created_ids,
        errors=errors[:50],
    )
