"""
Dashboard alert rule management API.

POST   /dashboard-alert-rules          Create rule
GET    /dashboard-alert-rules          List rules
GET    /dashboard-alert-rules/{id}     Get rule detail
PATCH  /dashboard-alert-rules/{id}     Update rule
DELETE /dashboard-alert-rules/{id}     Delete rule
GET    /dashboard-alert-events         List triggered events
POST   /dashboard-alert-events         Create event for scheduler integrations
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, require_engineer
from app.core.database import get_db
from app.models.dashboard_alert import DashboardAlertEvent, DashboardAlertRule
from app.models.notification import NotificationConfig
from app.models.project import Project
from app.models.user import UserRole
from app.models.user_project import ProjectRole
from app.schemas.dashboard_alert import (
    DashboardAlertEventCreate,
    DashboardAlertEventOut,
    DashboardAlertRuleCreate,
    DashboardAlertRuleOut,
    DashboardAlertRuleUpdate,
)

router = APIRouter(tags=["看板告警"])


def _is_admin(user) -> bool:
    return getattr(user, "role", None) == UserRole.admin


async def _ensure_notification_in_project(
    db: AsyncSession,
    notification_config_id: int | None,
    project_id: int,
) -> None:
    if notification_config_id is None:
        return
    cfg = await db.get(NotificationConfig, notification_config_id)
    if not cfg or cfg.project_id != project_id:
        raise HTTPException(status_code=400, detail="通知配置不存在或不属于当前项目")


@router.post(
    "/dashboard-alert-rules",
    response_model=DashboardAlertRuleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_dashboard_alert_rule(
    body: DashboardAlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.owner)
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    await _ensure_notification_in_project(db, body.notification_config_id, body.project_id)

    rule = DashboardAlertRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("/dashboard-alert-rules", response_model=list[DashboardAlertRuleOut])
async def list_dashboard_alert_rules(
    project_id: int | None = Query(None),
    enabled: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    elif not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可查看全局告警规则")

    q = select(DashboardAlertRule).order_by(DashboardAlertRule.created_at.desc())
    if project_id is not None:
        q = q.where(DashboardAlertRule.project_id == project_id)
    if enabled is not None:
        q = q.where(DashboardAlertRule.enabled == enabled)

    result = await db.execute(q)
    return result.scalars().all()


@router.get("/dashboard-alert-rules/{rule_id}", response_model=DashboardAlertRuleOut)
async def get_dashboard_alert_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    rule = await db.get(DashboardAlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    await assert_project_access(db, user, rule.project_id, ProjectRole.viewer)
    return rule


@router.patch("/dashboard-alert-rules/{rule_id}", response_model=DashboardAlertRuleOut)
async def update_dashboard_alert_rule(
    rule_id: int,
    body: DashboardAlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    rule = await db.get(DashboardAlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    await assert_project_access(db, user, rule.project_id, ProjectRole.owner)

    update_data = body.model_dump(exclude_unset=True)
    if "notification_config_id" in update_data:
        await _ensure_notification_in_project(
            db,
            update_data["notification_config_id"],
            rule.project_id,
        )
    for key, value in update_data.items():
        setattr(rule, key, value)

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/dashboard-alert-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard_alert_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    rule = await db.get(DashboardAlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    await assert_project_access(db, user, rule.project_id, ProjectRole.owner)
    await db.delete(rule)
    await db.commit()


@router.get("/dashboard-alert-events", response_model=list[DashboardAlertEventOut])
async def list_dashboard_alert_events(
    project_id: int | None = Query(None),
    rule_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    q = (
        select(DashboardAlertEvent)
        .join(DashboardAlertRule, DashboardAlertEvent.rule_id == DashboardAlertRule.id)
        .order_by(DashboardAlertEvent.triggered_at.desc())
        .limit(limit)
    )
    if rule_id is not None:
        rule = await db.get(DashboardAlertRule, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="告警规则不存在")
        await assert_project_access(db, user, rule.project_id, ProjectRole.viewer)
        q = q.where(DashboardAlertEvent.rule_id == rule_id)
    elif project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
        q = q.where(DashboardAlertRule.project_id == project_id)
    elif not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可查看全局告警事件")

    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/dashboard-alert-events",
    response_model=DashboardAlertEventOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_dashboard_alert_event(
    body: DashboardAlertEventCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    rule = await db.get(DashboardAlertRule, body.rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    await assert_project_access(db, user, rule.project_id, ProjectRole.owner)

    event = DashboardAlertEvent(
        rule_id=body.rule_id,
        actual_value=body.actual_value,
        triggered_at=body.triggered_at or datetime.now(timezone.utc),
        snoozed_until=body.snoozed_until,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event
