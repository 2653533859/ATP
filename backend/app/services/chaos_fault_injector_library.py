"""网络损伤与故障注入算子库服务 (T1.1)

在分布式系统混沌工程与韧性攻防演练中提供标准化的微服务故障注入算子:
1. 网络延迟抖动 (NETWORK_LATENCY)、丢包 (PACKET_LOSS)、HTTP 状态码变异 (HTTP_STATUS_MUTATION) 与超时截断 (TIMEOUT_ABORT);
2. 细粒度故障注入规则模型与概率触发控制 (ChaosFaultConfig);
3. 确定性故障演练注入计算与注入结果包装 (apply_chaos_fault_injection & ChaosFaultApplicationResult);
4. 算子库规则管理器与默认故障场景预置 (ChaosFaultInjectorLibrary)。
"""

from __future__ import annotations

import enum
import fnmatch
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ChaosFaultType(str, enum.Enum):
    NETWORK_LATENCY = "NETWORK_LATENCY"  # 网络高延迟与抖动 (Latency & Jitter)
    PACKET_LOSS = "PACKET_LOSS"  # 网络丢包与强制连接重置 (Packet Loss)
    HTTP_STATUS_MUTATION = "HTTP_STATUS_MUTATION"  # HTTP 错误码变异 (500 / 502 / 504)
    TIMEOUT_ABORT = "TIMEOUT_ABORT"  # 请求超时熔断中断 (Gateway Timeout)
    PAYLOAD_CORRUPTION = "PAYLOAD_CORRUPTION"  # 响应体报文损坏或乱码注入


class ChaosFaultAction(str, enum.Enum):
    PASSTHROUGH = "PASSTHROUGH"  # 未触发故障，正常放行
    INJECTED_LATENCY = "INJECTED_LATENCY"  # 注入延迟
    INJECTED_STATUS = "INJECTED_STATUS"  # 变异状态码
    DROPPED = "DROPPED"  # 丢包丢弃
    TIMED_OUT = "TIMED_OUT"  # 超时熔断
    CORRUPTED = "CORRUPTED"  # 报文损坏


@dataclass
class ChaosFaultConfig:
    fault_id: str
    name: str
    fault_type: ChaosFaultType
    target_pattern: str  # URL 通配符模式 (如 */payment/* 或 */orders/*)
    latency_ms: float = 0.0  # 基准延迟 (毫秒)
    jitter_ms: float = 0.0  # 抖动范围 (毫秒)
    loss_percentage: float = 0.0  # 丢包率 (0.0 ~ 100.0)
    mutated_status_code: int = 500  # 变异状态码
    corrupted_payload: Optional[str] = None  # 损坏报文样本
    effective_probability: float = 1.0  # 触发概率 (0.0 ~ 1.0)
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["fault_type"] = self.fault_type.value
        return d


@dataclass
class ChaosFaultApplicationResult:
    is_fault_injected: bool
    applied_fault_type: Optional[ChaosFaultType]
    action: ChaosFaultAction
    added_latency_ms: float
    effective_status_code: int
    effective_response_body: Any
    is_dropped: bool
    message: str
    injected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_fault_injected": self.is_fault_injected,
            "applied_fault_type": self.applied_fault_type.value if self.applied_fault_type else None,
            "action": self.action.value,
            "added_latency_ms": round(self.added_latency_ms, 2),
            "effective_status_code": self.effective_status_code,
            "effective_response_body": self.effective_response_body,
            "is_dropped": self.is_dropped,
            "message": self.message,
            "injected_at": self.injected_at,
        }


