# T4.1 混沌演练非生产隔离与绝对安全围栏看门狗服务验收 (2026-10-17)

## 概述与交付物

T4.1（混沌演练非生产隔离与绝对安全围栏看门狗服务）已全量研发交付并通过各项工程门禁，**正式开启 ATP v5.8.0 Phase 4（生产防击穿安全沙箱、合规存证与全量发布）的攻防安全治理**：
1. **多重安全隔离防线与准入看门狗 (`backend/app/services/chaos_safety_boundary_guard.py`)**：
   - **最高危核心资产禁止注入黑名单 (`FORBIDDEN_ASSET_PATTERNS`)**：严禁注入数据库主库（MySQL Primary、PostgreSQL Cluster Writer）、清算与计费账本（`core-ledger`、`billing-settlement`）及控制面集群（`k8s-apiserver`、`etcd-cluster`），命中绝对阻断（`BLOCKED_FORBIDDEN_ASSET`）；
   - **破坏性算子参数边界看门狗**：拦截丢包率超过 80% 或单次网络延迟超过 30,000ms 的击穿性参数（`BLOCKED_UNSAFE_OPERATOR`）；
   - **生产环境强隔离与三要素准入门禁**：
     1. 合法特批变更工单号（`approved_ticket_id` 须以 `CHG-` 开头）；
     2. 处于明确的维护演练窗口内（`maintenance_window_start <= now <= maintenance_window_end`）；
     3. 生产安全校验令牌有效性（`ATP-SAFETY-SECURE-*`）；
     4. 生产环境严禁注入脏数据载荷篡改算子（`PAYLOAD_CORRUPTION`）。
2. **结构化安全裁决报告输出 (`ChaosSafetyGuardVerdict`)**：
   - 提供布尔放行状态（`is_allowed`）、判定动作（`SafetyVerdictAction`）、命中规则明细及结构化字典导出。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_chaos_safety_boundary_guard.py`：7 passed（高危禁止资产黑名单判定、安全令牌格式验证、测试环境正常注入放行、非生产环境主库注入绝对拦截、超大丢包率参数拦截、生产环境无审批强制隔离拦截、生产环境三要素齐全合规演练放行及字典序列化）；
   - **通过率**：**7 passed in 0.33s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：1/1 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 1 source file.**。
