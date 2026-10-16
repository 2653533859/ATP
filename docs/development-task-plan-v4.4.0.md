# ATP v4.4.0 研发任务规划与执行计划 (2026-10-17)

> 版本定位：**多模态视觉 UI 跨分辨率像素级 Diff 与动态基线审计、AI 智能视觉断言与布局越界检测、无障碍 (a11y) 深度扫描与客户端性能全息度量引擎 (Multi-Modal Visual UI Pixel Diff & Dynamic Baseline Auditor, VLM Visual Assertion & Layout Defect Detector, Deep Accessibility Scanner & Client-Side Holistic Performance Profiler)**
> 承接基准：以 v4.2.0 / v4.3.0 交付的云原生弹性测试执行集群、跨环境配置/Schema 漂移治理、大模型用例生成与发版准入门禁为坚实底盘，进一步向多模态视觉 UI 质量、跨视口响应式布局演进、WCAG 2.2 无障碍合规与客户端运行时全息体验度量纵深推进，打造完整的立体式智能质量工程闭环。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 多模态视觉 UI 跨分辨率像素级 Diff 与动态智能去噪引擎 (Multi-Modal Visual Pixel Diff & Anti-Noise Dynamic Baseline Engine)**
  - 聚焦跨桌面端/平板/移动端多视口屏幕快照捕获与像素级 SSIM 结构相似性比对、动态忽略区域掩码与抗锯齿渲染微噪声过滤、以及多版本视觉黄金基线快照管理。
- **Phase 2: 基于大模型视觉多模态 (VLM) 的智能断言与 UI 布局越界/重叠检测 (VLM Visual Assertion & Layout Defect Detector)**
  - 聚焦视觉大模型端到端 UI 页面语义完整性推理与视觉断言、跨视口文本截断/元素重叠与布局溢出 (Layout Overflow) 智能探查、以及设计系统 Token 与色彩对比度合规检查。
- **Phase 3: 深度无障碍访问 (a11y) 全面自动化扫描与 WCAG 2.2 合规准入审计 (Deep Accessibility & WCAG Compliance Auditor)**
  - 聚焦基于 WCAG 2.2 标准的无障碍 DOM 深度扫描、屏幕阅读器焦点流转与键盘导航路径验证、以及色盲/色弱多模态视觉感知模拟缺陷分类。
- **Phase 4: 客户端运行时全息性能分析与用户体验感知度量引擎 (Client-Side Runtime Holistic Performance Profiler)**
  - 聚焦前端运行时长任务 (Long Task) 与主线程掉帧卡顿 (Jank) 诊断、页面内存泄漏与 DOM 节点脱落幽灵引用探测、以及 Web Vitals (LCP, INP, CLS) 全景审计报告生成。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：多模态视觉 UI 跨分辨率像素级 Diff 与动态智能去噪引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **跨分辨率视口快照捕获与像素级 SSIM 结构相似度比对器** | `visual_pixel_ssim_diff_engine` | 落地 `visual_pixel_ssim_diff_engine` 服务与 `/visual/pixel-diff/*` API；支持 Desktop/Tablet/Mobile 多视口像素比对、计算结构相似度 (SSIM 0~1.0) 与差异像素高亮图生成；单测独立通过；见 docs/evidence/visual-pixel-ssim-diff-engine-t1-1-2026-10-17.md |
| T1.2 `[x]` | **动态忽略区域掩码与抗锯齿渲染微噪声过滤去噪器** | `visual_anti_aliasing_noise_filter` | 落地 `visual_anti_aliasing_noise_filter` 服务与 `/visual/noise-filter/*` API；自动识别动态时间戳、轮播图区域并打标 Mask 掩码，过滤抗锯齿边缘引发的假阳性误报；单测独立通过；见 docs/evidence/visual-anti-aliasing-noise-filter-t1-2-2026-10-17.md |
| T1.3 `[x]` | **多版本视觉黄金基线快照管理与跨分支差异演变追踪器** | `visual_golden_baseline_branch_tracker` | 落地 `visual_golden_baseline_branch_tracker` 服务与 `/visual/baselines/*` API；支持多视口基线版本化打标、跨分支快照比对与历史视觉回归变迁审计；单测独立通过；见 docs/evidence/visual-golden-baseline-branch-tracker-t1-3-2026-10-17.md |

---

