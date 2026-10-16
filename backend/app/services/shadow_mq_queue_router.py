"""消息队列影子队列与死信重试分流隔离分流器 (T1.3)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MqBypassAction(str, Enum):
    """外部高危消费旁路阻断策略。"""

    REDIRECT_SHADOW_CONSUMER = "REDIRECT_SHADOW_CONSUMER"  # 重定向至影子消费者集群
    MOCK_DISPATCH = "MOCK_DISPATCH"  # 模拟下发 (返回假回执，不调用真实外部系统)
    DROP_SILENTLY = "DROP_SILENTLY"  # 静默丢弃 (防假短信/虚假扣款)


@dataclass
class ShadowMqRouteRule:
    """MQ 影子分流与隔离规则。"""

    rule_id: str
    production_topic: str
    shadow_topic: str
    dead_letter_queue: str
    bypass_action: MqBypassAction
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "production_topic": self.production_topic,
            "shadow_topic": self.shadow_topic,
            "dead_letter_queue": self.dead_letter_queue,
            "bypass_action": self.bypass_action.value,
            "is_active": self.is_active,
        }


@dataclass
class MqRoutingDecision:
    """单条消息路由决策详情。"""

    message_id: str
    original_topic: str
    is_shadow: bool
    routed_topic: str
    is_redirected: bool
    bypassed_action: MqBypassAction | None
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "original_topic": self.original_topic,
            "is_shadow": self.is_shadow,
            "routed_topic": self.routed_topic,
            "is_redirected": self.is_redirected,
            "bypassed_action": self.bypassed_action.value if self.bypassed_action else None,
            "explanation": self.explanation,
        }


@dataclass
class MqShuntingAuditReport:
    """MQ 影子分流审计全景报告。"""

    report_id: str
    cluster_name: str
    total_messages_processed: int
    shadow_messages_count: int
    redirected_to_shadow_count: int
    bypassed_mock_count: int
    unmapped_leak_count: int
    shunting_safety_score_pct: float
    decisions: list[MqRoutingDecision]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "cluster_name": self.cluster_name,
            "total_messages_processed": self.total_messages_processed,
            "shadow_messages_count": self.shadow_messages_count,
            "redirected_to_shadow_count": self.redirected_to_shadow_count,
            "bypassed_mock_count": self.bypassed_mock_count,
            "unmapped_leak_count": self.unmapped_leak_count,
            "shunting_safety_score_pct": round(self.shunting_safety_score_pct, 1),
            "decisions": [d.to_dict() for d in self.decisions],
            "created_at": self.created_at.isoformat(),
        }


# 全局默认分流规则仓库
_MQ_RULES: dict[str, ShadowMqRouteRule] = {
    "order_paid_events": ShadowMqRouteRule(
        "rule_01",
        "order_paid_events",
        "__shadow_order_paid_events__",
        "__shadow_order_dlq__",
        MqBypassAction.REDIRECT_SHADOW_CONSUMER,
    ),
    "user_sms_notification": ShadowMqRouteRule(
        "rule_02",
        "user_sms_notification",
        "__shadow_user_sms_notification__",
        "__shadow_sms_dlq__",
        MqBypassAction.DROP_SILENTLY,  # 影子短信静默丢弃，绝不发往真实手机
    ),
    "payment_recharge_callback": ShadowMqRouteRule(
        "rule_03",
        "payment_recharge_callback",
        "__shadow_payment_recharge_callback__",
        "__shadow_recharge_dlq__",
        MqBypassAction.MOCK_DISPATCH,  # 充值回调走 Mock 假入账
    ),
}

# 全局审计报告存储
_MQ_SHUNTING_REPORTS: dict[str, MqShuntingAuditReport] = {}


def clear_mq_shunting_store() -> None:
    """清空 MQ 规则与报告仓库 (单测专用)。"""
    _MQ_SHUNTING_REPORTS.clear()
    _MQ_RULES.clear()
    _MQ_RULES.update(
        {
            "order_paid_events": ShadowMqRouteRule(
                "rule_01",
                "order_paid_events",
                "__shadow_order_paid_events__",
                "__shadow_order_dlq__",
                MqBypassAction.REDIRECT_SHADOW_CONSUMER,
            ),
            "user_sms_notification": ShadowMqRouteRule(
                "rule_02",
                "user_sms_notification",
                "__shadow_user_sms_notification__",
                "__shadow_sms_dlq__",
                MqBypassAction.DROP_SILENTLY,
            ),
            "payment_recharge_callback": ShadowMqRouteRule(
                "rule_03",
                "payment_recharge_callback",
                "__shadow_payment_recharge_callback__",
                "__shadow_recharge_dlq__",
                MqBypassAction.MOCK_DISPATCH,
            ),
        }
    )


def register_mq_route_rule(
    production_topic: str,
    shadow_topic: str,
    dead_letter_queue: str,
    bypass_action: MqBypassAction = MqBypassAction.REDIRECT_SHADOW_CONSUMER,
) -> ShadowMqRouteRule:
    """注册或更新 MQ 影子分流规则。"""
    rule_id = f"rule_{uuid.uuid4().hex[:6]}"
    rule = ShadowMqRouteRule(
        rule_id=rule_id,
        production_topic=production_topic.strip(),
        shadow_topic=shadow_topic.strip(),
        dead_letter_queue=dead_letter_queue.strip(),
        bypass_action=bypass_action,
        is_active=True,
    )
    _MQ_RULES[production_topic.strip()] = rule
    return rule


def list_mq_route_rules() -> list[dict[str, Any]]:
    """获取所有已生效的 MQ 影子分流规则。"""
    return [r.to_dict() for r in _MQ_RULES.values()]


def route_mq_messages(
    cluster_name: str,
    messages: list[dict[str, Any]],
) -> MqShuntingAuditReport:
    """模拟消息中间件拦截器，对发布与消费的消息执行影子分流、死信隔离与旁路 Mock。"""
    decisions: list[MqRoutingDecision] = []
    shadow_count = 0
    redirect_count = 0
    bypassed_count = 0
    unmapped_leak = 0

    for m in messages:
        mid = str(m.get("message_id") or f"msg_{uuid.uuid4().hex[:6]}")
        topic = str(m.get("topic") or "default_topic").strip()
        headers = dict(m.get("headers") or {})

        # 判断是否带有影子染色标
        is_shadow = (
            headers.get("__atp_shadow_taint__") == "true"
            or headers.get("X-ATP-Shadow") == "true"
            or bool(m.get("is_shadow_traffic", False))
        )

        rule = _MQ_RULES.get(topic)

        if is_shadow:
            shadow_count += 1
            if rule and rule.is_active:
                routed = rule.shadow_topic
                redirect_count += 1
                bypass = rule.bypass_action
                if bypass in (MqBypassAction.DROP_SILENTLY, MqBypassAction.MOCK_DISPATCH):
                    bypassed_count += 1

                expl = f"已将影子消息安全分流至影子 Topic [{routed}]，执行策略: {bypass.value}。"
                decisions.append(
                    MqRoutingDecision(
                        message_id=mid,
                        original_topic=topic,
                        is_shadow=True,
                        routed_topic=routed,
                        is_redirected=True,
                        bypassed_action=bypass,
                        explanation=expl,
                    )
                )
            else:
                # 影子消息发送到未映射生产 Topic：高危泄漏隐患！
                unmapped_leak += 1
                expl = f"高危泄漏！影子消息投递至未配置影子 Topic 的生产队列 [{topic}]，可能诱发真实业务副效应！"
                decisions.append(
                    MqRoutingDecision(
                        message_id=mid,
                        original_topic=topic,
                        is_shadow=True,
                        routed_topic=topic,
                        is_redirected=False,
                        bypassed_action=None,
                        explanation=expl,
                    )
                )
        else:
            # 正常业务消息：投递至生产 Topic
            decisions.append(
                MqRoutingDecision(
                    message_id=mid,
                    original_topic=topic,
                    is_shadow=False,
                    routed_topic=topic,
                    is_redirected=False,
                    bypassed_action=None,
                    explanation="正常生产业务消息，安全直投生产队列。",
                )
            )

    total_m = max(1, len(messages))
    safety_score = 100.0 if unmapped_leak == 0 else max(0.0, 100.0 - (unmapped_leak / total_m) * 100.0)

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", cluster_name)[:16]
    report_id = f"mq_shunt_{safe_name}_{int(now.timestamp())}"

    report = MqShuntingAuditReport(
        report_id=report_id,
        cluster_name=cluster_name,
        total_messages_processed=len(messages),
        shadow_messages_count=shadow_count,
        redirected_to_shadow_count=redirect_count,
        bypassed_mock_count=bypassed_count,
        unmapped_leak_count=unmapped_leak,
        shunting_safety_score_pct=safety_score,
        decisions=decisions,
        created_at=now,
    )

    _MQ_SHUNTING_REPORTS[report_id] = report
    return report


def get_mq_shunting_report(report_id: str) -> MqShuntingAuditReport | None:
    """按 ID 查询 MQ 分流报告。"""
    return _MQ_SHUNTING_REPORTS.get(report_id)


def list_mq_shunting_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史 MQ 分流报告列表。"""
    reports = list(reversed(list(_MQ_SHUNTING_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
