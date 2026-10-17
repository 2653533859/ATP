"""全链路流量染色标规则配置与上下文透传器服务 (T1.1)

在全链路金丝雀灰度发布中负责流量染色标记识别、分流判定与跨微服务上下文透传:
1. 多维染色匹配规则定义 (HTTP Header, Cookie, 租户白名单, 用户ID取模, 纯随机权重分流);
2. 全链路染色上下文透传引擎 (自动装配 X-Canary-Traffic、X-Canary-Tag 与 W3C Baggage);
3. 染色匹配决策 (evaluate_traffic_coloration: 命中输出金丝雀标记，未命中回退基线稳定态);
4. 单例规则库管理与结构化结果输出 (CanaryTrafficContext & CanaryColorationRule)。
"""

from __future__ import annotations

import enum
import hashlib
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ColorationRuleType(str, enum.Enum):
    HTTP_HEADER = "HTTP_HEADER"  # 基于 HTTP 请求头精准或正则匹配 (如 X-Canary: true)
    COOKIE_PARAM = "COOKIE_PARAM"  # 基于客户端 Cookie 标记 (如 canary_beta=true)
    USER_MODULO = "USER_MODULO"  # 基于用户唯一标识 Hash 取模阶梯分流 (0~99 < threshold)
    TENANT_WHITELIST = "TENANT_WHITELIST"  # 指定内部租户/金丝雀账号白名单
    WEIGHT_RANDOM = "WEIGHT_RANDOM"  # 纯随机百分比概率分流 (1% ~ 50%)


RULE_TYPE_PRIORITY: Dict[ColorationRuleType, int] = {
    ColorationRuleType.TENANT_WHITELIST: 1,
    ColorationRuleType.HTTP_HEADER: 2,
    ColorationRuleType.COOKIE_PARAM: 3,
    ColorationRuleType.USER_MODULO: 4,
    ColorationRuleType.WEIGHT_RANDOM: 5,
}


@dataclass
class CanaryColorationRule:
    rule_id: str
    name: str
    rule_type: ColorationRuleType
    target_service: str
    canary_version_tag: str
    match_key: str = ""
    match_value: str = ""
    weight_pct: float = 10.0
    is_enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["rule_type"] = self.rule_type.value
        d["weight_pct"] = round(self.weight_pct, 1)
        return d


@dataclass
class CanaryTrafficContext:
    context_id: str
    is_canary: bool
    color_tag: str  # e.g. "v2.0.0-canary" or "baseline-v1"
    matched_rule_id: Optional[str]
    matched_by: Optional[ColorationRuleType]
    headers_to_propagate: Dict[str, str]
    baggage_items: Dict[str, str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_id": self.context_id,
            "is_canary": self.is_canary,
            "color_tag": self.color_tag,
            "matched_rule_id": self.matched_rule_id,
            "matched_by": self.matched_by.value if self.matched_by else None,
            "headers_to_propagate": self.headers_to_propagate,
            "baggage_items": self.baggage_items,
            "timestamp": self.timestamp,
        }


def hash_modulo_100(val: str) -> int:
    """对输入标识生成确定性的 0~99 哈希取模槽位"""
    digest = hashlib.md5(val.encode("utf-8")).hexdigest()
    return int(digest[:6], 16) % 100