### Phase 2：基于大模型视觉多模态 (VLM) 的智能断言与 UI 布局越界/重叠检测

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **基于视觉大模型 (VLM) 的 UI 页面语义完整性断言推理器** | `vlm_ui_semantic_assertion_reasoner` | 落地 `vlm_ui_semantic_assertion_reasoner` 服务与 `/visual-ai/semantic-assertion/*` API；基于视觉多模态对全页截图执行元素完整性、白屏缺失与错位语义推导断言；单测独立通过；见 docs/evidence/vlm-ui-semantic-assertion-reasoner-t2-1-2026-10-17.md |
| T2.2 `[x]` | **跨视口文本截断、元素重叠与布局溢出碰撞检测器** | `ui_layout_overflow_collision_detector` | 落地 `ui_layout_overflow_collision_detector` 服务与 `/visual-ai/layout-collision/*` API；基于 BoundingBox 空间坐标与盒模型计算，精准探查文本截断省略、组件层级碰撞重叠与视口水平溢出；单测独立通过；见 docs/evidence/ui-layout-overflow-collision-detector-t2-2-2026-10-17.md |
| T2.3 `[x]` | **品牌设计系统 (Design System Token) 与色彩对比度检查器** | `design_system_token_contrast_checker` | 落地 `design_system_token_contrast_checker` 服务与 `/visual-ai/design-tokens/*` API；验证字号间距圆角 Design Tokens 合规度，计算前景色/背景色 WCAG 对比度 (≥4.5:1)；单测独立通过；见 docs/evidence/design-system-token-contrast-checker-t2-3-2026-10-17.md |

---

### Phase 3：深度无障碍访问 (a11y) 全面自动化扫描与 WCAG 2.2 合规准入审计

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T3.1 `[x]` | **基于 WCAG 2.2 标准的无障碍可访问性 DOM 深度扫描器** | `wcag_accessibility_deep_scanner` | 落地 `wcag_accessibility_deep_scanner` 服务与 `/a11y/wcag-scanner/*` API；全面检查缺少 alt、表单无关联 label、aria 属性失效、空按钮链接等无障碍违规项并评级；单测独立通过；见 docs/evidence/wcag-accessibility-deep-scanner-t3-1-2026-10-17.md |
| T3.2 `[ ]` | **屏幕阅读器焦点流转与键盘全盲导航路径可达性验证器** | `a11y_keyboard_navigation_path_verifier` | 落地 `a11y_keyboard_navigation_path_verifier` 服务与 `/a11y/keyboard-nav/*` API；仿真 Tab 键序列化焦点流转，探测键盘陷阱 (Focus Trap)、跳过导航缺失与不可见焦点缺陷；单测独立通过。 |
| T3.3 `[ ]` | **色盲/色弱多模态视觉感知模拟与低视力辅助缺陷分类器** | `color_blindness_simulation_classifier` | 落地 `color_blindness_simulation_classifier` 服务与 `/a11y/color-blindness/*` API；模拟红绿色盲、全色盲与低对比度视觉感知，检测仅依赖颜色传达关键状态的无障碍违规；单测独立通过。 |

---

### Phase 4：客户端运行时全息性能分析与用户体验感知度量引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **前端运行时长任务 (Long Task) 与主线程掉帧卡顿诊断器** | `client_long_task_jank_profiler` | 落地 `client_long_task_jank_profiler` 服务与 `/client-perf/long-tasks/*` API；捕获超过 50ms 的 Long Task 堆栈，量化主线程阻塞时间 (TBT) 与 FPS 掉帧卡顿归因；单测独立通过。 |
| T4.2 `[ ]` | **页面内存泄漏与 DOM 节点脱落幽灵引用智能探测器** | `client_memory_leak_dom_detachment_detector` | 落地 `client_memory_leak_dom_detachment_detector` 服务与 `/client-perf/memory-leak/*` API；监控 JS Heap 增长曲线、未解绑事件监听器与 Detached DOM 幽灵节点泄露；单测独立通过。 |
| T4.3 `[ ]` | **核心体验 Web Vitals (LCP/INP/CLS) 全景审计报告生成器** | `web_vitals_experience_audit_reporter` | 落地 `web_vitals_experience_audit_reporter` 服务与 `/client-perf/web-vitals-report/*` API；汇总量化 Google Web Vitals 核心指标，输出体验达标率与针对性性能调优指引；单测独立通过。 |

---

## 3. 质量门禁规则

1. **代码风格与规范**：所有代码严格执行 `ruff format` 与 `ruff check`，无任何未忽略告警。
2. **类型检查**：新增服务与 API 严格遵从类型注解，`mypy` 校验保持零错误通过。
3. **单元测试与全覆盖**：所有新增服务均配备对应的 `test_*.py` 单元测试，Pytest 独立与全套件运行 100% PASS。
4. **无缝路由挂载**：所有 REST API 规范挂载于 `/api/v1` 路由树下。
5. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
