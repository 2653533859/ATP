"""第三方服务防击穿与写操作拦截看门狗服务 (T4.1)

严防流量回放中对外部第三方支付、短信网关或核心写操作造成击穿破坏:
1. 外部高危域名 (微信支付/支付宝/Stripe/短信网关) 与敏感路径智能识别 (Blast Target Matcher);
2. 三大安全围栏防护模式: 强制阻断 (BLOCK)、安全 Mock 旁路 (MOCK_BYPASS)、纯只读演练 (DRY_RUN_READONLY);
3. 动态防击穿规则定义 (BlastProtectionRule);
4. 拦截决策引擎与防击穿遥测审计跟踪 (evaluate_and_guard_traffic_write & TrafficBlastGuardMetrics)。
"""

from __future__ import annotations

import enum
import fnmatch
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class BlastProtectionMode(str, enum.Enum):
    BLOCK = "BLOCK"  # 强制阻断外部调用并记录安全告警
    MOCK_BYPASS = "MOCK_BYPASS"  # 拦截外部网络请求，就地返回高保真安全 Mock 响应
    PASSED = "PASSED"  # 安全合规放行


class BlastRiskCategory(str, enum.Enum):
    PAYMENT_GATEWAY = "PAYMENT_GATEWAY"  # 外部第三方支付 / 扣费 (微信支付/支付宝/Stripe)
    SMS_NOTIFICATION = "SMS_NOTIFICATION"  # 外部短信 / 语音 / 邮件外呼网关 (防短信轰炸)
    EXTERNAL_WRITE_API = "EXTERNAL_WRITE_API"  # 外部第三方核心不可逆写入 (CRM/ERP/电子签)
    STRICT_READONLY = "STRICT_READONLY"  # 纯只读演练写操作阻断


# 内置高危敏感域名与路径模式黑名单
_DEFAULT_HIGH_RISK_TARGETS: List[Dict[str, Any]] = [
    {
        "category": BlastRiskCategory.PAYMENT_GATEWAY,
        "pattern": "*api.mch.weixin.qq.com*",
        "name": "微信商户支付网关",
        "mock": {"return_code": "SUCCESS", "result_code": "SUCCESS", "trade_state": "SUCCESS"},
    },
    {
        "category": BlastRiskCategory.PAYMENT_GATEWAY,
        "pattern": "*openapi.alipay.com*",
        "name": "支付宝开放平台网关",
        "mock": {"alipay_trade_pay_response": {"code": "10000", "msg": "Success"}},
    },
    {
        "category": BlastRiskCategory.PAYMENT_GATEWAY,
        "pattern": "*api.stripe.com*",
        "name": "Stripe 国际支付网关",
        "mock": {"id": "ch_mock_success", "status": "succeeded", "paid": True},
    },
    {
        "category": BlastRiskCategory.SMS_NOTIFICATION,
        "pattern": "*dysmsapi.aliyuncs.com*",
        "name": "阿里云短信推送网关",
        "mock": {"Code": "OK", "Message": "Mock Send Success"},
    },
    {
        "category": BlastRiskCategory.SMS_NOTIFICATION,
        "pattern": "*sms.tencentcloudapi.com*",
        "name": "腾讯云短信服务网关",
        "mock": {"Response": {"SendStatusSet": [{"Code": "Ok"}]}},
    },
]


@dataclass
class BlastProtectionRule:
    rule_id: str
    name: str
    category: BlastRiskCategory
    url_pattern: str  # URL 通配符或域名模式 (如 *pay.weixin.qq.com*)
    mode: BlastProtectionMode = BlastProtectionMode.BLOCK
    mock_response: Optional[Dict[str, Any]] = None
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["mode"] = self.mode.value
        return d


@dataclass
class BlastInterceptionLog:
    log_id: str
    rule_id: Optional[str]
    category: BlastRiskCategory
    mode: BlastProtectionMode
    method: str
    target_url: str
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["mode"] = self.mode.value
        return d


@dataclass
class TrafficBlastGuardMetrics:
    total_evaluated_count: int = 0
    blocked_count: int = 0
    mocked_count: int = 0
    passed_count: int = 0
    interception_logs: List[BlastInterceptionLog] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_evaluated_count": self.total_evaluated_count,
            "blocked_count": self.blocked_count,
            "mocked_count": self.mocked_count,
            "passed_count": self.passed_count,
            "recent_interceptions": [log.to_dict() for log in self.interception_logs[-20:]],
        }


