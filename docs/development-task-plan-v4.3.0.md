# ATP v4.3.0 研发任务规划与执行计划 (2026-10-17)

> 版本定位：**云原生弹性集群监控大盘、多环境配置与数据漂移审计中心、大模型自主探索测试控制台与智能发版门禁决策看板 (Cloud-Native Elastic Cluster Dashboard, Multi-Env Drift Audit Center, LLM Autonomous Testing Console & Release Gatekeeper Board)**
> 承接基准：以 v4.2.0 交付的云原生动态 Worker 扩缩容、智能分片调度、临时沙箱环境、多环境配置与 Schema 漂移探测、IaC 合规巡检、LLM 用例生成、合成数据、模糊变异及质量发版门禁为坚实底座，在前端构建完整的可视化控制台、监控大盘与决策看板，实现端到端工业级全栈大闭环。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 云原生弹性测试执行集群与沙箱环境调度大盘 (Cloud-Native Elastic Test Cluster & Ephemeral Sandbox Console)**
  - 聚焦动态 Worker 容器 Pod 弹性扩缩容拓扑大盘、大规模测试套件智能动态分片装箱矩阵与长尾掉队节点重平衡、以及临时沙箱测试环境生命周期全景监控大盘。
- **Phase 2: 跨环境配置漂移自动探测与数据库 Schema 演化一致性审计中心 (Multi-Env Drift Audit Center)**
  - 聚焦跨多环境配置与环境变量差异比对卡片与敏感项泄露告警、数据库表结构与索引变更漂移双向比对及修复 DDL 导出大盘、以及基础设施即代码与网络策略合规巡检卡片。
- **Phase 3: 基于大模型 (LLM) 的测试用例智能生成、自主探索测试与合成数据控制台 (LLM Autonomous Testing & Synthetic Data Console)**
  - 聚焦接口契约/Spec 驱动的端到端用例智能生成编排、业务边界条件测试合成数据生成与批次导出、以及自主探索式 API 模糊变异探查与单行 cURL 复现控制台。
- **Phase 4: 软件发布质量全景度量与智能发版门禁决策看板 (Release Gatekeeper Decision Board)**
  - 聚焦全生命周期多维质量健康综合评分仪表盘与 A+ 等级诊断、自动化发版准入阻断裁决器 (Go/No-Go) 与特批风险豁免流转弹窗、以及带 SHA-256 防篡改指纹的交付物全景审计报告大盘页面。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：云原生弹性测试执行集群与沙箱环境调度大盘

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI1.1 `[x]` | **动态 Worker 容器 Pod 弹性扩缩容拓扑与配额监控抽屉** | `elastic_test_worker_autoscaler` | 落地 `ElasticWorkerAutoscalerDrawer.vue` 组件与 API 客户端；展示排队深度滑块、HPA 期望副本数、动作状态徽章、集群 CPU/内存配额水位；单测独立通过；见 docs/evidence/elastic-worker-autoscaler-drawer-ui1-1-2026-10-17.md |
| UI1.2 `[x]` | **大规模测试套件智能动态分片装箱矩阵与掉队重平衡面板** | `test_suite_dynamic_sharding_scheduler` | 落地 `TestSuiteDynamicShardingPanel.vue` 组件与 API 客户端；展示 LPT 贪心装箱多节点耗时分布柱状图、均衡度得分 (0~100%) 与长尾掉队节点告警；单测独立通过；见 docs/evidence/test-suite-dynamic-sharding-panel-ui1-2-2026-10-17.md |
| UI1.3 `[x]` | **临时沙箱测试环境生命周期拓扑与原子回收全景大盘页面** | `ephemeral_test_env_lifecycle_manager` | 落地 `EphemeralTestEnvDashboardView.vue` 视图与路由；展示多租户隔离沙箱列表、租约 TTL 倒计时、一键延长租约与优雅原子销毁控制台；单测独立通过；见 docs/evidence/ephemeral-test-env-dashboard-view-ui1-3-2026-10-17.md |

---

