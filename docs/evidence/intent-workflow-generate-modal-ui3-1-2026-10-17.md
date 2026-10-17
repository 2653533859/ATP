# UI3.1 自然语言对话式工作流生成弹窗组件验收 (2026-10-17)

## 概述与交付物

UI3.1（自然语言对话式工作流生成弹窗组件）已全量研发交付并与核心混合工作流编排工作台集成，**达成 ATP v5.2.0 Phase 3 首个关键里程碑**：
1. **核心弹窗组件 (`frontend/src/views/workbench/components/IntentWorkflowGenerateModal.vue`)**：
   - **意图输入与业务预设**：提供自然语言多行输入框，内置“电商端到端履约”、“金融风控与转账”、“移动端多协议对账”、“分布式微服务容灾”四大快捷模板；
   - **AI 语义推导洞察卡片**：展示 Synthesis ID、业务领域识别（如 `ecommerce`）、跨端协议矩阵徽标（`HTTP`, `Web`, `iOS`, `Android`, `SQL`）与拓扑规模（节点数、有向边数、动态变量依赖数）；
   - **DAG 节点流动态预览**：支持 8 大节点类型（REST API, gRPC, Web UI, Android, iOS, SQL, 分支, 延时）的彩色徽标识别、时序流转箭头指示与跨节点动态变量传递高亮（`{{node_1.output.body.order_id}}`）；
   - **对话式自然语言微调与迭代**：支持在生成结果下方直接输入微调指令（如“在支付前追加一个延时等待 500ms”），实时调用 `/refine` 接口局部刷新工作流拓扑；
   - **一键应用至编排画布**：触发 `applied` 事件，将生成的节点与连线无缝注入工作流画布并给出全局成功提示。
2. **API 客户端层 (`frontend/src/api/intentWorkflow.ts`)**：
   - 封装 `/workflow/intent/generate`、`/workflow/intent/refine`、`/workflow/intent/{synthesis_id}` 以及自主探索系列 REST 接口的强类型 DTO 与方法。
3. **工作台深度集成 (`frontend/src/views/workbench/HybridWorkflowWorkbenchView.vue`)**：
   - 顶部工具栏注入“AI 意图驱动生成”快捷入口；
   - 编排画布 (`HybridWorkflowDragCanvas.vue`) 暴露 `loadSynthesizedWorkflow` 挂载方法，实现一键从自然语言生成到画布编辑的端到端闭环。

## 质量与测试门禁验证

1. **前端单元测试**：
   - `frontend/src/views/workbench/components/IntentWorkflowGenerateModal.spec.ts`：5 passed；
   - `frontend/src/views/workbench/HybridWorkflowWorkbenchView.spec.ts`：4 passed；
   - `frontend/src/views/workbench/components/HybridWorkflowDragCanvas.spec.ts`：3 passed；
   - `frontend/src/views/workbench/components/VisualCoverageGapInspectorDrawer.spec.ts`：3 passed；
   - **累计 15 passed across 4 spec files (100% PASS)**。
2. **TypeScript 强类型检查**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean pass!**
3. **生产环境构建检查**：
   - `npm run build` (`vite build`)：**4544 modules transformed, built in 3.71s, 0 errors.**
