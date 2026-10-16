# UI4.1 基于流量特征匹配的应用层混沌故障注入编排抽屉验收 (2026-10-16)

## 概述与结论

UI4.1（基于流量特征匹配的应用层混沌故障注入编排抽屉）已完成全量交付与验证，正式开启 **ATP v3.9.0 最后一个收官阶段：Phase 4（流量驱动的混沌工程故障注入编排与系统韧性监控中心）**：
1. **API 客户端扩展 (`frontend/src/api/trafficGateway.ts` & `frontend/src/api/index.ts`)**：
   - 建立 `FaultType`（`LATENCY` | `ERROR_RESPONSE` | `CORRUPTION` | `ABRUPT_DROP`）、`CorruptionMode`、`TrafficMatchRuleItem`、`FaultInjectionRuleItem`、`FaultExecutionResultItem`、`ChaosExperimentSessionItem` 等强类型接口契约；
   - 封装 `trafficChaosApi` 客户端方法：`createRule`、`listRules`、`deleteRule`、`evaluateFault`、`startSession`、`stopSession`、`listSessions` 与 `getSession`。
2. **混沌故障注入编排控制台抽屉 (`TrafficChaosFaultInjectorDrawer.vue`)**：
   - **头部 Header & 4 大故障模式卡片**：
     - `LATENCY`（时延注入 + 动态抖动 Jitter）；
     - `ERROR_RESPONSE`（返回 500/502/503/504 等指定错误状态码与 Mock 错误体）；
     - `CORRUPTION`（数据载荷损坏，截断 TRUNCATE 或乱码 GARBLE）；
     - `ABRUPT_DROP`（中途连接重置断开/模拟网络丢包）；
   - **全局演练会话状态栏 (Session Bar)**：
     - 动态展示当前混沌演练批次运行状态（`ACTIVE` / `IDLE`）；
     - 统计拦截请求总数与注入故障总数；
     - 提供「启动混沌演练批次」与「停止演练 (恢复正常)」一键控制；
   - **规则清单与触发熔断进度表格 (左侧)**：
     - 规则名称与 ID、故障模式徽章、流量特征匹配（路径正则、HTTP 方法、Header、概率比例）、注入参数（毫秒/错误码/损坏模式）；
     - **触发熔断进度条**：直观展示已触发次数 / 最大上限（`max_triggers_limit`，超限自动熔断防失控）；
     - 支持一键将规则带入右侧沙箱演练或删除；
   - **规则编排表单 & 在线沙箱演练 Tabs (右侧)**：
     - **Tab 1: 编排新建故障规则**：支持表单选择故障模式，动态切换延时抖动、错误状态码、载荷破坏模式等参数，设置匹配条件与防失控上限并一键保存；
     - **Tab 2: 在线沙箱流量演练**：支持输入请求路径、方法与 Headers，一键「发送测试流量并评估故障拦截」，即时反馈是否命中故障注入（🚨 绿/红 Badge）、注入时延、生效状态码、拦截响应体与日志。
3. **接口测试工作台集成 (`ApiWorkbenchView.vue`)**：
   - 顶部工具栏挂载「混沌故障注入」按钮；
   - 支持一键滑出 1120px 宽幅控制台抽屉。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/TrafficChaosFaultInjectorDrawer.spec.ts`：**2 passed in 68ms**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed**；
   - 工作台核心测试套件：**14 passed in 603ms**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 3.05s, 0 errors**。
