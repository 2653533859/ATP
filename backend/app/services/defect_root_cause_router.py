"""故障责任微服务与团队智能归因路由器服务 (T2.1)

结合调用链上下文与异常报错堆栈，自动定位故障责任微服务与代码负责人，避免缺陷击鼓传花:
1. 微服务根因责任定位算法 (Service Attribution: 业务调用帧、RPC下游报错链、中间件异常排查);
2. 领域服务权属团队与智能负责人路由 (Domain Team & Smart Assignee Routing);
3. 根因分类识别 (DefectRootCauseType: 下游崩溃、数据库死锁、业务断言失败、安全鉴权拒绝);
4. 归因置信度精算与证据链追溯 (AttributedResponsibility)。
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DefectRootCauseType(str, enum.Enum):
    DOWNSTREAM_SERVICE_CRASH = "DOWNSTREAM_SERVICE_CRASH"  # 下游微服务崩溃/宕机/502 Bad Gateway
    DATABASE_TIMEOUT_OR_DEADLOCK = "DATABASE_TIMEOUT_OR_DEADLOCK"  # 数据库连接池打满/死锁/超时
    BUSINESS_ASSERTION_FAILED = "BUSINESS_ASSERTION_FAILED"  # 业务代码逻辑计算或断言不符
    AUTH_TOKEN_EXPIRED_OR_FORBIDDEN = "AUTH_TOKEN_EXPIRED_OR_FORBIDDEN"  # 鉴权过期或越权访问阻断
    NETWORK_LATENCY_OR_PARTITION = "NETWORK_LATENCY_OR_PARTITION"  # 网络抖动与丢包超时


@dataclass
class AttributedResponsibility:
    attribution_id: str
    root_cause_type: DefectRootCauseType
    responsible_service: str
    responsible_team: str
    suggested_assignee: str
    suggested_assignee_name: str
    attribution_confidence_pct: float
    root_cause_summary: str
    evidence_chain: List[str]
    attributed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["root_cause_type"] = self.root_cause_type.value
        d["attribution_confidence_pct"] = round(self.attribution_confidence_pct, 1)
        return d


# 预置企业微服务领域所有权映射表 (Service -> Team & Lead)
DEFAULT_SERVICE_OWNERSHIP_MAP: Dict[str, Dict[str, str]] = {
    "payment-service": {
        "team": "资金结算与计费组 (Billing & Payment Team)",
        "assignee": "lead_payment@atp.io",
        "name": "李强 (支付架构师)",
    },
    "order-service": {
        "team": "订单与履约中台组 (Order & Fulfillment Team)",
        "assignee": "order_dev@atp.io",
        "name": "王建国 (订单负责人)",
    },
    "auth-service": {
        "team": "统一身份与安全中台组 (Infra & Security Team)",
        "assignee": "sec_lead@atp.io",
        "name": "张雪 (安全工程师)",
    },
    "inventory-service": {
        "team": "智能仓储与库存中心 (Inventory Team)",
        "assignee": "inv_lead@atp.io",
        "name": "赵敏 (库存研发)",
    },
    "api-gateway": {
        "team": "微服务基础设施网关组 (Gateway & Mesh Team)",
        "assignee": "mesh_lead@atp.io",
        "name": "孙伟 (网关架构师)",
    },
}


def _infer_service_from_stack_and_error(
    error_message: str,
    stack_trace: str,
    target_endpoint: Optional[str] = None,
    caller_service: Optional[str] = None,
) -> tuple[str, float, List[str]]:
    """依据报错信息与堆栈推断真正发生故障的微服务"""
    evidences: List[str] = []
    text = f"{error_message}\n{stack_trace}".lower()

    # 1. 检查是否存在下游明确报错
    service_match_rules = [
        ("payment-service", [r"payment", r"charge", r"refund", r"alipay", r"wechat_pay", r"wallet"]),
        ("auth-service", [r"token", r"jwt", r"credential", r"unauthorized", r"forbidden", r"oauth"]),
        ("order-service", [r"order", r"checkout", r"cart", r"trade", r"sub_order"]),
        ("inventory-service", [r"inventory", r"stock", r"sku", r"warehouse"]),
        ("api-gateway", [r"gateway", r"502 bad gateway", r"504 gateway timeout", r"route not found"]),
    ]

    for svc_name, patterns in service_match_rules:
        for p in patterns:
            if re.search(r"\b" + p + r"\b", text):
                evidences.append(f"报错上下文命中微服务 [{svc_name}] 特征关键字 [{p}]")
                return svc_name, 92.0, evidences

    # 2. 检查接口端点路径
    if target_endpoint:
        ep_lower = target_endpoint.lower()
        if "pay" in ep_lower:
            evidences.append(f"端点路由 [{target_endpoint}] 归属于支付中台")
            return "payment-service", 85.0, evidences
        if "auth" in ep_lower or "token" in ep_lower or "login" in ep_lower:
            evidences.append(f"端点路由 [{target_endpoint}] 归属于安全鉴权中台")
            return "auth-service", 85.0, evidences
        if "order" in ep_lower:
            evidences.append(f"端点路由 [{target_endpoint}] 归属于订单中心")
            return "order-service", 85.0, evidences

    # 3. 兜底回退至调用方服务
    fallback_svc = caller_service or "api-gateway"
    evidences.append(f"未检测到明确的下游调用痕迹，归因至初始入口服务 [{fallback_svc}]")
    return fallback_svc, 65.0, evidences


def _classify_root_cause_type(error_message: str, stack_trace: str) -> tuple[DefectRootCauseType, str]:
    """判定故障根因业务类型"""
    text = f"{error_message}\n{stack_trace}".lower()

    if re.search(r"(database|db|postgres|mysql|deadlock|pool exhausted|connection refused)", text):
        return (
            DefectRootCauseType.DATABASE_TIMEOUT_OR_DEADLOCK,
            "底层数据库连接池耗尽或发生并发死锁/慢查询超时",
        )
    if re.search(r"(unauthorized|forbidden|token expired|permission denied|signature mismatch)", text):
        return (
            DefectRootCauseType.AUTH_TOKEN_EXPIRED_OR_FORBIDDEN,
            "调用凭据缺失、JWT 签名失效或被鉴权拦截器阻断",
        )
    if re.search(r"(502|504|upstream timeout|connection reset|econnrefused|service unavailable)", text):
        return (
            DefectRootCauseType.DOWNSTREAM_SERVICE_CRASH,
            "下游微服务出现进程宕机、网络熔断不可达或网关超时",
        )
    if re.search(r"(timeout|packet loss|latency|timed out)", text):
        return (
            DefectRootCauseType.NETWORK_LATENCY_OR_PARTITION,
            "网络传输链路出现高延迟、丢包或网络分区阻断",
        )
    return (
        DefectRootCauseType.BUSINESS_ASSERTION_FAILED,
        "代码业务计算逻辑与预期断言结果不符",
    )


def attribute_defect_root_cause(
    error_message: str,
    stack_trace: str,
    target_endpoint: Optional[str] = None,
    caller_service: Optional[str] = None,
    custom_ownership_map: Optional[Dict[str, Dict[str, str]]] = None,
) -> AttributedResponsibility:
    """深度分析异常报错与堆栈，精准定位责任服务、归属团队与推荐处理人"""
    attribution_id = f"attr_{uuid.uuid4().hex[:10]}"
    ownership = {**DEFAULT_SERVICE_OWNERSHIP_MAP, **(custom_ownership_map or {})}

    # 1. 微服务责任推导
    inferred_svc, confidence, evidences = _infer_service_from_stack_and_error(
        error_message=error_message,
        stack_trace=stack_trace,
        target_endpoint=target_endpoint,
        caller_service=caller_service,
    )

    # 2. 根因分类判定
    rc_type, rc_summary = _classify_root_cause_type(error_message, stack_trace)
    evidences.append(f"根因类型判定为 [{rc_type.value}]：{rc_summary}")

    # 3. 责任团队与负责人匹配
    owner_info = ownership.get(
        inferred_svc,
        {
            "team": "通用研发组 (Core Engineering Team)",
            "assignee": "oncall_dev@atp.io",
            "name": "值班工程师 (On-Call)",
        },
    )
    team = owner_info["team"]
    assignee = owner_info["assignee"]
    assignee_name = owner_info["name"]

    evidences.append(f"依据领域权属规则自动指派至 [{team}] 的 [{assignee_name} <{assignee}>]")

    return AttributedResponsibility(
        attribution_id=attribution_id,
        root_cause_type=rc_type,
        responsible_service=inferred_svc,
        responsible_team=team,
        suggested_assignee=assignee,
        suggested_assignee_name=assignee_name,
        attribution_confidence_pct=confidence,
        root_cause_summary=rc_summary,
        evidence_chain=evidences,
    )
