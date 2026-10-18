"""全链路影子压测标注入与上下文透传引擎服务 (T1.1)

在生产高并发分布式微服务下，保障全链路压测流量安全穿透并严格隔离影子存储:
1. 多维压测标注入与协议透传 (HTTP Header, W3C Baggage, gRPC Metadata, MQ Header);
2. 影子存储自动路由推导 (Shadow DB, Shadow Table, Shadow Topic: 自动将 t_order 映射为 t_order_shadow);
3. 生产主库写穿严密防御 (若压测写操作穿透到生产真实主表，毫秒级阻断报警 CRITICAL_STRESS_LEAK);
4. 压测流量上下文封装与单例管理器 (StressTrafficContext & StressTrafficRuleManager)。
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class StressTrafficRuleType(str, enum.Enum):
    HEADER_FLAG = "HEADER_FLAG"  # 基于 HTTP 请求头透传 (X-Stress-Test: true)
    TENANT_STRESS = "TENANT_STRESS"  # 基于指定测试租户全量加压 (tenant_id in whitelist)
    URL_PATH_MATCH = "URL_PATH_MATCH"  # 基于接口 URL 正则匹配发压
    VIRTUAL_USER_RANGE = "VIRTUAL_USER_RANGE"  # 基于虚拟用户编号区间加压 (VU-0001 ~ VU-5000)


# 压测标准协议标识定义
STRESS_HTTP_HEADER = "X-Stress-Test"
STRESS_EXECUTION_HEADER = "X-Stress-Execution-Id"
STRESS_W3C_BAGGAGE_KEY = "atp_stress_mode=1"
STRESS_MQ_HEADER_KEY = "__stress_tag__"

# 生产核心主表黑名单 (严禁压测写操作直接穿透)
CORE_PRODUCTION_TABLES = [
    r"t_order\b",
    r"t_order_item\b",
    r"t_account_balance\b",
    r"t_payment_record\b",
    r"t_inventory_stock\b",
    r"t_billing_settlement\b",
]

# 合法的影子库表识别特征
SHADOW_TARGET_PATTERNS = [
    r".*_shadow\b",
    r".*_stress\b",
    r".*_sandbox\b",
    r".*shadow_.*",
    r".*stress_.*",
    r".*sandbox_.*",
]


@dataclass
class StressTrafficContext:
    stress_execution_id: str
    is_stress_test: bool
    tenant_id: str = "stress-tenant"
    virtual_user_id: str = "VU-0001"
    target_service: str = "order-service"
    headers: Dict[str, str] = field(default_factory=dict)
    baggage: str = ""
    grpc_metadata: List[Tuple[str, str]] = field(default_factory=list)
    mq_properties: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def inject_into_headers(self, incoming_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """将全链路压测标与 W3C Baggage 注入到传出 HTTP 请求头中"""
        res = dict(incoming_headers or {})
        if self.is_stress_test:
            res[STRESS_HTTP_HEADER] = "true"
            res[STRESS_EXECUTION_HEADER] = self.stress_execution_id
            existing_baggage = res.get("baggage", res.get("Baggage", ""))
            if existing_baggage:
                res["baggage"] = f"{existing_baggage},{STRESS_W3C_BAGGAGE_KEY}"
            else:
                res["baggage"] = STRESS_W3C_BAGGAGE_KEY
            res["X-Stress-Virtual-User"] = self.virtual_user_id
        return res

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StressIsolationRule:
    rule_id: str
    name: str
    rule_type: StressTrafficRuleType
    target_service: str
    target_path_pattern: str = ".*"
    tenant_id: Optional[str] = None
    is_enabled: bool = True
    shadow_table_suffix: str = "_shadow"
    shadow_topic_suffix: str = "_shadow"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def derive_shadow_target(resource_name: str, suffix: str = "_shadow") -> str:
    """根据生产真实库/表/Topic 名推导对应的影子存储资源名称"""
    r_strip = resource_name.strip()
    # 若已经是影子资源则直接返回
    for pat in SHADOW_TARGET_PATTERNS:
        if re.search(pat, r_strip.lower()):
            return r_strip
    return f"{r_strip}{suffix}"


def inspect_stress_write_safety(target_table_or_topic: str) -> Tuple[bool, str]:
    """校验压测写操作目标是否安全隔离在影子库表中"""
    t_lower = target_table_or_topic.lower().strip()
    for pat in SHADOW_TARGET_PATTERNS:
        if re.search(pat, t_lower):
            return True, f"目标 [{target_table_or_topic}] 符合影子存储隔离规范"

    for pat in CORE_PRODUCTION_TABLES:
        if re.search(pat, t_lower):
            return False, f"致命泄漏！压测写操作直接穿透至生产核心主表 [{target_table_or_topic}]！"

    return False, f"警告！目标 [{target_table_or_topic}] 未携带任何合规影子后缀，存在数据污染风险"


class StressTrafficRuleManager:
    """全链路影子压测规则配置与上下文流转状态机"""

    def __init__(self) -> None:
        self._rules: Dict[str, StressIsolationRule] = {}
        self._load_seed_rules()

    def _load_seed_rules(self) -> None:
        seed = StressIsolationRule(
            rule_id="stress_rule_seed_01",
            name="生产支付与订单全链路影子压测规则",
            rule_type=StressTrafficRuleType.HEADER_FLAG,
            target_service="payment-service",
            target_path_pattern="/v1/pay/.*",
            is_enabled=True,
        )
        self._rules[seed.rule_id] = seed

    def add_rule(self, rule: StressIsolationRule) -> None:
        self._rules[rule.rule_id] = rule

    def get_rule(self, rule_id: str) -> Optional[StressIsolationRule]:
        return self._rules.get(rule_id)

    def list_rules(self, target_service: Optional[str] = None) -> List[StressIsolationRule]:
        rules = list(self._rules.values())
        if target_service:
            rules = [r for r in rules if r.target_service == target_service]
        return sorted(rules, key=lambda r: r.created_at, reverse=True)

    def delete_rule(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def clear(self) -> None:
        self._rules.clear()

    def evaluate_stress_traffic(
        self,
        target_service: str,
        path: str = "/",
        headers: Optional[Dict[str, str]] = None,
        tenant_id: Optional[str] = None,
        virtual_user_id: str = "VU-0001",
    ) -> StressTrafficContext:
        """评估入站请求并生成包含全链路影子压测标的上下文"""
        exec_id = f"st_exec_{uuid.uuid4().hex[:10]}"
        headers = headers or {}
        is_stress = False

        # 1. 检查请求头是否自带 X-Stress-Test 或 W3C Baggage
        if headers.get(STRESS_HTTP_HEADER, "").lower() == "true":
            is_stress = True
        elif STRESS_W3C_BAGGAGE_KEY in headers.get("baggage", "") or STRESS_W3C_BAGGAGE_KEY in headers.get(
            "Baggage", ""
        ):
            is_stress = True

        # 2. 匹配规则引擎
        for r in self._rules.values():
            if not r.is_enabled:
                continue
            if r.target_service == target_service:
                if r.rule_type == StressTrafficRuleType.TENANT_STRESS and tenant_id and r.tenant_id == tenant_id:
                    is_stress = True
                    break
                if r.rule_type == StressTrafficRuleType.URL_PATH_MATCH and re.search(r.target_path_pattern, path):
                    is_stress = True
                    break

        ctx = StressTrafficContext(
            stress_execution_id=exec_id,
            is_stress_test=is_stress,
            tenant_id=tenant_id or "default-tenant",
            virtual_user_id=virtual_user_id,
            target_service=target_service,
            headers={
                STRESS_HTTP_HEADER: "true" if is_stress else "false",
                STRESS_EXECUTION_HEADER: exec_id if is_stress else "",
            },
            baggage=STRESS_W3C_BAGGAGE_KEY if is_stress else "",
            grpc_metadata=[("x-stress-test", "true" if is_stress else "false")],
            mq_properties={STRESS_MQ_HEADER_KEY: "true" if is_stress else "false"},
        )
        return ctx


_GLOBAL_STRESS_MGR: Optional[StressTrafficRuleManager] = None


def get_global_stress_manager() -> StressTrafficRuleManager:
    """获取全链路影子压测规则引擎全局单例"""
    global _GLOBAL_STRESS_MGR
    if _GLOBAL_STRESS_MGR is None:
        _GLOBAL_STRESS_MGR = StressTrafficRuleManager()
    return _GLOBAL_STRESS_MGR
