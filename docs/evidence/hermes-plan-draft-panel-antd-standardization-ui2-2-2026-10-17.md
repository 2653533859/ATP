# UI2.2 Hermes 计划草稿面板非标输入与复选框规范化验收 (2026-10-17)

## 概述与结论

UI2.2（Hermes 计划草稿面板非标输入与复选框规范化 `HermesPlanDraftPanel.vue`）已全量交付并完成验证，持续推进 **ATP v4.8.0 Phase 2（非标原生标签肃清与组件库基座归一化）**：
1. **解决核心痛点（清理面板内遗留的 8 处原生 HTML 控件）**：
   - 彻底解决 `frontend/src/views/intelligence/components/HermesPlanDraftPanel.vue` 中遗留的裸写 `<input>` 与 `<input type="checkbox">` 问题；
   - **计划名称与目标输入框标准化**：将原生 `<input>` / `<textarea>` 升级为 `<a-input v-model:value="draft.name" :maxlength="256">` 与 `<a-textarea v-model:value="draft.objective" :maxlength="2000" :rows="3">`，无缝继承 Bento Box 聚焦微光环；
   - **计划测试点输入框标准化**：多项测试点输入列表全量升级为 `<a-input>`；
   - **复选框全量标准化**：推荐套件建议、范围模块、用例草稿选择以及回归范围全量替换为 `<a-checkbox v-model:checked="...">`，消除样式断层；
   - **用例草稿标题与预期标准化**：用例草稿条目内的标题与预期输入框均升级为 AntD `<a-input>`，提升编辑质感。
2. **测试与类型安全保护**：
   - 适配 `HermesWorkbenchPanels.spec.ts`，在 `globalStubs` 中增加对 `AInput`, `ATextarea`, `ACheckbox` 双向绑定的仿真支持，5 个用例 100% PASS。
   - `HermesAssistantView.spec.ts` 25 个用例 100% PASS。

## 质量与测试门禁验证

1. **组件单元测试 (`HermesWorkbenchPanels.spec.ts` & `HermesAssistantView.spec.ts`)**：
   - `HermesWorkbenchPanels.spec.ts`：5 passed in 72ms；
   - `HermesAssistantView.spec.ts`：25 passed in 553ms；
   - 总体 Vitest 套件：**30 passed 100%**。
2. **TypeScript 严格类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass!
3. **生产环境构建 (`vite build`)**：
   - 成功编译 4509 个模块，产物完整生成，耗时 3.65s，零构建错误。
