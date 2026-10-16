# ATP v4.2.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**云原生弹性测试执行集群调度、多环境配置与数据漂移审计、大模型自主探索式测试与智能发布门禁决策大脑 (Cloud-Native Elastic Test Execution Cluster, Multi-Env Drift Auditor, LLM Autonomous Exploratory Engine & Smart Release Gatekeeper)**
> 承接基准：以 v4.0.0 / v4.1.0 交付的分布式链路全息追踪、跨微服务数据一致性稽核、智能根因推导与断言自愈流水线为坚实底盘，进一步向云原生大规模弹性测试调度、跨环境配置/Schema 漂移治理、大模型自主探索测试与持续发布智能决策大脑纵深推进，打造全生命周期的工业级智能质量工程底盘。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 云原生动态弹性测试执行集群与工作流任务分片调度器 (Cloud-Native Elastic Test Cluster & Sharded Workflow Scheduler)**
  - 聚焦动态 Worker 容器 Pod 弹性扩缩容、大规模测试套件多节点动态分片与跨节点负载均衡调度、以及临时沙箱测试环境生命周期自动化供给与快速回收。
- **Phase 2: 跨环境配置漂移自动探测与数据库 Schema 演化一致性审计 (Multi-Environment Config Drift & Schema Evolution Auditor)**
  - 聚焦 Dev/Test/Staging/Prod 多环境配置差异比对、数据库表结构与索引变更漂移自动比对、以及基础设施即代码与网络策略安全合规巡检。
- **Phase 3: 基于大模型 (LLM) 的测试用例智能生成、自主探索式测试与合成数据引擎 (LLM Autonomous Exploratory Testing & Synthetic Data Engine)**
  - 聚焦接口契约/PRD 驱动的测试用例智能生成与编排、复杂业务边界条件测试数据合成生成、以及自主探索式 API 模糊变异与隐蔽缺陷探查。
- **Phase 4: 软件发布质量全景度量与智能发版门禁决策大脑 (Comprehensive Quality Metrics & Smart Release Gatekeeper)**
  - 聚焦全生命周期多维质量健康综合评分、自动化发版准入阻断裁决器 (Go/No-Go Decision Engine) 与免阻断流转、以及端到端质量全景审计报告生成。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：云原生动态弹性测试执行集群与工作流任务分片调度器

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **动态 Worker 容器 Pod 弹性扩缩容与集群资源配额仲裁器** | `elastic_test_worker_autoscaler` | 落地 `elastic_test_worker_autoscaler` 服务与 `/cluster/autoscaler/*` API；基于用例排队深度、预期 CPU/内存负载与配额阈值，动态计算 Worker 副本扩缩容决策并调度 Pod；单测独立通过；见 docs/evidence/elastic-test-worker-autoscaler-t1-1-2026-10-16.md |
| T1.2 `[x]` | **大规模测试套件智能动态分片与跨节点负载均衡调度器** | `test_suite_dynamic_sharding_scheduler` | 落地 `test_suite_dynamic_sharding_scheduler` 服务与 `/cluster/sharding/*` API；基于历史用例耗时与权重，执行动态分片切分 (Sharding)，实现多执行节点耗时均衡最大化；单测独立通过；见 docs/evidence/test-suite-dynamic-sharding-scheduler-t1-2-2026-10-16.md |
| T1.3 `[x]` | **临时沙箱测试环境生命周期自动化供给与快速回收器** | `ephemeral_test_env_lifecycle_manager` | 落地 `ephemeral_test_env_lifecycle_manager` 服务与 `/cluster/ephemeral-env/*` API；自动化拉起隔离测试环境命名空间、注入路由规则、并在测试结束后原子级优雅回收；单测独立通过；见 docs/evidence/ephemeral-test-env-lifecycle-manager-t1-3-2026-10-16.md |

---

