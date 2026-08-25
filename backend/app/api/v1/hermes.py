"""Hermes project retrieval API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.case import TestCase
from app.models.knowledge import KnowledgeEntry
from app.models.project import Module, Project
from app.models.requirement import TestRequirement
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.hermes import HermesQueryIn, HermesQueryOut, HermesSourceOut
from app.services.hermes import HermesCandidate, build_answer, rank_candidates

router = APIRouter(tags=["智能中枢"])


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
    return HermesQueryOut(
        project_id=body.project_id,
        query=body.query,
        mode=mode,
        answer=answer,
        sources=[HermesSourceOut(**asdict(source)) for source in sources],
        generated_at=datetime.now(timezone.utc),
    )