class ChaosFaultInjectorLibrary:
    """混沌故障注入算子库管理器"""

    def __init__(self):
        self.rules: Dict[str, ChaosFaultConfig] = {}
        self._load_seed_faults()

    def _load_seed_faults(self) -> None:
        """预置典型分布式故障演练算子规则"""
        # 1. 支付网关 500ms 高延迟抖动
        self.register_rule(
            ChaosFaultConfig(
                fault_id="fault_pay_latency_500ms",
                name="支付服务 500ms 高延迟抖动",
                fault_type=ChaosFaultType.NETWORK_LATENCY,
                target_pattern="*/pay/*",
                latency_ms=500.0,
                jitter_ms=100.0,
                effective_probability=1.0,
                description="验证调用方下游是否有超时熔断保护",
            )
        )

        # 2. 外部短信 20% 网络丢包模拟
        self.register_rule(
            ChaosFaultConfig(
                fault_id="fault_sms_loss_20pct",
                name="短信服务 20% 丢包模拟",
                fault_type=ChaosFaultType.PACKET_LOSS,
                target_pattern="*/sms/*",
                loss_percentage=20.0,
                effective_probability=1.0,
                description="验证客户端自动重试退避与降级旁路机制",
            )
        )

        # 3. 库存扣减 500 Internal Error 注入
        self.register_rule(
            ChaosFaultConfig(
                fault_id="fault_stock_500_error",
                name="库存服务 500 内部服务故障注入",
                fault_type=ChaosFaultType.HTTP_STATUS_MUTATION,
                target_pattern="*/stock/*",
                mutated_status_code=500,
                effective_probability=1.0,
                description="验证订单创建对库存挂死的降级熔断能力",
            )
        )

    def register_rule(self, config: ChaosFaultConfig) -> None:
        self.rules[config.fault_id] = config

    def get_rule(self, fault_id: str) -> Optional[ChaosFaultConfig]:
        return self.rules.get(fault_id)

    def list_rules(self, fault_type: Optional[ChaosFaultType] = None) -> List[ChaosFaultConfig]:
        res = list(self.rules.values())
        if fault_type:
            res = [r for r in res if r.fault_type == fault_type]
        return res

    def clear(self) -> None:
        self.rules.clear()


_GLOBAL_FAULT_LIBRARY = ChaosFaultInjectorLibrary()


def get_global_fault_library() -> ChaosFaultInjectorLibrary:
    return _GLOBAL_FAULT_LIBRARY


