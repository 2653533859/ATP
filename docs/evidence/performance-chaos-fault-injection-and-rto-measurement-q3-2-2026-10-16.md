# Q3.2 压力下故障注入与混沌恢复时长测定验收（2026-10-16）

## 概述与结论

Q3.2（压力下故障注入与混沌恢复时长测定）已完成全量代码演进与自动化质量验证：
1. **压测混沌故障注入计划模型 (`build_chaos_injection_plan`)**：
   - 支持在性能压测过程中动态编排 4 类主流混沌故障注入：
     - `service_unavailable`（模拟下游依赖 HTTP 503/502 服务不可用或宕机）；
     - `latency_spike`（模拟下游服务响应剧烈突增与线程池排队饱和）；
     - `packet_loss`（模拟网络传输丢包与重传恶化）；
     - `connection_reset`（模拟网络连接异常中断与重连雪崩）；
   - 严格校验故障开始延迟秒数、持续时长与参数合法性，生成可追溯的实验计划 ID 与状态。
2. **高精度服务自愈恢复时长（RTO）与韧性测定算法 (`calculate_chaos_rto`)**：
   - **基线与跌幅量化**：自动切分故障前（Baseline）、故障中（In-Fault）与故障后（Post-Fault）三段时序，精准核算 RPS 最大下跌幅度（`rps_drop_pct`）、P95 延迟恶化峰值与错误率跳变；
   - **自愈门槛对齐**：支持配置恢复容差比例（如 RPS 需恢复至基线 85% 以上、错误率增加不超过 3%、P95 延迟不超过 1.3 倍基线）；
   - **持续健康滑动窗口校验（Anti-Jitter Window）**：要求系统必须在故障解除后连续维持至少 `sustain_seconds` 秒的健康状态，彻底过滤指标偶发假自愈毛刺；
   - **自愈分级与建议（Resilience Grading）**：
     - RTO ≤ 3s：**Grade A（秒级极速自愈，断路器运行优良）**；
     - RTO 3-10s：**Grade B（良好自愈能力）**；
     - RTO 10-25s：**Grade C（恢复存在延迟，提示排队与超时回退优化）**；
     - RTO > 25s 或未恢复：**Grade D / F（严重迟缓或未自愈）**。
3. **REST API 统一管理端点 (`api/v1/performance.py`)**：
   - `POST /api/v1/performance/runs/{run_id}/chaos-plan`：为压测运行编排混沌故障注入任务；
   - `POST /api/v1/performance/runs/{run_id}/chaos-rto/evaluate`：基于时序采样数据实时核算 RTO 秒数、韧性得分与改善建议。

---

## 质量门禁与验证

1. **专项自动化测试**：
   - `backend/tests/services/test_performance_chaos_rto.py`：**6 passed in 0.28s**（覆盖参数校验拦截、秒级自愈 Grade A 评定、逐步恢复 Grade B 评定、未恢复 Grade F 判定、持续滑动窗口抗抖动过滤、时序边界与异常情况）；
   - `scripts/pytest-standalone-sweep.py`：**1 passed, 0 failed standalone**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 213 source files**。