class CanaryColorationManager:
    """全链路流量染色规则单例管理器"""

    def __init__(self):
        self.rules: Dict[str, CanaryColorationRule] = {}
        self._load_seed_rules()

    def _load_seed_rules(self) -> None:
        """加载初始种子染色规则"""
        r1 = CanaryColorationRule(
            rule_id="crule_header_01",
            name="灰度 Header 精准染色规则 (X-Canary: true)",
            rule_type=ColorationRuleType.HTTP_HEADER,
            target_service="payment-service",
            canary_version_tag="v2.1.0-canary",
            match_key="X-Canary",
            match_value="true",
            is_enabled=True,
        )
        r2 = CanaryColorationRule(
            rule_id="crule_weight_10pct",
            name="订单中台 10% 随机权重灰度规则",
            rule_type=ColorationRuleType.WEIGHT_RANDOM,
            target_service="order-service",
            canary_version_tag="v3.0.0-rc1",
            weight_pct=10.0,
            is_enabled=True,
        )
        self.rules[r1.rule_id] = r1
        self.rules[r2.rule_id] = r2

    def add_rule(self, rule: CanaryColorationRule) -> CanaryColorationRule:
        self.rules[rule.rule_id] = rule
        return rule

    def get_rule(self, rule_id: str) -> Optional[CanaryColorationRule]:
        return self.rules.get(rule_id)

    def list_rules(self, target_service: Optional[str] = None) -> List[CanaryColorationRule]:
        rules_list = list(self.rules.values())
        if target_service:
            rules_list = [r for r in rules_list if r.target_service == target_service]
        return rules_list

    def delete_rule(self, rule_id: str) -> bool:
        if rule_id in self.rules:
            del self.rules[rule_id]
            return True
        return False

    def clear(self) -> None:
        self.rules.clear()

    def evaluate_traffic_coloration(
        self,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        target_service: Optional[str] = None,
        random_roll: Optional[float] = None,
    ) -> CanaryTrafficContext:
        """核心染色判定引擎：依次比对启用的规则，输出透传上下文"""
        req_headers = {k.lower(): v for k, v in (headers or {}).items()}
        req_cookies = cookies or {}
        context_id = f"cctx_{uuid.uuid4().hex[:10]}"

        # 按照规则优先级排序比对 (白名单/Header/Cookie/取模 > 随机分流)
        applicable_rules = sorted(
            [
                r
                for r in self.rules.values()
                if r.is_enabled and (not target_service or r.target_service == target_service)
            ],
            key=lambda r: RULE_TYPE_PRIORITY.get(r.rule_type, 99),
        )

        for rule in applicable_rules:
            matched = False

            # 1. 检查 HTTP Header 匹配
            if rule.rule_type == ColorationRuleType.HTTP_HEADER:
                h_key = rule.match_key.lower()
                if h_key in req_headers:
                    if rule.match_value.strip() == "" or req_headers[h_key] == rule.match_value:
                        matched = True

            # 2. 检查 Cookie 匹配
            elif rule.rule_type == ColorationRuleType.COOKIE_PARAM:
                if rule.match_key in req_cookies:
                    if rule.match_value.strip() == "" or req_cookies[rule.match_key] == rule.match_value:
                        matched = True

            # 3. 检查租户白名单
            elif rule.rule_type == ColorationRuleType.TENANT_WHITELIST:
                if tenant_id and tenant_id == rule.match_value:
                    matched = True

            # 4. 检查用户 ID Hash 取模
            elif rule.rule_type == ColorationRuleType.USER_MODULO:
                if user_id:
                    slot = hash_modulo_100(user_id)
                    if slot < rule.weight_pct:
                        matched = True

            # 5. 纯随机权重分流
            elif rule.rule_type == ColorationRuleType.WEIGHT_RANDOM:
                roll = random_roll if random_roll is not None else (random.random() * 100.0)
                if roll <= rule.weight_pct:
                    matched = True

            if matched:
                # 组装金丝雀染色头与 Baggage 上下文
                propagate_headers = {
                    "X-Canary-Traffic": "true",
                    "X-Canary-Tag": rule.canary_version_tag,
                    "X-Canary-Rule": rule.rule_id,
                }
                baggage = {
                    "canary.enabled": "true",
                    "canary.version": rule.canary_version_tag,
                    "canary.service": rule.target_service,
                }
                return CanaryTrafficContext(
                    context_id=context_id,
                    is_canary=True,
                    color_tag=rule.canary_version_tag,
                    matched_rule_id=rule.rule_id,
                    matched_by=rule.rule_type,
                    headers_to_propagate=propagate_headers,
                    baggage_items=baggage,
                )

        # 未命中任何染色规则，正常回退基线稳定版本
        return CanaryTrafficContext(
            context_id=context_id,
            is_canary=False,
            color_tag="baseline",
            matched_rule_id=None,
            matched_by=None,
            headers_to_propagate={"X-Canary-Traffic": "false", "X-Canary-Tag": "baseline"},
            baggage_items={"canary.enabled": "false", "canary.version": "baseline"},
        )


_GLOBAL_CANARY_MANAGER = CanaryColorationManager()


def get_global_canary_manager() -> CanaryColorationManager:
    return _GLOBAL_CANARY_MANAGER
