"""生产环境灰度强准入与金丝雀发布审批看门狗单测 (T4.1)"""

from __future__ import annotations

from app.services.canary_safety_boundary_guard import (
    CanaryAdmissionRequest,
    CanaryAdmissionVerdictCode,
    CanaryReleaseTicket,
    MaintenanceWindowConfig,
    evaluate_canary_safety_admission,
)


def test_non_production_bypass():
    req = CanaryAdmissionRequest(
        target_service="payment-service",
        environment="staging",  # 非生产环境
        proposed_canary_weight_pct=15.0,
    )
    verdict = evaluate_canary_safety_admission(req)
    assert verdict.is_admitted is True
    assert verdict.verdict_code == CanaryAdmissionVerdictCode.BYPASS_NON_PRODUCTION
    assert "非生产环境" in verdict.reasons[0]


def test_production_three_factor_admitted_pass():
    req = CanaryAdmissionRequest(
        target_service="order-service",
        environment="production",
        proposed_canary_weight_pct=10.0,
        ticket=CanaryReleaseTicket(
            ticket_key="JIRA-CANARY-8899",
            status="APPROVED",
            approver="王总 (生产运维总监)",
        ),
        security_token="SEC_CANARY_TOKEN_998877665544",
        current_hour_utc=3,  # 3:00 UTC
    )
    cfg = MaintenanceWindowConfig(
        is_freeze_period=False,
        allowed_start_hour_utc=0,
        allowed_end_hour_utc=6,
    )

    verdict = evaluate_canary_safety_admission(req, window_cfg=cfg)
    assert verdict.is_admitted is True
    assert verdict.verdict_code == CanaryAdmissionVerdictCode.ADMITTED_PASS
    assert any("审批通过" in r for r in verdict.reasons)

    d = verdict.to_dict()
    assert d["is_admitted"] is True
    assert d["verdict_code"] == "ADMITTED_PASS"


def test_blocked_missing_or_unapproved_ticket():
    # 1. 缺失工单
    req_no_ticket = CanaryAdmissionRequest(
        target_service="payment-service",
        environment="production",
        proposed_canary_weight_pct=5.0,
        security_token="SEC_CANARY_TOKEN_123456",
    )
    v1 = evaluate_canary_safety_admission(req_no_ticket)
    assert v1.is_admitted is False
    assert v1.verdict_code == CanaryAdmissionVerdictCode.BLOCKED_NO_TICKET

    # 2. 工单处于 PENDING 审批中状态
    req_pending = CanaryAdmissionRequest(
        target_service="payment-service",
        environment="production",
        proposed_canary_weight_pct=5.0,
        ticket=CanaryReleaseTicket(
            ticket_key="JIRA-CANARY-9001",
            status="PENDING",
            approver="待审批",
        ),
        security_token="SEC_CANARY_TOKEN_123456",
    )
    v2 = evaluate_canary_safety_admission(req_pending)
    assert v2.is_admitted is False
    assert v2.verdict_code == CanaryAdmissionVerdictCode.BLOCKED_NO_TICKET


def test_blocked_during_freeze_period():
    req = CanaryAdmissionRequest(
        target_service="payment-service",
        environment="production",
        proposed_canary_weight_pct=5.0,
        ticket=CanaryReleaseTicket(
            ticket_key="JIRA-CANARY-8899",
            status="APPROVED",
            approver="王总",
        ),
        security_token="SEC_CANARY_TOKEN_123456",
    )
    cfg = MaintenanceWindowConfig(is_freeze_period=True)  # 大促封网保障期

    verdict = evaluate_canary_safety_admission(req, window_cfg=cfg)
    assert verdict.is_admitted is False
    assert verdict.verdict_code == CanaryAdmissionVerdictCode.BLOCKED_FREEZE_WINDOW
    assert "封网重大保障期" in verdict.reasons[0]


def test_blocked_outside_maintenance_window():
    req = CanaryAdmissionRequest(
        target_service="payment-service",
        environment="production",
        proposed_canary_weight_pct=5.0,
        ticket=CanaryReleaseTicket(
            ticket_key="JIRA-CANARY-8899",
            status="APPROVED",
            approver="王总",
        ),
        security_token="SEC_CANARY_TOKEN_123456",
        current_hour_utc=14,  # 白天业务高峰 14:00
    )
    cfg = MaintenanceWindowConfig(
        is_freeze_period=False,
        allowed_start_hour_utc=0,
        allowed_end_hour_utc=6,  # 仅夜间允许
    )

    verdict = evaluate_canary_safety_admission(req, window_cfg=cfg)
    assert verdict.is_admitted is False
    assert verdict.verdict_code == CanaryAdmissionVerdictCode.BLOCKED_FREEZE_WINDOW


def test_blocked_invalid_security_token():
    req = CanaryAdmissionRequest(
        target_service="payment-service",
        environment="production",
        proposed_canary_weight_pct=5.0,
        ticket=CanaryReleaseTicket(
            ticket_key="JIRA-CANARY-8899",
            status="APPROVED",
            approver="王总",
        ),
        security_token="INVALID_FORGED_TOKEN",  # 非法令牌
        current_hour_utc=2,
    )
    cfg = MaintenanceWindowConfig(allowed_start_hour_utc=0, allowed_end_hour_utc=6)

    verdict = evaluate_canary_safety_admission(req, window_cfg=cfg)
    assert verdict.is_admitted is False
    assert verdict.verdict_code == CanaryAdmissionVerdictCode.BLOCKED_INVALID_TOKEN
