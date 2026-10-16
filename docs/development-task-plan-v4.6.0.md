# ATP v4.6.0 研发任务规划与执行计划 (2026-10-17)

> 版本定位：**生产级全链路影子流量压测、单元化隔离 (Cell-based Testing)、多源资源瓶颈防雪崩熔断与数字孪生演练报告引擎 (Production Full-Link Shadow Stress Testing, Cell-based Isolation, Anti-Avalanche Watermark Guardian & Digital-Twin Drill Reporter Engine)**
> 承接基准：以 v4.4.0 视觉多模态智能与 Web Vitals 体验引擎和 v4.5.0 前端控制台为坚实基础，全面进军大规模企业级**生产全链路压测 (Full-Link Stress Testing)** 与高可用架构韧性领域。实现影子流量染色透传、影子库表防污染隔离、单元化/Cell 流量路由、资源瓶颈根因定位与毫秒级防击穿熔断保护。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 生产级全链路影子流量染色、透传与数据隔离引擎 (Shadow Traffic Tainting & Data Isolation Engine)**
  - 聚焦跨协议（HTTP/gRPC/MQ）影子流量染色透传注入与校验、影子数据库/影子表透明路由与防污染隔离拦截、以及消息队列影子队列/Topic 隔离分流器。
- **Phase 2: 单元化/细胞化架构测试隔离 (Cell-based Testing) 与拓扑调度 (Cell Isolation & Traffic Shunting)**
  - 聚焦多可用区/单元化 (Cell/Zone) 流量精准调度、跨单元依赖逃逸 (Cell Escape) 泄漏探查、以及常态化单元灾备接管演练自愈验证。
- **Phase 3: 压测容量水位实时度量、下游瓶颈智能归因与防雪崩熔断器 (Watermark Guardian & Bottleneck Analyzer)**
  - 聚焦数据库连接池/Redis 内存/MQ 堆积深度多源容量水位实时度量、调用链热点慢调用瓶颈根因自动归因、以及生产防击穿毫秒级自适应熔断大脑。
- **Phase 4: 全链路压测仿真数字孪生演练报告与演练准入发布 (Digital-Twin Drill Reporter & Release Gate)**
  - 聚焦 TPS/RPS 阶梯加压性能曲线与拐点检测器、生产全链路压测安全审计与爆炸半径评估器、以及全链路压力演练综合审计报告生成器。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：生产级全链路影子流量染色、透传与数据隔离引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **跨协议影子流量染色标动态注入与透明透传校验器** | `shadow_traffic_taint_propagator` | 落地 `shadow_traffic_taint_propagator` 服务与 `/stress/shadow-traffic/taint/*` API；支持 HTTP Header (`X-ATP-Shadow: true`)、gRPC Metadata 与 MQ Message Header 染色注入与端到端透传闭环；单测独立通过；见 docs/evidence/shadow-traffic-taint-propagator-t1-1-2026-10-17.md |
| T1.2 `[x]` | **影子数据库/影子表路由拦截与读写防污染安全隔离检查器** | `shadow_database_isolation_inspector` | 落地 `shadow_database_isolation_inspector` 服务与 `/stress/shadow-traffic/db-isolation/*` API；校验影子表命名规范与动态路由切换，严密拦截压测脏数据渗入生产真实表；单测独立通过；见 docs/evidence/shadow-database-isolation-inspector-t1-2-2026-10-17.md |
| T1.3 `[x]` | **消息队列影子队列与死信重试分流隔离分流器** | `shadow_mq_queue_router` | 落地 `shadow_mq_queue_router` 服务与 `/stress/shadow-traffic/mq-shunting/*` API；自动重定向影子消息至 Shadow Topic，隔离消费与死信队列避免触发真实短信/第三方充值；单测独立通过；见 docs/evidence/shadow-mq-queue-router-t1-3-2026-10-17.md |

---

