# ATP v4.5.0 研发任务规划与执行计划 (2026-10-17)

> 版本定位：**多模态视觉回归 Diff 审视大盘、页面布局越界与 Design Tokens 审查抽屉、无障碍 (a11y) WCAG 2.2 准入体检中心与客户端运行时 Web Vitals 全景体验看板 (Multimodal Visual Diff Inspection Board, Layout & Design Tokens Drawer, a11y WCAG 2.2 Health Check Center & Client Web Vitals Experience Dashboard)**
> 承接基准：以 v4.4.0 交付的像素级 SSIM Diff、动态掩码去噪、黄金基线演化追踪、VLM 页面语义断言、跨视口文本截断/碰撞检测、品牌设计系统 Tokens 与色彩对比度、WCAG 2.2 深度 DOM 扫描、屏幕阅读器焦点流转仿真、色盲感知多模态模拟、前端运行时长任务/TBT、内存泄漏/Detached DOM 与 Web Vitals 全景报告 12 大服务引擎与 REST API 为坚实底座，在 Vue 3 前端构建完整、优雅、专业的可视化抽屉、组件面板与全景监控大盘，达成端到端全栈工业级大闭环。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 多模态视觉回归像素级 Diff 与黄金基线演进审视大盘 (Visual Regression Diff & Baseline Inspection Board)**
  - 聚焦跨分辨率多视口像素级 SSIM 差异高亮与动态掩码忽略抽屉、黄金基线版本化演进追踪与跨分支视觉差异比对面板、以及多模态视觉回归与黄金基线管理全景大盘页面。
- **Phase 2: 页面语义完整性断言与布局越界/Design Tokens 审查抽屉 (VLM Assertion & Layout Tokens Drawer)**
  - 聚焦基于视觉大模型 (VLM) 的 UI 页面语义完整性推导断言配置抽屉、跨视口文本截断/元素重叠碰撞与横向溢出检测卡片、以及品牌设计系统 Tokens 与色彩对比度合规审查抽屉。
- **Phase 3: 深度无障碍访问 (a11y) WCAG 2.2 全面体检中心与色盲感知模拟控制台 (a11y WCAG 2.2 Health Check & CVD Console)**
  - 聚焦 WCAG 2.2 无障碍可访问性 DOM 深度扫描与修复指引抽屉、屏幕阅读器焦点流转与键盘死锁全盲路径仿真面板、以及色盲/色弱多模态视觉感知实时模拟与无障碍准入大盘页面。
- **Phase 4: 客户端运行时全息性能与 Web Vitals 体验监控大盘 (Client Performance & Web Vitals Dashboard)**
  - 聚焦前端运行时长任务 (Long Task) 堆栈下钻与 60 FPS 掉帧卡顿诊断抽屉、页面内存泄漏监控与 Detached DOM 幽灵引用探测卡片、以及 Google Core Web Vitals (LCP/INP/CLS) 全景体验审计大盘页面。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：多模态视觉回归像素级 Diff 与黄金基线演进审视大盘

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI1.1 `[x]` | **跨分辨率多视口像素级 SSIM 差异高亮与动态掩码忽略抽屉** | `visual_pixel_ssim_diff_engine` | 落地 `VisualPixelDiffInspectorDrawer.vue` 组件与 API 客户端；展示 Desktop/Tablet/Mobile 视口切换、差异像素红亮 Heatmap 覆盖层、动态 Mask 忽略区域打标；单测独立通过；见 docs/evidence/visual-pixel-diff-inspector-drawer-ui1-1-2026-10-17.md |
| UI1.2 `[x]` | **黄金基线版本化演进追踪与跨分支视觉差异比对面板** | `visual_golden_baseline_branch_tracker` | 落地 `VisualGoldenBaselineEvolutionPanel.vue` 组件与 API 客户端；展示主干 vs 特性分支视觉变迁流、基线晋升审批流（Promote to Golden Baseline）、差异类型徽章；单测独立通过；见 docs/evidence/visual-golden-baseline-evolution-panel-ui1-2-2026-10-17.md |
| UI1.3 `[x]` | **多模态视觉回归与黄金基线管理全景大盘页面** | `visual_regression_dashboard` | 落地 `VisualRegressionAuditDashboardView.vue` 视图与路由；汇总全站视觉 Diff 通过率、活跃黄金基线数、待审视视觉差异、一键全量回归；单测独立通过；见 docs/evidence/visual-regression-audit-dashboard-view-ui1-3-2026-10-17.md |

---

