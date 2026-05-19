"""AI 用例生成端点。

  - POST /ai/cases/parse-schema  解析 OpenAPI/Postman/cURL → 接口清单
  - POST /ai/cases/generate      根据接口 + 需求生成用例草稿（前端二次编辑后保存）
"""
from __future__ import annotations

from dataclasses import asdict

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_engineer
from app.core.database import get_db
from app.models.ai_llm_config import AILLMConfig
from app.models.project import Project
from app.models.user import User
from app.schemas.ai_case import (
    AICaseGenerateIn,
    AICaseGenerateOut,
    AIParseSchemaIn,
    AIParseSchemaOut,
)
from app.services.ai_case.generator import generate_case_drafts
from app.services.ai_case.parsers import parse_schema

router = APIRouter(prefix="/ai/cases", tags=["AI 用例生成"])


@router.post("/parse-schema", response_model=AIParseSchemaOut)
async def parse_schema_endpoint(
    body: AIParseSchemaIn,
    _: User = Depends(require_engineer),
):
    try:
        result = parse_schema(body.source_type, body.content)
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
    _: User = Depends(require_engineer),
):
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.ai_llm_config_id:
        raise HTTPException(status_code=400, detail="项目未配置 AI 模型")
    config = await db.get(AILLMConfig, project.ai_llm_config_id)
    if not config:
        raise HTTPException(status_code=400, detail="项目关联的 AI 配置不存在")
    if not config.enabled:
        raise HTTPException(status_code=400, detail="AI 配置已禁用")

    endpoints_payload = [
        e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in body.endpoints
    ]

    try:
        result = await generate_case_drafts(
            config=config,
            endpoints=endpoints_payload,
            user_requirement=body.user_requirement,
            case_type=body.case_type.value if hasattr(body.case_type, "value") else str(body.case_type),
            priority=body.priority,
            case_level=body.case_level,
            max_cases=body.max_cases,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM 调用失败: {exc.response.status_code} {exc.response.text[:200]}",
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"LLM 网络错误: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return AICaseGenerateOut(
        project_id=body.project_id,
        module_id=body.module_id,
        drafts=result.drafts,  # type: ignore[arg-type]
        raw_response=result.raw_text,
        warnings=result.warnings,
    )