### Phase 2：单元化/细胞化架构测试隔离 (Cell-based Testing) 与拓扑调度

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[ ]` | **多可用区单元化 (Cell/Zone) 流量切流与路由策略控制器** | `cell_based_testing_traffic_controller` | 落地 `cell_based_testing_traffic_controller` 服务与 `/stress/cell-isolation/routing/*` API；支持多单元流量动态权重视流、灰度引流与压测单元受控隔离；单测独立通过。 |
| T2.2 `[ ]` | **跨单元服务依赖逃逸 (Cell Escape) 与拓扑孤岛检测器** | `cell_escape_dependency_detector` | 落地 `cell_escape_dependency_detector` 服务与 `/stress/cell-isolation/escape/*` API；自动探查流量跨越单元物理边界访问非隔离共享资源的越界泄漏隐患；单测独立通过。 |
| T2.3 `[ ]` | **单元故障演练与常态化容灾接管自愈验证器** | `cell_failover_resilience_verifier` | 落地 `cell_failover_resilience_verifier` 服务与 `/stress/cell-isolation/failover/*` API；模拟单单元整体瘫痪，量化备用单元自动接管耗时、流量丢包率与自愈状态；单测独立通过。 |

---

### Phase 3：压测容量水位实时度量、下游瓶颈智能归因与防雪崩熔断器

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T3.1 `[ ]` | **多源基础设施 (DB池/Redis/MQ) 容量水位实时度量器** | `multisource_capacity_watermark_meter` | 落地 `multisource_capacity_watermark_meter` 服务与 `/stress/bottleneck-guardian/watermark/*` API；采集并聚合 DB 连接池水位、Redis 内存消耗率与 MQ 积压量，计算健康负荷指数；单测独立通过。 |
| T3.2 `[ ]` | **压测调用链下游热点慢调用与资源争用瓶颈归因器** | `distributed_bottleneck_root_cause_classifier` | 落地 `distributed_bottleneck_root_cause_classifier` 服务与 `/stress/bottleneck-guardian/bottlenecks/*` API；分析压测调用链 P99 抖动，自动归因至死锁、慢 SQL、线程池打满与带宽饱和；单测独立通过。 |
| T3.3 `[ ]` | **生产防击穿自适应毫秒级分级限流与熔断保护大脑** | `adaptive_avalanche_circuit_breaker` | 落地 `adaptive_avalanche_circuit_breaker` 服务与 `/stress/bottleneck-guardian/circuit-breaker/*` API；当下游依赖容量超过 85% 预警水位时，毫秒级自适应阶梯限流与自动阻断压测；单测独立通过。 |

---

### Phase 4：全链路压测仿真数字孪生演练报告与演练准入发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **全链路压测 TPS 阶梯加压性能曲线与拐点检测器** | `step_load_throughput_knee_detector` | 落地 `step_load_throughput_knee_detector` 服务与 `/stress/drill-report/knee-detection/*` API；自动拟合并发线程 vs TPS 曲线，精准定位系统性能吞吐最大拐点 (Knee Point) 与崩溃点；单测独立通过。 |
| T4.2 `[ ]` | **生产全链路压测安全审计与爆炸半径评估器** | `stress_blast_radius_safety_evaluator` | 落地 `stress_blast_radius_safety_evaluator` 服务与 `/stress/drill-report/blast-radius/*` API；量化演练潜在破坏半径，生成压测安全防篡改审计日志与熔断应急预案；单测独立通过。 |
| T4.3 `[ ]` | **全链路压力演练综合审计报告生成器与 Markdown 导出** | `full_link_stress_drill_reporter` | 落地 `full_link_stress_drill_reporter` 服务与 `/stress/drill-report/summary/*` API；汇总量化并发、TPS、P99 延迟、熔断事件与资源水位，支持一键导出标准 Markdown 演练报告；单测独立通过。 |

---

## 3. 质量门禁规则

1. **代码风格与规范**：所有代码严格执行 `ruff format` 与 `ruff check`，无任何未忽略告警。
2. **类型检查**：新增服务与 API 严格遵从类型注解，`mypy` 校验保持零错误通过。
3. **单元测试与全覆盖**：所有新增服务均配备对应的 `test_*.py` 单元测试，Pytest 独立与全套件运行 100% PASS。
4. **无缝路由挂载**：所有 REST API 规范挂载于 `/api/v1` 路由树下。
5. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
