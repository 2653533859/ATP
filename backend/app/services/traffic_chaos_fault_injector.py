"""基于流量特征匹配的微服务故障注入编排执行器服务 (T4.1)。

负责在业务流量链路中精准施加应用层混沌故障注入：
1. 细粒度流量特征匹配 (Path 正则、HTTP 方法、Header 标签、Query/Body 字段、动态采样率)；
2. 四大故障动作模式：
   - LATENCY (指定延迟与随机抖动 Jitter)；
   - ERROR_RESPONSE (HTTP 500/502/503/504 错误应答)；
   - CORRUPTION (响应负载数据损坏与格式破坏)；
   - ABRUPT_DROP (异常连接断开与丢包)；
3. 演练触发熔断保护 (max_triggers_limit) 与全局运行状态监控。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import random
import re
import time
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class FaultType(str, Enum):
    LATENCY = "LATENCY"  # 网络慢调用延迟注入
    ERROR_RESPONSE = "ERROR_RESPONSE"  # HTTP/RPC 错误码注入 (500/502/503/504)
    CORRUPTION = "CORRUPTION"  # 数据载荷损坏破坏注入
    ABRUPT_DROP = "ABRUPT_DROP"  # 模拟网络丢包或连接中途重置断开


@dataclass
class TrafficMatchRule:
    endpoint_pattern: str | None = None  # 接口路径正则 (如 r"^/api/v1/orders.*")
    methods: list[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    header_match: dict[str, str] = field(default_factory=dict)  # 如 {"X-Canary": "beta"}
    param_match: dict[str, Any] = field(default_factory=dict)  # 如 {"user_id": 888}
    traffic_ratio: float = 1.0  # 故障注入概率 (0.0 ~ 1.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint_pattern": self.endpoint_pattern,
            "methods": self.methods,
            "header_match": self.header_match,
            "param_match": self.param_match,
            "traffic_ratio": self.traffic_ratio,
        }


@dataclass
class FaultInjectionRule:
    rule_id: str
    rule_name: str
    fault_type: FaultType
    match_criteria: TrafficMatchRule
    latency_ms: float = 0.0
    latency_jitter_max_ms: float = 0.0
    error_status_code: int = 500
    error_response_body: str = '{"code": 500, "error": "Chaos Fault Injected: Internal Error"}'
    corruption_mode: str = "TRUNCATE"  # TRUNCATE | GARBLE
    enabled: bool = True
    max_triggers_limit: int = 1000  # 保护上限：触发超过此次数自动禁用
    current_triggers_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "fault_type": self.fault_type.value,
            "match_criteria": self.match_criteria.to_dict(),
            "latency_ms": self.latency_ms,
            "latency_jitter_max_ms": self.latency_jitter_max_ms,
            "error_status_code": self.error_status_code,
            "error_response_body": self.error_response_body,
            "corruption_mode": self.corruption_mode,
            "enabled": self.enabled,
            "max_triggers_limit": self.max_triggers_limit,
            "current_triggers_count": self.current_triggers_count,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class FaultExecutionResult:
    intercept_id: str
    rule_id: str | None
    fault_triggered: bool
    fault_type: FaultType | None
    injected_latency_ms: float
    effective_status_code: int
    effective_response_body: str
    log_message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "intercept_id": self.intercept_id,
            "rule_id": self.rule_id,
            "fault_triggered": self.fault_triggered,
            "fault_type": self.fault_type.value if self.fault_type else None,
            "injected_latency_ms": round(self.injected_latency_ms, 2),
            "effective_status_code": self.effective_status_code,
            "effective_response_body": self.effective_response_body[:1024],
            "log_message": self.log_message,
        }


@dataclass
class ChaosExperimentSession:
    experiment_id: str
    name: str
    description: str
    rules: list[FaultInjectionRule]
    total_requests_intercepted: int = 0
    total_faults_injected: int = 0
    fault_breakdown: dict[str, int] = field(default_factory=dict)
    is_active: bool = True
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stopped_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "rules": [r.to_dict() for r in self.rules],
            "total_requests_intercepted": self.total_requests_intercepted,
            "total_faults_injected": self.total_faults_injected,
            "fault_breakdown": self.fault_breakdown,
            "is_active": self.is_active,
            "started_at": self.started_at.isoformat(),
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
        }


# 全局内存规则与演练仓库
_FAULT_RULES: dict[str, FaultInjectionRule] = {}
_CHAOS_SESSIONS: dict[str, ChaosExperimentSession] = {}


def _create_default_fault_rules() -> None:
    if _FAULT_RULES:
        return

    # 1. 默认延迟注入规则 (订单结算接口 800ms 慢调用)
    r1 = FaultInjectionRule(
        rule_id="fault_latency_checkout",
        rule_name="订单结算接口慢调用延迟注入 (800ms)",
        fault_type=FaultType.LATENCY,
        match_criteria=TrafficMatchRule(
            endpoint_pattern=r".*/orders/checkout.*",
            methods=["POST"],
            traffic_ratio=1.0,
        ),
        latency_ms=800.0,
        latency_jitter_max_ms=200.0,
    )

    # 2. 默认错误码注入 (支付服务 503 临时不可用)
    r2 = FaultInjectionRule(
        rule_id="fault_error_payment",
        rule_name="支付网关 503 Service Unavailable 故障注入",
        fault_type=FaultType.ERROR_RESPONSE,
        match_criteria=TrafficMatchRule(
            endpoint_pattern=r".*/pay.*",
            methods=["POST"],
            header_match={"X-Chaos-Test": "true"},
            traffic_ratio=1.0,
        ),
        error_status_code=503,
        error_response_body='{"code": 50301, "error": "Chaos Injected: Payment Gateway Overloaded"}',
    )

    _FAULT_RULES[r1.rule_id] = r1
    _FAULT_RULES[r2.rule_id] = r2


_create_default_fault_rules()


def create_or_update_fault_rule(
    rule_name: str,
    fault_type: str | FaultType,
    endpoint_pattern: str | None = None,
    methods: list[str] | None = None,
    header_match: dict[str, str] | None = None,
    param_match: dict[str, Any] | None = None,
    traffic_ratio: float = 1.0,
    latency_ms: float = 0.0,
    latency_jitter_max_ms: float = 0.0,
    error_status_code: int = 500,
    error_response_body: str = "",
    corruption_mode: str = "TRUNCATE",
    enabled: bool = True,
    max_triggers_limit: int = 1000,
    rule_id: str | None = None,
) -> FaultInjectionRule:
    """创建或更新混沌故障注入规则。"""
    try:
        f_type = FaultType(fault_type.upper()) if isinstance(fault_type, str) else fault_type
    except ValueError:
        f_type = FaultType.LATENCY

    r_id = rule_id or f"cflt_{uuid.uuid4().hex[:10]}"
    rule = FaultInjectionRule(
        rule_id=r_id,
        rule_name=rule_name.strip(),
        fault_type=f_type,
        match_criteria=TrafficMatchRule(
            endpoint_pattern=endpoint_pattern,
            methods=methods or ["GET", "POST", "PUT", "DELETE"],
            header_match=header_match or {},
            param_match=param_match or {},
            traffic_ratio=max(0.0, min(1.0, float(traffic_ratio))),
        ),
        latency_ms=max(0.0, float(latency_ms)),
        latency_jitter_max_ms=max(0.0, float(latency_jitter_max_ms)),
        error_status_code=int(error_status_code),
        error_response_body=error_response_body or '{"error": "Chaos Injected"}',
        corruption_mode=corruption_mode.upper(),
        enabled=enabled,
        max_triggers_limit=max_triggers_limit,
    )
    _FAULT_RULES[r_id] = rule
    logger.info("混沌故障注入规则已注册 [%s]: %s (模式: %s)", r_id, rule_name, f_type.value)
    return rule


def get_fault_rule(rule_id: str) -> FaultInjectionRule | None:
    """获取指定故障规则。"""
    return _FAULT_RULES.get(rule_id)


def list_fault_rules() -> list[FaultInjectionRule]:
    """查询当前已生效的故障注入规则列表。"""
    return list(_FAULT_RULES.values())


def delete_fault_rule(rule_id: str) -> bool:
    """删除故障规则。"""
    if rule_id in _FAULT_RULES:
        del _FAULT_RULES[rule_id]
        return True
    return False


def _matches_traffic(
    rule: FaultInjectionRule,
    method: str,
    path_or_endpoint: str,
    headers: dict[str, str],
    body_data: Any,
) -> bool:
    """检查单条请求流量是否精准命中故障注入匹配标准。"""
    if not rule.enabled:
        return False

    if rule.current_triggers_count >= rule.max_triggers_limit:
        return False

    mc = rule.match_criteria
    method_upper = method.upper()

    # 1. 方法过滤
    if mc.methods and method_upper not in [m.upper() for m in mc.methods]:
        return False

    # 2. 路径正则过滤
    if mc.endpoint_pattern:
        try:
            if not re.search(mc.endpoint_pattern, path_or_endpoint, re.IGNORECASE):
                return False
        except re.error:
            if mc.endpoint_pattern.lower() not in path_or_endpoint.lower():
                return False

    # 3. Header 标签匹配
    if mc.header_match:
        norm_headers = {k.lower(): str(v) for k, v in headers.items()}
        for hk, hv in mc.header_match.items():
            if hk.lower() not in norm_headers or norm_headers[hk.lower()] != str(hv):
                return False

    # 4. Param / Body 字段匹配
    if mc.param_match and isinstance(body_data, dict):
        for pk, pv in mc.param_match.items():
            if pk not in body_data or body_data[pk] != pv:
                return False

    # 5. 采样概率判定
    if mc.traffic_ratio < 1.0:
        if random.random() > mc.traffic_ratio:
            return False

    return True


def evaluate_and_inject_fault(
    method: str,
    path_or_endpoint: str,
    headers: dict[str, str] | None = None,
    request_body: str = "",
    default_status_code: int = 200,
    default_response_body: str = '{"code": 0, "status": "OK"}',
    execute_actual_delay: bool = False,
) -> FaultExecutionResult:
    """核心故障注入判定拦截管道：根据流量特征评估是否施加延迟、错误码、数据损坏或丢包。"""
    intercept_id = f"cin_{uuid.uuid4().hex[:10]}"
    req_headers = headers or {}

    # 尝试解析 request body
    parsed_body = None
    if request_body:
        try:
            parsed_body = json.loads(request_body) if isinstance(request_body, str) else request_body
        except Exception:
            pass

    # 寻找匹配的故障规则 (按优先级首个命中生效)
    matched_rule: FaultInjectionRule | None = None
    for r in _FAULT_RULES.values():
        if _matches_traffic(r, method, path_or_endpoint, req_headers, parsed_body):
            matched_rule = r
            break

    # 若未命中任何故障，原样放行正常响应
    if not matched_rule:
        return FaultExecutionResult(
            intercept_id=intercept_id,
            rule_id=None,
            fault_triggered=False,
            fault_type=None,
            injected_latency_ms=0.0,
            effective_status_code=default_status_code,
            effective_response_body=default_response_body,
            log_message=f"流量正常放行，未命中混沌故障规则: {method} {path_or_endpoint}",
        )

    # 命中故障规则，累加触发计数
    matched_rule.current_triggers_count += 1
    ft = matched_rule.fault_type
    injected_latency = 0.0
    effective_status = default_status_code
    effective_body = default_response_body
    log_msg = f"【混沌故障已注入】规则 [{matched_rule.rule_name}] 命中请求: {method} {path_or_endpoint}"

    # 1. LATENCY (网络延迟)
    if ft == FaultType.LATENCY:
        jitter = (
            random.uniform(0.0, matched_rule.latency_jitter_max_ms) if matched_rule.latency_jitter_max_ms > 0 else 0.0
        )
        injected_latency = matched_rule.latency_ms + jitter
        log_msg += f" -> 注入时延 {injected_latency:.1f}ms"
        if execute_actual_delay and injected_latency > 0:
            time.sleep(injected_latency / 1000.0)

    # 2. ERROR_RESPONSE (HTTP 错误码)
    elif ft == FaultType.ERROR_RESPONSE:
        effective_status = matched_rule.error_status_code
        effective_body = matched_rule.error_response_body
        log_msg += f" -> 注入 HTTP {effective_status} 异常响应"

    # 3. CORRUPTION (数据损坏)
    elif ft == FaultType.CORRUPTION:
        if matched_rule.corruption_mode == "TRUNCATE":
            half_len = max(2, len(default_response_body) // 2)
            effective_body = default_response_body[:half_len]  # 非法 JSON 截断
            log_msg += " -> 注入数据截断损坏 (TRUNCATE)"
        else:
            effective_body = default_response_body + "###CORRUPTED_GARBAGE_PAYLOAD###"
            log_msg += " -> 注入乱码数据损坏 (GARBLE)"

    # 4. ABRUPT_DROP (丢包 / 连接断开)
    elif ft == FaultType.ABRUPT_DROP:
        effective_status = 0  # 类似 TCP RST / Connection Dropped
        effective_body = ""
        log_msg += " -> 注入连接断开丢包 (ABRUPT_DROP)"

    # 更新全局会话统计 (若有活跃演练)
    for s in _CHAOS_SESSIONS.values():
        if s.is_active:
            s.total_requests_intercepted += 1
            s.total_faults_injected += 1
            s.fault_breakdown[ft.value] = s.fault_breakdown.get(ft.value, 0) + 1

    return FaultExecutionResult(
        intercept_id=intercept_id,
        rule_id=matched_rule.rule_id,
        fault_triggered=True,
        fault_type=ft,
        injected_latency_ms=injected_latency,
        effective_status_code=effective_status,
        effective_response_body=effective_body,
        log_message=log_msg,
    )


def start_chaos_session(
    name: str,
    description: str = "",
    rule_ids: list[str] | None = None,
) -> ChaosExperimentSession:
    """启动全局微服务流量混沌演练批次。"""
    exp_id = f"cexp_{uuid.uuid4().hex[:10]}"
    active_rules = []
    if rule_ids:
        for rid in rule_ids:
            if rid in _FAULT_RULES:
                active_rules.append(_FAULT_RULES[rid])
    else:
        active_rules = list(_FAULT_RULES.values())

    session = ChaosExperimentSession(
        experiment_id=exp_id,
        name=name.strip(),
        description=description,
        rules=active_rules,
        is_active=True,
    )
    _CHAOS_SESSIONS[exp_id] = session
    logger.info("混沌演练批次已启动 [%s]: %s (挂载 %d 条规则)", exp_id, name, len(active_rules))
    return session


def stop_chaos_session(experiment_id: str) -> ChaosExperimentSession | None:
    """停止指定的混沌演练批次。"""
    session = _CHAOS_SESSIONS.get(experiment_id)
    if session and session.is_active:
        session.is_active = False
        session.stopped_at = datetime.now(timezone.utc)
        logger.info("混沌演练批次已终止 [%s]", experiment_id)
    return session


def get_chaos_session(experiment_id: str) -> ChaosExperimentSession | None:
    """获取指定演练会话详情。"""
    return _CHAOS_SESSIONS.get(experiment_id)


def list_chaos_sessions() -> list[ChaosExperimentSession]:
    """查询演练会话列表。"""
    sessions = list(_CHAOS_SESSIONS.values())
    sessions.sort(key=lambda s: s.started_at, reverse=True)
    return sessions


def clear_fault_rules_and_sessions() -> int:
    """清空规则并恢复出厂默认规则。"""
    count = len(_FAULT_RULES)
    _FAULT_RULES.clear()
    _CHAOS_SESSIONS.clear()
    _create_default_fault_rules()
    return count
