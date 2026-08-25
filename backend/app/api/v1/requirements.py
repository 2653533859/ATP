"""Project requirements, acceptance criteria, and case traceability APIs."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.case import TestCase
from app.models.project import Module, Project
from app.models.requirement import RequirementCaseLink, TestRequirement
from app.models.user import User
from app.models.user import UserRole
from app.models.user_project import ProjectRole, UserProject
from app.schemas.requirement import (
    AcceptanceCriterion,
    RequirementCaseLinkCreate,
    RequirementCaseLinkOut,
    RequirementCreate,
    RequirementDetailOut,
    RequirementImpactCandidate,
    RequirementImpactOut,
    RequirementListItem,
    RequirementListOut,
    RequirementParseIn,
    RequirementParseOut,
    RequirementUpdate,
)
from app.services.audit import write_audit_log
from app.services.project_scope import scope_to_visible_projects

router = APIRouter(tags=["需求追踪"])

_CRITERION_RE = re.compile(r"^(?:[-*•]|\d+[.)]|验收标准[:：])\s*", re.IGNORECASE)
_TERM_RE = re.compile(r"[\u4e00-\u9fff]{2,12}|[A-Za-z][A-Za-z0-9_-]{2,}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_criteria(values: list[AcceptanceCriterion | dict]) -> list[dict]:
    normalized: list[dict] = []
    used: set[str] = set()
    for index, raw in enumerate(values, start=1):
        criterion = raw if isinstance(raw, AcceptanceCriterion) else AcceptanceCriterion.model_validate(raw)
        criterion_id = (criterion.id or f"AC-{index}").strip().upper()
        if not criterion_id or criterion_id in used:
            criterion_id = f"AC-{index}"
            while criterion_id in used:
                index += 1
                criterion_id = f"AC-{index}"
        used.add(criterion_id)
        normalized.append(
            {
                "id": criterion_id,
                "text": criterion.text.strip(),
                "priority": criterion.priority,
                "status": criterion.status,
            }
        )
    return normalized


def _criteria_for_output(requirement: TestRequirement) -> list[AcceptanceCriterion]:
    return [AcceptanceCriterion.model_validate(item) for item in (requirement.acceptance_criteria or [])]


def _covered_criterion_ids(requirement: TestRequirement, links: list[RequirementCaseLink]) -> set[str]:
    valid_ids = {criterion.id for criterion in _criteria_for_output(requirement)}
    return {criterion_id for link in links for criterion_id in (link.criterion_ids or []) if criterion_id in valid_ids}


def _requirement_item(
    requirement: TestRequirement,
    *,
    linked_case_count: int,
    covered_ids: set[str],
) -> RequirementListItem:
    criteria = _criteria_for_output(requirement)
    criteria_total = len(criteria)
    coverage_rate = (
        (len(covered_ids) / criteria_total * 100) if criteria_total else (100.0 if linked_case_count else 0.0)
    )
    return RequirementListItem(
        id=requirement.id,
        project_id=requirement.project_id,
        requirement_code=requirement.requirement_code,
        title=requirement.title,
        description=requirement.description,
        status=requirement.status,
        priority=requirement.priority,
        acceptance_criteria=criteria,
        source=requirement.source,
        source_ref=requirement.source_ref,
        version=requirement.version or 1,
        creator_id=requirement.creator_id,
        owner_id=requirement.owner_id,
        linked_case_count=linked_case_count,
        covered_criterion_count=len(covered_ids),
        coverage_rate=round(coverage_rate, 2),
        created_at=requirement.created_at or _now(),
        updated_at=requirement.updated_at or _now(),
    )


def _case_type(case: TestCase) -> str:
    return str(getattr(case.case_type, "value", case.case_type))


def _link_item(link: RequirementCaseLink, case: TestCase, module: Module) -> RequirementCaseLinkOut:
    return RequirementCaseLinkOut(
        id=link.id,
        requirement_id=link.requirement_id,
        case_id=case.id,
        case_name=case.name,
        case_code=case.case_code,
        case_type=_case_type(case),
        case_status=str(getattr(case.status, "value", case.status)),
        review_status=case.review_status,
        module_id=module.id,
        module_name=module.name,
        relation_type=link.relation_type,
        criterion_ids=list(link.criterion_ids or []),
        note=link.note,
        created_by=link.created_by,
        created_at=link.created_at or _now(),
    )


async def _get_requirement(db: AsyncSession, requirement_id: int) -> TestRequirement:
    requirement = await db.get(TestRequirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="需求不存在")
    return requirement


async def _assert_requirement_access(
    db: AsyncSession,
    user: User,
    requirement: TestRequirement,
    role: ProjectRole,
) -> None:
    await assert_project_access(db, user, requirement.project_id, role)


async def _ensure_owner(db: AsyncSession, project_id: int, owner_id: int | None, user: User) -> None:
    """Only allow active project members (or admins) to own a requirement."""
    if owner_id is None:
        return
    owner = await db.get(User, owner_id)
    if owner is None or not owner.is_active:
        raise HTTPException(status_code=400, detail="需求负责人不存在或已禁用")
    if getattr(getattr(user, "role", None), "value", getattr(user, "role", None)) == UserRole.admin.value:
        return
    membership = await db.execute(
        select(UserProject.id).where(UserProject.user_id == owner_id, UserProject.project_id == project_id)
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(status_code=400, detail="需求负责人不是该项目成员")


async def _load_links(
    db: AsyncSession,
    requirement_id: int,
) -> list[tuple[RequirementCaseLink, TestCase, Module]]:
    result = await db.execute(
        select(RequirementCaseLink, TestCase, Module)
        .join(TestCase, TestCase.id == RequirementCaseLink.case_id)
        .join(Module, Module.id == TestCase.module_id)
        .where(RequirementCaseLink.requirement_id == requirement_id)
        .order_by(RequirementCaseLink.created_at.asc(), RequirementCaseLink.id.asc())
    )
    return list(result.all())


def _parse_requirement_text(text: str) -> RequirementParseOut:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else "未命名需求"
    title = re.sub(r"^(?:需求|标题|title)\s*[:：]\s*", "", title, flags=re.IGNORECASE).strip() or "未命名需求"
    body_lines = lines[1:] if len(lines) > 1 else []
    description = "\n".join(body_lines).strip() or title

    criteria_text: list[str] = []
    for line in lines:
        criterion = _CRITERION_RE.sub("", line).strip()
        if criterion != line or line.lower().startswith("acceptance") or line.startswith("验收"):
            criterion = re.sub(
                r"^(?:验收标准|acceptance criteria)\s*[:：]?\s*", "", criterion, flags=re.IGNORECASE
            ).strip()
            if criterion:
                criteria_text.append(criterion)
    if not criteria_text:
        fragments = [fragment.strip() for fragment in re.split(r"[。；;\n]", description) if fragment.strip()]
        criteria_text = fragments[:6]
    if not criteria_text:
        criteria_text = ["系统应满足需求描述中的主流程和异常流程"]

    unique_criteria = list(dict.fromkeys(criteria_text))[:50]
    criteria = [
        AcceptanceCriterion(id=f"AC-{index}", text=value, priority="P2", status="draft")
        for index, value in enumerate(unique_criteria, start=1)
    ]
    terms: list[str] = []
    for term in _TERM_RE.findall(f"{title} {description}"):
        if term not in terms and term.lower() not in {"the", "with", "from", "and"}:
            terms.append(term)
    warnings = ["解析结果是可编辑草稿，保存前请人工确认标题、验收标准和关联用例。"]
    return RequirementParseOut(
        title=title[:256],
        description=description[:20_000],
        acceptance_criteria=criteria,
        keywords=terms[:20],
        warnings=warnings,
    )


def _impact_terms(requirement: TestRequirement) -> list[str]:
    raw_terms = _TERM_RE.findall(f"{requirement.title} {requirement.description or ''}")
    terms: list[str] = []
    for term in raw_terms:
        if term not in terms and term.lower() not in {"the", "with", "from", "and"}:
            terms.append(term)
        if len(term) > 4 and any("\u4e00" <= char <= "\u9fff" for char in term):
            for index in range(len(term) - 1):
                pair = term[index : index + 2]
                if pair not in terms:
                    terms.append(pair)
    return terms[:30]


@router.get("/requirements", response_model=RequirementListOut)
async def list_requirements(
    project_id: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    query = scope_to_visible_projects(select(TestRequirement), TestRequirement.project_id, user, project_id)
    if status_filter:
        if status_filter not in {"draft", "active", "archived"}:
            raise HTTPException(status_code=422, detail="status 必须为 draft、active 或 archived")
        query = query.where(TestRequirement.status == status_filter)
    if keyword and keyword.strip():
        like_keyword = f"%{keyword.strip()}%"
        query = query.where(
            or_(
                TestRequirement.title.ilike(like_keyword),
                TestRequirement.description.ilike(like_keyword),
                TestRequirement.requirement_code.ilike(like_keyword),
            )
        )

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = int(total_result.scalar_one() or 0)
    rows = (
        (
            await db.execute(
                query.order_by(TestRequirement.updated_at.desc(), TestRequirement.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    items: list[RequirementListItem] = []
    for requirement in rows:
        links = await db.execute(
            select(RequirementCaseLink).where(RequirementCaseLink.requirement_id == requirement.id)
        )
        link_rows = list(links.scalars().all())
        items.append(
            _requirement_item(
                requirement,
                linked_case_count=len(link_rows),
                covered_ids=_covered_criterion_ids(requirement, link_rows),
            )
        )
    return RequirementListOut(items=items, total=total, page=page, page_size=page_size)


@router.post("/requirements/parse", response_model=RequirementParseOut)
async def parse_requirement(
    body: RequirementParseIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    return _parse_requirement_text(body.text)


@router.post("/requirements", response_model=RequirementDetailOut, status_code=status.HTTP_201_CREATED)
async def create_requirement(
    body: RequirementCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    project = await db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    await _ensure_owner(db, body.project_id, body.owner_id, user)
    requirement = TestRequirement(
        project_id=body.project_id,
        title=body.title,
        description=body.description,
        status=body.status,
        priority=body.priority,
        acceptance_criteria=_normalize_criteria(body.acceptance_criteria),
        source=body.source,
        source_ref=body.source_ref,
        creator_id=user.id,
        owner_id=body.owner_id,
    )
    db.add(requirement)
    await db.flush()
    requirement.requirement_code = f"REQ-{body.project_id:03d}-{requirement.id:05d}"
    await write_audit_log(
        db,
        action="requirement_create",
        resource_type="test_requirement",
        resource_id=requirement.id,
        user_id=user.id,
        username=user.username,
        project_id=body.project_id,
        detail=f"创建需求: {requirement.requirement_code}",
    )
    await db.commit()
    # AsyncSession expires ORM attributes on commit by default. Refresh before
    # building the response so serialization never triggers implicit IO outside
    # an awaitable context (which raises MissingGreenlet under async SQLAlchemy).
    await db.refresh(requirement)
    return RequirementDetailOut(
        **_requirement_item(requirement, linked_case_count=0, covered_ids=set()).model_dump(),
        links=[],
    )


@router.get("/requirements/{requirement_id}", response_model=RequirementDetailOut)
async def get_requirement(
    requirement_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requirement = await _get_requirement(db, requirement_id)
    await _assert_requirement_access(db, user, requirement, ProjectRole.viewer)
    rows = await _load_links(db, requirement.id)
    links = [link for link, case, module in rows]
    return RequirementDetailOut(
        **_requirement_item(
            requirement, linked_case_count=len(rows), covered_ids=_covered_criterion_ids(requirement, links)
        ).model_dump(),
        links=[_link_item(link, case, module) for link, case, module in rows],
    )


@router.patch("/requirements/{requirement_id}", response_model=RequirementDetailOut)
async def update_requirement(
    requirement_id: int,
    body: RequirementUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requirement = await _get_requirement(db, requirement_id)
    await _assert_requirement_access(db, user, requirement, ProjectRole.editor)
    payload = body.model_dump(exclude_unset=True)
    if "owner_id" in payload:
        await _ensure_owner(db, requirement.project_id, payload["owner_id"], user)
    changed = False
    for field in ("title", "description", "status", "priority", "source", "source_ref", "owner_id"):
        if field in payload:
            value = payload[field]
            if getattr(requirement, field) != value:
                setattr(requirement, field, value)
                changed = True
    if "acceptance_criteria" in payload:
        criteria = _normalize_criteria(body.acceptance_criteria or [])
        if (requirement.acceptance_criteria or []) != criteria:
            requirement.acceptance_criteria = criteria
            changed = True
    if changed:
        requirement.version += 1
        await write_audit_log(
            db,
            action="requirement_update",
            resource_type="test_requirement",
            resource_id=requirement.id,
            user_id=user.id,
            username=user.username,
            project_id=requirement.project_id,
            detail=f"更新需求版本: {requirement.version}",
        )
    await db.commit()
    rows = await _load_links(db, requirement.id)
    links = [link for link, case, module in rows]
    return RequirementDetailOut(
        **_requirement_item(
            requirement, linked_case_count=len(rows), covered_ids=_covered_criterion_ids(requirement, links)
        ).model_dump(),
        links=[_link_item(link, case, module) for link, case, module in rows],
    )


@router.delete("/requirements/{requirement_id}")
async def delete_requirement(
    requirement_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requirement = await _get_requirement(db, requirement_id)
    await _assert_requirement_access(db, user, requirement, ProjectRole.editor)
    await db.delete(requirement)
    await write_audit_log(
        db,
        action="requirement_delete",
        resource_type="test_requirement",
        resource_id=requirement.id,
        user_id=user.id,
        username=user.username,
        project_id=requirement.project_id,
        detail=f"删除需求: {requirement.requirement_code or requirement.id}",
    )
    await db.commit()
    return {"deleted": True, "id": requirement_id}


@router.post("/requirements/{requirement_id}/case-links", response_model=RequirementCaseLinkOut)
async def link_requirement_case(
    requirement_id: int,
    body: RequirementCaseLinkCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requirement = await _get_requirement(db, requirement_id)
    await _assert_requirement_access(db, user, requirement, ProjectRole.editor)
    case = await db.get(TestCase, body.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    module = await db.get(Module, case.module_id)
    if module is None or module.project_id != requirement.project_id:
        raise HTTPException(status_code=400, detail="测试用例不属于当前需求项目")
    criterion_ids = list(dict.fromkeys(body.criterion_ids))
    valid_ids = {criterion.id for criterion in _criteria_for_output(requirement)}
    unknown_ids = [criterion_id for criterion_id in criterion_ids if criterion_id not in valid_ids]
    if unknown_ids:
        raise HTTPException(status_code=400, detail=f"验收标准不存在: {', '.join(unknown_ids)}")
    existing_result = await db.execute(
        select(RequirementCaseLink).where(
            RequirementCaseLink.requirement_id == requirement.id,
            RequirementCaseLink.case_id == case.id,
            RequirementCaseLink.relation_type == body.relation_type,
        )
    )
    link = existing_result.scalar_one_or_none()
    if link is None:
        link = RequirementCaseLink(
            requirement_id=requirement.id,
            case_id=case.id,
            relation_type=body.relation_type,
            criterion_ids=criterion_ids,
            note=body.note,
            created_by=user.id,
        )
        db.add(link)
        await db.flush()
        action = "requirement_case_link_create"
    else:
        link.criterion_ids = criterion_ids
        link.note = body.note
        action = "requirement_case_link_update"
    await write_audit_log(
        db,
        action=action,
        resource_type="requirement_case_link",
        resource_id=link.id,
        user_id=user.id,
        username=user.username,
        project_id=requirement.project_id,
        detail=f"需求 {requirement.id} 关联用例 {case.id}",
    )
    await db.commit()
    return _link_item(link, case, module)


@router.delete("/requirements/{requirement_id}/case-links/{link_id}")
async def unlink_requirement_case(
    requirement_id: int,
    link_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requirement = await _get_requirement(db, requirement_id)
    await _assert_requirement_access(db, user, requirement, ProjectRole.editor)
    link = await db.get(RequirementCaseLink, link_id)
    if link is None or link.requirement_id != requirement.id:
        raise HTTPException(status_code=404, detail="需求用例关联不存在")
    await db.delete(link)
    await write_audit_log(
        db,
        action="requirement_case_link_delete",
        resource_type="requirement_case_link",
        resource_id=link.id,
        user_id=user.id,
        username=user.username,
        project_id=requirement.project_id,
        detail=f"解除需求 {requirement.id} 与用例的关联",
    )
    await db.commit()
    return {"deleted": True, "id": link_id}


@router.get("/requirements/{requirement_id}/impact", response_model=RequirementImpactOut)
async def get_requirement_impact(
    requirement_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requirement = await _get_requirement(db, requirement_id)
    await _assert_requirement_access(db, user, requirement, ProjectRole.viewer)
    rows = await _load_links(db, requirement.id)
    links = [link for link, _case, _module in rows]
    linked_ids = {case.id for _link, case, _module in rows}
    terms = _impact_terms(requirement)
    case_rows = (
        await db.execute(
            select(TestCase, Module)
            .join(Module, Module.id == TestCase.module_id)
            .where(Module.project_id == requirement.project_id)
            .order_by(TestCase.updated_at.desc(), TestCase.id.desc())
        )
    ).all()
    candidates: list[RequirementImpactCandidate] = []
    for case, module in case_rows:
        if case.id in linked_ids:
            continue
        haystack = " ".join([case.name, case.summary or "", " ".join(case.tags or [])]).lower()
        matches = [term for term in terms if term.lower() in haystack]
        if matches:
            candidates.append(
                RequirementImpactCandidate(
                    case_id=case.id,
                    case_name=case.name,
                    case_code=case.case_code,
                    case_type=_case_type(case),
                    module_id=module.id,
                    module_name=module.name,
                    match_terms=list(dict.fromkeys(matches))[:6],
                )
            )
        if len(candidates) >= 20:
            break

    criteria = _criteria_for_output(requirement)
    covered_ids = _covered_criterion_ids(requirement, links)
    uncovered = [criterion for criterion in criteria if criterion.id not in covered_ids]
    criteria_total = len(criteria)
    coverage_rate = (len(covered_ids) / criteria_total * 100) if criteria_total else (100.0 if rows else 0.0)
    if not rows or (criteria_total and not covered_ids):
        impact_level = "high"
    elif coverage_rate < 100 or candidates:
        impact_level = "medium"
    else:
        impact_level = "low"
    return RequirementImpactOut(
        requirement_id=requirement.id,
        requirement_version=requirement.version,
        criteria_total=criteria_total,
        criteria_covered=len(covered_ids),
        coverage_rate=round(coverage_rate, 2),
        linked_case_count=len(rows),
        impact_level=impact_level,
        uncovered_criteria=uncovered,
        candidate_cases=candidates,
    )
