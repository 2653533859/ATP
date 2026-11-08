# ATP 界面去 Slop（Unslopping）系统化改造开发文档

## 一、改造背景与定位

根据对当前 ATP 前端代码的深入审计，界面存在较为典型的 Vibecoded / AI 模板化问题（如紫粉渐变色块、全局扩散发光 Glow、大写加宽字距 Uppercase wide tracking、散落的装饰 Emoji、多色彩虹卡片边框、以及带刘海和彩色方块 App 的虚假 CSS 手机模型）。

本改造计划旨在去除浮躁与装饰性干扰，将 ATP 重塑为一个**精准、克制、高信息密度的工业级自动化测试平台**。

### 核心设计宪章（Direction）
- **Product（产品）**：ATP 是面向工程与测试团队的高可用自动化测试效能平台，覆盖接口场景编排、UI/移动端测试、真实设备矩阵与质量治理。
- **Character（气质）**：精确、克制、工程感（calm, exact, technical）。
- **World（领域归属）**：专业测控台与自动化仪器。使用沉稳的石墨灰中性阶梯（Graphite Ramp）与专业工程蓝（#2563eb / #3b82f6），杜绝紫粉渐变与发光微光。
- **Moments（视觉聚焦点）**：真实的测试步骤执行管道、高信息密度的指标与缺陷趋势折线、真实的设备遥测与日志流。
- **Signature（专属细节）**：对齐严谨的平整实心状态指示点（Status dot）与微型等宽代码标签（Mono tag），杜绝发光外圈。

---

## 二、Unslop 9-Pass 实施规范

在每一个视图和组件的改造中，严格遵循以下 9 步走查与重构规范：

1. **Spacing（间距）**：严格依循 4px 格栅系统（4, 8, 12, 16, 20, 24, 32px）；同类元素统一内边距与间距；对齐图标、标签与数值列。
2. **Color（色彩）**：单一套石墨中性色阶；全局仅保留一个主工程强调色；删除全色渐变、发光（Glow）、径向扩散（Radial wash）；语义色（红/黄/绿）只承载语义。
3. **Icons（图标）**：全面移除 Emoji 装饰，统一使用 AntD Line Icons；固定图标框尺寸，与文字严格居中对齐。
4. **Copy（文案）**：清除 AI 夸张口吻与套话；清除无意义惊叹号与短文本句号；采用真实严谨的工程术语。
5. **Type（排版）**：界面字体字重收敛为 400（常规）与 500（中粗）；清除所有的 `text-transform: uppercase` 配合宽字距；所有数值均采用 `tabular-nums` 避免抖动。
6. **Layout（布局）**：保持已有功能区块与流转，强化桌面工程工具比例；去除浮夸 Bento 盒卡片跳动。
7. **Details（细节）**：圆角遵循内外嵌套收敛原则（内圆角 = 外圆角 - 间距），一般为 6px ~ 10px；清除卡片角落伪元素切角圆圈。
8. **Visuals（视觉呈现）**：删除伪造的 CSS 手机模型（Notch、假摄像头、彩色假 App 块），替换为真实的设备技术遥测卡片与 ADB 状态板。
9. **Motion（动效）**：移除所有卡片 hover 时的 `translateY(-2px)` 与大阴影浮起；过渡仅限于 0.15s~0.2s 的表面色/边框微妙变化。

---

## 三、改造任务分解与实施清单

### Phase 1: 设计系统基建与 Token 净化 (Tokens & Shell Foundation)
- [x] **`frontend/src/styles/theme.css`**
  - 清理 `--c-primary-glow`、`--shadow-glow`、`--c-ai: #ec4899` 等发光/霓虹变量。
  - 重设 `--c-primary`、`--c-bg-*`、`--c-border-*`、`--c-text-*` 为石墨中性色阶。
  - 清除 `.ant-btn-primary` 的 `box-shadow` 发光微光。
  - 清除 `.ant-table-thead th` 的 `uppercase` 与加宽字距。
