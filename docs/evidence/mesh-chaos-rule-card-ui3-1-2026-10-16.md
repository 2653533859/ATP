# UI3.1 微服务网关混沌故障注入规则编排卡片与抽样调节器验收（2026-10-16）

## 概述与结论

UI3.1（微服务网关混沌故障注入规则编排卡片与抽样调节器）已完成全量交付与验证，正式开启 **v3.1.0 Phase 3（微服务网关混沌演练与爆炸半径控制台）**：
1. **统一 API 客户端 (`frontend/src/api/meshChaos.ts`)**：
   - 封装 `listExperiments`、`createExperiment`、`getExperiment`、`setExperimentStatus`、`evaluateMeshRequest`、`getTopology`、`evaluateBlastRadius`、`enforceBlastRadius` 与 `compileResilienceReport` 9 大网关混沌演练接口；
   - 建立完整 TypeScript 强类型定义（`ChaosRule`、`ChaosExperiment`、`ChaosActionType` 等）。
2. **网关混沌规则编排卡片组件 (`MeshChaosRuleCard.vue`)**：
   - **规则头部与下发控制**：实验名称配置、启用/禁用状态开关与一键保存下发按钮；
   - **四大典型分布式故障单选切换**：
     - `service_down_503` (503 实例宕机)；
     - `circuit_breaker_trip` (网关断路熔断 ECONNRESET)；
     - `latency_jitter` (网络延迟抖动排队)；
     - `corrupt_payload` (报文畸形损坏)。
   - **流量抽样比例动态滑块**：支持 0% ~ 100% 动态调节，实时展示灰度比例与注入模式提示；
   - **多维路由与上下文匹配**：目标微服务匹配（支持 `*` 全局）、URL 正则表达式（`route_pattern`）以及金丝雀标签匹配（如 `x-canary=true`）；
   - **在线请求评估与故障决策预演**：支持在线发送试探请求，即时查看命中故障动作、HTTP 状态码、注入延迟与响应体 JSON 预览。
3. **性能中心操作入口挂载集成 (`PerformanceCenterView.vue`)**：
   - 在性能压测中心头部操作栏挂载「网关混沌演练」快捷入口；
   - 支持从当前项目一键呼出网关混沌编排控制台。

---

## 质量门禁与验证

1. **单元测试与组件交互**：
   - `frontend/src/views/workbench/components/MeshChaosRuleCard.spec.ts`：**3 passed in 153ms**（覆盖四大故障动作单选渲染、流量滑块比例调节、试探请求评估决策校验、一键下发保存实验与 `saved` 事件抛出）；
   - `PerformanceCenterView.spec.ts`：**13 passed in 293ms**。
2. **类型检查与生产构建**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**；
   - `npm run build` (`vite build`)：**✓ built in 2.38s, 0 errors**。
