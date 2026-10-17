"""架构韧性弱点雷达分析与加固建议生成器服务 (T2.3)

聚合混沌故障注入、稳态破损采样与断路器 RTO 指标，计算五维韧性雷达模型并生成可落地的架构加固建议:
1. 五维系统韧性雷达模型 (Fault Isolation, Tripping Speed, Fallback, Recovery, Anti-Avalanche);
2. 架构弱点识别与分级推荐引擎 (HardeningActionType: 超时调优、退避重试、舱壁隔离、缓存兜底);
3. 综合韧性健康指数 (Composite Resilience Score, 0~100) 与评级;
4. 结构化雷达分析报告输出 (ArchitectureResilienceRadarReport)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.chaos_blast_radius_controller import BlastControllerVerdict
from app.services.resilience_rto_evaluator import ResilienceRTOEvaluation


class HardeningActionType(str, enum.Enum):
    CIRCUIT_BREAKER_TUNING = "CIRCUIT_BREAKER_TUNING"  # 断路器超时与错误率阈值调优
    EXPONENTIAL_BACKOFF_RETRY = "EXPONENTIAL_BACKOFF_RETRY"  # 引入指数退避加抖动重试机制
    BULKHEAD_ISOLATION = "BULKHEAD_ISOLATION"  # 舱壁隔离与独立线程池/连接池切分
    CACHE_FALLBACK_STRENGTHEN = "CACHE_FALLBACK_STRENGTHEN"  # 加强本地/Redis只读缓存兜底降级
    RATE_LIMITING_THROTTLE = "RATE_LIMITING_THROTTLE"  # 入口网关动态限流反压加固


@dataclass
class ResilienceDimensionScore:
    dimension_key: str
    dimension_name: str
    score: float  # 0.0 ~ 100.0
    grade: str  # EXCELLENT | GOOD | FAIR | POOR
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HardeningRecommendationItem:
    rec_id: str
    action_type: HardeningActionType
    priority: str  # P0_URGENT | P1_HIGH | P2_MEDIUM
    target_service: str
    title: str
    concrete_proposal: str
    expected_impact: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["action_type"] = self.action_type.value
        return d


@dataclass
class ArchitectureResilienceRadarReport:
    report_id: str
    experiment_id: str
    target_service: str
    composite_resilience_score: float  # 综合韧性分 (0.0 ~ 100.0)
    dimension_scores: Dict[str, float]  # 5 个维度分数映射
    radar_dimensions: List[ResilienceDimensionScore]
    identified_weaknesses_count: int
    recommendations: List[HardeningRecommendationItem]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "experiment_id": self.experiment_id,
            "target_service": self.target_service,
            "composite_resilience_score": round(self.composite_resilience_score, 1),
            "dimension_scores": {k: round(v, 1) for k, v in self.dimension_scores.items()},
            "radar_dimensions": [d.to_dict() for d in self.radar_dimensions],
            "identified_weaknesses_count": self.identified_weaknesses_count,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "generated_at": self.generated_at,
        }


def _get_dim_grade(score: float) -> str:
    if score >= 90.0:
        return "EXCELLENT"
    if score >= 75.0:
        return "GOOD"
    if score >= 60.0:
        return "FAIR"
    return "POOR"


def analyze_architecture_resilience_radar(
    rto_evaluation: ResilienceRTOEvaluation,
    blast_verdict: Optional[BlastControllerVerdict] = None,
    steady_violations: Optional[List[str]] = None,
) -> ArchitectureResilienceRadarReport:
    """综合计算五维韧性雷达模型并输出架构弱点加固策略"""
    report_id = f"rad_{uuid.uuid4().hex[:10]}"
    violations = steady_violations or []

    # 1. 维度一: 故障隔离性 (Fault Isolation)
    iso_score = 95.0
    if blast_verdict and blast_verdict.is_tripped:
        iso_score -= 30.0
        iso_expl = f"爆炸半径触碰安全红线 ({blast_verdict.action.value})，故障存在横向跨节点蔓延隐患"
    else:
        iso_expl = "故障严格限制在受试微服务节点，未发生无序横向扩散"

    # 2. 维度二: 熔断及时性 (Circuit Tripping Speed)
    trip_time = rto_evaluation.circuit_breaker_trip_time_ms
    if trip_time <= 300.0:
        trip_score = 98.0
        trip_expl = f"毫秒级极速熔断响应 ({trip_time}ms)，有效阻断级联雪崩"
    elif trip_time <= 1000.0:
        trip_score = 85.0
        trip_expl = f"断路器在 {trip_time}ms 内响应熔断，基本符合准入门槛"
    elif trip_time <= 3000.0:
        trip_score = 65.0
        trip_expl = f"断路器触发迟缓 ({trip_time}ms)，下游服务有较大超时积压"
    else:
        trip_score = 40.0
        trip_expl = "严重缺失有效断路器配置，故障注入期间超时严重失控"

    # 3. 维度三: 降级有效性 (Fallback Effectiveness)
    fallback_rate = rto_evaluation.fallback_takeover_rate_pct
    fb_score = max(0.0, min(100.0, fallback_rate))
    fb_expl = f"降级旁路接管率为 {fallback_rate}%"

    # 4. 维度四: 自愈收敛力 (Self-Healing Recovery)
    rto = rto_evaluation.recovery_time_objective_seconds
    if rto <= 3.0:
        rec_score = 96.0
        rec_expl = f"系统极速自愈恢复稳态 (RTO={rto}s)"
    elif rto <= 10.0:
        rec_score = 85.0
        rec_expl = f"系统在 {rto}s 内自愈恢复，处于预期指标内"
    elif rto <= 25.0:
        rec_score = 65.0
        rec_expl = f"自愈收敛耗时较长 ({rto}s)，存在缓存冷启动或连接池争用"
    else:
        rec_score = 40.0
        rec_expl = f"故障恢复严重超时 ({rto}s)，未能按期恢复稳态"

    # 5. 维度五: 雪崩抗脆弱度 (Anti-Avalanche Robustness)
    avalanche_score = 92.0
    if len(violations) > 0:
        penalty = min(50.0, len(violations) * 15.0)
        avalanche_score -= penalty
        av_expl = f"演练期间发生 {len(violations)} 次稳态击穿告警，抗雪崩抗性受损"
    else:
        av_expl = "演练期间未发生稳态假说违背，系统抗脆弱性坚固"

    dim_scores: Dict[str, float] = {
        "fault_isolation": iso_score,
        "circuit_tripping_speed": trip_score,
        "fallback_effectiveness": fb_score,
        "self_healing_recovery": rec_score,
        "anti_avalanche_robustness": avalanche_score,
    }

    radar_dimensions: List[ResilienceDimensionScore] = [
        ResilienceDimensionScore("fault_isolation", "故障隔离性", iso_score, _get_dim_grade(iso_score), iso_expl),
        ResilienceDimensionScore(
            "circuit_tripping_speed", "熔断及时性", trip_score, _get_dim_grade(trip_score), trip_expl
        ),
        ResilienceDimensionScore("fallback_effectiveness", "降级有效性", fb_score, _get_dim_grade(fb_score), fb_expl),
        ResilienceDimensionScore("self_healing_recovery", "自愈收敛力", rec_score, _get_dim_grade(rec_score), rec_expl),
        ResilienceDimensionScore(
            "anti_avalanche_robustness", "雪崩抗脆弱度", avalanche_score, _get_dim_grade(avalanche_score), av_expl
        ),
    ]

    composite_score = sum(dim_scores.values()) / len(dim_scores)

    # 依据弱点维度生成精准加固建议
    recommendations: List[HardeningRecommendationItem] = []
    target_svc = rto_evaluation.target_service

    if trip_score < 80.0:
        recommendations.append(
            HardeningRecommendationItem(
                rec_id=f"hrec_{uuid.uuid4().hex[:8]}",
                action_type=HardeningActionType.CIRCUIT_BREAKER_TUNING,
                priority="P0_URGENT",
                target_service=target_svc,
                title="调优断路器超时判定阈值与滑动窗口",
                concrete_proposal=f"建议在 [{target_svc}] 的客户端断路器配置中，将 failureRateThreshold 从默认 50% 下调至 30%，并将 slowCallDurationThreshold 缩减为 400ms。",
                expected_impact="将故障熔断触发时间缩减 60% 以上，防止下游线程池堆积。",
            )
        )

    if fb_score < 95.0:
        recommendations.append(
            HardeningRecommendationItem(
                rec_id=f"hrec_{uuid.uuid4().hex[:8]}",
                action_type=HardeningActionType.CACHE_FALLBACK_STRENGTHEN,
                priority="P1_HIGH",
                target_service=target_svc,
                title="增强只读缓存旁路降级保底能力",
                concrete_proposal=f"建议在 [{target_svc}] 接入本地双级缓存（Caffeine + Redis），当底层微服务报错时自动返回最近 5 分钟有效快照数据。",
                expected_impact="将故障期间降级接管率提升至 99.5% 以上，保障用户端体验无感。",
            )
        )

    if iso_score < 80.0:
        recommendations.append(
            HardeningRecommendationItem(
                rec_id=f"hrec_{uuid.uuid4().hex[:8]}",
                action_type=HardeningActionType.BULKHEAD_ISOLATION,
                priority="P1_HIGH",
                target_service=target_svc,
                title="引入舱壁隔离线程池与连接池物理切分",
                concrete_proposal=f"为 [{target_svc}] 分配独立的外部下游 RPC 连接池，设定 maxConcurrentCalls 限制为 30，避免耗尽共享 Web 容器线程。",
                expected_impact="彻底切断横向故障蔓延链路，爆炸半径收敛在 1 个服务以内。",
            )
        )

    if rec_score < 80.0:
        recommendations.append(
            HardeningRecommendationItem(
                rec_id=f"hrec_{uuid.uuid4().hex[:8]}",
                action_type=HardeningActionType.EXPONENTIAL_BACKOFF_RETRY,
                priority="P2_MEDIUM",
                target_service=target_svc,
                title="客户端重试引入指数退避加随机抖动算法",
                concrete_proposal=f"客户端重试策略由固定 1000ms 调整为 Full Jitter 指数退避 (base=200ms, max=2000ms)，避免自愈恢复期的惊群重试风暴。",
                expected_impact="平滑自愈收敛曲线，缩短 RTO 恢复耗时 50%。",
            )
        )

    return ArchitectureResilienceRadarReport(
        report_id=report_id,
        experiment_id=rto_evaluation.experiment_id,
        target_service=target_svc,
        composite_resilience_score=composite_score,
        dimension_scores=dim_scores,
        radar_dimensions=radar_dimensions,
        identified_weaknesses_count=len(recommendations),
        recommendations=recommendations,
    )
