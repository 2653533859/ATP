# T1.2 分布式混沌实验编排与稳态探测引擎服务验收 (2026-10-17)

## 概述与交付物

T1.2（分布式混沌实验编排与稳态探测引擎服务）已全量研发交付并通过各项工程门禁，**达成 ATP v5.8.0 Phase 1 第二个核心稳态探测与实验编排里程碑**：
1. **稳态假说与多维健康探测引擎 (`backend/app/services/chaos_steady_state_evaluator.py`)**：
   - **稳态假说模型 (`SteadyStateHypothesis`)**：
     - 明确约束混沌故障注入期间系统的可用性底线（最低成功率门限 `min_success_rate_pct`、最高 P99 响应延迟 `max_p99_latency_ms`、最大允许错误率与探针存活要求）；
   - **混沌实验全生命周期状态机 (`ChaosExperimentState`)**：
     - 涵盖 `CREATED` ➔ `BASELINE_STABILIZING` ➔ `FAULT_INJECTING` ➔ `STEADY_STATE_VERIFIED`（稳态成立）/ `STEADY_STATE_VIOLATED`（稳态被打破）➔ `STOPPED`（终止恢复）；
   - **高频指标采样与偏离实时评估 (`evaluate_steady_state`)**：
     - 毫秒级核验采样点是否违背稳态假说，实时输出破损原因列表；
   - **实验单例管理器 (`ChaosExperimentManager`)**：
     - 提供实验创建、采样记录与稳态流式评估、终止恢复与列表检索。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_chaos_steady_state_evaluator.py`：3 passed（指标采样点快照计算、稳态合规/成功率跌破/延迟超标/探针宕机多维评估分支、实验全生命周期状态机跃迁与字典序列化）；
   - **通过率**：**3 passed in 0.33s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：2/2 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
