# Q3.1 定时自动化性能基准打标与趋势偏移告警验收（2026-10-16）

## 概述与结论

Q3.1（定时自动化性能基准打标与趋势偏移告警）已完成全量代码演进与自动化质量验证：
1. **自动化性能基准晋升与打标引擎 (`evaluate_baseline_candidate`)**：
   - 支持自动化判定最新成功压测是否具备成为新性能基线（Baseline）的资格；
   - **首个基线规则**：测试尚未绑定基线时，首次成功的压测运行直接具备基准资格；
   - **基准超越晋升规则**：当新运行的吞吐量高于既有基线 5% 以上，且 P95 延迟与错误率不劣化时，自动打标为更优候选，并支持一键 `auto_promote` 晋升。
2. **多维性能趋势漂移与告警计算 (`calculate_baseline_drift_alert`)**：
   - 自动对比最新运行与基准线的核心指标偏离度：
     - **吞吐量下跌告警**：RPS 下跌超过 15% 自动触发 `critical` 严重漂移告警；
     - **P95 延迟恶化告警**：P95 延迟恶化超过 20% 自动触发 `warning`，超过 50% 触发 `critical`；
     - **错误率尖刺告警**：错误率绝对增量超过 2% 自动触发 `critical` 告警；
   - 输出详细的告警原因清单（`alert_reasons`）与是否应当发起外呼通知标志（`should_alert`）。
3. **项目级基线巡检与 REST API 统一扩展 (`performance.py`)**：
   - 实现了 `run_project_baseline_alignment_scan`：项目范围定时遍历全量压测用例，检测最新运行的漂移报告；
   - 开放专属评估端点：
     - `POST /api/v1/performance/runs/{run_id}/drift-alert`：计算单次运行相对于既有基准的漂移详情与告警；
     - `POST /api/v1/performance/tests/{test_id}/align-baseline`：评估并支持一键自动晋升优质基线。

---

## 质量门禁与验证

1. **专项自动化测试**：
   - `backend/tests/services/test_performance_baseline_alignment.py`：**6 passed in 0.57s**（覆盖容差范围内正常放行、RPS 严重下跌拦截、P95 恶化告警、错误率增长告警、基线候选晋升资格计算、项目级全量基线对齐扫描）；
   - `scripts/pytest-standalone-sweep.py`：**1 passed, 0 failed standalone**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 212 source files**。
