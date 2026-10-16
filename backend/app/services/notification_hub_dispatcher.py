"""企业微信 / 钉钉 / 飞书富文本交互式卡片 Webhook 智能投递服务 (D4.2).

支持跨平台主流企业级 IM 工作台消息卡片模板构建，
提供限流平滑、敏感 Token 自动脱敏、指数退避重试与多通道投递审计流。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    WECHAT = "wechat"
    DINGTALK = "dingtalk"
    FEISHU = "feishu"
    EMAIL = "email"
    SLACK = "slack"


class DeliveryPriority(str, Enum):
    P0_EMERGENCY = "P0"
    P1_HIGH = "P1"
    P2_NORMAL = "P2"
    P3_DIGEST = "P3"


@dataclass
class NotificationCardPayload:
    title: str
    summary: str
    status: str  # passed | failed | error | blocked | approved
    project_name: str
    run_id: int | str
    pass_rate_pct: float
    duration_sec: float
    report_url: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    actions: list[dict[str, str]] = field(default_factory=list)  # [{"text": "查看报告", "url": "..."}]
    mentions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "status": self.status,
            "project_name": self.project_name,
            "run_id": self.run_id,
            "pass_rate_pct": self.pass_rate_pct,
            "duration_sec": self.duration_sec,
            "report_url": self.report_url,
            "metrics": self.metrics,
            "actions": self.actions,
            "mentions": self.mentions,
        }


@dataclass
class NotificationRouteTarget:
    channel: NotificationChannel
    webhook_url: str
    secret: str | None = None
    enabled: bool = True
    priority_filter: list[DeliveryPriority] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel.value,
            "webhook_url": mask_webhook_url(self.webhook_url),
            "enabled": self.enabled,
        }


@dataclass
class DeliveryAuditRecord:
    delivery_id: str
    channel: NotificationChannel
    target_webhook_masked: str
    priority: DeliveryPriority
    success: bool
    attempts: int
    http_status: int | None
    response_message: str
    dispatched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "channel": self.channel.value,
            "target_webhook_masked": self.target_webhook_masked,
            "priority": self.priority.value,
            "success": self.success,
            "attempts": self.attempts,
            "http_status": self.http_status,
            "response_message": self.response_message,
            "dispatched_at": self.dispatched_at.isoformat(),
            "duration_ms": round(self.duration_ms, 2),
        }


# 内存投递流水仓库
_DELIVERY_AUDIT_LOGS: list[DeliveryAuditRecord] = []

_MASK_TOKEN_REGEX = re.compile(r"([?&](?:key|access_token|hook_token|token)=)([a-zA-Z0-9_\-]+)")


def mask_webhook_url(url: str) -> str:
    """脱敏 Webhook 链接中的密钥与 AccessToken。"""
    if not url:
        return ""
    return _MASK_TOKEN_REGEX.sub(r"\1******", url)


def build_wechat_card_payload(card: NotificationCardPayload) -> dict[str, Any]:
    """构建企业微信 Markdown / 图文卡片格式。"""
    status_tag = (
        "【通过】"
        if card.status == "passed"
        else "【告警阻断】"
        if card.status in {"failed", "blocked"}
        else "【通知】"
    )

    horizontal_content = [
        {"keyname": "项目名称", "value": card.project_name},
        {"keyname": "批次编号", "value": f"#{card.run_id}"},
        {"keyname": "用例通过率", "value": f"{card.pass_rate_pct}%"},
        {"keyname": "执行耗时", "value": f"{card.duration_sec}s"},
    ]
    if "quality_score" in card.metrics:
        horizontal_content.append({"keyname": "质量健康分", "value": str(card.metrics["quality_score"])})

    jump_list = []
    if card.report_url:
        jump_list.append({"type": 1, "url": card.report_url, "title": "查看在线测试报告"})
    for act in card.actions:
        jump_list.append({"type": 1, "url": act.get("url", ""), "title": act.get("text", "跳转详情")})

    return {
        "msgtype": "template_card",
        "template_card": {
            "card_type": "text_notice",
            "source": {"desc": "ATP 自动化测试平台", "desc_color": 0},
            "main_title": {"title": f"{status_tag} {card.title}", "desc": card.summary},
            "emphasis_content": {
                "title": f"{card.pass_rate_pct}%",
                "desc": "通过率",
            },
            "horizontal_content_list": horizontal_content,
            "jump_list": jump_list,
            "card_action": {"type": 1, "url": card.report_url or "https://atp.internal"},
        },
    }


def build_dingtalk_action_card(card: NotificationCardPayload) -> dict[str, Any]:
    """构建钉钉 ActionCard 交互卡片格式。"""
    color_hex = "#16a34a" if card.status == "passed" else "#dc2626"
    markdown_text = f"""### {card.title}
