# ATP v5.1.0 研发任务规划与执行计划 (2026-10-17)

## 1. 版本背景与目标 (Executive Scope)

在 ATP 历经全链路分布式追踪中台（v4.9.0）与 iOS 移动真机池化调度（v5.0.0）的里程碑演进后，平台在单协议（HTTP, gRPC, WebSocket）与单终端（Web, Android, iOS）上的自动化测试能力已高度完备。根据平台技术演进基线规划（`docs/current-capability-baseline-2026-10-15.md`），平台下一代核心突破点聚焦于**端到端综合业务链路的混合编排与漏测血缘治理**：
**ATP v5.1.0 目标打造拖拽式多协议多端混合工作流编排器与低代码漏测血缘分析中枢 (Drag-and-Drop Hybrid Workflow Orchestrator & Visual Coverage Lineage Hub)**。

业务核心诉求：
1. **多端多协议工作流编排 (Phase 1)**：通过拓扑有向无环图（DAG），将 HTTP 准备数据 ➔ Web 登录 ➔ gRPC 校验 ➔ iOS/Android 真机下单 ➔ 数据库比对 串联为统一工作流，支持动态变量总线（`{{node1.output.id}}`）在跨节点间透明传递；
2. **可视化漏测血缘与覆盖间隙分析 (Phase 2)**：自动比对需求业务路径、API 契约字段分支与用例执行覆盖矩阵，精确定位未覆盖的盲区节点（漏测红斑），并一键生成补测用例草稿；
3. **交互式拖拽画布与全景大盘 (Phase 3)**：Vue 3 前端提供专业级可视化拖拽编排画布、节点连线、执行流光状态与漏测血缘下钻抽屉；
4. **沙箱熔断与防篡改发布 (Phase 4)**：提供工作流死循环超时看门狗与 SHA-256 证据签名存证，通过全套严苛工程门禁并完成正式发布。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：拖拽式多协议多端工作流 DAG 编排引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **多协议多端工作流拓扑 DAG 执行引擎** | `backend/app/services/hybrid_workflow_dag_engine.py` | 实现包含 HTTP, gRPC, Web UI, Android, iOS, SQL, Condition, Loop 等多类型节点的拓扑排序执行与分支流转；单测独立通过；见 docs/evidence/hybrid-workflow-dag-engine-t1-1-t1-3-2026-10-17.md |
| T1.2 `[x]` | **跨节点动态变量总线与表达式求值器** | `backend/app/services/workflow_context_variable_bus.py` | 实现 `{{node.output.field}}` 跨端变量提取、JSONPath 解析与动态上下文求值注入；单测独立通过；见 docs/evidence/hybrid-workflow-dag-engine-t1-1-t1-3-2026-10-17.md |
| T1.3 `[x]` | **混合工作流编排与执行管理 REST API** | `backend/app/api/v1/hybrid_workflow_api.py` | 暴露 `/workflow/save`, `/workflow/execute`, `/workflow/run/{run_id}` 等接口；单测独立通过；见 docs/evidence/hybrid-workflow-dag-engine-t1-1-t1-3-2026-10-17.md |

---

### Phase 2：低代码可视化漏测血缘与测试间隙识别器

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **业务分支与契约多维漏测血缘分析器** | `backend/app/services/visual_coverage_lineage_analyzer.py` | 计算业务路径、接口分支与测试用例覆盖矩阵，自动标定未测试漏测节点 (Coverage Gap)；单测独立通过；见 docs/evidence/visual-coverage-lineage-analyzer-t2-1-t2-3-2026-10-17.md |
| T2.2 `[x]` | **漏测盲区智能补全用例草稿合成器** | `backend/app/services/missing_test_case_synthesizer.py` | 基于未覆盖分支逆向推导前置条件与预期断言，一键生成补测用例草稿；单测独立通过；见 docs/evidence/visual-coverage-lineage-analyzer-t2-1-t2-3-2026-10-17.md |
| T2.3 `[x]` | **漏测血缘与推荐补测管理 REST API** | `backend/app/api/v1/coverage_lineage_api.py` | 暴露 `/coverage/lineage`, `/coverage/gaps`, `/coverage/synthesize` 等接口；单测独立通过；见 docs/evidence/visual-coverage-lineage-analyzer-t2-1-t2-3-2026-10-17.md |

---

### Phase 3：可视化拖拽工作流画布与漏测血缘全景大盘

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[ ]` | **可视化拖拽工作流编排画布组件** | `frontend/src/views/workbench/components/HybridWorkflowDragCanvas.vue` | 实现节点拖拽摆放、端口连线、属性抽屉配置与执行状态流光动画；单测独立通过。 |
| UI3.2 `[ ]` | **漏测血缘图谱与覆盖间隙下钻抽屉** | `frontend/src/views/workbench/components/VisualCoverageGapInspectorDrawer.vue` | 呈现业务与接口血缘拓扑树、红斑漏测节点高亮与一键智能补测；单测独立通过。 |
| UI3.3 `[ ]` | **混合工作流与漏测血缘中枢工作台页面** | `frontend/src/views/workbench/HybridWorkflowWorkbenchView.vue` | 落地路由 `/workbench/hybrid-orchestrator`，集成 4 大 Bento KPI、画布与大盘总表；单测独立通过。 |

---

### Phase 4：容灾沙箱、执行签名与全量发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **工作流执行死循环与超时熔断看门狗** | `backend/app/services/workflow_execution_sandbox_guard.py` | 监控循环节点迭代次数与链路总超时，防范死锁并安全熔断终止；单测独立通过。 |
| T4.2 `[ ]` | **工作流执行证据链 64 位 SHA-256 签名存证器** | `backend/app/services/workflow_evidence_fingerprint_signer.py` | 为多端执行结果生成不可篡改 SHA-256 存证证书并支持在线验签；单测独立通过。 |
| T4.3 `[ ]` | **v5.1.0 混合编排与漏测血缘中台综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v5.1.0-release-notes.md` 与专项交付证据。 |

---

## 3. 质量门禁规则

1. **后端质量门禁**：
   - `pytest` 单测 100% PASS；
   - `pytest-standalone-sweep.py` 隔离单跑 100% PASS；
   - `ruff check` 零警告；
   - `ruff format --check` 格式化完全合规；
   - `mypy` 强类型安全通过。
2. **前端质量门禁**：
   - `vue-tsc --noEmit` 严格类型零错误；
   - `vitest run` 单测 100% PASS；
   - `vite build` 生产构建成功。
3. **专项证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
