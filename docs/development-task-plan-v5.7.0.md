# ATP v5.7.0 研发任务规划：智能用例依赖拓扑与增量精准回归编排中台 (Intelligent Case Dependency Topology & Incremental Precision Regression Orchestrator)

**规划日期**：2026-10-17
**版本代号**：**Precision Regression & DAG Topology Orchestrator**
**核心目标**：彻底解决万级用例全量回归耗时过长与隐式依赖假失败的行业痛点。构建基于 Git Diff AST 代码变更分析、符号调用链映射、用例有向无环图 (DAG) 拓扑排序与增量精准推荐引擎。在 PR 提交后秒级锁定最小影响面用例集，按最优波次并发调度，实现回归效率提升 10 倍与零漏测风险保障。

---

## 1. 架构设计与系统全景拓扑

```mermaid
flowchart TD
    subgraph Phase 1 [Phase 1: 代码变更 AST 影响面追踪与符号依赖映射器]
        T1_1["T1.1 Git Diff 与 AST 变更高危符号提取器 (code_diff_symbol_extractor)"]
        T1_2["T1.2 接口-函数-用例三维调用链拓扑映射引擎 (symbol_call_graph_mapper)"]
        T1_3["T1.3 增量影响面计算与精准用例推荐 REST API (/api/v1/precision-regression/*)"]
        T1_1 --> T1_2 --> T1_3
    end

    subgraph Phase 2 [Phase 2: 用例 DAG 依赖拓扑编排与执行波次调度器]
        T2_1["T2.1 用例数据上下文有向无环图构建与环路检测器 (case_dag_dependency_builder)"]
        T2_2["T2.2 基于拓扑排序的并发波次分发与前置状态传递器 (dag_wave_execution_dispatcher)"]
        T2_3["T2.3 拓扑中断级联跳过与孤立节点容错控制器 (dag_cascade_fault_controller)"]
        T2_1 --> T2_2 --> T2_3
    end

    subgraph Phase 3 [Phase 3: 增量回归拓扑中枢与精准演练工作台]
        UI3_1["UI3.1 用例依赖 DAG 拓扑可视化与影响面透视抽屉 (CaseDagTopologyDrawer.vue)"]
        UI3_2["UI3.2 增量用例推荐与影响分析对比模拟弹窗 (PrecisionSelectionDiffModal.vue)"]
        UI3_3["UI3.3 智能增量回归编排工作台中枢页面 (/workbench/precision-regression)"]
        UI3_1 --> UI3_2 --> UI3_3
    end

    subgraph Phase 4 [Phase 4: 漏测风险防护围栏看门狗、存证证书与全量发布]
        T4_1["T4.1 增量筛选漏测风险动态防线看门狗 (regression_leak_safety_guard)"]
        T4_2["T4.2 增量用例推荐与拓扑调度 64 位 SHA-256 存证证书器 (precision_evidence_signer)"]
        T4_3["T4.3 v5.7.0 智能增量回归中台综合验收与发布说明 (v5.7.0-release-notes)"]
        T4_1 --> T4_2 --> T4_3
    end

    Phase 1 --> Phase 2 --> Phase 3 --> Phase 4
```

---

## 2. 任务分解清单 (Phase 1 ~ Phase 4)

### Phase 1：代码变更 AST 影响面追踪与符号依赖映射器

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **Git Diff 与 AST 变更高危符号提取器** | `backend/app/services/code_diff_symbol_extractor.py` | 解析代码 Diff 补丁，基于 Python AST 精确提取受影响的类、函数与方法签名变动及修改行号；单测独立通过；见 docs/evidence/code-diff-symbol-extractor-t1-1-2026-10-17.md |
| T1.2 `[x]` | **接口-函数-用例三维调用链拓扑映射引擎** | `backend/app/services/symbol_call_graph_mapper.py` | 建立代码符号到接口端点、端点到测试用例的三维调用血缘关系树，实现双向拓扑可达性查询；单测独立通过；见 docs/evidence/symbol-call-graph-mapper-t1-2-2026-10-17.md |
| T1.3 `[x]` | **增量影响面计算与精准用例推荐 REST API** | `backend/app/api/v1/precision_regression_api.py` | 挂载 `/api/v1/precision-regression/*`，提供 Diff 解析、影响面计算、受影响用例精准推荐与覆盖率预估端点；单测独立通过；见 docs/evidence/precision-regression-api-t1-3-2026-10-17.md |

