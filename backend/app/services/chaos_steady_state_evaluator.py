"""分布式混沌实验编排与稳态探测引擎服务 (T1.2)

贯彻混沌工程核心原则，定义演练前基线稳态假说并在演练中实时探测系统弹性指标偏离:
1. 稳态假说模型 (SteadyStateHypothesis: 最小成功率、P99 延迟阈值、探针健康);
2. 实验生命周期状态机 (ChaosExperimentState: BASELINE_STABILIZING -> FAULT_INJECTING -> VERIFIED / VIOLATED);
3. 实时指标采样与稳态偏离探测器 (evaluate_steady_state & SteadyStateMetricSample);
4. 混沌实验会话管理器与历史观测流 (ChaosExperimentSession & ChaosExperimentManager)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class ChaosExperimentState(str, enum.Enum):
    CREATED = "CREATED"  # 已创建待执行
    BASELINE_STABILIZING = "BASELINE_STABILIZING"  # 基线稳态校准中
    FAULT_INJECTING = "FAULT_INJECTING"  # 故障注入进行中
    STEADY_STATE_VERIFIED = "STEADY_STATE_VERIFIED"  # 稳态假说成立 (系统具备高弹性)
    STEADY_STATE_VIOLATED = "STEADY_STATE_VIOLATED"  # 稳态假说被打破 (存在韧性弱点)
    STOPPED = "STOPPED"  # 实验已终止并恢复现场


@dataclass
class SteadyStateHypothesis:
    hypothesis_id: str
    target_service: str  # 目标服务 (如 orders-service 或 /api/v1/orders/*)
    min_success_rate_pct: float = 98.0  # 允许的最低成功率 (默认 >= 98.0%)
    max_p99_latency_ms: float = 400.0  # 允许的最高 P99 延迟 (默认 <= 400ms)
    max_error_rate_pct: float = 2.0  # 允许的最大错误率 (默认 <= 2.0%)
    require_probe_healthy: bool = True  # 要求健康探针始终 200

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SteadyStateMetricSample:
    sample_id: str
    total_requests: int
    success_requests: int
    failed_requests: int
    current_success_rate_pct: float
    current_p99_latency_ms: float
    is_probe_healthy: bool
    sampled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChaosExperimentSession:
    experiment_id: str
    name: str
    target_service: str
    active_fault_id: str
    hypothesis: SteadyStateHypothesis
    state: ChaosExperimentState
    baseline_metrics: Optional[SteadyStateMetricSample] = None
    metric_samples: List[SteadyStateMetricSample] = field(default_factory=list)
    violation_reasons: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "target_service": self.target_service,
            "active_fault_id": self.active_fault_id,
            "hypothesis": self.hypothesis.to_dict(),
            "state": self.state.value,
            "baseline_metrics": self.baseline_metrics.to_dict() if self.baseline_metrics else None,
            "metric_samples": [s.to_dict() for s in self.metric_samples[-30:]],
            "violation_reasons": self.violation_reasons,
            "created_at": self.created_at,
        }


def create_steady_state_sample(
    total_requests: int,
    failed_requests: int,
    p99_latency_ms: float,
    is_probe_healthy: bool = True,
) -> SteadyStateMetricSample:
    """创建指标采样点快照"""
    sample_id = f"samp_{uuid.uuid4().hex[:8]}"
    success_requests = max(0, total_requests - failed_requests)
    rate = (success_requests / total_requests * 100.0) if total_requests > 0 else 100.0

    return SteadyStateMetricSample(
        sample_id=sample_id,
        total_requests=total_requests,
        success_requests=success_requests,
        failed_requests=failed_requests,
        current_success_rate_pct=round(rate, 2),
        current_p99_latency_ms=round(p99_latency_ms, 2),
        is_probe_healthy=is_probe_healthy,
    )


def evaluate_steady_state(
    hypothesis: SteadyStateHypothesis,
    sample: SteadyStateMetricSample,
) -> Tuple[bool, List[str]]:
    """比对当前采样指标是否满足预期的稳态假说

    Returns:
        (is_steady: bool, violations: List[str])
    """
    violations: List[str] = []

    # 1. 检查成功率红线
    if sample.current_success_rate_pct < hypothesis.min_success_rate_pct:
        violations.append(
            f"成功率跌破稳态门限: 当前 {sample.current_success_rate_pct}% < 预期 {hypothesis.min_success_rate_pct}%"
        )

    # 2. 检查 P99 延迟红线
    if sample.current_p99_latency_ms > hypothesis.max_p99_latency_ms:
        violations.append(
            f"P99 延迟击穿稳态上限: 当前 {sample.current_p99_latency_ms}ms > 预期 {hypothesis.max_p99_latency_ms}ms"
        )

    # 3. 检查探针存活健康状态
    if hypothesis.require_probe_healthy and not sample.is_probe_healthy:
        violations.append("系统健康检查探针失联，发生节点不可用宕机")

    is_steady = len(violations) == 0
    return is_steady, violations


class ChaosExperimentManager:
    """混沌演练实验单例管理器"""

    def __init__(self):
        self.experiments: Dict[str, ChaosExperimentSession] = {}
        self._load_seed_experiments()

    def _load_seed_experiments(self) -> None:
        """加载系统预置的典型演练实验"""
        exp_id = "exp_pay_circuit_breaker"
        hypo = SteadyStateHypothesis(
            hypothesis_id="hypo_pay_01",
            target_service="payment-service",
            min_success_rate_pct=98.0,
            max_p99_latency_ms=450.0,
            require_probe_healthy=True,
        )
        base_sample = create_steady_state_sample(
            total_requests=1000,
            failed_requests=2,
            p99_latency_ms=120.0,
            is_probe_healthy=True,
        )

        session = ChaosExperimentSession(
            experiment_id=exp_id,
            name="收银台支付网关高延迟熔断演练",
            target_service="payment-service",
            active_fault_id="fault_pay_latency_500ms",
            hypothesis=hypo,
            state=ChaosExperimentState.STEADY_STATE_VERIFIED,
            baseline_metrics=base_sample,
            metric_samples=[base_sample],
        )
        self.experiments[exp_id] = session

    def create_experiment(
        self,
        name: str,
        target_service: str,
        fault_id: str,
        hypothesis: SteadyStateHypothesis,
    ) -> ChaosExperimentSession:
        """创建新的混沌实验会话"""
        exp_id = f"exp_{uuid.uuid4().hex[:10]}"
        session = ChaosExperimentSession(
            experiment_id=exp_id,
            name=name,
            target_service=target_service,
            active_fault_id=fault_id,
            hypothesis=hypothesis,
            state=ChaosExperimentState.CREATED,
        )
        self.experiments[exp_id] = session
        return session

    def record_and_evaluate(
        self,
        experiment_id: str,
        sample: SteadyStateMetricSample,
    ) -> Tuple[ChaosExperimentState, List[str]]:
        """向指定实验记录指标采样，并更新稳态评估结论"""
        session = self.experiments.get(experiment_id)
        if not session:
            return ChaosExperimentState.STOPPED, [f"未找到实验会话 [{experiment_id}]"]

        session.metric_samples.append(sample)
        is_steady, violations = evaluate_steady_state(session.hypothesis, sample)

        if not is_steady:
            session.state = ChaosExperimentState.STEADY_STATE_VIOLATED
            session.violation_reasons.extend(violations)
        else:
            if session.state in (ChaosExperimentState.FAULT_INJECTING, ChaosExperimentState.CREATED):
                session.state = ChaosExperimentState.STEADY_STATE_VERIFIED

        return session.state, violations

    def stop_experiment(self, experiment_id: str) -> Optional[ChaosExperimentSession]:
        session = self.experiments.get(experiment_id)
        if session:
            session.state = ChaosExperimentState.STOPPED
        return session

    def get_experiment(self, experiment_id: str) -> Optional[ChaosExperimentSession]:
        return self.experiments.get(experiment_id)

    def list_experiments(self) -> List[ChaosExperimentSession]:
        return list(self.experiments.values())

    def clear(self) -> None:
        self.experiments.clear()


_GLOBAL_CHAOS_MANAGER = ChaosExperimentManager()


def get_global_chaos_manager() -> ChaosExperimentManager:
    return _GLOBAL_CHAOS_MANAGER