class TrafficWriteBlastGuard:
    """防击穿安全看门狗状态机管理器"""

    def __init__(self):
        self.rules: List[BlastProtectionRule] = []
        self.metrics = TrafficBlastGuardMetrics()
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """加载开箱即用的高危支付与短信防护规则"""
        for idx, item in enumerate(_DEFAULT_HIGH_RISK_TARGETS):
            rid = f"rule_default_{idx + 1}"
            self.rules.append(
                BlastProtectionRule(
                    rule_id=rid,
                    name=item["name"],
                    category=item["category"],
                    url_pattern=item["pattern"],
                    mode=BlastProtectionMode.MOCK_BYPASS,
                    mock_response=item["mock"],
                    enabled=True,
                    description="系统内置第三方高危网关防击穿规则",
                )
            )

    def clear_metrics(self) -> None:
        """重置审计统计 (测试使用)"""
        self.metrics = TrafficBlastGuardMetrics()

    def add_rule(self, rule: BlastProtectionRule) -> None:
        self.rules.append(rule)

    def evaluate_traffic_target(
        self,
        method: str,
        url: str,
        path: Optional[str] = None,
        read_only_strictly: bool = False,
    ) -> Tuple[bool, BlastProtectionMode, Optional[Dict[str, Any]], str]:
        """评估回放目标请求是否需要拦截或 Mock 旁路

        Returns:
            (allowed: bool, action: BlastProtectionMode, mock_response: Optional[dict], reason: str)
        """
        self.metrics.total_evaluated_count += 1
        m_upper = method.upper()
        target = url or path or ""

        # 1. 严格只读模式检查 (对写操作一律阻断)
        if read_only_strictly and m_upper in ("POST", "PUT", "DELETE", "PATCH"):
            log_id = f"log_blast_{uuid.uuid4().hex[:8]}"
            log = BlastInterceptionLog(
                log_id=log_id,
                rule_id=None,
                category=BlastRiskCategory.STRICT_READONLY,
                mode=BlastProtectionMode.BLOCK,
                method=m_upper,
                target_url=target,
                reason=f"严格只读安全模式下阻断写操作 [{m_upper} {target}]",
            )
            self.metrics.blocked_count += 1
            self.metrics.interception_logs.append(log)
            return False, BlastProtectionMode.BLOCK, None, log.reason

        # 2. 匹配防击穿规则黑名单
        for r in self.rules:
            if not r.enabled:
                continue

            # 支持 url_pattern fnmatch 通配符与正则模式
            if fnmatch.fnmatch(target, r.url_pattern) or (re.search(r.url_pattern.replace("*", ".*"), target)):
                log_id = f"log_blast_{uuid.uuid4().hex[:8]}"
                if r.mode == BlastProtectionMode.BLOCK:
                    log = BlastInterceptionLog(
                        log_id=log_id,
                        rule_id=r.rule_id,
                        category=r.category,
                        mode=BlastProtectionMode.BLOCK,
                        method=m_upper,
                        target_url=target,
                        reason=f"命中防击穿强阻断规则 [{r.name}]: 严防外部写入与调用击穿",
                    )
                    self.metrics.blocked_count += 1
                    self.metrics.interception_logs.append(log)
                    return False, BlastProtectionMode.BLOCK, None, log.reason

                elif r.mode == BlastProtectionMode.MOCK_BYPASS:
                    log = BlastInterceptionLog(
                        log_id=log_id,
                        rule_id=r.rule_id,
                        category=r.category,
                        mode=BlastProtectionMode.MOCK_BYPASS,
                        method=m_upper,
                        target_url=target,
                        reason=f"命中防击穿规则 [{r.name}]: 安全旁路拦截，返回高保真模拟 Mock 响应",
                    )
                    self.metrics.mocked_count += 1
                    self.metrics.interception_logs.append(log)
                    return False, BlastProtectionMode.MOCK_BYPASS, r.mock_response or {}, log.reason

        # 3. 未命中任何黑名单，安全放行
        self.metrics.passed_count += 1
        return True, BlastProtectionMode.PASSED, None, "安全放行：目标为线下可信或幂等服务"


# 全局单例看门狗
_GLOBAL_BLAST_GUARD = TrafficWriteBlastGuard()


def get_global_blast_guard() -> TrafficWriteBlastGuard:
    return _GLOBAL_BLAST_GUARD


def evaluate_and_guard_traffic_write(
    method: str,
    url: str,
    path: Optional[str] = None,
    read_only_strictly: bool = False,
    guard: Optional[TrafficWriteBlastGuard] = None,
) -> Tuple[bool, BlastProtectionMode, Optional[Dict[str, Any]], str]:
    """快捷调用单例看门狗拦截判定"""
    g = guard or _GLOBAL_BLAST_GUARD
    return g.evaluate_traffic_target(
        method=method,
        url=url,
        path=path,
        read_only_strictly=read_only_strictly,
    )
