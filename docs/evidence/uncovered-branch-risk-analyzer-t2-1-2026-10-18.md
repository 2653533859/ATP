# T2.1 未覆盖高危分支路径漏洞挖掘器服务验收 (2026-10-18)

## 概述与交付物

T2.1（未覆盖高危分支路径漏洞挖掘器服务）已全量研发交付并通过各项工程门禁，**正式开启 ATP v5.9.0 Phase 2（未覆盖高危分支分析与自动化测试补齐推荐器）的核心研发**：
1. **多维业务语义识别与定级引擎 (`backend/app/services/uncovered_branch_risk_analyzer.py`)**：
   - **高危业务语义分类 (`UncoveredBranchCategory`)**：
     - `PAYMENT_FINANCIAL`：资金支付、退款、计费、优惠核算（极高危 P0）；
     - `AUTH_SECURITY`：安全鉴权、令牌校验、权限越权拦截（极高危 P0）；
     - `EXCEPTION_ROLLBACK`：异常抛错（raise/throw）、事务回滚（rollback）（高危 P1）；
     - `CIRCUIT_BREAKER_FALLBACK`：熔断降级、重试与缓存兜底（高危 P1）；
     - `GENERAL_BUSINESS`：常规业务逻辑条件（中危 P2）；
   - **严重度分级 (`BranchRiskSeverity`)**：
     - `P0_BLOCKING`（核心资损或安全漏洞，触发发布强阻断 `is_release_blocked=True`）；
     - `P1_CRITICAL`（严重异常或降级旁路未经验证，须限期补齐）；
     - `P2_MAJOR`（常规业务分支）；
   - **触发条件表达式与未测后果推导**：
     - `condition_expr`：向上回溯提取触发当前未测代码的条件表达式；
     - `consequence_summary`：推演生产环境未测异常或扣款分支触发的潜在危害后果。
2. **结构化诊断报告输出 (`UncoveredBranchAnalysisReport`)**：
   - 统计 P0/P1/P2 各级未覆盖分支数量与发布阻断裁决结论。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_uncovered_branch_risk_analyzer.py`：3 passed（未覆盖支付扣款分支触发 P0 与发布阻断验证、未覆盖鉴权拦截与异常回滚分支双重定级验证、全覆盖零未测分支安全放行验证及字典序列化）；
   - **通过率**：**3 passed in 0.28s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：1/1 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 1 source file.**。
