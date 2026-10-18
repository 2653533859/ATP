"""大模型推理延迟、Token 吞吐与成本效益推演器 (T2.3)

功能职责:
1. 毫秒级采集大模型首字延迟 (TTFT, Time To First Token) 与端到端耗时;
2. 推导持续生成速率 TPS (Tokens Per Second) 与并发吞吐特征;
3. 动态核算多模型 Prompt 输入与 Completion 生成 Token 计费成本;
4. 综合构建“单位美金吞吐性价比指数 (Cost-Efficiency Index)”;
5. 针对高频企业应用测算每日/每月开销推演 (Projection) 与性价比梯队评级。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


class EfficiencyTier(str, Enum):
    """性价比综合梯队评级"""

    ULTRA_HIGH_VALUE = "ULTRA_HIGH_VALUE"  # 极高性价比 (高吞吐 + 极致低价，如 DeepSeek V3 / Qwen 2.5 72B)
    HIGH_EFFICIENCY = "HIGH_EFFICIENCY"  # 优秀性价比 (均衡高吞吐与亲民计费，如 Llama 3.3 70B / GPT-4o-mini)
    BALANCED = "BALANCED"  # 性能平稳，适合特定工业场景
    PREMIUM_COSTLY = "PREMIUM_COSTLY"  # 昂贵旗舰型 (高精度但调用开销大，如 GPT-4o / Claude 3.5 Sonnet)


class ModelPricingSpec(BaseModel):
    """单模型官方/私有化 Token 计费规范 (按每百万 Token 美元计)"""

    model_name: str = Field(..., description="模型唯一代号")
    provider: str = Field(..., description="模型提供方或底座")
    input_cost_per_million_usd: float = Field(..., ge=0.0, description="输入 Prompt 计费 ($/1M tokens)")
    output_cost_per_million_usd: float = Field(..., ge=0.0, description="输出 Completion 计费 ($/1M tokens)")
    cache_hit_cost_per_million_usd: Optional[float] = Field(default=None, description="上下文缓存命中优惠计费")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "provider": self.provider,
            "input_cost_per_million_usd": self.input_cost_per_million_usd,
            "output_cost_per_million_usd": self.output_cost_per_million_usd,
            "cache_hit_cost_per_million_usd": self.cache_hit_cost_per_million_usd,
        }


# 2026 年行业主流大模型标准官方定价目录
MODEL_PRICING_CATALOG: Dict[str, ModelPricingSpec] = {
    "deepseek-v3": ModelPricingSpec(
        model_name="deepseek-v3",
        provider="DeepSeek",
        input_cost_per_million_usd=0.14,
        output_cost_per_million_usd=0.28,
        cache_hit_cost_per_million_usd=0.014,
    ),
    "deepseek-r1": ModelPricingSpec(
        model_name="deepseek-r1",
        provider="DeepSeek",
        input_cost_per_million_usd=0.55,
        output_cost_per_million_usd=2.19,
        cache_hit_cost_per_million_usd=0.14,
    ),
    "qwen-2.5-72b": ModelPricingSpec(
        model_name="qwen-2.5-72b",
        provider="Alibaba Cloud",
        input_cost_per_million_usd=0.40,
        output_cost_per_million_usd=1.20,
    ),
    "llama-3.3-70b": ModelPricingSpec(
        model_name="llama-3.3-70b",
        provider="Meta / Cloud Hub",
        input_cost_per_million_usd=0.35,
        output_cost_per_million_usd=0.90,
    ),
    "gpt-4o-mini": ModelPricingSpec(
        model_name="gpt-4o-mini",
        provider="OpenAI",
        input_cost_per_million_usd=0.15,
        output_cost_per_million_usd=0.60,
    ),
    "gpt-4o": ModelPricingSpec(
        model_name="gpt-4o",
        provider="OpenAI",
        input_cost_per_million_usd=2.50,
        output_cost_per_million_usd=10.00,
    ),
    "claude-3-5-sonnet": ModelPricingSpec(
        model_name="claude-3-5-sonnet",
        provider="Anthropic",
        input_cost_per_million_usd=3.00,
        output_cost_per_million_usd=15.00,
    ),
}


class SingleInferenceMetric(BaseModel):
    """单次模型请求推理性能与成本指标"""

    sample_id: str = Field(..., description="唯一样本标识")
    model_name: str = Field(..., description="模型名称")
    input_tokens: int = Field(..., ge=0, description="Prompt 输入 Token 数")
    output_tokens: int = Field(..., ge=0, description="Completion 生成 Token 数")
    total_tokens: int = Field(..., ge=0, description="单次交互总 Token 数")
    ttft_ms: float = Field(..., ge=0.0, description="首字响应延迟 TTFT (毫秒)")
    total_latency_ms: float = Field(..., ge=0.0, description="端到端总耗时 (毫秒)")
    tps: float = Field(..., ge=0.0, description="持续生成速率 (Tokens Per Second)")
    estimated_cost_usd: float = Field(..., ge=0.0, description="单次请求实际成本(美元)")
    cost_efficiency_index: float = Field(..., ge=0.0, description="单位美元产出 Token 数")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "model_name": self.model_name,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "ttft_ms": round(self.ttft_ms, 1),
            "total_latency_ms": round(self.total_latency_ms, 1),
            "tps": round(self.tps, 2),
            "estimated_cost_usd": round(self.estimated_cost_usd, 7),
            "cost_efficiency_index": round(self.cost_efficiency_index, 1),
        }


class ModelEconomicsSummary(BaseModel):
    """单模型多样本聚合经济学与性能指标总览"""

    model_name: str = Field(..., description="模型名称")
    provider: str = Field(..., description="提供方")
    sample_count: int = Field(..., ge=0, description="样本数量")
    p50_ttft_ms: float = Field(..., description="中位数首字延迟 (毫秒)")
    p95_ttft_ms: float = Field(..., description="P95 首字延迟 (毫秒)")
    p99_ttft_ms: float = Field(..., description="P99 首字延迟 (毫秒)")
    avg_tps: float = Field(..., description="平均生成速率 (TPS)")
    p95_tps: float = Field(..., description="P95 峰值生成速率 (TPS)")
    avg_input_tokens: float = Field(..., description="单请求平均输入 Token")
    avg_output_tokens: float = Field(..., description="单请求平均输出 Token")
    avg_cost_per_query_usd: float = Field(..., description="单次请求平均开销 (美元)")
    monthly_projection_usd_100k_qpd: float = Field(..., description="按日调用量 10 万次推演的月度成本 (美元)")
    efficiency_tier: EfficiencyTier = Field(..., description="性价比分档")
    recommendation_note: str = Field(..., description="模型工业选型推荐建议")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "provider": self.provider,
            "sample_count": self.sample_count,
            "p50_ttft_ms": round(self.p50_ttft_ms, 1),
            "p95_ttft_ms": round(self.p95_ttft_ms, 1),
            "p99_ttft_ms": round(self.p99_ttft_ms, 1),
            "avg_tps": round(self.avg_tps, 2),
            "p95_tps": round(self.p95_tps, 2),
            "avg_input_tokens": round(self.avg_input_tokens, 1),
            "avg_output_tokens": round(self.avg_output_tokens, 1),
            "avg_cost_per_query_usd": round(self.avg_cost_per_query_usd, 6),
            "monthly_projection_usd_100k_qpd": round(self.monthly_projection_usd_100k_qpd, 2),
            "efficiency_tier": self.efficiency_tier.value,
            "recommendation_note": self.recommendation_note,
        }


class EconomicsComparisonReport(BaseModel):
    """全模型成本与推理性能对比评估报告"""

    report_id: str = Field(..., description="报告唯一标识")
    generated_at: str = Field(..., description="生成时间")
    benchmarked_models_count: int = Field(..., description="对比模型总数")
    top_speed_model: str = Field(..., description="吞吐速率冠军模型")
    top_cost_saver_model: str = Field(..., description="最具成本优势模型")
    best_value_model: str = Field(..., description="综合性价比最高推荐模型")
    models: List[ModelEconomicsSummary] = Field(default_factory=list, description="各模型明细数据")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "benchmarked_models_count": self.benchmarked_models_count,
            "top_speed_model": self.top_speed_model,
            "top_cost_saver_model": self.top_cost_saver_model,
            "best_value_model": self.best_value_model,
            "models": [m.to_dict() for m in self.models],
        }


# ==================== 统计推演算法与纯 Python 分位数 ====================


def _calculate_percentile(values: List[float], p: float) -> float:
    """纯 Python 线性插值分位数推导算法 (P50, P95, P99)"""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_v) - 1)
    d = k - f
    return sorted_v[f] + (sorted_v[c] - sorted_v[f]) * d


def measure_single_inference(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    ttft_ms: float,
    total_latency_ms: float,
    custom_pricing: Optional[ModelPricingSpec] = None,
) -> SingleInferenceMetric:
    """采集单次大模型调用并推导生成速率与成本开销

    参数:
      model_name: 模型代号
      input_tokens: Prompt 输入 Token 数量
      output_tokens: Completion 输出 Token 数量
      ttft_ms: 首字延迟 (毫秒)
      total_latency_ms: 总交互时延 (毫秒)
      custom_pricing: 自定义计费规范(若为空则使用官方预置配置)
    """
    sample_id = f"inf_{uuid.uuid4().hex[:10]}"
    total_tokens = input_tokens + output_tokens

    # 计算持续生成速率 TPS = output_tokens / generation_duration_seconds
    gen_duration_sec = max(0.001, (total_latency_ms - ttft_ms) / 1000.0)
    tps = output_tokens / gen_duration_sec

    # 获取价格规格
    pricing = custom_pricing or MODEL_PRICING_CATALOG.get(
        model_name.lower(),
        ModelPricingSpec(
            model_name=model_name,
            provider="Custom/Private",
            input_cost_per_million_usd=0.50,
            output_cost_per_million_usd=1.50,
        ),
    )

    cost_in = (input_tokens / 1_000_000.0) * pricing.input_cost_per_million_usd
    cost_out = (output_tokens / 1_000_000.0) * pricing.output_cost_per_million_usd
    estimated_cost_usd = cost_in + cost_out

    # 性价比指数: 每消费 1 美元所产出的总 Token 数
    cost_efficiency_index = total_tokens / max(1e-9, estimated_cost_usd)

    return SingleInferenceMetric(
        sample_id=sample_id,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        ttft_ms=ttft_ms,
        total_latency_ms=total_latency_ms,
        tps=tps,
        estimated_cost_usd=estimated_cost_usd,
        cost_efficiency_index=cost_efficiency_index,
    )


def aggregate_model_economics(
    model_name: str,
    samples: List[SingleInferenceMetric],
    custom_pricing: Optional[ModelPricingSpec] = None,
) -> ModelEconomicsSummary:
    """聚合多条调用采样数据，推导 P50/P95/P99 TTFT、平均 TPS 与月度开销"""
    pricing = custom_pricing or MODEL_PRICING_CATALOG.get(
        model_name.lower(),
        ModelPricingSpec(
            model_name=model_name,
            provider="Generic Provider",
            input_cost_per_million_usd=0.50,
            output_cost_per_million_usd=1.50,
        ),
    )

    if not samples:
        return ModelEconomicsSummary(
            model_name=model_name,
            provider=pricing.provider,
            sample_count=0,
            p50_ttft_ms=0.0,
            p95_ttft_ms=0.0,
            p99_ttft_ms=0.0,
            avg_tps=0.0,
            p95_tps=0.0,
            avg_input_tokens=0.0,
            avg_output_tokens=0.0,
            avg_cost_per_query_usd=0.0,
            monthly_projection_usd_100k_qpd=0.0,
            efficiency_tier=EfficiencyTier.BALANCED,
            recommendation_note="暂无充足采样数据",
        )

    ttfts = [s.ttft_ms for s in samples]
    tpss = [s.tps for s in samples]
    costs = [s.estimated_cost_usd for s in samples]
    in_tokens = [s.input_tokens for s in samples]
    out_tokens = [s.output_tokens for s in samples]

    p50_ttft = _calculate_percentile(ttfts, 50.0)
    p95_ttft = _calculate_percentile(ttfts, 95.0)
    p99_ttft = _calculate_percentile(ttfts, 99.0)

    avg_tps = sum(tpss) / len(tpss)
    p95_tps = _calculate_percentile(tpss, 95.0)

    avg_in = sum(in_tokens) / len(in_tokens)
    avg_out = sum(out_tokens) / len(out_tokens)
    avg_cost = sum(costs) / len(costs)

    # 10 万次/天 x 30 天 = 3,000,000 次/月 开销推演
    monthly_projection = avg_cost * 100_000.0 * 30.0

    # 性价比分级判断
    # 规则:
    # 1. 均价极低且 TPS >= 60 -> ULTRA_HIGH_VALUE
    # 2. 均价较低或中等且 TPS >= 40 -> HIGH_EFFICIENCY
    # 3. 价格昂贵 (单次请求 > 0.003 美元) -> PREMIUM_COSTLY
    if avg_cost <= 0.0003 and avg_tps >= 50.0:
        tier = EfficiencyTier.ULTRA_HIGH_VALUE
        note = "极致性价比模型：吞吐强劲且成本极低，极力推荐用于高频企业在线问答与自动化流"
    elif avg_cost <= 0.0010 and avg_tps >= 35.0:
        tier = EfficiencyTier.HIGH_EFFICIENCY
        note = "高性价比模型：生成表现与成本控制极佳，适合中大型批量推理与智能体协同"
    elif avg_cost > 0.0025:
        tier = EfficiencyTier.PREMIUM_COSTLY
        note = "高精度旗舰模型：单次调用成本较高，建议仅用于关键核心复杂决策或低频专家兜底"
    else:
        tier = EfficiencyTier.BALANCED
        note = "均衡型模型：适合常规通用轻量级任务"

    return ModelEconomicsSummary(
        model_name=model_name,
        provider=pricing.provider,
        sample_count=len(samples),
        p50_ttft_ms=p50_ttft,
        p95_ttft_ms=p95_ttft,
        p99_ttft_ms=p99_ttft,
        avg_tps=avg_tps,
        p95_tps=p95_tps,
        avg_input_tokens=avg_in,
        avg_output_tokens=avg_out,
        avg_cost_per_query_usd=avg_cost,
        monthly_projection_usd_100k_qpd=monthly_projection,
        efficiency_tier=tier,
        recommendation_note=note,
    )


def compare_model_economics(summaries: List[ModelEconomicsSummary]) -> EconomicsComparisonReport:
    """全域对比多模型性价比报告，遴选速率冠军、成本之星与最佳推荐"""
    report_id = f"econ_rep_{uuid.uuid4().hex[:10]}"
    now_str = datetime.now(timezone.utc).isoformat()

    if not summaries:
        return EconomicsComparisonReport(
            report_id=report_id,
            generated_at=now_str,
            benchmarked_models_count=0,
            top_speed_model="N/A",
            top_cost_saver_model="N/A",
            best_value_model="N/A",
            models=[],
        )

    # 1. 吞吐速率最高
    top_speed = max(summaries, key=lambda m: m.avg_tps).model_name

    # 2. 单请求开销最低 (成本优势)
    top_cost_saver = min(summaries, key=lambda m: m.avg_cost_per_query_usd).model_name

    # 3. 综合性价比推荐 (优先在 ULTRA_HIGH_VALUE 或 HIGH_EFFICIENCY 中选 TPS 最高的)
    high_value_models = [
        m for m in summaries if m.efficiency_tier in (EfficiencyTier.ULTRA_HIGH_VALUE, EfficiencyTier.HIGH_EFFICIENCY)
    ]
    if high_value_models:
        best_value = max(high_value_models, key=lambda m: m.avg_tps).model_name
    else:
        best_value = top_cost_saver

    return EconomicsComparisonReport(
        report_id=report_id,
        generated_at=now_str,
        benchmarked_models_count=len(summaries),
        top_speed_model=top_speed,
        top_cost_saver_model=top_cost_saver,
        best_value_model=best_value,
        models=summaries,
    )
