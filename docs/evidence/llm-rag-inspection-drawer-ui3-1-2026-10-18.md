# UI3.1 RAG 检索召回与上下文溯源透视抽屉验收 (2026-10-18)

## 概述与交付物

UI3.1（RAG 检索召回与上下文溯源透视抽屉）已全量研发交付并通过各项前端与工程门禁，**正式开启 ATP v6.3.0 Phase 3（大模型智能体评测全景大盘与红蓝攻防工作台）**：
1. **组件落地实现 (`frontend/src/views/workbench/components/LlmRagInspectionDrawer.vue`)**：
   - **RAG 三元组顶部 Hero 横幅**：
     - 实时呈现三元组综合评分（Composite Score）、评级标签（EXCELLENT/GOOD/MARGINAL/POOR）；
     - 上下文相关度（Context Relevance %）、知识忠实度（Groundedness %）、回答准确度（Answer Relevance %）与命中 Chunk 块数统计；
   - **Tab 1: 检索 Chunk 相关度热力透视**：
     - 展示原始用户评测 Query；
     - 遍历展示检索匹配知识块（Chunk ID、所属文档来源、相关度得分热力色彩进度条及正文内容）；
   - **Tab 2: 模型回答事实引用溯源**：
     - 完整展示模型生成回答全文；
     - 表格细分展示断言事实句（Claim Attributions）、支撑 Chunk 标签（点击一键定位跳转）与匹配证据重合度解释；
   - **Tab 3: 事实一致性与冲突检出详情**：
     - 幻觉偏离率（Hallucination Rate %）、事实一致性得分、极性矛盾检出数与虚构实体检出数 KPI 概览；
   - **设计系统对齐**：
     - 100% 遵循设计系统规范变量（`--c-primary`、`--c-bg-card`、`--c-border`、`--c-success`、`--c-warning`、`--c-error`）；
     - 保持 `font-mono` 与 `tabular-nums` 数值排版。

## 质量与测试门禁验证

1. **前端单元测试**：
   - `src/views/workbench/components/LlmRagInspectionDrawer.spec.ts`：**5 passed in 2.21s (100% PASS)**。
2. **前端类型与工程门禁**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean pass!**；
   - `npm run build` (`vite build`)：**4644 modules transformed, built in 21.42s, 0 errors!**。
