"""AI 用例生成端点。

- POST /ai/cases/parse-schema  解析 OpenAPI/Postman/cURL → 接口清单
- POST /ai/cases/generate      根据接口 + 需求生成用例草稿（前端二次编辑后保存）
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, require_admin, require_engineer
from app.models.user_project import ProjectRole
from app.core.database import get_db
from app.models.ai_llm_config import AILLMConfig
from app.models.audit import AuditLog
from app.models.dataset import TestDataset, TestDatasetVersion
from app.models.mock import MockRule
from app.models.project import Module, Project
from app.models.user import User
from app.schemas.ai_case import (
    AICaseFunnelStatsOut,
    AICaseGenerateIn,
    AICaseGenerateOut,
    AIParseSchemaIn,
    AIParseSchemaOut,
)
from app.services.audit import write_audit_log
from app.services.ai_case.funnel import AICaseFunnelEvent, build_funnel_stats
from app.services.ai_case.context import build_dataset_context, build_mock_rule_context
from app.services.ai_case.generator import generate_case_drafts
from app.services.ai_case.parsers import parse_schema
from app.services.ai_governance import redact_llm_text

router = APIRouter(prefix="/ai/cases", tags=["AI 用例生成"])


@router.get("/funnel-stats", response_model=AICaseFunnelStatsOut)
async def get_ai_case_funnel_stats(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(AuditLog).where(
        AuditLog.action.in_(["ai_case_generate", "ai_case_generate_failed", "ai_case_draft_saved"]),
        AuditLog.created_at >= since,
    )
    if project_id is not None:
        stmt = stmt.where(AuditLog.project_id == project_id)
    result = await db.execute(stmt)
    events = [
        AICaseFunnelEvent(action=row.action, detail=row.detail, created_at=row.created_at)
        for row in result.scalars().all()
    ]
    return AICaseFunnelStatsOut(**build_funnel_stats(events))


@router.post("/parse-schema", response_model=AIParseSchemaOut)
async def parse_schema_endpoint(
    body: AIParseSchemaIn,
    user: User = Depends(require_engineer),
):
    try:
        result = parse_schema(
            body.source_type,
            body.content,
            external_ref_policy=body.external_ref_policy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"解析失败: {exc}")
    return AIParseSchemaOut(
        endpoints=[asdict(e) for e in result.endpoints],  # type: ignore[arg-type]
        warnings=result.warnings,
    )


@router.post("/generate", response_model=AICaseGenerateOut)
async def generate_cases_endpoint(
    body: AICaseGenerateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    module = await db.get(Module, body.module_id)
    if not module:
        raise HTTPException(status_code=404, detail="模块不存在")
    if module.project_id != body.project_id:
        raise HTTPException(status_code=400, detail="模块不属于当前项目")
    if not project.ai_llm_config_id:
        raise HTTPException(status_code=400, detail="项目未配置 AI 模型")
    config = await db.get(AILLMConfig, project.ai_llm_config_id)
    if not config:
        raise HTTPException(status_code=400, detail="项目关联的 AI 配置不存在")
    if not config.enabled:
        raise HTTPException(status_code=400, detail="AI 配置已禁用")

    if body.dataset_version is not None and body.dataset_id is None:
        raise HTTPException(status_code=400, detail="数据集版本必须依赖数据集")

    dataset_context = None
    if body.dataset_id is not None:
        dataset = await db.get(TestDataset, body.dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="测试数据集不存在")
        if dataset.project_id != body.project_id:
            raise HTTPException(status_code=400, detail="测试数据集不属于当前项目")
        dataset_snapshot = None
        if body.dataset_version is not None:
            version_result = await db.execute(
                select(TestDatasetVersion)
                .where(
                    TestDatasetVersion.dataset_id == body.dataset_id,
                    TestDatasetVersion.version == body.dataset_version,
                )
                .limit(1)
            )
            dataset_snapshot = version_result.scalar_one_or_none()
            if dataset_snapshot is None:
                raise HTTPException(status_code=404, detail="测试数据集版本未找到")
        dataset_context = build_dataset_context(dataset, snapshot=dataset_snapshot)

    mock_context = []
    for mock_rule_id in dict.fromkeys(body.mock_rule_ids):
        mock_rule = await db.get(MockRule, mock_rule_id)
        if not mock_rule:
            raise HTTPException(status_code=404, detail=f"Mock 规则不存在: {mock_rule_id}")
        if mock_rule.project_id != body.project_id:
            raise HTTPException(status_code=400, detail=f"Mock 规则不属于当前项目: {mock_rule_id}")
        mock_context.append(build_mock_rule_context(mock_rule))

    endpoints_payload = [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in body.endpoints]

    try:
        result = await generate_case_drafts(
            config=config,
            endpoints=endpoints_payload,
            user_requirement=body.user_requirement,
            case_type=body.case_type.value if hasattr(body.case_type, "value") else str(body.case_type),
            priority=body.priority,
            case_level=body.case_level,
            max_cases=body.max_cases,
            dataset_context=dataset_context,
            mock_context=mock_context,
            dataset_id=body.dataset_id,
            dataset_version=body.dataset_version,
        )
    except httpx.TimeoutException:
        await _record_generation_event(db, user, body, action="ai_case_generate_failed", error_type="timeout")
        raise HTTPException(status_code=504, detail="LLM 请求超时")
    except httpx.HTTPStatusError as exc:
        await _record_generation_event(db, user, body, action="ai_case_generate_failed", error_type="http_status")
        raise HTTPException(
            status_code=502,
            detail=f"LLM 调用失败（HTTP {exc.response.status_code}）",
        )
    except httpx.RequestError:
        await _record_generation_event(db, user, body, action="ai_case_generate_failed", error_type="network")
        raise HTTPException(status_code=502, detail="LLM 网络请求失败")
    except ValueError as exc:
        await _record_generation_event(db, user, body, action="ai_case_generate_failed", error_type="validation")
        raise HTTPException(status_code=400, detail=str(exc))

    await _record_generation_event(
        db,
        user,
        body,
        action="ai_case_generate",
        draft_count=len(result.drafts),
        warning_count=len(result.warnings),
    )

    return AICaseGenerateOut(
        project_id=body.project_id,
        module_id=body.module_id,
        drafts=result.drafts,  # type: ignore[arg-type]
        raw_response=redact_llm_text(result.raw_text),
        warnings=result.warnings,
    )


async def _record_generation_event(
    db: AsyncSession,
    user: User,
    body: AICaseGenerateIn,
    *,
    action: str,
    draft_count: int = 0,
    warning_count: int = 0,
    error_type: str | None = None,
) -> None:
    detail = {
        "project_id": body.project_id,
        "module_id": body.module_id,
        "endpoint_count": len(body.endpoints),
        "max_cases": body.max_cases,
        "case_type": body.case_type.value if hasattr(body.case_type, "value") else str(body.case_type),
        "draft_count": draft_count,
        "warning_count": warning_count,
        "dataset_id": body.dataset_id,
        "dataset_version": body.dataset_version,
        "mock_rule_count": len(body.mock_rule_ids),
        "mock_rule_ids": list(dict.fromkeys(body.mock_rule_ids)),
    }
    if error_type:
        detail["error_type"] = error_type
    await write_audit_log(
        db,
        action=action,
        resource_type="ai_case_generation",
        resource_id=body.module_id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", ""),
        project_id=body.project_id,
        detail=json.dumps(detail, ensure_ascii=False),
    )
    if hasattr(db, "commit"):
        await db.commit()
