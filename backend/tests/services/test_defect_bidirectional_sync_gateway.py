"""跨平台缺陷工单双向状态同步网关单测 (T2.2)"""

from __future__ import annotations

import pytest

from app.services.defect_bidirectional_sync_gateway import (
    DefectLifecycleState,
    ExternalTicketBinding,
    ExternalTicketPlatform,
    SyncActionType,
    clear_sync_audit_logs,
    get_sync_audit_logs,
    handle_inbound_external_webhook,
    sync_defect_status_on_regression_result,
)


@pytest.fixture(autouse=True)
def setup_gateway():
    clear_sync_audit_logs()
    yield
    clear_sync_audit_logs()


def test_regression_pass_auto_resolves_open_defect():
    binding = ExternalTicketBinding(
        defect_id="DEF-1001",
        platform=ExternalTicketPlatform.JIRA,
        external_ticket_key="JIRA-BUG-4021",
        external_status="Open",
        atp_status=DefectLifecycleState.OPEN,
        linked_case_id="case_payment_checkout",
    )

    result = sync_defect_status_on_regression_result(
        binding=binding,
        regression_passed=True,
    )
    assert result.action_taken == SyncActionType.AUTO_RESOLVED_ON_PASS
    assert result.new_state == DefectLifecycleState.CLOSED.value
    assert binding.atp_status == DefectLifecycleState.CLOSED
    assert binding.external_status == "Resolved"
    assert "回归验证通过" in result.sync_message

    logs = get_sync_audit_logs("DEF-1001")
    assert len(logs) == 1


def test_regression_fail_auto_reopens_resolved_defect():
    # 模拟已被标记为 Resolved 的工单，回归再次失败
    binding = ExternalTicketBinding(
        defect_id="DEF-1002",
        platform=ExternalTicketPlatform.GITHUB,
        external_ticket_key="#452",
        external_status="Closed",
        atp_status=DefectLifecycleState.CLOSED,
        linked_case_id="case_auth_login",
    )

    result = sync_defect_status_on_regression_result(
        binding=binding,
        regression_passed=False,
        latest_error_detail="TokenSignatureExpiredException: token invalid",
    )
    assert result.action_taken == SyncActionType.AUTO_REOPENED_ON_FAIL
    assert result.new_state == DefectLifecycleState.REOPENED.value
    assert binding.atp_status == DefectLifecycleState.REOPENED
    assert binding.external_status == "open"
    assert "自动激活重新打开" in result.sync_message
    assert "TokenSignatureExpiredException" in result.sync_message


def test_regression_noop_scenarios():
    # 1. 已经是 Closed 的工单回归再次通过 -> NO_OP
    binding_closed = ExternalTicketBinding(
        defect_id="DEF-1003",
        platform=ExternalTicketPlatform.JIRA,
        external_ticket_key="JIRA-55",
        external_status="Closed",
        atp_status=DefectLifecycleState.CLOSED,
        linked_case_id="case_order_calc",
    )
    res_pass = sync_defect_status_on_regression_result(binding_closed, regression_passed=True)
    assert res_pass.action_taken == SyncActionType.NO_OP_ALREADY_IN_SYNC

    # 2. 本身是 Open 的工单回归仍然失败 -> NO_OP
    binding_open = ExternalTicketBinding(
        defect_id="DEF-1004",
        platform=ExternalTicketPlatform.JIRA,
        external_ticket_key="JIRA-66",
        external_status="Open",
        atp_status=DefectLifecycleState.OPEN,
        linked_case_id="case_order_calc",
    )
    res_fail = sync_defect_status_on_regression_result(binding_open, regression_passed=False)
    assert res_fail.action_taken == SyncActionType.NO_OP_ALREADY_IN_SYNC


def test_inbound_external_webhook():
    binding = ExternalTicketBinding(
        defect_id="DEF-1005",
        platform=ExternalTicketPlatform.ZHENTAO,
        external_ticket_key="BUG-899",
        external_status="active",
        atp_status=DefectLifecycleState.OPEN,
        linked_case_id="case_inv_sku",
    )

    # 外部 Jira / 禅道开发人员点击了 In Progress
    res_prog = handle_inbound_external_webhook(
        binding, external_event="jira:issue_updated", new_external_status="In Progress"
    )
    assert res_prog.action_taken == SyncActionType.INBOUND_STATUS_UPDATED
    assert binding.atp_status == DefectLifecycleState.IN_PROGRESS

    # 外部点击了 Resolved
    res_done = handle_inbound_external_webhook(
        binding, external_event="jira:issue_resolved", new_external_status="Resolved"
    )
    assert binding.atp_status == DefectLifecycleState.RESOLVED

    d = res_done.to_dict()
    assert d["action_taken"] == "INBOUND_STATUS_UPDATED"
    assert d["new_state"] == "RESOLVED"