### Phase 2：页面语义完整性断言与布局越界/Design Tokens 审查抽屉

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI2.1 `[x]` | **基于视觉大模型 (VLM) 的 UI 页面语义完整性推导断言配置抽屉** | `vlm_ui_semantic_assertion_reasoner` | 落地 `VLMVisualSemanticAssertionDrawer.vue` 组件与 API 客户端；展示白屏检测、断图检测、自然语言断言配置卡片、视觉语义综合得分雷达图；单测独立通过；见 docs/evidence/vlm-visual-semantic-assertion-drawer-ui2-1-2026-10-17.md |
| UI2.2 `[x]` | **跨视口文本截断、元素重叠碰撞与横向溢出检测卡片** | `ui_layout_overflow_collision_detector` | 落地 `UILayoutCollisionDetectorCard.vue` 组件与 API 客户端；展示空间 AABB 碰撞交叠区域高亮、文本截断省略告警、移动端横向滚动条溢出标注、修复 CSS 快捷复制；单测独立通过；见 docs/evidence/ui-layout-collision-detector-card-ui2-2-2026-10-17.md |
| UI2.3 `[x]` | **品牌设计系统 (Design System Token) 与色彩对比度合规审查抽屉** | `design_system_token_contrast_checker` | 落地 `DesignSystemTokenAuditDrawer.vue` 组件与 API 客户端；展示字号/间距/圆角偏离标准 Token 散点图、前背景色 WCAG AA (4.5:1) 对比度指示器、标准 Token 智能对齐建议；单测独立通过；见 docs/evidence/design-system-token-audit-drawer-ui2-3-2026-10-17.md |

---

### Phase 3：深度无障碍访问 (a11y) WCAG 2.2 全面体检中心与色盲感知模拟控制台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[x]` | **WCAG 2.2 无障碍可访问性 DOM 深度扫描与修复指引抽屉** | `wcag_accessibility_deep_scanner` | 落地 `WcagA11yDeepScannerDrawer.vue` 组件与 API 客户端；展示缺少 alt、表单无标签、触控热区 <24x24px、重复 ID 清单、一键复制修复代码；单测独立通过；见 docs/evidence/wcag-a11y-deep-scanner-drawer-ui3-1-2026-10-17.md |
| UI3.2 `[ ]` | **屏幕阅读器焦点流转与键盘死锁全盲路径仿真面板** | `a11y_keyboard_navigation_path_verifier` | 落地 `A11yKeyboardNavPathPanel.vue` 组件与 API 客户端；展示虚拟键盘 Tab 步进流转轨迹图、Focus Trap 死锁告警、无高亮焦点环高亮警告；单测独立通过。 |
| UI3.3 `[ ]` | **色盲/色弱多模态视觉感知实时模拟与无障碍准入大盘页面** | `color_blindness_simulation_classifier` | 落地 `ColorBlindnessAuditDashboardView.vue` 视图与路由；提供红盲、绿盲、蓝盲、全色盲 4 分屏滤镜实时预览、WCAG 1.4.1 单色状态指示器违规警报；单测独立通过。 |

---

### Phase 4：客户端运行时全息性能与 Web Vitals 体验监控大盘

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI4.1 `[ ]` | **前端运行时长任务 (Long Task) 堆栈下钻与 60 FPS 掉帧卡顿诊断抽屉** | `client_long_task_jank_profiler` | 落地 `ClientLongTaskJankProfilerDrawer.vue` 组件与 API 客户端；展示超过 50ms 长任务耗时火焰图、总阻塞时间 (TBT) 评级仪表、掉帧率量化、强制布局与 Canvas 归因；单测独立通过。 |
| UI4.2 `[ ]` | **页面内存泄漏监控与 Detached DOM 幽灵引用探测卡片** | `client_memory_leak_dom_detachment_detector` | 落地 `ClientMemoryLeakDetectorCard.vue` 组件与 API 客户端；展示 JS Heap 增长折线图、未释放事件监听器计数、脱落游离 DOM 树节点闭包样本；单测独立通过。 |
| UI4.3 `[ ]` | **Google Core Web Vitals (LCP/INP/CLS) 全景体验审计大盘页面** | `web_vitals_experience_audit_reporter` | 落地 `ClientWebVitalsExperienceDashboardView.vue` 视图与路由；展示三大核心指标（LCP/INP/CLS）红黄绿评级、加权性能体验分、Markdown 报告一键导出；单测独立通过。 |

---

## 3. 质量门禁规则

1. **类型检查与前端编译**：前端组件与路由严格执行 `npm run type-check` (`vue-tsc --noEmit`) 零错误；`npm run build` (`vite build`) 成功构建。
2. **组件单元测试**：所有新增组件均配备对应的 `*.spec.ts` 单元测试，Vitest 运行 100% PASS。
3. **路由与导航无缝接入**：所有视图页面接入 `frontend/src/router/index.ts` 并同步至 `frontend/src/layouts/navigation.ts`。
4. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