- [x] **`frontend/src/styles/page-shell.css`**
  - 移除 `.stat-card:hover`、`.kpi-card:hover` 的 `transform: translateY(-2px)` 及浮动投影。
  - 规范基础卡片与工具栏的 4px 阶梯间距。
- [x] **`frontend/src/App.vue`**
  - 校准 Ant Design Vue 的 `ConfigProvider` 主题 Token（主色、圆角、字号）。

### Phase 2: 框架壳层与多语言文案净化 (Layout, Chrome & Locales)
- [x] **`frontend/src/views/auth/LoginView.vue`**
  - 移除背景两处巨大的 `radial-gradient` 弥散斑块。
  - 移除 Logo 的紫粉渐变与紫色大投影，采用扁平工整的实心徽标。
- [x] **`frontend/src/layouts/MainLayout.vue`**
  - 顶栏与侧栏 Brand Logo 移除紫粉渐变与光晕。
  - 运行状态指示点（在线/离线/降级）移除荧光扩散外圈（`box-shadow: 0 0 6px ...`）。
  - Worker 进度条与头像移除彩虹水平渐变。
- [x] **`frontend/src/locales/{zh-CN,en-US}.ts`**
  - 全局清理 Emoji 标签（`✨ AI`, `⚡`, `🌐`, `📁`, `💡`, `🟢` 等）。

### Phase 3: 核心看板与用例管理去 Slop (Dashboard & Cases)
- [x] **`frontend/src/views/dashboard/DashboardView.vue`**
  - 移除 KPI 卡片与快捷入口卡片的 Hover `translateY(-2px)`。
  - 移除状态点荧光光晕，规范数值等宽字体 `tabular-nums`。
- [x] **`frontend/src/views/case/CaseList.vue` & `CaseDetail.vue`**
  - 移除用例列表上的 `✨ AI` 芯片标签。
  - 清理 `.case-bento-tile` 样式，移除大写加宽标签与卡片悬浮跳动。
- [x] **`frontend/src/components/common/CaseFormDrawer.vue` & `ApiScenarioPipeline.vue`**
  - 清理预设项中的 Emoji（`📋`, `🔑`, `🛡️`, `🩺` 等），替换为 AntD 线性图标。
  - 规范流水线步骤指示卡片。

### Phase 4: 设备矩阵遥测化与工作台彩虹卡清理 (Workbenches, Device Mockup & Reports)
- [x] **`frontend/src/views/device/components/DeviceMatrixPanel.vue`**
  - 彻底删除 CSS 手机外壳（Notch/听筒/摄像头）与 6 个彩色假 App 方块。
  - 重构为技术遥测面板：真实 ADB 状态、延迟、分辨率、电池、占用人和明确操作按钮。
- [x] **`frontend/src/views/workbench/AIWorkbenchView.vue`**
  - 拆除 `.signal-card-violet/blue/amber/green` 四色彩虹顶边卡片，统一为中性卡片。
  - 移除漏斗条内的紫粉/青绿渐变色，移除 `uppercase wide-tracking`。
- [x] **`frontend/src/views/report/ReportCenterView.vue`**
  - 删除全色渐变指标卡（`.metric-card-indigo/teal/amber`）及角落伪元素半圆环切线。
- [x] **`frontend/src/views/case/CaseReviewWorkbench.vue` & `RequirementTraceabilityView.vue`**
  - 清除卡片角落利用 `::after` 绘制的 110px 装饰性圆形色块。

### Phase 5: 智能中心专业化重构 (Intelligence Center & Hermes)
- [x] **`frontend/src/views/intelligence/AiChatView.vue`**
  - 重写空态文案，删除“自由闲聊模式”等非专业口吻。
  - 移除预设 Prompt 上的 Emoji（`💡`, `🧪`, `🔍`, `🚀`），替换为 AntD 图标。
- [x] **`frontend/src/views/intelligence/components/HermesConversationPanel.vue`**
  - 移除青紫渐变发光头像，采用沉静工程色；优化消息气泡与代码块阅读体验。

