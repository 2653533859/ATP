"""系统容量拐点智能推演与吞吐天花板挖掘器单测 (T2.1)"""

from __future__ import annotations

from app.services.capacity_knee_point_deductor import (
    CapacityTestSample,
    deduct_capacity_knee_point,
    fit_usl_parameters,
    predict_usl_throughput,
)


def test_predict_usl_throughput_basics():
    # 1. 0 并发为 0
    assert predict_usl_throughput(0, gamma=20.0, sigma=0.02, kappa=0.0001) == 0.0

    # 2. 单并发 (N=1) 理论吞吐应完全等于 gamma
    tps_1 = predict_usl_throughput(1, gamma=25.0, sigma=0.05, kappa=0.0002)
    assert abs(tps_1 - 25.0) < 1e-4

    # 3. 随并发提升先升后降或饱和
    tps_10 = predict_usl_throughput(10, gamma=25.0, sigma=0.05, kappa=0.0002)
    tps_50 = predict_usl_throughput(50, gamma=25.0, sigma=0.05, kappa=0.0002)
    assert tps_50 > tps_10 > tps_1


def test_fit_usl_parameters_synthetic():
    # 模拟真实微服务压测梯度采样 (100 ~ 4000 VU)
    samples = [
        CapacityTestSample(concurrency_vu=50, measured_tps=950.0, measured_p99_latency_ms=25.0),
        CapacityTestSample(concurrency_vu=100, measured_tps=1800.0, measured_p99_latency_ms=32.0),
        CapacityTestSample(concurrency_vu=200, measured_tps=3200.0, measured_p99_latency_ms=45.0),
        CapacityTestSample(concurrency_vu=500, measured_tps=6500.0, measured_p99_latency_ms=68.0),
        CapacityTestSample(concurrency_vu=1000, measured_tps=9800.0, measured_p99_latency_ms=110.0),
        CapacityTestSample(concurrency_vu=2000, measured_tps=13200.0, measured_p99_latency_ms=185.0),
        CapacityTestSample(concurrency_vu=3000, measured_tps=14500.0, measured_p99_latency_ms=290.0),
        CapacityTestSample(concurrency_vu=4000, measured_tps=13800.0, measured_p99_latency_ms=450.0),  # 出现倒挂
    ]

    gamma, sigma, kappa, r2 = fit_usl_parameters(samples)

    assert gamma > 5.0
    assert 0.001 <= sigma <= 0.5
    assert kappa >= 0.0
    assert r2 > 0.85  # 拟合度优良


def test_fit_usl_parameters_fallback_on_insufficient_samples():
    samples_few = [
        CapacityTestSample(concurrency_vu=100, measured_tps=1500.0, measured_p99_latency_ms=30.0),
    ]
    gamma, sigma, kappa, r2 = fit_usl_parameters(samples_few)
    assert gamma > 0
    assert sigma > 0
    assert kappa >= 0
    assert r2 >= 0.90


def test_deduct_capacity_knee_point_full():
    samples = [
        CapacityTestSample(concurrency_vu=100, measured_tps=1900.0, measured_p99_latency_ms=28.0),
        CapacityTestSample(concurrency_vu=300, measured_tps=4800.0, measured_p99_latency_ms=42.0),
        CapacityTestSample(concurrency_vu=600, measured_tps=8200.0, measured_p99_latency_ms=75.0),
        CapacityTestSample(concurrency_vu=1200, measured_tps=12400.0, measured_p99_latency_ms=130.0),
        CapacityTestSample(concurrency_vu=2000, measured_tps=14800.0, measured_p99_latency_ms=210.0),
        CapacityTestSample(concurrency_vu=3000, measured_tps=15200.0, measured_p99_latency_ms=340.0),
    ]

    report = deduct_capacity_knee_point(samples, target_service="order-service")

    assert report.target_service == "order-service"
    assert report.samples_count == 6
    assert report.knee_point_vu > 0
    assert report.saturation_vu >= report.knee_point_vu
    assert report.recommended_safe_concurrency <= report.knee_point_vu
    assert report.peak_tps_ceiling >= report.knee_point_tps
    assert "USL 模型" in report.deduction_summary

    d = report.to_dict()
    assert d["target_service"] == "order-service"
    assert "knee_point_vu" in d
    assert "saturation_vu" in d
    assert "recommended_safe_concurrency" in d
    assert d["r_squared_fit"] >= 0.8