### Phase 2：跨环境配置漂移自动探测与数据库 Schema 演化一致性审计

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **跨多环境配置与环境变量差异比对探测器** | `multi_env_config_drift_detector` | 落地 `multi_env_config_drift_detector` 服务与 `/env-drift/config/*` API；提取多环境 ConfigMap、环境变量与服务配置，执行深层差异差分比对并分级告警；单测独立通过；见 docs/evidence/multi-env-config-drift-detector-t2-1-2026-10-17.md |
| T2.2 `[x]` | **数据库 Schema 结构与索引变更漂移自动比对器** | `db_schema_drift_compatibility_checker` | 落地 `db_schema_drift_compatibility_checker` 服务与 `/env-drift/schema/*` API；逆向推导表字段、主外键、索引结构，探测未同步的破坏性变更并生成同步 DDL 脚本；单测独立通过；见 docs/evidence/db-schema-drift-compatibility-checker-t2-2-2026-10-17.md |
| T2.3 `[x]` | **基础设施即代码 (IaC) 与网络策略安全合规巡检引擎** | `iac_network_policy_compliance_scanner` | 落地 `iac_network_policy_compliance_scanner` 服务与 `/env-drift/iac-compliance/*` API；扫描 K8s NetworkPolicy 与 Docker Compose 配置，检测未受限入方向、特权容器与合规缺陷；单测独立通过；见 docs/evidence/iac-network-policy-compliance-scanner-t2-3-2026-10-17.md |

---

### Phase 3：基于大模型 (LLM) 的测试用例智能生成、自主探索式测试与合成数据引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T3.1 `[x]` | **接口契约与业务 Spec 驱动的端到端用例智能生成编排器** | `llm_spec_to_e2e_case_synthesizer` | 落地 `llm_spec_to_e2e_case_synthesizer` 服务与 `/llm-testing/synthesize-cases/*` API；解析 OpenAPI 契约与业务流程描述，推导业务依赖上下文并生成标准测试用例；单测独立通过；见 docs/evidence/llm-spec-to-e2e-case-synthesizer-t3-1-2026-10-17.md |
| T3.2 `[ ]` | **针对复杂业务边界条件的生产级测试合成数据生成器** | `synthetic_test_data_generator` | 落地 `synthetic_test_data_generator` 服务与 `/llm-testing/synthetic-data/*` API；基于字段约束与边界特征，合成多样化符合校验规则的生产级测试数据包；单测独立通过。 |
| T3.3 `[ ]` | **自主探索式 API 模糊变异与隐蔽缺陷深度探查器** | `autonomous_api_fuzzing_explorer` | 落地 `autonomous_api_fuzzing_explorer` 服务与 `/llm-testing/fuzzing-explore/*` API；执行基于状态反馈的智能变异探测，探查未预期的 5xx 服务崩溃与逻辑旁路缺陷；单测独立通过。 |

---

### Phase 4：软件发布质量全景度量与智能发版门禁决策大脑

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **全生命周期多维质量健康综合评分引擎** | `quality_health_composite_score_engine` | 落地 `quality_health_composite_score_engine` 服务与 `/gatekeeper/health-score/*` API；融合用例成功率、缺陷密度、变更风险、变异测试得分与覆盖率，量化系统质量健康得分；单测独立通过。 |
| T4.2 `[ ]` | **自动化发版准入阻断裁决器 (Go/No-Go) 与豁免流转网关** | `smart_release_go_no_go_decider` | 落地 `smart_release_go_no_go_decider` 服务与 `/gatekeeper/release-verdict/*` API；根据门禁规则裁决 GO / CAUTION / NO-GO，支持特批阻断豁免流转与审计留痕；单测独立通过。 |
| T4.3 `[ ]` | **端到端测试执行与质量合规全景审计报告生成器** | `comprehensive_test_audit_report_generator` | 落地 `comprehensive_test_audit_report_generator` 服务与 `/gatekeeper/audit-report/*` API；组装跨维度执行与门禁数据，生成带 SHA-256 防篡改指纹的发布质量审计报告；单测独立通过。 |

---

## 3. 质量门禁规则

1. **代码风格与规范**：所有代码严格执行 `ruff format` 与 `ruff check`，无任何未忽略告警。
2. **类型检查**：新增服务与 API 严格遵从类型注解，`mypy` 校验保持零错误通过。
3. **单元测试与全覆盖**：所有新增服务均配备对应的 `test_*.py` 单元测试，Pytest 独立与全套件运行 100% PASS。
4. **无缝路由挂载**：所有 REST API 规范挂载于 `/api/v1` 路由树下。
5. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