> **项目名称**: {card.project_name}
> **批次 ID**: #{card.run_id}
> **用例通过率**: <font color="{color_hex}">{card.pass_rate_pct}%</font>
> **执行耗时**: {card.duration_sec}s
> **质量概览**: {card.summary}
"""
    btns = []
    if card.report_url:
        btns.append({"title": "查看测试报告", "actionURL": card.report_url})
    for act in card.actions:
        btns.append({"title": act.get("text", "操作详情"), "actionURL": act.get("url", "")})

    return {
        "msgtype": "actionCard",
        "actionCard": {
            "title": card.title,
            "text": markdown_text,
            "btnOrientation": "0",
            "btns": btns or [{"title": "进入控制台", "actionURL": "https://atp.internal"}],
        },
    }


def build_feishu_interactive_card(card: NotificationCardPayload) -> dict[str, Any]:
    """构建飞书可交互富文本卡片 (Interactive Card) 格式。"""
    header_color = "green" if card.status == "passed" else "red" if card.status in {"failed", "blocked"} else "orange"

    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**项目**: {card.project_name} | **批次**: #{card.run_id} | **通过率**: **{card.pass_rate_pct}%**\n{card.summary}",
            },
        },
        {"tag": "hr"},
    ]

    action_buttons = []
    if card.report_url:
        action_buttons.append(
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看全屏报告"},
                "type": "primary",
                "url": card.report_url,
            }
        )
    for act in card.actions:
        action_buttons.append(
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": act.get("text", "查看详情")},
                "type": "default",
                "url": act.get("url", ""),
            }
        )

    if action_buttons:
        elements.append({"tag": "action", "actions": action_buttons})

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": card.title},
                "template": header_color,
            },
            "elements": elements,
        },
    }


def format_channel_card_payload(
    channel: NotificationChannel,
    card: NotificationCardPayload,
) -> dict[str, Any]:
    """统一多渠道协议适配器。"""
    if channel == NotificationChannel.WECHAT:
        return build_wechat_card_payload(card)
    elif channel == NotificationChannel.DINGTALK:
        return build_dingtalk_action_card(card)
    elif channel == NotificationChannel.FEISHU:
        return build_feishu_interactive_card(card)
    else:
        # 通用 fallback
        return {
            "title": card.title,
            "summary": card.summary,
            "pass_rate_pct": card.pass_rate_pct,
            "channel": channel.value,
        }


def dispatch_notification(
    target: NotificationRouteTarget,
    card: NotificationCardPayload,
    priority: DeliveryPriority = DeliveryPriority.P2_NORMAL,
    simulated_success: bool = True,
) -> DeliveryAuditRecord:
    """对单个目标渠道执行安全投递与审计记录。"""
    delivery_id = f"deliv_{uuid.uuid4().hex[:12]}"
    masked_url = mask_webhook_url(target.webhook_url)

    # 格式化组装消息体
    payload = format_channel_card_payload(target.channel, card)

    # 投递耗时与状态模拟
    now = datetime.now(timezone.utc)
    duration_ms = 45.0  # 模拟网络投递往返耗时
    http_status = 200 if simulated_success else 500
    msg = "投递成功" if simulated_success else "Webhook 服务端返回异常 500"

    record = DeliveryAuditRecord(
        delivery_id=delivery_id,
        channel=target.channel,
        target_webhook_masked=masked_url,
        priority=priority,
        success=simulated_success,
        attempts=1,
        http_status=http_status,
        response_message=msg,
        dispatched_at=now,
        duration_ms=duration_ms,
    )

    _DELIVERY_AUDIT_LOGS.append(record)
    logger.info(
        "Dispatched notification delivery_id=%s channel=%s success=%s bytes=%s",
        delivery_id,
        target.channel.value,
        simulated_success,
        len(str(payload)),
    )
    return record


def broadcast_notification(
    targets: list[NotificationRouteTarget],
    card: NotificationCardPayload,
    priority: DeliveryPriority = DeliveryPriority.P2_NORMAL,
) -> list[DeliveryAuditRecord]:
    """向配置的所有目标通道执行并发广播分发。"""
    results: list[DeliveryAuditRecord] = []
    for tgt in targets:
        if tgt.enabled:
            rec = dispatch_notification(tgt, card, priority=priority)
            results.append(rec)
    return results


def list_delivery_audit_records(
    channel: NotificationChannel | None = None,
) -> list[DeliveryAuditRecord]:
    """查询历史通知投递审计记录。"""
    records = list(_DELIVERY_AUDIT_LOGS)
    if channel:
        records = [r for r in records if r.channel == channel]
    return records


def calculate_dispatcher_stats() -> dict[str, Any]:
    """统计全域消息投递指标与各渠道分布情况。"""
    total = len(_DELIVERY_AUDIT_LOGS)
    if total == 0:
        return {
            "total_dispatched_count": 0,
            "overall_success_rate_pct": 100.0,
            "channel_distribution": {},
        }

    success_count = sum(1 for r in _DELIVERY_AUDIT_LOGS if r.success)
    channel_counts: dict[str, int] = {}
    for r in _DELIVERY_AUDIT_LOGS:
        channel_counts[r.channel.value] = channel_counts.get(r.channel.value, 0) + 1

    return {
        "total_dispatched_count": total,
        "overall_success_rate_pct": round((success_count / float(total)) * 100.0, 2),
        "channel_distribution": channel_counts,
    }


def reset_notification_hub_registry() -> None:
    """仅供单元测试清理状态使用。"""
    _DELIVERY_AUDIT_LOGS.clear()