def apply_chaos_fault_injection(
    path: str,
    original_status_code: int = 200,
    original_body: Any = None,
    active_fault: Optional[ChaosFaultConfig] = None,
    random_seed: Optional[float] = None,
) -> ChaosFaultApplicationResult:
    """计算单个请求在故障注入算子作用下的变异执行结果"""
    if not active_fault or not active_fault.enabled:
        return ChaosFaultApplicationResult(
            is_fault_injected=False,
            applied_fault_type=None,
            action=ChaosFaultAction.PASSTHROUGH,
            added_latency_ms=0.0,
            effective_status_code=original_status_code,
            effective_response_body=original_body,
            is_dropped=False,
            message="未启用故障注入或未指定规则，正常放行",
        )

    # 1. 检查目标 URL 模式匹配
    pattern = active_fault.target_pattern
    if not (fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.rstrip("/"), pattern.rstrip("/"))):
        return ChaosFaultApplicationResult(
            is_fault_injected=False,
            applied_fault_type=None,
            action=ChaosFaultAction.PASSTHROUGH,
            added_latency_ms=0.0,
            effective_status_code=original_status_code,
            effective_response_body=original_body,
            is_dropped=False,
            message=f"请求路径 '{path}' 未匹配故障目标 '{pattern}'",
        )

    # 2. 检查概率命中
    prob_roll = random_seed if random_seed is not None else random.random()
    if prob_roll > active_fault.effective_probability:
        return ChaosFaultApplicationResult(
            is_fault_injected=False,
            applied_fault_type=None,
            action=ChaosFaultAction.PASSTHROUGH,
            added_latency_ms=0.0,
            effective_status_code=original_status_code,
            effective_response_body=original_body,
            is_dropped=False,
            message="故障触发概率未命中，正常放行",
        )

    # 3. 根据故障类型执行变异演算
    ftype = active_fault.fault_type

    if ftype == ChaosFaultType.NETWORK_LATENCY:
        # 计算基准延迟 + 抖动
        jitter = (prob_roll - 0.5) * 2 * active_fault.jitter_ms
        total_latency = max(0.0, active_fault.latency_ms + jitter)
        return ChaosFaultApplicationResult(
            is_fault_injected=True,
            applied_fault_type=ftype,
            action=ChaosFaultAction.INJECTED_LATENCY,
            added_latency_ms=total_latency,
            effective_status_code=original_status_code,
            effective_response_body=original_body,
            is_dropped=False,
            message=f"已注入网络延迟: {round(total_latency, 1)}ms (基准: {active_fault.latency_ms}ms, 抖动: ±{active_fault.jitter_ms}ms)",
        )

    elif ftype == ChaosFaultType.PACKET_LOSS:
        loss_pct = active_fault.loss_percentage
        # 判定是否丢包
        is_loss = (prob_roll * 100) < loss_pct
        if is_loss:
            return ChaosFaultApplicationResult(
                is_fault_injected=True,
                applied_fault_type=ftype,
                action=ChaosFaultAction.DROPPED,
                added_latency_ms=0.0,
                effective_status_code=0,
                effective_response_body=None,
                is_dropped=True,
                message=f"网络丢包触发 (丢包率: {loss_pct}%)，强制中断连接",
            )
        else:
            return ChaosFaultApplicationResult(
                is_fault_injected=False,
                applied_fault_type=None,
                action=ChaosFaultAction.PASSTHROUGH,
                added_latency_ms=0.0,
                effective_status_code=original_status_code,
                effective_response_body=original_body,
                is_dropped=False,
                message="丢包抽样未命中，报文正常通过",
            )

    elif ftype == ChaosFaultType.HTTP_STATUS_MUTATION:
        mutated_code = active_fault.mutated_status_code
        err_body = {
            "error": "ChaosFaultInjected",
            "message": f"由混沌实验注入 HTTP {mutated_code} 服务故障",
            "status_code": mutated_code,
        }
        return ChaosFaultApplicationResult(
            is_fault_injected=True,
            applied_fault_type=ftype,
            action=ChaosFaultAction.INJECTED_STATUS,
            added_latency_ms=10.0,
            effective_status_code=mutated_code,
            effective_response_body=err_body,
            is_dropped=False,
            message=f"已将 HTTP 状态码由 {original_status_code} 变异篡改为 {mutated_code}",
        )

    elif ftype == ChaosFaultType.TIMEOUT_ABORT:
        return ChaosFaultApplicationResult(
            is_fault_injected=True,
            applied_fault_type=ftype,
            action=ChaosFaultAction.TIMED_OUT,
            added_latency_ms=3000.0,
            effective_status_code=504,
            effective_response_body={"error": "GatewayTimeout", "message": "混沌实验超时熔断"},
            is_dropped=False,
            message="触发服务端超时挂起熔断 (HTTP 504 Gateway Timeout)",
        )

    elif ftype == ChaosFaultType.PAYLOAD_CORRUPTION:
        corrupted = active_fault.corrupted_payload or "###CORRUPTED_RAW_BINARY_DATA###"
        return ChaosFaultApplicationResult(
            is_fault_injected=True,
            applied_fault_type=ftype,
            action=ChaosFaultAction.CORRUPTED,
            added_latency_ms=5.0,
            effective_status_code=original_status_code,
            effective_response_body=corrupted,
            is_dropped=False,
            message="已注入损坏的乱码报文载荷，验证反序列化容错",
        )

    return ChaosFaultApplicationResult(
        is_fault_injected=False,
        applied_fault_type=None,
        action=ChaosFaultAction.PASSTHROUGH,
        added_latency_ms=0.0,
        effective_status_code=original_status_code,
        effective_response_body=original_body,
        is_dropped=False,
        message="未命中支持的算子类型，正常放行",
    )
