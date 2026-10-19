"""大模型线上接入合规审批与安全强准入看门狗单测 (T4.1)"""

from __future__ import annotations

import pytest

from app.services.llm_eval_safety_boundary_guard import (
    LlmAdmissionRequest,
    LlmAdmissionTicket,
    LlmAdmissionVerdictCode,
    LlmSafetyAdmissionError,
    evaluate_llm_safety_admission,
    enforce_llm_safety_admission,
)

VALID_TOKEN = "LLM_SEC_TOKEN_20261019_PROD_998877"


def test_non_production_bypass():
    """测试非生产环境 (staging/test/dev) 安全旁路快速放行 (BYPASS_NON_PRODUCTION)"""
    req = LlmAdmissionRequest(
        model_name="experimental-model-v1",
        environment="staging",
        caller_service="qa-test-agent",
    )
    verdict = evaluate_llm_safety_admission(req)

    assert verdict.is_admitted is True
    assert verdict.verdict_code == LlmAdmissionVerdictCode.BYPASS_NON_PRODUCTION
    assert "非生产环境" in verdict.reason


def test_production_admitted_pass():
    """测试生产环境三要素全部合格准予接入放行 (ADMITTED_PASS)"""
    ticket = LlmAdmissionTicket(
        ticket_key="OA-LLM-20261019-001",
        status="APPROVED",
        approver="sec_architect_01",
        composite_score=94.5,
        red_team_defense_rate=98.0,
    )
    req = LlmAdmissionRequest(
        model_name="qwen-2.5-72b",
        environment="production",
        caller_service="payment-recommend-agent",
        ticket=ticket,
        security_token=VALID_TOKEN,
    )
    verdict = evaluate_llm_safety_admission(req)

    assert verdict.is_admitted is True
    assert verdict.verdict_code == LlmAdmissionVerdictCode.ADMITTED_PASS
    assert verdict.checked_items["model_whitelist_check"] is True
    assert verdict.checked_items["token_check"] is True
    assert verdict.checked_items["ticket_status_check"] is True


def test_blocked_unauthorized_model():
    """测试未列入企业备案白名单的模型被生产强阻断 (BLOCKED_UNAUTHORIZED_MODEL)"""
    ticket = LlmAdmissionTicket(
        ticket_key="OA-LLM-20261019-002",
        status="APPROVED",
        approver="sec_architect_01",
    )
    req = LlmAdmissionRequest(
        model_name="unauthorized-wild-model-v9",
        environment="prod",
        caller_service="unknown-service",
        ticket=ticket,
        security_token=VALID_TOKEN,
    )
    verdict = evaluate_llm_safety_admission(req)

    assert verdict.is_admitted is False
    assert verdict.verdict_code == LlmAdmissionVerdictCode.BLOCKED_UNAUTHORIZED_MODEL
    assert "未列入企业合规准入白名单" in verdict.reason


def test_blocked_invalid_token():
    """测试安全访问鉴权令牌缺失或伪造时的阻断 (BLOCKED_INVALID_TOKEN)"""
    ticket = LlmAdmissionTicket(
        ticket_key="OA-LLM-20261019-003",
        status="APPROVED",
        approver="sec_architect_01",
    )
    # 令牌前缀错误或缺失
    req = LlmAdmissionRequest(
        model_name="deepseek-v3",
        environment="production",
        caller_service="payment-agent",
        ticket=ticket,
        security_token="INVALID_FORGED_TOKEN",
    )
    verdict = evaluate_llm_safety_admission(req)

    assert verdict.is_admitted is False
    assert verdict.verdict_code == LlmAdmissionVerdictCode.BLOCKED_INVALID_TOKEN
    assert "未提供合法的大模型生产访问鉴权令牌" in verdict.reason


def test_blocked_no_ticket():
    """测试生产环境缺失安全评测审批单时的阻断 (BLOCKED_NO_TICKET)"""
    req = LlmAdmissionRequest(
        model_name="deepseek-r1",
        environment="production",
        caller_service="settlement-agent",
        ticket=None,
        security_token=VALID_TOKEN,
    )
    verdict = evaluate_llm_safety_admission(req)

    assert verdict.is_admitted is False
    assert verdict.verdict_code == LlmAdmissionVerdictCode.BLOCKED_NO_TICKET
    assert "当前未提供有效审批单" in verdict.reason


def test_blocked_ticket_not_approved():
    """测试审批单处于 PENDING/REJECTED 状态时的阻断 (BLOCKED_TICKET_NOT_APPROVED)"""
    ticket = LlmAdmissionTicket(
        ticket_key="OA-LLM-20261019-004",
        status="PENDING",
        approver="pending_approver",
    )
    req = LlmAdmissionRequest(
        model_name="llama-3.3-70b",
        environment="production",
        caller_service="analytics-agent",
        ticket=ticket,
        security_token=VALID_TOKEN,
    )
    verdict = evaluate_llm_safety_admission(req)

    assert verdict.is_admitted is False
    assert verdict.verdict_code == LlmAdmissionVerdictCode.BLOCKED_TICKET_NOT_APPROVED
    assert "尚未审批通过" in verdict.reason


def test_blocked_substandard_metrics():
    """测试审批单内评测综合分或越狱防御率不达标时的阻断"""
    # 综合分仅 72.0 (低于门槛 80.0)
    ticket = LlmAdmissionTicket(
        ticket_key="OA-LLM-20261019-005",
        status="APPROVED",
        approver="sec_architect_01",
        composite_score=72.0,
        red_team_defense_rate=80.0,
    )
    req = LlmAdmissionRequest(
        model_name="gpt-4o",
        environment="production",
        caller_service="ops-agent",
        ticket=ticket,
        security_token=VALID_TOKEN,
    )
    verdict = evaluate_llm_safety_admission(req)

    assert verdict.is_admitted is False
    assert verdict.verdict_code == LlmAdmissionVerdictCode.BLOCKED_TICKET_NOT_APPROVED
    assert "安全审批单指标不达标" in verdict.reason


def test_enforce_llm_safety_admission():
    """测试看门狗强断言异常抛出与合规返回"""
    # 1. 违规请求抛出 LlmSafetyAdmissionError
    req_bad = LlmAdmissionRequest(
        model_name="illegal-model",
        environment="production",
        caller_service="rogue-service",
    )
    with pytest.raises(LlmSafetyAdmissionError) as exc_info:
        enforce_llm_safety_admission(req_bad)
    assert exc_info.value.verdict.is_admitted is False

    # 2. 合规请求正常返回 verdict
    req_good = LlmAdmissionRequest(
        model_name="qwen-2.5-72b",
        environment="test",
        caller_service="test-service",
    )
    verdict_good = enforce_llm_safety_admission(req_good)
    assert verdict_good.is_admitted is True
