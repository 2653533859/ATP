# UI4.1 UI 元素定位漂移动态自愈推导与降级重试控制台验收 (2026-10-16)

## 概述与结论

UI4.1（UI 元素定位漂移动态自愈推导与降级重试控制台）已完成全量交付与验证，正式开启 **ATP v4.1.0 最后一个收官阶段：Phase 4（AI 驱动的用例脚本断言自愈与代码级自动修复补丁大盘）**：
1. **API 客户端扩展 (`frontend/src/api/testSelfHealing.ts` & `frontend/src/api/index.ts`)**：
   - 建立 `TargetElementSpec`、`CandidateElementItem`、`StrategyScoreBreakdown`、`LocatorHealingResult`、`HealingStatistics` 等强类型接口契约；
   - 封装 `smartLocatorHealingApi` 客户端方法：`heal`、`getHistory` 与 `clearHistory`；
   - 同时声明 `adaptiveAssertionPatchApi` 与 `selfHealingPipelineApi` 为后续任务奠定通用底盘。
2. **选择器自愈与降级重试控制台抽屉 (`SmartLocatorHealingConsoleDrawer.vue`)**：
   - **头部 Header & 5 维加权降级策略微卡片**：
     - `📝 文本语义 (30%)`：可见文本归一化 Levenshtein 模糊相似度；
     - `🎯 TestID 标识 (25%)`：`data-testid` / `data-test` 唯一稳定性特征；
     - `🏷️ 标签角色 (15%)`：HTML TagName 与 ARIA Role 规范对齐；
     - `🧬 属性指纹 (15%)`：name / placeholder / title 辅助属性匹配；
     - `📐 空间邻域 (15%)`：外接矩形中心欧氏几何距离衰减；
   - **典型演练预设场景**：
     - `场景 1: 文本语义优先 (ID 变动态哈希，文本保持 "立即提交订单")`；
     - `场景 2: TestID 优先 (data-testid 稳定优先命中)`；
     - `场景 3: 空间邻域优先 (同名加购按钮，靠近原屏幕坐标者胜出)`；
     - `场景 4: 无关节点安全拒绝 (置信度不足拒绝误命中)`；
   - **自愈裁决大横幅 (Verdict Banner)**：
     - 自愈状态徽章（绿色 HEALED / 红色 UNRESOLVED）；
     - 综合置信度得分（如 `79%` ≥ 68%）；
     - 失效旧定位器 vs 自愈新选择器（`[data-testid='...']` 或 `//button[contains(normalize-space(), '...')]`）并排对比，支持一键复制新选择器；
     - 降级重试执行结果反馈；
   - **五维策略得分细目分解 (Score Breakdown)**：5 个微进度条展示各维度加权得分与贡献；
   - **代码级自愈补丁预览 (Playwright / Selenium Patch)**：展示 Python 自动化脚本代码级修复补丁，支持一键复制代码；
   - **全网自愈引擎运行指标统计**：展示累计自愈尝试总数、修复成功数与全网自愈成功率（100.0% ≥ 90%）。
3. **工作台集成 (`ApiWorkbenchView.vue`)**：
   - 顶部工具栏挂载「选择器自愈」入口；
   - 支持一键滑出 1120px 宽幅控制台抽屉。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/SmartLocatorHealingConsoleDrawer.spec.ts`：**2 passed in 67ms**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed**；
   - 工作台核心测试套件：**14 passed in 601ms**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 10.92s, 0 errors**。
