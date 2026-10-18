"""生产全链路压测特批审批与窗口期强准入看门狗单测 (T4.1)"""

from __future__ import annotations

from app.services.stress_safety_boundary_guard import (
    StressAdmissionRequest,
    StressAdmissionVerdictCode,
    StressDrillTicket,
    StressWindowConfig,
    evaluate_stress_safety_admission,
)


def test_non_production_bypass():
    req = StressAdmissionRequest(
        target_service="payment-service",
        environment="staging",  # 非生产环境
        planned_peak_vu=5000,
    )
    verdict = evaluate_stress_safety_admission(req)
    assert verdict.is_admitted is True
    assert verdict.verdict_code == StressAdmissionVerdictCode.BYPASS_NON_PRODUCTION
    assert "非生产环境" in verdict.reasons[0]


def test_production_three_factor_admitted_pass():
    req = StressAdmissionRequest(
        target_service="order-service",
        environment="production",
        planned_peak_vu=10000,
        ticket=StressDrillTicket(
            ticket_key="JIRA-STRESS-8899",
            status="APPROVED",
            drill_director="张总 (压测演练总指挥)",
        ),
        security_token="SEC_STRESS_TOKEN_998877665544",
        current_hour_utc=2,  # 2:00 UTC (在 01:00 ~ 05:00 窗口内)
    )
    cfg = StressWindowConfig(
        is_freeze_period=False,
        allowed_start_hour_utc=1,
        allowed_end_hour_utc=5,
    )

    verdict = evaluate_stress_safety_admission(req, window_cfg=cfg)
    assert verdict.is_admitted is True
    assert verdict.verdict_code == StressAdmissionVerdictCode.ADMITTED_PASS
    assert any("审批通过" in r for r in verdict.reasons)

    d = verdict.to_dict()
    assert d["is_admitted"] is True
    assert d["verdict_code"] == "ADMITTED_PASS"


def test_blocked_missing_or_unapproved_ticket():
    # 1. 缺失工单
    req_no_ticket = StressAdmissionRequest(
        target_service="payment-service",
        environment="production",
        planned_peak_vu=5000,
        security_token="SEC_STRESS_TOKEN_123456",
        current_hour_utc=2,
    )
    v1 = evaluate_stress_safety_admission(req_no_ticket)
    assert v1.is_admitted is False
    assert v1.verdict_code == StressAdmissionVerdictCode.BLOCKED_NO_TICKET

    # 2. 工单处于 PENDING 审批中状态
    req_pending = StressAdmissionRequest(
        target_service="payment-service",
        environment="production",
        planned_peak_vu=5000,
        ticket=StressDrillTicket(
            ticket_key="JIRA-STRESS-9001",
            status="PENDING",
            drill_director="待审批",
        ),
        security_token="SEC_STRESS_TOKEN_123456",
        current_hour_utc=2,
    )
    v2 = evaluate_stress_safety_admission(req_pending)
    assert v2.is_admitted is False
    assert v2.verdict_code == StressAdmissionVerdictCode.BLOCKED_NO_TICKET


def test_blocked_during_freeze_period():
    req = StressAdmissionRequest(
        target_service="payment-service",
        environment="production",
        planned_peak_vu=5000,
        ticket=StressDrillTicket(
            ticket_key="JIRA-STRESS-8899",
            status="APPROVED",
            drill_director="张总",
        ),
        security_token="SEC_STRESS_TOKEN_123456",
        current_hour_utc=2,
    )
    cfg = StressWindowConfig(is_freeze_period=True)  # 大促封网保障期

    verdict = evaluate_stress_safety_admission(req, window_cfg=cfg)
    assert verdict.is_admitted is False
    assert verdict.verdict_code == StressAdmissionVerdictCode.BLOCKED_FREEZE_WINDOW
    assert "封网重大保障期" in verdict.reasons[0]


def test_blocked_outside_maintenance_window():
    req = StressAdmissionRequest(
        target_service="payment-service",
        environment="production",
        planned_peak_vu=5000,
        ticket=StressDrillTicket(
            ticket_key="JIRA-STRESS-8899",
            status="APPROVED",
            drill_director="张总",
        ),
        security_token="SEC_STRESS_TOKEN_123456",
        current_hour_utc=10,  # 处于白天高峰 10:00 UTC
    )
    cfg = StressWindowConfig(
        is_freeze_period=False,
        allowed_start_hour_utc=1,
        allowed_end_hour_utc=5,  # 仅夜间允许
    )

    verdict = evaluate_stress_safety_admission(req, window_cfg=cfg)
    assert verdict.is_admitted is False
    assert verdict.verdict_code == StressAdmissionVerdictCode.BLOCKED_FREEZE_WINDOW


def test_blocked_invalid_security_token():
    req = StressAdmissionRequest(
        target_service="payment-service",
        environment="production",
        planned_peak_vu=5000,
        ticket=StressDrillTicket(
            ticket_key="JIRA-STRESS-8899",
            status="APPROVED",
            drill_director="张总",
        ),
        security_token="INVALID_TOKEN_TEST",  # 非法令牌
        current_hour_utc=2,
    )
    cfg = StressWindowConfig(allowed_start_hour_utc=1, allowed_end_hour_utc=5)

    verdict = evaluate_stress_safety_admission(req, window_cfg=cfg)
    assert verdict.is_admitted is False
    assert verdict.verdict_code == StressAdmissionVerdictCode.BLOCKED_INVALID_TOKEN