---

### Phase 2：用例 DAG 依赖拓扑编排与执行波次调度器

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **用例数据上下文有向无环图构建与环路检测器** | `backend/app/services/case_dag_dependency_builder.py` | 解析用例间显式/隐式数据依赖（如前置创建、Token共享），构建 DAG 并执行 Tarjan 算法环路死锁检测；单测独立通过；见 docs/evidence/case-dag-dependency-builder-t2-1-2026-10-17.md |
| T2.2 `[ ]` | **基于拓扑排序的并发波次分发与前置状态传递器** | `backend/app/services/dag_wave_execution_dispatcher.py` | 将 DAG 划分为多级独立波次（Waves），支持同波次最大并发调度与跨波次上下文变量安全管道传递；单测独立通过。 |
| T2.3 `[ ]` | **拓扑中断级联跳过与孤立节点容错控制器** | `backend/app/services/dag_cascade_fault_controller.py` | 前置节点失败时智能级联跳过依赖下游（CASCADE_SKIPPED），同时安全调度无依赖孤立节点，防止雪崩误报；单测独立通过。 |

---

### Phase 3：增量回归拓扑中枢与精准演练工作台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[ ]` | **用例依赖 DAG 拓扑可视化与影响面透视抽屉** | `frontend/src/views/workbench/components/CaseDagTopologyDrawer.vue` | 呈现交互式有向无环拓扑图、波次分级卡片、节点状态流转与数据依赖透视；单测独立通过。 |
| UI3.2 `[ ]` | **增量用例推荐与影响分析对比模拟弹窗** | `frontend/src/views/workbench/components/PrecisionSelectionDiffModal.vue` | 对比全量用例集 vs 增量精准推荐集，展示节省耗时比率、AST 符号变更树与一键试跑；单测独立通过。 |
| UI3.3 `[ ]` | **智能增量回归编排工作台中枢页面** | `frontend/src/views/workbench/PrecisionRegressionWorkbenchView.vue` | 落地路由 `/workbench/precision-regression`，集成 4 大 Bento KPI、拓扑大盘与波次调度执行；单测独立通过。 |

---

### Phase 4：漏测风险防护围栏看门狗、存证证书与全量发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **增量筛选漏测风险动态防线看门狗** | `backend/app/services/regression_leak_safety_guard.py` | 严防高危核心模块（如支付、权限、计费）被过度裁剪导致漏测，提供核心基线保底与风险阻断规则；单测独立通过。 |
| T4.2 `[ ]` | **增量用例推荐与拓扑调度 64 位 SHA-256 存证证书器** | `backend/app/services/precision_evidence_signer.py` | 为增量筛选决策、变更符号清单与 DAG 波次执行记录签发不可篡改 SHA-256 + HMAC 存证证书；单测独立通过。 |
| T4.3 `[ ]` | **v5.7.0 智能增量回归中台综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v5.7.0-release-notes.md` 与专项交付证据。 |

---

## 3. 质量门禁规则

1. **后端质量门禁**：
   - `pytest` 单测 100% PASS；
   - `pytest-standalone-sweep.py` 隔离单跑 100% PASS；
   - `ruff check` 零警告；
   - `ruff format --check` 格式全合规；
   - `mypy` 强类型安全通过。
2. **前端质量门禁**：
   - `vitest` 前端单测 100% PASS；
   - `vue-tsc --noEmit` 0 错误；
   - `vite build` 生产打包成功。
3. **专项证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
