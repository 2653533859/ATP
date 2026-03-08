from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_engineer
from app.core.database import get_db
from app.models.mock import MockRule
from app.models.project import Project
from app.models.user import User
from app.schemas.mock import MockRuleCreate, MockRuleUpdate, MockRuleOut
from app.api.v1.mock_server import get_mock_logs

router = APIRouter(tags=["mock-rules"])


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
    return rule


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
    """获取指定项目最近的 Mock 请求日志"""
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
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(rule, key, value)
    await db.commit()
    await db.refresh(rule)
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
    await db.delete(rule)
    await db.commit()
