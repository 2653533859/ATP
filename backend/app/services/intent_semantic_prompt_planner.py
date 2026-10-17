"""测试领域意图语义规划与提示词编排器服务 (T1.2)

负责解析业务人员与测试工程师的自然语言测试需求,
抽取业务领域槽位、参与协议/终端与前后依赖序列,
并规划结构化 Prompt 上下文与推导规则。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class IntentSemanticSlots:
    raw_prompt: str
    business_domain: str  # ecommerce | fintech | social | general
    protocols: List[str]  # http | grpc | web | android | ios | sql
    actions: List[str]  # 抽取的核心动词动作
    extracted_entities: List[str]  # 抽取的实体 (order, token, payment, cart)
    suggested_node_count: int
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_prompt": self.raw_prompt,
            "business_domain": self.business_domain,
            "protocols": self.protocols,
            "actions": self.actions,
            "extracted_entities": self.extracted_entities,
            "suggested_node_count": self.suggested_node_count,
            "analyzed_at": self.analyzed_at,
        }


# 业务动词与协议关键词映射规则
_PROTOCOL_PATTERNS = {
    "http": [r"http", r"rest", r"api", r"接口", r"post", r"get", r"创建", r"查询"],
    "grpc": [r"grpc", r"rpc", r"微服务", r"内部调用", r"protobuf"],
    "web": [r"web", r"浏览器", r"网页", r"登录", r"前端页面", r"页面点击"],
    "android": [r"android", r"安卓", r"uiautomator", r"app端", r"apk"],
    "ios": [r"ios", r"iphone", r"苹果", r"wda", r"真机", r"手势"],
    "sql": [r"sql", r"数据库", r"db", r"postgres", r"mysql", r"对账", r"校验数据", r"落库"],
}

_DOMAIN_PATTERNS = {
    "ecommerce": [r"商品", r"订单", r"购物车", r"支付", r"下单", r"结算", r"库存", r"sku"],
    "fintech": [r"转账", r"还款", r"信贷", r"风控", r"余额", r"开户", r"利息", r"提现"],
    "social": [r"聊天", r"发帖", r"评论", r"点赞", r"消息", r"好友", r"关注"],
}


def plan_semantic_slots(prompt: str) -> IntentSemanticSlots:
    """从自然语言文本中提取业务槽位与协议矩阵"""
    p_lower = prompt.lower()

    # 1. 识别协议与平台
    detected_protocols: List[str] = []
    for proto, patterns in _PROTOCOL_PATTERNS.items():
        if any(re.search(pat, p_lower) for pat in patterns):
            detected_protocols.append(proto)
    if not detected_protocols:
        detected_protocols = ["http", "web"]

    # 2. 识别领域
    detected_domain = "general"
    for domain, patterns in _DOMAIN_PATTERNS.items():
        if any(re.search(pat, p_lower) for pat in patterns):
            detected_domain = domain
            break

    # 3. 抽取动作序列 (按逗号、分号、句号、连词分割)
    raw_segments = re.split(r"[,;，。然后接着最后首先再并且以及]", prompt)
    actions = [s.strip() for s in raw_segments if len(s.strip()) >= 2]
    if not actions:
        actions = ["创建前置数据", "执行业务操作", "核验数据状态"]

    # 4. 抽取关键实体
    entities = []
    entity_keywords = [
        "order",
        "token",
        "payment",
        "user",
        "goods",
        "cart",
        "db",
        "订单",
        "用户",
        "商品",
        "支付",
        "库存",
    ]
    for kw in entity_keywords:
        if kw in p_lower:
            entities.append(kw)
    if not entities:
        entities = ["data_record"]

    return IntentSemanticSlots(
        raw_prompt=prompt,
        business_domain=detected_domain,
        protocols=detected_protocols,
        actions=actions,
        extracted_entities=entities,
        suggested_node_count=max(2, min(8, len(actions))),
    )
