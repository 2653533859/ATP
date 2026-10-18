"""大模型推理延迟、Token 吞吐与成本效益推演器单测 (T2.3)"""

from __future__ import annotations

import pytest

from app.services.llm_economics_benchmarker import (
    EfficiencyTier,
    ModelPricingSpec,
    _calculate_percentile,
    aggregate_model_economics,
    compare_model_economics,
    measure_single_inference,
)


def test_measure_single_inference_official_pricing():
    """测试采集单次推理并套用官方预置定价目录计算 TPS 与成本"""
    # 模拟 DeepSeek-V3 推理: 输入 500 Token, 生成 200 Token, 首字 200ms, 端到端 2200ms
    metric = measure_single_inference(
        model_name="deepseek-v3",
        input_tokens=500,
        output_tokens=200,
        ttft_ms=200.0,
        total_latency_ms=2200.0,
    )

    assert metric.model_name == "deepseek-v3"
    assert metric.input_tokens == 500
    assert metric.output_tokens == 200
    assert metric.total_tokens == 700
    assert metric.ttft_ms == 200.0
    assert metric.total_latency_ms == 2200.0

    # 持续生成时长 = (2200 - 200) / 1000 = 2.0s -> TPS = 200 / 2.0 = 100.0
    assert pytest.approx(metric.tps, 0.1) == 100.0

    # 成本 = (500 / 1M) * 0.14 + (200 / 1M) * 0.28 = 0.00007 + 0.000056 = 0.000126 美元
    assert pytest.approx(metric.estimated_cost_usd, rel=1e-3) == 0.000126

    # 性价比指数 = 700 / 0.000126 > 5,000,000
    assert metric.cost_efficiency_index > 5_000_000.0


def test_measure_single_inference_custom_pricing():
    """测试自定义企业私有化部署定价规格"""
    custom_price = ModelPricingSpec(
        model_name="my-custom-llm",
        provider="Internal GPU Cluster",
        input_cost_per_million_usd=0.10,
        output_cost_per_million_usd=0.20,
    )

    metric = measure_single_inference(
        model_name="my-custom-llm",
        input_tokens=1000,
        output_tokens=500,
        ttft_ms=150.0,
        total_latency_ms=1150.0,
        custom_pricing=custom_price,
    )

    # 持续生成 1.0s, 输出 500 Token -> TPS = 500.0
    assert pytest.approx(metric.tps, 0.1) == 500.0
    # 成本 = 1000 * 0.10 / 1M + 500 * 0.20 / 1M = 0.00010 + 0.00010 = 0.00020
    assert pytest.approx(metric.estimated_cost_usd, rel=1e-3) == 0.00020


def test_percentile_calculation():
    """测试纯 Python 分位数插值算法 (P50, P95, P99)"""
    latencies = [100.0, 200.0, 300.0, 400.0, 500.0]

    p50 = _calculate_percentile(latencies, 50.0)
    assert pytest.approx(p50, 0.1) == 300.0

    p90 = _calculate_percentile(latencies, 90.0)
    assert pytest.approx(p90, 0.1) == 460.0

    # 边界情况
    assert _calculate_percentile([], 95.0) == 0.0
    assert _calculate_percentile([42.0], 99.0) == 42.0


def test_aggregate_model_economics():
    """测试多样本聚合推导 P50/P95 TTFT、平均 TPS 与月度开销测算"""
    samples = []
    # 构造 10 次采样数据
    for i in range(10):
        samples.append(
            measure_single_inference(
                model_name="qwen-2.5-72b",
                input_tokens=400 + i * 20,
                output_tokens=150 + i * 10,
                ttft_ms=180.0 + i * 15.0,  # 180 ~ 315 ms
                total_latency_ms=2180.0 + i * 15.0,
            )
        )

    summary = aggregate_model_economics("qwen-2.5-72b", samples)

    assert summary.model_name == "qwen-2.5-72b"
    assert summary.sample_count == 10
    assert 180.0 <= summary.p50_ttft_ms <= 315.0
    assert summary.p95_ttft_ms >= summary.p50_ttft_ms
    assert summary.avg_tps > 50.0
    assert summary.avg_cost_per_query_usd > 0.0

    # 月度开销 = 单次均价 * 100,000 次/天 * 30 天
    expected_monthly = summary.avg_cost_per_query_usd * 3_000_000.0
    assert pytest.approx(summary.monthly_projection_usd_100k_qpd, rel=1e-3) == expected_monthly
    assert summary.efficiency_tier in (EfficiencyTier.ULTRA_HIGH_VALUE, EfficiencyTier.HIGH_EFFICIENCY)
    assert len(summary.recommendation_note) > 5


def test_aggregate_model_economics_empty():
    """测试空样本聚合边界"""
    summary = aggregate_model_economics("empty-model", [])
    assert summary.sample_count == 0
    assert summary.p50_ttft_ms == 0.0
    assert summary.avg_tps == 0.0
    assert summary.monthly_projection_usd_100k_qpd == 0.0


def test_compare_model_economics():
    """测试全模型经济学与吞吐性能横向对比"""
    # 1. 极速便宜的 DeepSeek-V3
    s1 = aggregate_model_economics(
        "deepseek-v3",
        [
            measure_single_inference("deepseek-v3", 500, 300, 150.0, 2150.0),  # TPS = 150
            measure_single_inference("deepseek-v3", 500, 300, 160.0, 2160.0),
        ],
    )

    # 2. 旗舰高价的 GPT-4o
    s2 = aggregate_model_economics(
        "gpt-4o",
        [
            measure_single_inference("gpt-4o", 500, 300, 350.0, 3350.0),  # TPS = 100
            measure_single_inference("gpt-4o", 500, 300, 400.0, 3400.0),
        ],
    )

    report = compare_model_economics([s1, s2])

    assert report.benchmarked_models_count == 2
    assert report.top_speed_model == "deepseek-v3"
    assert report.top_cost_saver_model == "deepseek-v3"
    assert report.best_value_model == "deepseek-v3"
    assert len(report.models) == 2

    # 边界情况：空列表
    empty_rep = compare_model_economics([])
    assert empty_rep.benchmarked_models_count == 0
    assert empty_rep.top_speed_model == "N/A"
