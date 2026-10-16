"""缺陷严重度智能评级与第三方工单自动指派网关服务 (T3.3)。

负责对测试执行失败与根因推导结果：
1. 智能评估缺陷严重度等级 (CRITICAL P0 / MAJOR P1 / NORMAL P2 / MINOR P3)；
2. 依据责任微服务与故障属性智能推荐指派责任人与团队 (Assignee Routing)；
3. 对接 Jira、GitHub Issues 与 企业微信/钉钉/飞书 Webhook 自动化创建工单并广播。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class DefectSeverity(str, Enum):
    CRITICAL = "CRITICAL"  # P0: 核心资损、支付崩溃、数据死锁、全网阻塞
    MAJOR = "MAJOR"  # P1: 核心业务流程中断、微服务 500、网关 504 超时
    NORMAL = "NORMAL"  # P2: 业务功能断言不符、非核心流程异常
    MINOR = "MINOR"  # P3: 轻微展示异常、非阻断性告警或文案漂移


class TicketPlatform(str, Enum):
    JIRA = "JIRA"
    GITHUB_ISSUE = "GITHUB_ISSUE"
    WEBHOOK_ROBOT = "WEBHOOK_ROBOT"


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    DISPATCHED = "DISPATCHED"
    RESOLVED = "RESOLVED"


@dataclass
class DefectTicketItem:
    ticket_id: str
    title: str
    severity: DefectSeverity
    platform: TicketPlatform
    case_id: str
    case_name: str
    culprit_service: str
    assignee: str
    external_issue_id: str
    description: str
    status: TicketStatus = TicketStatus.OPEN
    labels: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "title": self.title,
            "severity": self.severity.value,
            "platform": self.platform.value,
            "case_id": self.case_id,
            "case_name": self.case_name,
            "culprit_service": self.culprit_service,
            "assignee": self.assignee,
            "external_issue_id": self.external_issue_id,
            "description": self.description,
            "status": self.status.value,
            "labels": self.labels,
            "created_at": self.created_at.isoformat(),
        }


# 全局默认服务指派路由映射表: service_name -> assignee
_DEFAULT_SERVICE_OWNER_MAP: dict[str, str] = {
    "order-service": "OrderTeam-DevLead",
    "pay-service": "FinancePay-OnCall",
    "auth-service": "SecurityAuth-Team",
    "inventory-service": "SupplyChain-Dev",
    "gateway": "InfraGateway-OnCall",
    "database": "DBA-Team",
    "frontend-web": "Frontend-QA-Lead",
}

# 全局工单存储仓库: ticket_id -> DefectTicketItem
_TICKET_STORE: dict[str, DefectTicketItem] = {}


def determine_defect_severity(
    category: str,
    http_status_code: int | None = None,
    error_message: str = "",
    is_critical_asset: bool = False,
) -> DefectSeverity:
    """根据根因分类、状态码与错误语义智能评定缺陷严重度。"""
    cat = category.upper()
    err_lower = error_message.lower()

    # 1. CRITICAL (P0): 涉及支付、资金、数据死锁、跨微服务数据撕裂或核心资产损坏
    if is_critical_asset or cat == "DATABASE_EXECUTION_FAILURE" or "deadlock" in err_lower or "pay" in err_lower:
        return DefectSeverity.CRITICAL

    # 2. MAJOR (P1): 500 服务崩溃或 504 网关超时
    if cat in ("DOWNSTREAM_SERVICE_CRASH", "NETWORK_GATEWAY_TIMEOUT") or (
        http_status_code and http_status_code in (500, 502, 503, 504)
    ):
        return DefectSeverity.MAJOR

    # 3. NORMAL (P2): 认证过期、业务逻辑断言失败或前置数据缺失
    if cat in ("AUTHENTICATION_EXPIRED", "ASSERTION_BUSINESS_LOGIC_DEFECT", "TEST_DATA_PRECONDITION_UNMET"):
        return DefectSeverity.NORMAL

    # 4. MINOR (P3): 前端定位漂移、轻微告警
    if cat == "UI_DOM_LOCATOR_DRIFT":
        return DefectSeverity.MINOR

    return DefectSeverity.NORMAL


def _format_ticket_description(
    case_id: str,
    case_name: str,
    severity: DefectSeverity,
    culprit_service: str,
    culprit_location: str,
    primary_summary: str,
    causal_chain: list[str],
    suggested_action: str,
) -> str:
    """组装标准化 Markdown 格式缺陷工单正文。"""
    lines = [
        f"### 🚨 自动化测试失败缺陷工单: [{severity.value}] {case_name}",
        f"- **关联用例 ID**: `{case_id}`",
        f"- **故障责任微服务**: `{culprit_service}`",
        f"- **首发异常位置**: `{culprit_location}`",
        f"- **严重度等级**: `{severity.value}`",
        "",
        "#### 1. 缺陷与根本原因摘要",
        f"> {primary_summary}",
        "",
        "#### 2. 失效因果传播链条 (Causal Chain)",
    ]
    for step in causal_chain:
        lines.append(f"- {step}")

    lines.extend(
        [
            "",
            "#### 3. 专家排查与修复建议",
            f"> {suggested_action}",
            "",
            "_此工单由 ATP 自动化测试平台智能根因推导网关自动生成_",
        ]
    )
    return "\n".join(lines)


def dispatch_defect_ticket(
    case_id: str,
    case_name: str,
    category: str,
    primary_summary: str,
    culprit_service: str = "unknown-service",
    culprit_location: str = "unknown_location",
    causal_chain: list[str] | None = None,
    suggested_action: str = "排查相关服务日志与代码实现",
    http_status_code: int | None = None,
    error_message: str = "",
    platform: str = "JIRA",
    override_assignee: str | None = None,
    is_critical_asset: bool = False,
    ticket_id: str | None = None,
) -> DefectTicketItem:
    """根据多模态根因推导结果自动评级并向指定缺陷管理平台分发工单。"""
    tid = ticket_id or f"tkt_{uuid.uuid4().hex[:10]}"
    severity = determine_defect_severity(
        category=category,
        http_status_code=http_status_code,
        error_message=error_message,
        is_critical_asset=is_critical_asset,
    )

    plat = (
        TicketPlatform(platform.upper())
        if platform.upper() in TicketPlatform._value2member_map_
        else TicketPlatform.JIRA
    )

    # 确定指派人: 优先传入覆盖，次选配置路由，保底默认
    assignee = override_assignee or _DEFAULT_SERVICE_OWNER_MAP.get(culprit_service) or f"{culprit_service}-maintainer"

    # 生成各平台对应的外部票据号模拟
    if plat == TicketPlatform.JIRA:
        ext_issue = f"ATP-JIRA-{uuid.uuid4().int % 9000 + 1000}"
    elif plat == TicketPlatform.GITHUB_ISSUE:
        ext_issue = f"GH#{uuid.uuid4().int % 900 + 100}"
    else:
        ext_issue = f"ROBOT-NOTIFY-{uuid.uuid4().hex[:8]}"

    desc = _format_ticket_description(
        case_id=case_id,
        case_name=case_name,
        severity=severity,
        culprit_service=culprit_service,
        culprit_location=culprit_location,
        primary_summary=primary_summary,
        causal_chain=causal_chain or [],
        suggested_action=suggested_action,
    )

    title = f"[{severity.value}] [{culprit_service}] {case_name} 自动化测试执行失败"

    labels = ["atp-auto-bug", f"severity-{severity.value.lower()}", f"service-{culprit_service}"]

    ticket = DefectTicketItem(
        ticket_id=tid,
        title=title,
        severity=severity,
        platform=plat,
        case_id=case_id,
        case_name=case_name,
        culprit_service=culprit_service,
        assignee=assignee,
        external_issue_id=ext_issue,
        description=desc,
        status=TicketStatus.DISPATCHED,
        labels=labels,
    )

    _TICKET_STORE[tid] = ticket
    return ticket


def get_ticket(ticket_id: str) -> DefectTicketItem | None:
    """获取指定缺陷工单详情。"""
    return _TICKET_STORE.get(ticket_id)


def list_tickets(
    platform: str | None = None,
    severity: str | None = None,
    culprit_service: str | None = None,
    limit: int = 50,
) -> list[DefectTicketItem]:
    """查询已分发的缺陷工单列表。"""
    res = list(_TICKET_STORE.values())

    if platform:
        res = [t for t in res if t.platform.value == platform.upper()]
    if severity:
        res = [t for t in res if t.severity.value == severity.upper()]
    if culprit_service:
        res = [t for t in res if t.culprit_service == culprit_service]

    res.sort(key=lambda t: t.created_at, reverse=True)
    return res[:limit]


def update_ticket_status(ticket_id: str, new_status: str) -> bool:
    """更新缺陷工单状态 (OPEN / ASSIGNED / DISPATCHED / RESOLVED)。"""
    t = _TICKET_STORE.get(ticket_id)
    if not t:
        return False
    try:
        t.status = TicketStatus(new_status.upper())
        return True
    except ValueError:
        return False


def clear_ticket_store() -> int:
    """清空工单缓存。"""
    c = len(_TICKET_STORE)
    _TICKET_STORE.clear()
    return c
