# UI3.2 微服务调用依赖拓扑与爆炸半径逆向 BFS 级联阻断图验收（2026-10-16）

## 概述与结论

UI3.2（微服务调用依赖拓扑与爆炸半径逆向 BFS 级联阻断图）已完成全量交付与验证：
1. **拓扑与爆炸半径分析联动 (`frontend/src/api/meshChaos.ts`)**：
   - 联动 `getTopology` 获取全网微服务节点与有向调用边（Caller $\rightarrow$ Callee）；
   - 联动 `evaluateBlastRadius` 与 `enforceBlastRadius` 接口，执行逆向 BFS 上游级联受损推导与安全红线核验。
2. **微服务拓扑力导向可视化组件 (`BlastRadiusTopologyGraph.vue`)**：
   - **头部参数与安全红线设定**：可选择故障注入靶点服务、设定最大允许波及微服务数（`max_impacted_services`）、最大传导深度（`max_depth`）以及受保护核心服务名单（如 `user-auth`、`billing-core`）；
   - **紧急熔断告警与安全受控横幅**：
     - 若判定越界或波及受保护核心服务，立即弹出亮红告警：`[EMERGENCY ABORT 紧急熔断已触发]`，并逐条列出违约原因与自动暂停实验指示；
     - 若在边界内，显示绿色安全受控横幅并量化指示安全余量；
   - **ECharts 力导向关系拓扑图 (Force-Directed Graph)**：
     - 注入靶点服务：红色醒目大节点与外发光阴影；
     - 级联受波及节点：橙色/琥珀色节点与虚线警示边；
     - 核心受保护服务：紫色盾牌节点；
     - 正常健康微服务：蓝色节点；
   - **BFS 级联调用链明细**：分层展示直接受波及微服务（Direct）与逆向级联波及上游（Cascading）标签清单。
3. **性能中心双重挂载集成 (`PerformanceCenterView.vue`)**：
   - 在性能压测中心分析工具弹窗第四 Tab 挂载「微服务拓扑与爆炸半径控制」；
   - 在网关混沌控制台抽屉内无缝集成「微服务拓扑与爆炸半径」Tab 页。

---

## 质量门禁与验证

1. **单元测试与组件交互**：
   - `frontend/src/views/workbench/components/BlastRadiusTopologyGraph.spec.ts`：**3 passed in 176ms**（覆盖初始化自动拉取拓扑、评估爆炸半径参数传递与直接/级联节点展示、突破安全边界触发 Emergency Abort 红色告警）；
   - `MeshChaosRuleCard.spec.ts` 与 `PerformanceCenterView.spec.ts` 联合回归：**19 passed in 710ms**。
2. **类型检查与生产构建**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**；
   - `npm run build` (`vite build`)：**✓ built in 2.35s, 0 errors**。
