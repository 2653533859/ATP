# ATP v3.8.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**微服务网关生产流量镜像录制、影子流量智能回放比对、契约动态漂移防线与流量驱动韧性演练引擎 (Traffic Mirroring, Shadow Replay, Contract Drift Guard & Resilience Verification Engine)**
> 承接基准：以 v3.6.0 / v3.7.0 交付的代码变更影响面分析、精准推荐与变异门禁为基础，进一步深入真实微服务生产与集成环境，构建无侵入流量录制转用例、影子双写比对、实时契约漂移探测与韧性演练核心引擎。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 真实微服务网关生产流量镜像录制、智能脱敏与用例合成引擎 (Production Traffic Mirroring, Masking & Case Synthesis)**
  - 聚焦微服务网关旁路流量捕获与多协议解析、生产敏感数据自适应规则脱敏、以及流量聚类特征归一化自动转测试用例。
- **Phase 2: 影子流量无副作用双写回放、字段级智能差分与黄金基线校验 (Shadow Traffic Replay, Diff & Baseline Verification)**
  - 聚焦影子流量沙箱隔离回放与写操作安全屏蔽、响应体动态字段智能过滤比对、以及接口黄金基线管理与偏离判定。
- **Phase 3: 实时接口契约动态漂移逆向推导与 Breaking 变更阻断卫士 (Live Contract Drift Detection & Breaking Guard)**
  - 聚焦生产流量 OpenAPI/Protobuf 契约动态逆向推导、新旧契约兼容性差分与破坏性变更分级、以及下游受波及服务级联追溯。
- **Phase 4: 流量驱动的混沌工程故障注入编排与系统韧性验证 (Traffic-Driven Chaos Injection & Resilience Verification)**
  - 聚焦流量特征匹配的故障注入编排、服务熔断降级 RTO 恢复指标量化、以及生产流量防线端到端 CLI 与 OpenAPI 编排。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：真实微服务网关生产流量镜像录制、智能脱敏与用例合成引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **微服务网关旁路流量捕获与 HTTP/gRPC 多协议解析过滤服务** | `traffic_capture_gateway` | 落地 `traffic_capture_gateway` 服务与 `/traffic/capture/*` API；支持 HTTP(REST)/gRPC 流量镜像捕获、路径/方法正则过滤、采样率控制及头部元数据标准化提取；见 docs/evidence/traffic-capture-gateway-t1-1-2026-10-16.md |
| T1.2 `[x]` | **生产敏感数据自适应规则脱敏与模式识别脱敏器** | `traffic_data_masker` | 落地 `traffic_data_masker` 服务与 `/traffic/mask/*` API；支持手机号、身份证、银行卡、鉴权 Token、密码等高敏模式自动识别与可逆/不可逆哈希脱敏掩码；见 docs/evidence/traffic-data-masker-t1-2-2026-10-16.md |
| T1.3 `[x]` | **真实流量请求聚类归一与自动化测试用例智能生成器** | `traffic_to_test_case_synthesizer` | 落地 `traffic_to_test_case_synthesizer` 服务与 `/traffic/synthesize/*` API；基于入参模式聚类去重，自动转换为 ATP 标准 TestCase 与动态测试数据集；见 docs/evidence/traffic-to-test-case-synthesizer-t1-3-2026-10-16.md |

---

### Phase 2：影子流量无副作用双写回放、字段级智能差分与黄金基线校验

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **影子流量无副作用沙箱隔离回放与外部依赖 Mock 代理** | `shadow_traffic_replay_engine` | 落地 `shadow_traffic_replay_engine` 服务与 `/traffic/replay/*` API；支持并发流速控制、写操作拦截或影子标记、外部第三方下游请求自动拦截 Mock；见 docs/evidence/shadow-traffic-replay-engine-t2-1-2026-10-16.md |
| T2.2 `[x]` | **响应体动态字段智能过滤与字段级精确差分比对器** | `traffic_diff_comparator` | 落地 `traffic_diff_comparator` 服务与 `/traffic/diff/*` API；自动识别并忽略时间戳、UUID、随机 Token 等动态噪声字段，对核心业务响应体执行精确差分 (Diff)；见 docs/evidence/traffic-diff-comparator-t2-2-2026-10-16.md |
| T2.3 `[ ]` | **接口黄金响应基线版本化管理与回归偏离判定器** | `golden_response_baseline_manager` | 落地 `golden_response_baseline_manager` 服务与 `/traffic/golden-baselines/*` API；支持基线版本快照打标、容差阈值配置与显著响应漂移报警。 |

---

### Phase 3：实时接口契约动态漂移逆向推导与 Breaking 变更阻断卫士

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T3.1 `[ ]` | **生产流量 OpenAPI/Protobuf 契约动态逆向提取推导器** | `live_contract_schema_extractor` | 落地 `live_contract_schema_extractor` 服务与 `/contract-guard/extract/*` API；从海量实时调用流量中自动推导推断接口 OpenAPI 3.0 / Protobuf Schema 结构。 |
| T3.2 `[ ]` | **接口契约字段级兼容性差分与 Breaking 破坏性评级引擎** | `contract_drift_breaking_evaluator` | 落地 `contract_drift_breaking_evaluator` 服务与 `/contract-guard/evaluate/*` API；比较现网真实流量 Schema 与设计期契约，判定 BREAKING / WARNING / COMPATIBLE 等级。 |
| T3.3 `[ ]` | **契约漂移下游受影响服务级联拓扑探测与告警网关** | `contract_drift_impact_topology_router` | 落地 `contract_drift_impact_topology_router` 服务与 `/contract-guard/impact-topology/*` API；根据受影响字段级联追溯调用方微服务依赖拓扑并触发安全告警。 |

---

### Phase 4：流量驱动的混沌工程故障注入编排与系统韧性验证

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **基于流量特征匹配的微服务故障注入编排执行器** | `traffic_chaos_fault_injector` | 落地 `traffic_chaos_fault_injector` 服务与 `/chaos-traffic/inject/*` API；支持针对特定流量特征精准注入网络延迟 (Latency)、错误响应 (500/503)、异常截断与丢包。 |
| T4.2 `[ ]` | **服务断路器/降级策略生效时延与 RTO 恢复指标量化器** | `resilience_rto_recovery_evaluator` | 落地 `resilience_rto_recovery_evaluator` 服务与 `/chaos-traffic/evaluate-rto/*` API；量化注入故障后断路器触发时延、降级响应正确率与故障消除后 RTO 自愈时长。 |
| T4.3 `[ ]` | **生产流量录制回放与契约防线端到端 CLI 与 OpenAPI 编排** | `traffic_guard_pipeline_api` | 落地 `traffic_guard_pipeline_api` 服务、`/traffic-guard/pipeline/*` API 与 `scripts/ci_atp_traffic_guard.py` CLI 工具；输出 0/1/2 标准状态码与全景执行报告。 |

---

## 3. 质量门禁规则

1. **后端单元测试全覆盖**：所有新增后端服务均配备对应的 `test_*.py` 单元测试，pytest 运行 100% PASS。
2. **测试用例独立运行验证**：`python scripts/pytest-standalone-sweep.py` 必须保持全量独立运行 100% PASS。
3. **代码规范与格式化**：`ruff check` 与 `ruff format --check` 零违规。
4. **静态强类型检查**：`mypy` 检查无类型错误。
5. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
