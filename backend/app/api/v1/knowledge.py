"""Project-aware knowledge hub search and article management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Text, and_, cast, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.case import RunStatus, TestCase, TestRun
from app.models.defect import Defect
from app.models.knowledge import KnowledgeEntry
from app.models.project import Module, Project
from app.models.requirement import TestRequirement
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject
from app.schemas.knowledge import (
    KnowledgeCreate,
    KnowledgeDetailOut,
    KnowledgeListOut,
    KnowledgeSearchItem,
    KnowledgeUpdate,
)
from app.services.audit import write_audit_log
from app.services.knowledge import (
    make_excerpt,
    redact_knowledge_tags,
    redact_knowledge_text,
    redact_knowledge_value,
    score_text,
)

router = APIRouter(tags=["知识中枢"])

_SOURCE_TYPES = {"standard", "defect", "solution", "runbook", "experience", "requirement", "execution"}
_STATUSES = {"draft", "published", "archived"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_admin(user: User) -> bool:
    return getattr(user, "role", None) in {UserRole.admin, UserRole.admin.value}


def _visible_projects(column, user: User, project_id: int | None = None):
    if _is_admin(user):
        predicate = true()
    else:
        predicate = column.in_(select(UserProject.project_id).where(UserProject.user_id == user.id))
    return predicate if project_id is None else predicate & (column == project_id)


async def _editable_project_ids(db: AsyncSession, user: User, project_ids: set[int]) -> set[int]:
    if _is_admin(user):
        return project_ids
    if not project_ids:
        return set()
    result = await db.execute(
        select(UserProject.project_id).where(
            UserProject.user_id == user.id,
            UserProject.project_id.in_(project_ids),
            UserProject.role.in_([ProjectRole.owner, ProjectRole.editor]),
        )
    )
    return {int(value) for value in result.scalars().all()}


async def _assert_entry_access(db: AsyncSession, user: User, entry: KnowledgeEntry, role: ProjectRole) -> None:
    if entry.project_id is None:
        if role != ProjectRole.viewer and not _is_admin(user):
            raise HTTPException(status_code=403, detail="全局知识仅管理员可维护")
        if role == ProjectRole.viewer and entry.status != "published" and not _is_admin(user):
            raise HTTPException(status_code=404, detail="知识条目不存在")
        return
    await assert_project_access(db, user, entry.project_id, role)


def _entry_item(
    entry: KnowledgeEntry, project_name: str | None, query: str | None, editable: bool
) -> KnowledgeSearchItem:
    body = "\n".join(value for value in (entry.summary, entry.content) if value)
    score, terms = score_text(query, entry.title, body, entry.tags or [])
    return KnowledgeSearchItem(
        key=f"entry:{entry.id}",
        document_id=entry.id,
        source_type=entry.source_type,
        title=entry.title,
        excerpt=make_excerpt(body, query),
        project_id=entry.project_id,
        project_name=project_name,
        source_ref=redact_knowledge_text(entry.source_ref),
        tags=redact_knowledge_tags(entry.tags),
        status=entry.status,
        match_terms=terms,
        match_score=score,
        is_global=entry.project_id is None,
        is_editable=editable,
        updated_at=entry.updated_at or entry.created_at or _now(),
    )


def _derived_item(
    *,
    key: str,
    source_type: str,
    title: str,
    body: str,
    project_id: int,
    project_name: str,
    source_ref: str | None,
    tags: list[str],
    status_value: str,
    target_path: str,
    query: str | None,
    updated_at: datetime | None,
) -> KnowledgeSearchItem:
    safe_title = redact_knowledge_text(title) or title
    safe_body = redact_knowledge_text(body) or ""
    safe_tags = redact_knowledge_tags(tags)
    score, terms = score_text(query, safe_title, safe_body, safe_tags)
    return KnowledgeSearchItem(
        key=key,
        source_type=source_type,
        title=safe_title,
        excerpt=make_excerpt(safe_body, query),
        project_id=project_id,
        project_name=project_name,
        source_ref=redact_knowledge_text(source_ref),
        tags=safe_tags,
        status=status_value,
        match_terms=terms,
        match_score=score,
        target_path=target_path,
        is_editable=False,
        updated_at=updated_at or _now(),
    )


def _detail(entry: KnowledgeEntry, project_name: str | None, editable: bool) -> KnowledgeDetailOut:
    item = _entry_item(entry, project_name, None, editable)
    return KnowledgeDetailOut(
        **item.model_dump(),
        summary=redact_knowledge_text(entry.summary),
        content=redact_knowledge_text(entry.content) or "",
        version=entry.version or 1,
        author_id=entry.author_id,
        created_at=entry.created_at or _now(),
    )


@router.get("/knowledge", response_model=KnowledgeListOut)
async def search_knowledge(
    project_id: int | None = Query(default=None, ge=1),
    keyword: str | None = Query(default=None, max_length=128),
    source_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=40, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    if source_type and source_type not in _SOURCE_TYPES:
        raise HTTPException(status_code=422, detail="source_type 不受支持")
    if status_filter and status_filter not in _STATUSES:
        raise HTTPException(status_code=422, detail="status 必须为 draft、published 或 archived")

    query_text = keyword.strip() if keyword and keyword.strip() else None
    like = f"%{query_text}%" if query_text else None
    items: list[KnowledgeSearchItem] = []
    project_ids: set[int] = set()

    entry_query = select(KnowledgeEntry, Project.name).outerjoin(Project, Project.id == KnowledgeEntry.project_id)
    entry_visibility = _visible_projects(KnowledgeEntry.project_id, user, project_id)
    if _is_admin(user):
        entry_visibility = or_(entry_visibility, KnowledgeEntry.project_id.is_(None))
    else:
        entry_visibility = or_(
            entry_visibility,
            and_(KnowledgeEntry.project_id.is_(None), KnowledgeEntry.status == "published"),
        )
    entry_query = entry_query.where(entry_visibility)
    if source_type:
        entry_query = entry_query.where(KnowledgeEntry.source_type == source_type)
    if status_filter:
        entry_query = entry_query.where(KnowledgeEntry.status == status_filter)
    if like:
        entry_query = entry_query.where(
            or_(
                KnowledgeEntry.title.ilike(like),
                KnowledgeEntry.summary.ilike(like),
                KnowledgeEntry.content.ilike(like),
                KnowledgeEntry.source_ref.ilike(like),
                cast(KnowledgeEntry.tags, Text).ilike(like),
            )
        )
    entry_rows = (await db.execute(entry_query.order_by(KnowledgeEntry.updated_at.desc()).limit(500))).all()
    project_ids.update(entry.project_id for entry, _name in entry_rows if entry.project_id is not None)

    requirements_rows = []
    if source_type in {None, "requirement"}:
        requirement_query = (
            select(TestRequirement, Project.name)
            .join(Project, Project.id == TestRequirement.project_id)
            .where(_visible_projects(TestRequirement.project_id, user, project_id))
        )
        if like:
            requirement_query = requirement_query.where(
                or_(
                    TestRequirement.title.ilike(like),
                    TestRequirement.description.ilike(like),
                    cast(TestRequirement.acceptance_criteria, Text).ilike(like),
                )
            )
        requirements_rows = (
            await db.execute(requirement_query.order_by(TestRequirement.updated_at.desc()).limit(300))
        ).all()
        project_ids.update(requirement.project_id for requirement, _name in requirements_rows)

    defects_rows = []
    if source_type in {None, "defect"}:
        defect_query = (
            select(Defect, Project.name)
            .join(Project, Project.id == Defect.project_id)
            .where(_visible_projects(Defect.project_id, user, project_id))
        )
        if like:
            defect_query = defect_query.where(
                or_(
                    Defect.title.ilike(like),
                    Defect.description.ilike(like),
                    Defect.resolution.ilike(like),
                    cast(Defect.labels, Text).ilike(like),
                )
            )
        defects_rows = (await db.execute(defect_query.order_by(Defect.updated_at.desc()).limit(300))).all()
        project_ids.update(defect.project_id for defect, _name in defects_rows)

    runs_rows = []
    if source_type in {None, "execution"}:
        run_query = (
            select(TestRun, TestCase.name, Project.id, Project.name)
            .join(TestCase, TestCase.id == TestRun.case_id)
            .join(Module, Module.id == TestCase.module_id)
            .join(Project, Project.id == Module.project_id)
            .where(
                _visible_projects(Project.id, user, project_id),
                TestRun.status.in_([RunStatus.failed, RunStatus.error]),
            )
        )
        if like:
            run_query = run_query.where(
                or_(
                    TestCase.name.ilike(like),
                    TestRun.error_message.ilike(like),
                    cast(TestRun.result_summary, Text).ilike(like),
                )
            )
        runs_rows = (await db.execute(run_query.order_by(TestRun.updated_at.desc()).limit(300))).all()
        project_ids.update(project_id_value for _run, _case_name, project_id_value, _name in runs_rows)

    editable_ids = await _editable_project_ids(db, user, project_ids)
    for entry, project_name in entry_rows:
        items.append(_entry_item(entry, project_name, query_text, _is_admin(user) or entry.project_id in editable_ids))
    for requirement, project_name in requirements_rows:
        criteria = redact_knowledge_value(requirement.acceptance_criteria or [])
        items.append(
            _derived_item(
                key=f"requirement:{requirement.id}",
                source_type="requirement",
                title=f"{requirement.requirement_code or f'REQ-{requirement.id}'} · {requirement.title}",
                body="\n".join(value for value in (requirement.description, criteria) if value),
                project_id=requirement.project_id,
                project_name=project_name,
                source_ref=requirement.requirement_code,
                tags=[requirement.priority, requirement.status],
                status_value=requirement.status,
                target_path=f"/requirements?project_id={requirement.project_id}&requirement_id={requirement.id}",
                query=query_text,
                updated_at=requirement.updated_at,
            )
        )
    for defect, project_name in defects_rows:
        items.append(
            _derived_item(
                key=f"defect:{defect.id}",
                source_type="defect",
                title=defect.title,
                body="\n".join(value for value in (defect.description, defect.resolution) if value),
                project_id=defect.project_id,
                project_name=project_name,
                source_ref=f"BUG-{defect.id}",
                tags=[defect.priority, defect.severity, *(defect.labels or [])],
                status_value=defect.status,
                target_path=f"/bugs?project_id={defect.project_id}&defect_id={defect.id}",
                query=query_text,
                updated_at=defect.updated_at,
            )
        )
    for run, case_name, run_project_id, project_name in runs_rows:
        body = "\n".join(
            value
            for value in (
                run.error_message,
                redact_knowledge_value(run.result_summary or {}),
            )
            if value
        )
        status_value = str(getattr(run.status, "value", run.status))
        items.append(
            _derived_item(
                key=f"execution:{run.id}",
                source_type="execution",
                title=f"运行 #{run.id} · {case_name}",
                body=body or "失败运行未提供错误摘要",
                project_id=run_project_id,
                project_name=project_name,
                source_ref=run.trace_id or f"RUN-{run.id}",
                tags=[status_value, run.environment or ""],
                status_value=status_value,
                target_path=f"/runs/{run.id}",
                query=query_text,
                updated_at=run.updated_at,
            )
        )

    def sort_key(item: KnowledgeSearchItem) -> tuple[int, float]:
        timestamp = (
            item.updated_at.timestamp()
            if item.updated_at.tzinfo
            else item.updated_at.replace(tzinfo=timezone.utc).timestamp()
        )
        return (-item.match_score, -timestamp)

    items.sort(key=sort_key)
    source_counts: dict[str, int] = {}
    for item in items:
        source_counts[item.source_type] = source_counts.get(item.source_type, 0) + 1
    start = (page - 1) * page_size
    return KnowledgeListOut(
        items=items[start : start + page_size],
        total=len(items),
        page=page,
        page_size=page_size,
        source_counts=source_counts,
    )


@router.get("/knowledge/{knowledge_id}", response_model=KnowledgeDetailOut)
async def get_knowledge(
    knowledge_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await db.get(KnowledgeEntry, knowledge_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    await _assert_entry_access(db, user, entry, ProjectRole.viewer)
    project_name = None
    if entry.project_id is not None:
        project_name = await db.scalar(select(Project.name).where(Project.id == entry.project_id))
    editable = _is_admin(user)
    if entry.project_id is not None and not editable:
        result = await db.execute(
            select(UserProject.id).where(
                UserProject.user_id == user.id,
                UserProject.project_id == entry.project_id,
                UserProject.role.in_([ProjectRole.owner, ProjectRole.editor]),
            )
        )
        editable = result.scalar_one_or_none() is not None
    return _detail(entry, project_name, editable)


@router.post("/knowledge", response_model=KnowledgeDetailOut, status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    body: KnowledgeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.project_id is None:
        if not _is_admin(user):
            raise HTTPException(status_code=403, detail="全局知识仅管理员可创建")
    else:
        await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    entry = KnowledgeEntry(
        project_id=body.project_id,
        source_type=body.source_type,
        title=redact_knowledge_text(body.title, limit=256) or body.title,
        summary=redact_knowledge_text(body.summary, limit=2_000),
        content=redact_knowledge_text(body.content, limit=50_000) or "",
        source_ref=redact_knowledge_text(body.source_ref, limit=512),
        tags=redact_knowledge_tags(body.tags),
        status=body.status,
        author_id=user.id,
    )
    db.add(entry)
    await db.flush()
    await write_audit_log(
        db,
        action="knowledge_create",
        resource_type="knowledge_entry",
        resource_id=entry.id,
        user_id=user.id,
        username=user.username,
        project_id=body.project_id,
        detail=f"创建知识条目: {entry.title}",
    )
    await db.commit()
    project_name = None
    if entry.project_id is not None:
        project_name = await db.scalar(select(Project.name).where(Project.id == entry.project_id))
    return _detail(entry, project_name, True)


@router.patch("/knowledge/{knowledge_id}", response_model=KnowledgeDetailOut)
async def update_knowledge(
    knowledge_id: int,
    body: KnowledgeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await db.get(KnowledgeEntry, knowledge_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    await _assert_entry_access(db, user, entry, ProjectRole.editor)
    payload = body.model_dump(exclude_unset=True)
    changed = False
    for field in ("source_type", "title", "summary", "source_ref", "tags", "status"):
        if field in payload and getattr(entry, field) != payload[field]:
            value = payload[field]
            if field == "tags":
                value = redact_knowledge_tags(value)
            if field in {"title", "summary", "source_ref"}:
                value = redact_knowledge_text(
                    value, limit=256 if field == "title" else 2_000 if field == "summary" else 512
                )
            setattr(entry, field, value)
            changed = True
    if "content" in payload:
        content = redact_knowledge_text(payload["content"], limit=50_000) or ""
        if entry.content != content:
            entry.content = content
            changed = True
    if changed:
        entry.version += 1
        await write_audit_log(
            db,
            action="knowledge_update",
            resource_type="knowledge_entry",
            resource_id=entry.id,
            user_id=user.id,
            username=user.username,
            project_id=entry.project_id,
            detail=f"更新知识条目版本: {entry.version}",
        )
    await db.commit()
    project_name = None
    if entry.project_id is not None:
        project_name = await db.scalar(select(Project.name).where(Project.id == entry.project_id))
    return _detail(entry, project_name, True)


@router.delete("/knowledge/{knowledge_id}")
async def delete_knowledge(
    knowledge_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await db.get(KnowledgeEntry, knowledge_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    await _assert_entry_access(db, user, entry, ProjectRole.editor)
    await db.delete(entry)
    await write_audit_log(
        db,
        action="knowledge_delete",
        resource_type="knowledge_entry",
        resource_id=entry.id,
        user_id=user.id,
        username=user.username,
        project_id=entry.project_id,
        detail=f"删除知识条目: {entry.title}",
    )
    await db.commit()
    return {"deleted": True, "id": knowledge_id}
