# T2.3 动态反压与队列吞吐自适应均衡器服务验收 (2026-10-17)

## 概述与交付物

T2.3（动态反压与队列吞吐自适应均衡器服务）已全量研发交付并通过各项质量门禁，**标志着 ATP v5.4.0 Phase 2（任务节点热漂移与无感自愈重平衡）全量大闭环**：
1. **AIMD 自适应并发窗口流控算法 (`backend/app/services/dynamic_backpressure_balancer.py`)**：
   - 实时计算集群总容量、当前占用并发、饱和度（`saturation_ratio`）与过热设备感知；
   - **加法递增 (Additive Increase)**：当集群饱和度 < 70% 且时延正常时，动态每秒派发窗口自增 +2，稳步释放吞吐能力；
   - **乘法递减 (Multiplicative Decrease)**：当集群饱和度 >= 85%、排队时延 >= 1500ms 或检测到过热机器时，窗口乘法收缩至 60%（`HEAVY_BACKPRESSURE`），主动实施反压限流；
   - **溢出熔断拒绝 (`OVERFLOW_REJECTION`)**：排队任务深度突破安全阈值（如 >= 100）时，触发安全熔断保护，窗口收缩至最小（2 个）。
2. **四级反压等级体系 (`BackpressureLevel`)**：
   - `NORMAL`（畅通）、`LIGHT_THROTTLING`（轻度流控）、`HEAVY_BACKPRESSURE`（重度反压）、`OVERFLOW_REJECTION`（溢出拒绝）。
3. **REST API 端点拓展 (`backend/app/api/v1/fleet_scheduler_api.py`)**：
   - `POST /api/v1/scheduler/backpressure/adjust`：根据排队指标计算自适应反压窗口与动作说明；
   - `GET /api/v1/scheduler/backpressure/status`：查询当前动态流控窗口与集群水位状态；
   - `GET /api/v1/scheduler/backpressure/snapshots`：反压调节历史流水查询。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_dynamic_backpressure_balancer.py`：4 passed（低载健康加法递增、高载过热乘法递减、超载队列溢出拒绝、快照状态与历史流水查询）；
   - `backend/tests/api/test_fleet_scheduler_api.py`：5 passed；
   - **总体通过率**：**23 passed across all Phase 1 & 2 backend test files (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：6/6 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**4 files already formatted.**；
   - `mypy`：**Success: no issues found in 3 source files.**。