### Phase 2：跨环境配置漂移自动探测与数据库 Schema 演化一致性审计中心

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI2.1 `[x]` | **跨多环境配置差异比对卡片与敏感密钥泄漏告警抽屉** | `multi_env_config_drift_detector` | 落地 `MultiEnvConfigDriftDrawer.vue` 组件与 API 客户端；展示基准 vs 目标环境配置差分树、CRITICAL 密钥高危标识、一致性得分与修复建议；单测独立通过；见 docs/evidence/multi-env-config-drift-drawer-ui2-1-2026-10-17.md |
| UI2.2 `[x]` | **数据库 Schema 结构与索引变更漂移双向比对大盘页面** | `db_schema_drift_compatibility_checker` | 落地 `DbSchemaDriftAuditDashboardView.vue` 视图与路由；展示表/列/索引差异矩阵、破坏性变更等级评定与合成修复 DDL 脚本一键复制导出；单测独立通过；见 docs/evidence/db-schema-drift-audit-dashboard-view-ui2-2-2026-10-17.md |
| UI2.3 `[ ]` | **基础设施即代码 (IaC) 与网络策略安全合规巡检卡片** | `iac_network_policy_compliance_scanner` | 落地 `IaCComplianceScannerCard.vue` 组件与 API 客户端；展示特权容器/敏感卷挂载违规清单、安全扣分模型与准入阻断裁决结论；单测独立通过。 |

---

### Phase 3：基于大模型 (LLM) 的测试用例智能生成、自主探索测试与合成数据控制台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[ ]` | **接口契约与业务 Spec 驱动的端到端用例智能生成编排抽屉** | `llm_spec_to_e2e_case_synthesizer` | 落地 `LLMSpecToE2ECaseSynthesizerDrawer.vue` 组件与 API 客户端；展示时序依赖 DAG 节点流转、上下文变量提取、Python 测试脚本实时预览与复制；单测独立通过。 |
| UI3.2 `[ ]` | **针对复杂业务边界条件的生产级测试合成数据生成卡片** | `synthetic_test_data_generator` | 落地 `SyntheticTestDataGeneratorCard.vue` 组件与 API 客户端；支持正向/边界/负向三模态切换、字段约束配置、数据表预览与多格式导出；单测独立通过。 |
| UI3.3 `[ ]` | **自主探索式 API 模糊变异与隐蔽缺陷探查及 cURL 复现控制台** | `autonomous_api_fuzzing_explorer` | 落地 `AutonomousApiFuzzingExplorerDrawer.vue` 组件与 API 客户端；展示 6 大变异策略执行状态、5xx 崩溃与注入缺陷卡片、单行 cURL 复现命令；单测独立通过。 |

---

### Phase 4：软件发布质量全景度量与智能发版门禁决策看板

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI4.1 `[ ]` | **全生命周期多维质量健康综合评分仪表盘与 A+ 评级诊断卡片** | `quality_health_composite_score_engine` | 落地 `QualityHealthCompositeScoreCard.vue` 组件与 API 客户端；展示 6 维雷达图/进度条、A+/A/B/C 等级微章、P0 一票否决标识与首要扣分项归因；单测独立通过。 |
| UI4.2 `[ ]` | **自动化发版准入阻断裁决器 (Go/No-Go) 与特批豁免流转弹窗** | `smart_release_go_no_go_decider` | 落地 `ReleaseGateVerdictWaiverModal.vue` 弹窗与 API 客户端；展示 GO/CAUTION/NO_GO 裁决大横幅、阻断清单、架构师签署特批风险豁免与撤销流转；单测独立通过。 |
| UI4.3 `[ ]` | **端到端测试执行与质量合规全景审计报告大盘页面** | `comprehensive_test_audit_report_generator` | 落地 `ComprehensiveAuditReportView.vue` 视图与路由；全景组装 5 大维度证据链、展示 64 位 SHA-256 防篡改指纹、在线验签与 Markdown 审计文档导出；单测独立通过。 |

---

## 3. 质量门禁规则

1. **类型零报错**：`npm run type-check` (`vue-tsc --noEmit`) 保持 100% 通过。
2. **构建零错误**：`npm run build` (`vite build`) 保持生产构建通过。
3. **单元测试与全覆盖**：所有新增 Vue 组件均配备对应的 `*.spec.ts` 单元测试，Vitest 运行 100% PASS。
4. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
