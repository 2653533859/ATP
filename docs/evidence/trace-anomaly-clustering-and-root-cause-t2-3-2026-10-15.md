# T2.3 失败步骤慢调用瓶颈与异常 Span 自动标红聚类验收（2026-10-15）

## 概述与结论

T2.3（失败步骤慢调用瓶颈与异常 Span 自动标红聚类）已完成全量代码演进与自动化质量验证：
1. **多维微服务 Span 异常分析器 (`classify_span`)**：
   - **慢数据库 / 慢 SQL 检测 (`slow_database_query`)**：
     - 识别包含 `db.system` 与 `db.statement` 的数据访问 Span；
     - 耗时超过预设阈值（默认 100ms）自动标黄/标红，提取脱敏后的 SQL 语句片段，精准暴露数据库慢查询；
   - **下游微服务 HTTP 5xx 故障检测 (`downstream_service_fault`)**：
     - 识别状态码 >= 500、`otel.status_code == "ERROR"` 或带有错误标签的外部调用 Span；
   - **RPC / 网络超时检测 (`rpc_timeout`)**：
     - 深度识别 `timeout`、`timed out`、`deadline exceeded` 等超时特征；
   - **慢微服务调用检测 (`slow_service_call`)**：
     - 识别耗时超过 500ms 的中间层服务节点。
2. **Span 拓扑聚类与根因自动归因 (`cluster_trace_anomalies`)**：
   - 遍历微服务调用链全量节点，聚类输出异常 Span 列表并按严重级别与耗时倒序排列；
   - 自动推导链路首要根因节点：定位 `root_cause_service`（根因服务）、`root_cause_span`（根因 Span）与高可读的中文根因诊断摘要 `root_cause_summary`；
   - 输出错误 Span 计数与慢调用计数，全面赋能前端调用链视图的自动标红高亮与下钻聚焦。
3. **数据模型与 API 接入 (`api/v1/traces.py`)**：
   - 开放专属异常聚类接口：`GET /api/v1/traces/{trace_id}/anomalies`；
   - 在瀑布图返回模型 `DistributedTraceWaterfallOut` 中无缝内嵌 `anomaly_cluster` 诊断数据。

---

## 质量门禁与验证

1. **专项自动化测试**：
   - `backend/tests/services/test_trace_anomaly_clustering.py`：**6 passed in 0.39s**（覆盖慢 SQL 识别、下游 502 故障识别、RPC 超时优先判定、正常 Span 过滤、多节点复杂调用链根因自动归因、干净链路零异常退化）；
   - 回归测试：20 项链路追踪专项测试全量一次性通过；
   - `scripts/pytest-standalone-sweep.py`：**1 passed, 0 failed standalone**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 199 source files**。
