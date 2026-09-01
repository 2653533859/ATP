"""Hermes project retrieval API."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.encryption import decrypt
from app.core.database import get_db
from app.models.ai_llm_config import AILLMConfig
from app.models.case import TestCase
from app.models.knowledge import KnowledgeEntry
from app.models.project import Module, Project
from app.models.requirement import TestRequirement
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.hermes import HermesQueryIn, HermesQueryOut, HermesSourceOut
from app.services.ai_case.llm_client import LLMRequest, call_llm
from app.services.ai_governance import (
    check_and_incr_daily_limit,
    llm_extra_params,
    redact_llm_text,
    resolve_system_prompt,
)
from app.services.knowledge import redact_knowledge_text
from app.services.hermes import (
    HERMES_SYSTEM_PROMPT,
    HermesCandidate,
    HermesRankedSource,
    build_answer,
    build_grounded_prompt,
    has_valid_source_citation,
    rank_candidates,
)


logger = logging.getLogger(__name__)

router = APIRouter(tags=["智能中枢"])


async def _llm_answer(
    db: AsyncSession,
    project: Project,
    query: str,
    sources: list[HermesRankedSource],
) -> str | None:
    """Generate a grounded answer when the project has an enabled AI config."""

    config_id = getattr(project, "ai_llm_config_id", None)
    if not sources or not config_id:
        return None
    config = await db.get(AILLMConfig, config_id)
    if config is None or not config.enabled:
        return None
    try:
        api_key = (
            "" if config.provider == "ollama" and not config.api_key_encrypted else decrypt(config.api_key_encrypted)
        )
        if not await check_and_incr_daily_limit(config=config, capability="hermes_query"):
            return None
        response = await call_llm(
            LLMRequest(
                provider=config.provider,
                api_key=api_key,
                model_name=config.model_name,
                prompt=build_grounded_prompt(redact_knowledge_text(query, limit=2_000) or "", sources),
                endpoint=config.endpoint,
                system_prompt=resolve_system_prompt(config, "hermes_query", HERMES_SYSTEM_PROMPT),
                timeout_seconds=60.0,
                extra_params=llm_extra_params(config),
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hermes LLM query failed: config_id=%s error_type=%s", config.id, type(exc).__name__)
        return None

    answer = redact_llm_text(response.text, limit=4_000).strip()
    if not has_valid_source_citation(answer, len(sources)):
        logger.warning("Hermes LLM query returned no valid source citation: config_id=%s", config.id)
        return None
    return answer


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _knowledge_candidates(rows: list[tuple[KnowledgeEntry, str | None]], project_id: int) -> list[HermesCandidate]:
    return [
        HermesCandidate(
            source_type="knowledge",
            source_id=entry.id,
            project_id=entry.project_id,
            title=entry.title,
            body="\n".join(value for value in (entry.summary, entry.content) if value),
            source_ref=entry.source_ref or f"KNOWLEDGE-{entry.id}",
            path=f"/knowledge?project_id={project_id}&knowledge_id={entry.id}",
            tags=tuple(entry.tags or []),
            updated_at=entry.updated_at or entry.created_at,
        )
        for entry, _project_name in rows
    ]


def _requirement_candidates(rows: list[tuple[TestRequirement, str]], project_id: int) -> list[HermesCandidate]:
    return [
        HermesCandidate(
            source_type="requirement",
            source_id=requirement.id,
            project_id=requirement.project_id,
            title=requirement.title,
            body="\n".join(
                value
                for value in (
                    requirement.description,
                    " ".join(str(item.get("text", "")) for item in (requirement.acceptance_criteria or [])),
                )
                if value
            ),
            source_ref=requirement.requirement_code or f"REQ-{requirement.id}",
            path=f"/requirements?project_id={project_id}&requirement_id={requirement.id}",
            tags=(requirement.priority, requirement.status),
            updated_at=requirement.updated_at or requirement.created_at,
        )
        for requirement, _project_name in rows
    ]


def _case_candidates(rows: list[tuple[TestCase, Module]]) -> list[HermesCandidate]:
    return [
        HermesCandidate(
            source_type="case",
            source_id=case.id,
            project_id=module.project_id,
            title=case.name,
            body="\n".join(value for value in (case.summary, case.description) if value),
            source_ref=case.case_code,
            path=f"/cases?project_id={module.project_id}&case_id={case.id}",
            tags=tuple(case.tags or []) + (_enum_value(case.case_type), case.priority, case.case_level),
            updated_at=case.updated_at or case.created_at,
        )
        for case, module in rows
    ]


@router.post("/hermes/query", response_model=HermesQueryOut)
async def query_hermes(
    body: HermesQueryIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.viewer)
    project = await db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    knowledge_query = (
        select(KnowledgeEntry, Project.name)
        .outerjoin(Project, Project.id == KnowledgeEntry.project_id)
        .where(
            or_(
                KnowledgeEntry.project_id == body.project_id,
                and_(KnowledgeEntry.project_id.is_(None), KnowledgeEntry.status == "published"),
            )
        )
        .order_by(KnowledgeEntry.updated_at.desc(), KnowledgeEntry.id.desc())
        .limit(200)
    )
    requirement_query = (
        select(TestRequirement, Project.name)
        .join(Project, Project.id == TestRequirement.project_id)
        .where(TestRequirement.project_id == body.project_id)
        .order_by(TestRequirement.updated_at.desc(), TestRequirement.id.desc())
        .limit(200)
    )
    case_query = (
        select(TestCase, Module)
        .join(Module, Module.id == TestCase.module_id)
        .where(Module.project_id == body.project_id)
        .order_by(TestCase.updated_at.desc(), TestCase.id.desc())
        .limit(300)
    )
    knowledge_rows = (await db.execute(knowledge_query)).all()
    requirement_rows = (await db.execute(requirement_query)).all()
    case_rows = (await db.execute(case_query)).all()

    candidates = (
        _knowledge_candidates(knowledge_rows, body.project_id)
        + _requirement_candidates(requirement_rows, body.project_id)
        + _case_candidates(case_rows)
    )
    sources = rank_candidates(body.query, candidates, body.limit)
    answer, mode = build_answer(sources)
    llm_answer = await _llm_answer(db, project, body.query, sources)
    if llm_answer:
        answer, mode = llm_answer, "llm_grounded"
    return HermesQueryOut(
        project_id=body.project_id,
        query=body.query,
        mode=mode,
        answer=answer,
        sources=[HermesSourceOut(**asdict(source)) for source in sources],
        generated_at=datetime.now(timezone.utc),
    )
