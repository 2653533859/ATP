"""Dashboard alert evaluation and notification dispatch."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_config
from app.models.case import RunStatus, TestCase, TestRun
from app.models.dashboard_alert import (
    DashboardAlertEvent,
    DashboardAlertMetric,
    DashboardAlertOperator,
    DashboardAlertRule,
)
from app.models.notification import NotificationConfig, NotifyChannel
from app.models.project import Module

logger = logging.getLogger(__name__)

_FINISHED_RUN_STATUSES = [RunStatus.passed, RunStatus.failed, RunStatus.error]


def compare_metric(actual: float, op: DashboardAlertOperator, threshold: float) -> bool:
    if op == DashboardAlertOperator.gt:
        return actual > threshold
    if op == DashboardAlertOperator.gte:
        return actual >= threshold
    if op == DashboardAlertOperator.lt:
        return actual < threshold
    if op == DashboardAlertOperator.lte:
        return actual <= threshold
    if op == DashboardAlertOperator.eq:
        return actual == threshold
    return False


def _operator_label(op: DashboardAlertOperator) -> str:
    return {
        DashboardAlertOperator.gt: ">",
        DashboardAlertOperator.gte: ">=",
        DashboardAlertOperator.lt: "<",
        DashboardAlertOperator.lte: "<=",
        DashboardAlertOperator.eq: "=",
    }.get(op, op.value)


def _metric_label(metric: DashboardAlertMetric) -> str:
    return {
        DashboardAlertMetric.pass_rate: "通过率",
        DashboardAlertMetric.avg_duration_ms: "平均耗时(ms)",
        DashboardAlertMetric.failure_count: "失败数",
        DashboardAlertMetric.error_count: "错误数",
        DashboardAlertMetric.total_runs: "执行数",
    }.get(metric, metric.value)


def is_event_suppressed(
    latest_event: DashboardAlertEvent | None,
    now: datetime,
    suppress_minutes: int,
) -> bool:
    if latest_event is None:
        return False
    if latest_event.snoozed_until and latest_event.snoozed_until > now:
        return True
    return latest_event.triggered_at + timedelta(minutes=suppress_minutes) > now


def build_alert_summary(rule: DashboardAlertRule, actual_value: float) -> dict:
    metric = _metric_label(rule.metric)
    op = _operator_label(rule.op)
    title = f"看板告警「{rule.name}」触发：{metric} {actual_value:g} {op} {rule.threshold:g}"
    return {
        "title": title,
        "status": "error",
        "total": 1,
        "passed": 0,
        "failed": 1,
        "error": 0,
        "duration_ms": 0,
        "trigger_type": "dashboard_alert",
    }


async def calculate_rule_metric(
    db: AsyncSession,
    rule: DashboardAlertRule,
    now: datetime,
) -> float | None:
    since = now - timedelta(minutes=rule.window_minutes)
    from sqlalchemy import case as sql_case

    stmt = (
        select(
            func.count(TestRun.id).label("total"),
            func.sum(sql_case((TestRun.status == RunStatus.passed, 1), else_=0)).label("passed"),
            func.sum(sql_case((TestRun.status == RunStatus.failed, 1), else_=0)).label("failed"),
            func.sum(sql_case((TestRun.status == RunStatus.error, 1), else_=0)).label("error"),
            func.avg(TestRun.duration_ms).label("avg_duration_ms"),
        )
        .select_from(TestRun)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .join(Module, TestCase.module_id == Module.id)
        .where(
            Module.project_id == rule.project_id,
            TestRun.status.in_(_FINISHED_RUN_STATUSES),
            TestRun.created_at >= since,
            TestRun.created_at <= now,
        )
    )
    row = (await db.execute(stmt)).one()
    total = int(row.total or 0)
    passed = int(row.passed or 0)

    if rule.metric == DashboardAlertMetric.total_runs:
        return float(total)
    if rule.metric == DashboardAlertMetric.failure_count:
        return float(row.failed or 0)
    if rule.metric == DashboardAlertMetric.error_count:
        return float(row.error or 0)
    if total == 0:
        return None
    if rule.metric == DashboardAlertMetric.pass_rate:
        return round(passed / total * 100, 1)
    if rule.metric == DashboardAlertMetric.avg_duration_ms:
        return float(row.avg_duration_ms) if row.avg_duration_ms is not None else None
    return None


async def _latest_event(db: AsyncSession, rule_id: int) -> DashboardAlertEvent | None:
    result = await db.execute(
        select(DashboardAlertEvent)
        .where(DashboardAlertEvent.rule_id == rule_id)
        .order_by(DashboardAlertEvent.triggered_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _send_notification(db: AsyncSession, rule: DashboardAlertRule, actual_value: float) -> bool:
    if not rule.notification_config_id:
        return False

    cfg = await db.get(NotificationConfig, rule.notification_config_id)
    if not cfg or not cfg.is_enabled or cfg.project_id != rule.project_id:
        return False

    from app.services.notifier import _send_dingtalk, _send_email, _send_wechat

    real_config = decrypt_config(cfg.config)
    summary = build_alert_summary(rule, actual_value)
    if cfg.channel == NotifyChannel.email:
        await _send_email(real_config, summary)
    elif cfg.channel == NotifyChannel.wechat:
        await _send_wechat(real_config, summary)
    elif cfg.channel == NotifyChannel.dingtalk:
        await _send_dingtalk(real_config, summary)
    else:
        return False
    return True


async def evaluate_dashboard_alerts(
    db: AsyncSession,
    now: datetime | None = None,
) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    result = await db.execute(
        select(DashboardAlertRule)
        .where(DashboardAlertRule.enabled == True)  # noqa: E712
        .order_by(DashboardAlertRule.id.asc())
    )
    rules = result.scalars().all()

    summary = {
        "rules": len(rules),
        "evaluated": 0,
        "no_data": 0,
        "suppressed": 0,
        "triggered": 0,
        "notifications_sent": 0,
        "notification_errors": 0,
    }

    for rule in rules:
        actual = await calculate_rule_metric(db, rule, now)
        if actual is None:
            summary["no_data"] += 1
            continue

        summary["evaluated"] += 1
        if not compare_metric(actual, rule.op, rule.threshold):
            continue

        latest_event = await _latest_event(db, rule.id)
        if is_event_suppressed(latest_event, now, rule.suppress_minutes):
            summary["suppressed"] += 1
            continue

        event = DashboardAlertEvent(
            rule_id=rule.id,
            triggered_at=now,
            actual_value=actual,
            snoozed_until=now + timedelta(minutes=rule.suppress_minutes),
        )
        db.add(event)
        await db.commit()
        summary["triggered"] += 1

        try:
            if await _send_notification(db, rule, actual):
                summary["notifications_sent"] += 1
        except Exception as exc:
            summary["notification_errors"] += 1
            logger.warning("Dashboard alert notification failed rule_id=%s: %s", rule.id, exc)

    return summary
