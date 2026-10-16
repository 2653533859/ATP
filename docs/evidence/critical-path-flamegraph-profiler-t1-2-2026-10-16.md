# T1.2 跨服务调用关键路径时延分析与火焰图性能瓶颈定位器验收 (2026-10-16)

## 概述与结论

T1.2（跨服务调用关键路径时延分析与火焰图性能瓶颈定位器）已完成全量交付与验证，持续推进 **ATP v4.0.0 Phase 1（分布式调用链全息追踪与拓扑性能瓶颈火焰图）**：
1. **核心服务实现 (`backend/app/services/critical_path_flamegraph_profiler.py`)**：
   - 实现动态规划与最长路径搜索算法，从复杂的微服务并发/异步调用链中精准识别端到端**关键执行路径（Critical Path）**；
   - 精确计算各 Span 节点的自身独占耗时（`self_time_ms = duration - sum(children_durations)`）与关键路径贡献比（`critical_path_ratio_pct`）；
   - 智能定位系统首要瓶颈并归类（`DATABASE_SLOW_QUERY` / `EXTERNAL_HTTP_LATENCY` / `INTERNAL_COMPUTATION` / `QUEUE_LAG`）；
   - 输出前端 ECharts/D3 友好的层级火焰图数据结构 `FlamegraphNode`（包含 `name`、`value`、`self_value`、`service_name`、`is_critical_path`、`is_bottleneck` 与 `children`）；
   - 支持根据已采集 TraceId 联动中继数据仓库直接执行分析（`profile_trace_critical_path_by_id`），或传入自定义 Span 实时分析（`profile_spans_critical_path`）。
2. **REST API 接入 (`backend/app/api/v1/critical_path_flamegraph.py`)**：
   - 挂载路由前缀 `/trace/flamegraph`：
     - `GET /trace/flamegraph/profile/{trace_id}`：根据 TraceId 获取关键路径分析与分层火焰图；
     - `POST /trace/flamegraph/profile-spans`：传入自定义 Span 集合实时分析性能瓶颈；
   - 并在 `backend/app/api/v1/router.py` 中稳定接入全局 API 路由表。

## 质量与测试门禁验证

1. **自动化单元测试 (`backend/tests/services/test_critical_path_flamegraph_profiler.py`)**：
   - 4 项测试全部通过（**4 passed in 0.31s**）：
     - `test_critical_path_identification_with_parallel_branches`：验证并行分支下准确识别耗时最长链路并剔除旁路，准确定位第三方支付外部 HTTP 延迟瓶颈与火焰图结构；
     - `test_database_bottleneck_detection`：验证 SQL 慢查询属性提取与 `DATABASE_SLOW_QUERY` 类别判定；
     - `test_profile_by_trace_id_integration`：验证 TraceId 联动已采集 Span 进行关键路径推导与内部计算瓶颈诊断；
     - `test_empty_spans_profile`：验证空 Span 数组的边界安全防护。
2. **独立文件执行**：
   - `python scripts/pytest-standalone-sweep.py` 单文件独立执行 **1 passed, 0 failed (100% PASS)**。
3. **代码规范与格式化**：
   - `ruff check` 与 `ruff format --check` 全部通过，零代码异味。
4. **静态类型安全**：
   - `mypy` 增量检查通过（Success: no issues found in 2 source files）。
