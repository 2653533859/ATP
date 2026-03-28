from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_engineer
from app.core.database import get_db
from app.models.mock import MockRule
from app.models.project import Project
from app.models.user import User
from app.schemas.mock import (
    MockRuleCreate,
    MockRuleUpdate,
    MockRuleOut,
    MockRulesExportOut,
    MockRulesImportRequest,
)
from app.api.v1.mock_server import get_mock_logs, invalidate_mock_cache

router = APIRouter(tags=["mock-rules"])


def _bump_rule_version(rule: MockRule):
    rule.version = (rule.version or 1) + 1


@router.post("/mock-rules", response_model=MockRuleOut, status_code=201)
async def create_mock_rule(
    body: MockRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    rule = MockRule(**body.model_dump(), creator_id=current_user.id)
    db.add(rule)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail="项目不存在") from exc
    await db.refresh(rule)
    await invalidate_mock_cache(rule.project_id)
    return rule


@router.post("/mock-rules/import", response_model=list[MockRuleOut])
async def import_mock_rules(
    body: MockRulesImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    created_rules = []
    for item in body.rules:
        payload = item.model_dump(exclude={"project_id"})
        rule = MockRule(**payload, project_id=body.project_id, creator_id=current_user.id)
        db.add(rule)
        created_rules.append(rule)
    await db.commit()
    for rule in created_rules:
        await db.refresh(rule)
    await invalidate_mock_cache(body.project_id)
    return created_rules


@router.get("/mock-rules/export/{project_id}", response_model=MockRulesExportOut)
async def export_mock_rules(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(MockRule).where(MockRule.project_id == project_id).order_by(MockRule.id.desc())
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return MockRulesExportOut(project_id=project_id, rules=rules)


@router.get("/mock-rules", response_model=list[MockRuleOut])
async def list_mock_rules(
    project_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(MockRule).order_by(MockRule.id.desc())
    if project_id is not None:
        stmt = stmt.where(MockRule.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/mock-rules/logs/{project_id}")
async def list_mock_logs(
    project_id: int,
    _: User = Depends(get_current_user),
):
    return get_mock_logs(project_id)


@router.get("/mock-rules/{rule_id}", response_model=MockRuleOut)
async def get_mock_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rule = await db.get(MockRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Mock 规则不存在")
    return rule


@router.patch("/mock-rules/{rule_id}", response_model=MockRuleOut)
async def update_mock_rule(
    rule_id: int,
    body: MockRuleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_engineer),
):
    rule = await db.get(MockRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Mock 规则不存在")

    payload = body.model_dump(exclude_none=True)
    if payload:
        for key, value in payload.items():
            setattr(rule, key, value)
        _bump_rule_version(rule)
    await db.commit()
    await db.refresh(rule)
    await invalidate_mock_cache(rule.project_id)
    return rule


@router.delete("/mock-rules/{rule_id}", status_code=204)
async def delete_mock_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_engineer),
):
    rule = await db.get(MockRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Mock 规则不存在")
    project_id = rule.project_id
    await db.delete(rule)
    await db.commit()
    await invalidate_mock_cache(project_id)
