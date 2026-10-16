"""Unit Tests for Defect Auto Ticket Dispatcher (T3.3)。"""

from __future__ import annotations

import pytest

from app.services.defect_auto_ticket_dispatcher import (
    DefectSeverity,
    TicketPlatform,
    TicketStatus,
    clear_ticket_store,
    determine_defect_severity,
    dispatch_defect_ticket,
    get_ticket,
    list_tickets,
    update_ticket_status,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_ticket_store()
    yield
    clear_ticket_store()


def test_determine_defect_severity_rules():
    # 1. 核心资损或死锁 -> CRITICAL (P0)
    assert determine_defect_severity("DATABASE_EXECUTION_FAILURE") == DefectSeverity.CRITICAL
    assert determine_defect_severity("OTHER", error_message="payment deduct failed") == DefectSeverity.CRITICAL
    assert determine_defect_severity("OTHER", is_critical_asset=True) == DefectSeverity.CRITICAL

    # 2. 500 / 504 -> MAJOR (P1)
    assert determine_defect_severity("DOWNSTREAM_SERVICE_CRASH", http_status_code=500) == DefectSeverity.MAJOR
    assert determine_defect_severity("NETWORK_GATEWAY_TIMEOUT", http_status_code=504) == DefectSeverity.MAJOR

    # 3. 业务断言 / 认证过期 -> NORMAL (P2)
    assert determine_defect_severity("ASSERTION_BUSINESS_LOGIC_DEFECT") == DefectSeverity.NORMAL
    assert determine_defect_severity("AUTHENTICATION_EXPIRED", http_status_code=401) == DefectSeverity.NORMAL

    # 4. 前端定位失效 -> MINOR (P3)
    assert determine_defect_severity("UI_DOM_LOCATOR_DRIFT") == DefectSeverity.MINOR


def test_dispatch_defect_ticket_to_jira_and_github():
    # 1. 建 Jira 工单
    jira_tkt = dispatch_defect_ticket(
        case_id="case_tcc_101",
        case_name="分布式长事务提交用例",
        category="DATABASE_EXECUTION_FAILURE",
        primary_summary="MySQL 订单行锁循环等待死锁导致事务异常中断",
        culprit_service="order-service",
        culprit_location="order_dao.py:210 in lock_order()",
        causal_chain=["[1] 行锁争用", "[2] 抛出死锁异常", "[3] 用例断言失败"],
        suggested_action="按主键升序加锁并优化索引",
        platform="JIRA",
    )

    assert jira_tkt.severity == DefectSeverity.CRITICAL
    assert jira_tkt.platform == TicketPlatform.JIRA
    assert jira_tkt.assignee == "OrderTeam-DevLead"  # 命中 order-service 负责人映射
    assert jira_tkt.external_issue_id.startswith("ATP-JIRA-")
    assert "order_dao.py:210 in lock_order()" in jira_tkt.description
    assert "[1] 行锁争用" in jira_tkt.description

    # 2. 建 GitHub Issue
    gh_tkt = dispatch_defect_ticket(
        case_id="case_ui_202",
        case_name="前端结账按钮点击流",
        category="UI_DOM_LOCATOR_DRIFT",
        primary_summary="按钮 DOM 选择器失效",
        culprit_service="frontend-web",
        platform="GITHUB_ISSUE",
        override_assignee="Frontend-QA-Alice",
    )

    assert gh_tkt.severity == DefectSeverity.MINOR
    assert gh_tkt.platform == TicketPlatform.GITHUB_ISSUE
    assert gh_tkt.assignee == "Frontend-QA-Alice"
    assert gh_tkt.external_issue_id.startswith("GH#")
    assert "atp-auto-bug" in gh_tkt.labels


def test_ticket_lifecycle_status_update():
    ticket = dispatch_defect_ticket(
        case_id="case_303",
        case_name="测试用例303",
        category="DOWNSTREAM_SERVICE_CRASH",
        primary_summary="服务500崩溃",
        culprit_service="pay-service",
    )

    assert ticket.status == TicketStatus.DISPATCHED

    # 更新为已解决
    ok = update_ticket_status(ticket.ticket_id, "RESOLVED")
    assert ok is True
    assert ticket.status == TicketStatus.RESOLVED

    # 非法状态拒绝
    invalid_ok = update_ticket_status(ticket.ticket_id, "INVALID_STATUS")
    assert invalid_ok is False


def test_list_and_filter_tickets():
    dispatch_defect_ticket(
        case_id="c1",
        case_name="用例1",
        category="DATABASE_EXECUTION_FAILURE",
        primary_summary="死锁",
        culprit_service="order-service",
        platform="JIRA",
    )
    dispatch_defect_ticket(
        case_id="c2",
        case_name="用例2",
        category="UI_DOM_LOCATOR_DRIFT",
        primary_summary="定位",
        culprit_service="frontend-web",
        platform="GITHUB_ISSUE",
    )

    all_tkts = list_tickets()
    assert len(all_tkts) == 2

    # 按平台过滤
    jira_tkts = list_tickets(platform="JIRA")
    assert len(jira_tkts) == 1
    assert jira_tkts[0].platform == TicketPlatform.JIRA

    # 按严重度过滤
    crit_tkts = list_tickets(severity="CRITICAL")
    assert len(crit_tkts) == 1
    assert crit_tkts[0].severity == DefectSeverity.CRITICAL

    # 单工单查询
    found = get_ticket(all_tkts[0].ticket_id)
    assert found is not None
