# ATP v4.8.0 研发任务规划与执行计划 (2026-10-17)

## 1. 版本定位与目标

**ATP v4.8.0** 聚焦于自动化测试平台在经历连续多个重大架构功能演进（微服务自愈、全链路压测、单元化切流）后的**企业级 UI/UX 体验重构、设计系统归一化与认知降噪 (Developer Experience & Design System Consolidation)**。

彻底解决既有页面在 UI/UX 深度审查中识别出的 4 大核心痛点：
1. **工具栏按钮通胀与断行**：推行“渐进式披露 (Progressive Disclosure)”模式，采用主操作高亮 + 业务域分组下拉（Dropdown）收纳；
2. **非标原生标签混用断层**：肃清裸写 `<select>`、`<input>`、`<button>`，全量对齐 Ant Design Vue 4.x Design Token 体系与焦点环；
3. **Bento 网格信息层级与对比度失衡**：引入等宽数字排印（`tabular-nums`），修复次级文本对比度达到 WCAG 2.1 AA 4.5:1 标准，并补齐骨架屏（Skeleton）；
4. **数据大盘图表静态孤岛**：引入异常阈值基线（Threshold MarkLine）与图表到明细列表的点击穿透联动（Cross-filtering）。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：工具栏渐进式披露与操作认知降噪 (Toolbar Progressive Disclosure)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI1.1 `[x]` | **API 工作台工具栏分组收纳与渐进式披露重构** | `frontend/src/views/workbench/ApiWorkbenchView.vue` | 将 35+ 平铺按钮重构为 5 大业务域分组下拉（流量契约、混沌韧性、变异自愈、体验a11y、门禁集群），彻底消除断行，1440px 视口无溢出；单测通过；见 docs/evidence/api-workbench-toolbar-progressive-disclosure-ui1-1-2026-10-17.md |
| UI1.2 `[x]` | **性能测试工作台工具栏动作分级与高维诊断折叠** | `frontend/src/views/workbench/PerformanceWorkbenchView.vue` | 将新增的 5 大高维容量与熔断抽屉收纳为 3 大分组下拉菜单（单元调度容灾、容量熔断大脑、拐点爆炸半径），保持顶栏清爽极简；单测通过；见 docs/evidence/performance-workbench-toolbar-progressive-disclosure-ui1-2-2026-10-17.md |
| UI1.3 `[x]` | **报表中心与 Hermes 助手工具栏响应式与动作规范化** | `frontend/src/views/report/ReportCenterView.vue`, `HermesAssistantView.vue` | 统一工具栏高度、按钮间距节奏与主次视觉权重，优化小屏分辨率弹性换行；单测通过；见 docs/evidence/report-and-hermes-toolbar-standardization-ui1-3-2026-10-17.md |

---

### Phase 2：非标原生标签肃清与组件库基座归一化 (Component Consistency)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI2.1 `[x]` | **配置中心原生 HTML 标签肃清与 AntD 样式对齐** | `frontend/src/views/system/ConfigurationCenterView.vue` | 移除原生 `<select class="project-select-native">` 与原生 `<button class="button-light">`，全量对齐 `<a-select>` 与 `<a-button>`；单测通过；见 docs/evidence/configuration-center-antd-standardization-ui2-1-2026-10-17.md |
| UI2.2 `[x]` | **Hermes 计划草稿面板非标输入与复选框规范化** | `frontend/src/views/intelligence/components/HermesPlanDraftPanel.vue` | 移除 8 处原生 `<input>` 与 `<input type="checkbox">`，全量替换为 `<a-input>`, `<a-textarea>` 与 `<a-checkbox>`；单测通过；见 docs/evidence/hermes-plan-draft-panel-antd-standardization-ui2-2-2026-10-17.md |
| UI2.3 `[x]` | **全站 WCAG 2.1 AA 级对比度校准与主题变量升级** | `frontend/src/styles/theme.css` | 调整浅色模式 `--c-text-tertiary` 从 `#6e6b7b` 升级为 `#475569`（Slate 600），确保浅色背景对比度 ≥ 4.5:1，微调暗色边框与卡片层级；单测通过；见 docs/evidence/wcag-a11y-contrast-and-theme-tokens-ui2-3-2026-10-17.md |

---

### Phase 3：Bento 2.0 空间排版与交互加载质感升级 (Ergonomics & Loading)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[x]` | **全站 KPI 与统计卡片等宽数字字体与视觉锚点增强** | `frontend/src/styles/page-shell.css` | 为所有 `.kpi-value`, `.stat-card`, `.aggregate-report-value` 注入等宽数字 `font-variant-numeric: tabular-nums`，强化大号数值与辅助文字的反差梯度；单测通过；见 docs/evidence/bento-metric-tabular-numbers-typography-ui3-1-2026-10-17.md |
| UI3.2 `[x]` | **用例列表 Bento 统计卡与下方表格交互联动闭环** | `frontend/src/views/case/CaseList.vue` | 实现点击顶部 4 个 Bento Tile（全部用例、业务模块、待评审、Flaky抖动）自动作为过滤器联动过滤下方表格；单测通过；见 docs/evidence/caselist-bento-card-cross-filtering-ui3-2-2026-10-17.md |
| UI3.3 `[x]` | **核心页面与卡片骨架屏 (Skeleton) 预占位接入** | `frontend/src/views/dashboard/DashboardView.vue` 等 | 替换局部纯 Spinner 转圈为平滑骨架屏（`<a-skeleton>`），显著压降首屏异步渲染累积布局位移 (CLS)；单测通过；见 docs/evidence/dashboard-skeleton-loading-state-ui3-3-2026-10-17.md |

---

### Phase 4：数据大盘图表可解释性与穿透下钻 (Chart Cross-Filtering & Baselines)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI4.1 `[x]` | **质量大盘与报表折线图通过率/安全阈值基线接入** | `frontend/src/views/dashboard/DashboardView.vue`, `ReportCenterView.vue` | 在趋势折线图中增加 90% 合格基线（绿色 MarkLine）与 75% 警戒红线，提供直观的指标安全区间；单测通过；见 docs/evidence/dashboard-and-report-threshold-baselines-ui4-1-2026-10-17.md |
| UI4.2 `[x]` | **图表点击穿透联动表格筛选 (Cross-filtering) 闭环** | `frontend/src/views/dashboard/DashboardView.vue` | 点击失败原因、趋势、用例类型分布等扇区与数据点，自动联动跳转至运行/用例明细；单测通过；见 docs/evidence/dashboard-chart-cross-filtering-drilldown-ui4-2-2026-10-17.md |
| UI4.3 `[x]` | **v4.8.0 UI/UX 体验重构综合验收与发布说明** | 全局体验回归 | 执行全量前端测试与生产构建验证，归档发布说明与工程交付证据；见 docs/evidence/v4-8-0-ui-ux-consolidation-summary-acceptance-2026-10-17.md |

---

## 3. 质量门禁规则

1. **零破坏既有业务与测试**：所有重构均不得破坏既有 API 调用、状态流转与 E2E 流程；
2. **TypeScript 严格类型检查**：`npm run type-check` (`vue-tsc --noEmit`) 保持 0 错误；
3. **单元测试 100% 通过**：前端 200+ 测试套件与相关 spec.ts 100% PASS；
4. **生产环境构建通过**：`npm run build` (`vite build`) 成功生成 dist 产物；
5. **专项证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
