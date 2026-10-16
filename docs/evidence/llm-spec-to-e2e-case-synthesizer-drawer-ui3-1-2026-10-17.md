# UI3.1 接口契约与业务 Spec 驱动的端到端用例智能生成编排抽屉验收 (2026-10-17)

## 概述与结论

UI3.1（接口契约与业务 Spec 驱动的端到端用例智能生成编排抽屉）已完成全量交付与验证，正式开启 **ATP v4.3.0 Phase 3（基于大模型 LLM 的测试用例智能生成、自主探索测试与合成数据控制台）**：
1. **核心组件实现 (`frontend/src/views/workbench/components/LLMSpecToE2ECaseSynthesizerDrawer.vue`)**：
   - **头部机制说明 Banner**：
     - 解析结合自然语言业务 Spec 与 OpenAPI 接口契约推导时序依赖 DAG、参数上下文变量提取与 Python 测试脚本合成机制；
   - **业务场景与预设配置栏 (Config Section)**：
     - 内置 3 组典型业务闭环（电商交易全流程、用户账号注册与授权体系、售后退款全流程闭环）；
     - 支持自定义场景标题（`spec_title`）与自然语言业务流程描述；
   - **4 大核心 KPI 统计卡片**：
     - 时序执行步骤数；
     - 流程完整度评分（`flow_completeness_score_pct 0~100%`，达到 95% 高质量闭环）；
     - 上下文流转变量数（`${AUTH_TOKEN}`, `${ORDER_ID}` 等）；
     - 生成用例 ID 标识；
   - **左右双栏工作台布局 (Workbench Layout)**：
     - **左侧：时序依赖 DAG 步骤流转卡片**：展示每步接口端点、HTTP 方法、动态请求 Payload（含上游变量注入）、导向下游的变量映射与自动校验断言；
     - **右侧：自动合成 Python 自动化测试脚本预览器**：实时渲染可直接执行的 `pytest` + `httpx` 异步用例代码，配备**一键复制脚本**快捷功能。
2. **工作台集成 (`frontend/src/views/workbench/ApiWorkbenchView.vue`)**：
   - 工具栏挂载「E2E 用例合成」(`<RobotOutlined />`) 快捷入口；
   - 挂载 1120px 宽幅控制台抽屉。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/LLMSpecToE2ECaseSynthesizerDrawer.spec.ts`：**1 passed in 41ms**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed in 593ms**。
2. **TypeScript 严格类型检查**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean PASS**。
3. **生产环境完整构建**：
   - `npm run build` (`vite build`)：**✓ built in 3.07s, 0 errors**。
