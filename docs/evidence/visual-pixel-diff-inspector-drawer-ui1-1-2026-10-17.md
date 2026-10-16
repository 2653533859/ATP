# UI1.1 跨分辨率多视口像素级 SSIM 差异高亮与动态掩码忽略抽屉验收 (2026-10-17)

## 概述与结论

UI1.1（跨分辨率多视口像素级 SSIM 差异高亮与动态掩码忽略抽屉 `VisualPixelDiffInspectorDrawer.vue`）已完成全量交付与验证，正式启动 **ATP v4.5.0 Phase 1（多模态视觉回归像素级 Diff 与黄金基线演进审视大盘）**：
1. **核心组件实现 (`frontend/src/views/workbench/components/VisualPixelDiffInspectorDrawer.vue`)**：
   - **多视口分辨率快速切换与对比视窗**：
     - 支持 Desktop (1920×1080)、Tablet (1280×720)、Mobile (375×812) 三档视口无缝切换；
     - 黄金基线快照（Golden Baseline）与当前运行快照双屏对照，叠加红色半透明差异像素 Heatmap 覆盖层；
   - **4 项核心 KPI 体验指标仪表盘**：
     - 综合判定结论（`PERFECT_MATCH`、`ACCEPTABLE_DRIFT`、`REGRESSION_BLOCKED`）；
     - 平均 SSIM 结构相似度（基准阈值 $\ge 95.0\%$）；
     - 像素差异比率（量化最大视口漂移百分比）；
     - 差异聚类区域数（圈定高亮 BoundingBox 个数）；
   - **差异空间边界框表格与一键 Mask 屏蔽**：
     - 展示差异聚类 AABB 空间坐标（$x, y, w, h$）、差异像素数与严重度 Tag；
     - 支持“设为忽略 Mask”一键录入动态忽略区域（如轮播图、时钟时间戳），杜绝假阳性。
2. **API 客户端对接 (`frontend/src/api/visualRegressionA11y.ts`)**：
   - 对接后端 `/api/v1/visual/pixel-diff/compare` 与 `/api/v1/visual/noise-filter/masks` REST API。
3. **工作台挂载 (`frontend/src/views/workbench/ApiWorkbenchView.vue`)**：
   - 工具栏挂载 `<EyeOutlined /> 视觉 Diff 审视` 唤起按钮与抽屉响应式绑定。

## 质量与测试门禁验证

1. **组件单元测试 (`VisualPixelDiffInspectorDrawer.spec.ts` & `ApiWorkbenchView.spec.ts`)**：
   - `VisualPixelDiffInspectorDrawer.spec.ts`：2 passed；
   - `ApiWorkbenchView.spec.ts`：12 passed；
   - 总体 Vitest 套件：**14 passed 100%**。
2. **TypeScript 严格类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass!
3. **生产环境构建 (`vite build`)**：
   - 成功编译 4439 个模块，产物完整生成，耗时 15.81s，零构建错误。