### Phase 6: 全局类型检查与构建测试验证 (Verification)
- [x] 运行 `npm run type-check` (`vue-tsc --noEmit`) 验证零类型错误。
- [x] 运行 `npm run build` 确保前端构建与样式打包无损。
- [x] 运行前端单元测试与关键视图验证。

### Phase 7: 长尾边缘视图与次级标签排版净化 (Long-tail Views & Kickers)
- [x] **`AppWorkbenchView.vue` & `UiWorkbenchView.vue`**：清理 `.signal-label`、`.strip-label`、`.case-list-head` 的大写加宽字距，移除卡片跳跃与状态发光。
- [x] **`ApiWorkbenchView.vue`、`TaskCenterView.vue`、`WorkbenchTodosView.vue`**：收敛 `.column-kicker`、`.eyebrow`、`.detail-block-title`，规范等宽数字与间距。
- [x] **`NavigationPlaceholderView.vue` & `KnowledgeHubView.vue`**：移除顶部径向渐变光晕斑块，收敛占位页与知识库标签排版。
- [x] **`StartupConfigView.vue`、`ApiContractAssetsView.vue`、`ConfigurationCenterView.vue`**：移除渐变进度条与宽字距大写标签，规范配置中心与契约比对面板。

### Phase 8: 深度精修——图表色阶、子工作台私有色板归口与全站字重收敛 (Deep Polish Mode)
- [x] **全局图表主题与看板主次节奏 (`chartTheme.ts` & `DashboardView.vue`)**
  - 重构 `LIGHT_PALETTE` 与 `DARK_PALETTE`，移除旧版 Indigo 紫粉彩虹 8 色，确立以单一工程蓝（`#2563eb` / `#3b82f6`）为主导、石墨中性色阶（`#64748b` / `#94a3b8`）与克制语义色为辅的工业级图表配色，坐标轴刻度统一为 `11px` `JetBrains Mono` 等宽字体。
  - 遵循“单图单主色（One accent per chart）”原则：Dashboard 通过率与汇总趋势图中主折线采用工程蓝，次级执行量柱状图收敛为半透明石墨灰 `rgba(148, 163, 184, 0.45)`（兼顾深浅双模式 WCAG 1.4.11 图形对比度）；移除快捷卡片图标 Hover `scale(1.06)` 缩放。
- [x] **子工作台私有色板清理与深色模式适配 (`KnowledgeHubView.vue`, `RequirementTraceabilityView.vue`, `ConfigurationCenterView.vue`, `CaseReviewWorkbench.vue` 等)**
  - 清除各子页面孤立定义的 `--aqua`、`--copper`、`--olive`、`--coral`、`--teal`、`--violet` 等私有色板与仅适配浅色模式的马卡龙硬编码底色（`#eef0f8`、`#fff4e8`、`#fcfaff` 等），全量归口至 `--c-bg-subtle`、`--c-primary-soft` 与语义软底色 Token。
  - 移除 `PerformanceCenterView.vue`、`RemoteToolboxView.vue`、`ReportDetailView.vue` 中最后 3 处 `linear-gradient` 背景，以及 `AppWorkbenchView.vue`、`PerformanceWorkbenchView.vue`、`ReportDetailView.vue` 中状态圆点的 `box-shadow` 光晕与 `live-pulse` 呼吸动画。
  - 修复 `RemoteToolboxView.vue` 历史遗留重复按钮样式与 `ConfigurationCenterView.vue` 差异徽章语义文字颜色对齐。
- [x] **全站字重封顶 600、圆角统一与零悬浮位移**
  - 将全站 35 个组件中残余的 90+ 处 `font-weight: 700` / `750` / `800` / `900` 统一收敛至 `600`（正文与常规标签保持 `400`/`500`）。
  - 将知识库、需求追踪、评审工作台、测试报告中残留的 `14px`–`18px` 大圆角面板统一收敛为 `var(--radius-lg)` (`8px`)。
  - 清除 `ProjectList.vue`、`DefectListView.vue`、`RemoteToolboxView.vue`、`ApiLibraryPickerDrawer.vue`、`AiChatView.vue` 中残余的 Hover `translateY` 位移。
