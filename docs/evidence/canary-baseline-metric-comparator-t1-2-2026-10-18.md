# T1.2 金丝雀与基线双轨指标实时对比推演器服务验收 (2026-10-18)

## 概述与交付物

T1.2（金丝雀与基线双轨指标实时对比推演器服务）已全量研发交付并通过各项工程门禁，**达成 ATP v6.1.0 Phase 1 第二个核心双轨指标推演计算引擎交付**：
1. **双轨指标采样采集模型 (`TrackMetricsSample`)**：
   - 细粒度聚合基线（Baseline）与金丝雀（Canary）版本的实时错误率（%）、业务成功率（%）、P99 延迟（ms）、平均时延（ms）与 CPU/内存使用率；
2. **科学相对偏离度精算算法 (`compare_canary_and_baseline_tracks`)**：
   - `error_rate_diff_pct`：金丝雀相对基线的绝对错误率差值（排除集群全局外部网络环境干扰）；
   - `latency_p99_ratio`：金丝雀 P99 响应相对基线的时延倍率（`> 1.0` 代表性能劣化）；
   - `cpu_diff_pct`：算力资源占用相对偏离；
3. **指标健康度三态智能裁决 (`MetricDeviationVerdict`)**：
   - `CONFORMANT`（合规平稳，各项指标偏离均在安全容差内）；
   - `WARNING_DEGRADED`（轻度偏离退化，错误率差值在 0.5%~1.5% 或延迟在 1.1x~1.25x 之间，触发黄色告警预警）；
   - `BREACHED_DEFICIT`（严重击穿超标，错误率差值 > 1.5% 或延迟 > 1.25x，为后续触发自动熔断回滚提供确凿依据）；
4. **输出结构化推演报告 (`CanaryDualTrackComparisonReport`)**：
   - 包含双轨完整指标对比、综合结论及按项诊断依据（`findings`）。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_canary_baseline_metric_comparator.py`：4 passed（指标平稳合规评定、轻度偏离预警评定、错误率突增严重击穿评定、延迟飙升严重击穿评定及字典序列化）；
   - **通过率**：**4 passed in 0.32s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：2/2 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
