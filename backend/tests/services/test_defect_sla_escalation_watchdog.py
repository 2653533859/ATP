"""缺陷 SLA 超时预警与升级看门狗单测 (T2.3)"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.defect_sla_escalation_watchdog import (
    DefectSLATrackingItem,
    DefectSeverity,
    SLAComplianceStatus,
    SLAEscalationAction,
    batch_evaluate_defects_sla,
    evaluate_defect_sla,
)


def test_evaluate_defect_resolved_in_time():
    created = datetime(2026, 10, 18, 10, 0, 0, tzinfo=timezone.utc)
    resolved = created + timedelta(hours=5)

    item = DefectSLATrackingItem(
        defect_id="DEF-101",
        title="支付金额四舍五入偏差",
        severity=DefectSeverity.P1_CRITICAL,  # 解决时限 48h
        status="RESOLVED",
        created_at=created,
        resolved_at=resolved,
        current_assignee="dev_lead@atp.io",
    )

    result = evaluate_defect_sla(item)
    assert result.compliance_status == SLAComplianceStatus.RESOLVED_IN_TIME
    assert result.escalation_action == SLAEscalationAction.NO_ACTION
    assert result.is_release_blocked is False


def test_evaluate_defect_healthy_on_track():
    created = datetime(2026, 10, 18, 10, 0, 0, tzinfo=timezone.utc)
    now = created + timedelta(hours=1)

    item = DefectSLATrackingItem(
        defect_id="DEF-102",
        title="用户头像缩略图清晰度",
        severity=DefectSeverity.P2_MAJOR,  # 响应 12h, 解决 72h
        status="OPEN",
        created_at=created,
        current_assignee="ui_dev@atp.io",
    )

    result = evaluate_defect_sla(item, current_time=now)
    assert result.compliance_status == SLAComplianceStatus.HEALTHY_ON_TRACK
    assert result.escalation_action == SLAEscalationAction.NO_ACTION
    assert result.remaining_hours > 70.0


def test_evaluate_defect_warning_near_breach():
    created = datetime(2026, 10, 18, 0, 0, 0, tzinfo=timezone.utc)
    # P0 解决时限 24h，已过去 18h，剩余 6h (<= 30% 即 7.2h)
    now = created + timedelta(hours=18)

    item = DefectSLATrackingItem(
        defect_id="DEF-103",
        title="支付通道网络超时重试故障",
        severity=DefectSeverity.P0_BLOCKING,
        status="IN_PROGRESS",
        created_at=created,
        first_responded_at=created + timedelta(hours=0.5),
        current_assignee="pay_dev@atp.io",
    )

    result = evaluate_defect_sla(item, current_time=now)
    assert result.compliance_status == SLAComplianceStatus.WARNING_NEAR_BREACH
    assert result.escalation_action == SLAEscalationAction.SEND_YELLOW_WARNING
    assert "临期预警" in result.escalation_notice


def test_evaluate_defect_p0_breached_triggers_release_block():
    created = datetime(2026, 10, 18, 0, 0, 0, tzinfo=timezone.utc)
    # P0 解决时限 24h，已过去 26h，已击穿超时！
    now = created + timedelta(hours=26)

    item = DefectSLATrackingItem(
        defect_id="DEF-104",
        title="核心收银台无法发起支付死锁",
        severity=DefectSeverity.P0_BLOCKING,
        status="IN_PROGRESS",
        created_at=created,
        current_assignee="pay_dev@atp.io",
    )

    result = evaluate_defect_sla(item, current_time=now)
    assert result.compliance_status == SLAComplianceStatus.BREACHED_TIMEOUT
    assert result.escalation_action == SLAEscalationAction.EMERGENCY_RELEASE_BLOCK
    assert result.is_release_blocked is True
    assert "上线发布强阻断" in result.escalation_notice


def test_batch_evaluate_defects_sla():
    now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    items = [
        DefectSLATrackingItem(
            defect_id="D1",
            title="缺陷1",
            severity=DefectSeverity.P2_MAJOR,
            status="OPEN",
            created_at=now - timedelta(hours=2),
            current_assignee="a1@atp.io",
        ),
        DefectSLATrackingItem(
            defect_id="D2",
            title="缺陷2",
            severity=DefectSeverity.P0_BLOCKING,
            status="OPEN",
            created_at=now - timedelta(hours=30),  # 超时
            current_assignee="a2@atp.io",
        ),
    ]

    report = batch_evaluate_defects_sla(items, current_time=now)
    assert report.total_tracked_defects == 2
    assert report.healthy_count == 1
    assert report.breached_count == 1
    assert report.overall_sla_compliance_rate_pct == 50.0

    d = report.to_dict()
    assert d["total_tracked_defects"] == 2
    assert len(d["evaluations"]) == 2
