# UI3.1 移动端性能时序曲线与卡顿/内存泄露体检报告看板验收 (2026-10-16)

## 概述与结论

UI3.1（移动端性能时序曲线与卡顿/内存泄露体检报告看板）已完成全量交付与验证，正式开启 **ATP v3.5.0 Phase 3（多端原生性能剖析与深度质量诊断控制台）** 研发建设：
1. **API 客户端创建与导出 (`frontend/src/api/mobilePerf.ts` & `frontend/src/api/index.ts`)**：
   - 创建 `mobilePerfApi` 客户端封装：`startSession`、`appendSamples`、`stopSession`、`listSessions` 与 `getSession`；
   - 建立 `PerformanceSamplePoint`（CPU/内存 PSS/Native/Dalvik/FPS/Jank/Net TX/RX）、`DiagnosticAnomaly`、`MobilePerfSummary`、`MobilePerfSessionReport` 等强类型接口定义。
2. **移动端原生性能诊断全景看板组件 (`frontend/src/views/workbench/components/MobilePerfDiagnosticsViewer.vue`)**：
   - **体检诊断结论横幅 (Diagnostic Verdict Banner)**：智能归因健康状态（健康合格绿 / 轻中度警告黄 / 严重劣化红），呈现会话/设备/包名与采样点元数据；
   - **四大核心 KPI 卡片**：
     - App 平均 CPU / 峰值（带 75% 警戒水位判定）；
     - 物理内存峰值 PSS 与持续增长斜率（Linear Regression Slope，斜率 > 5.0 MB/min 触发高危泄露卡片标红）；
     - 平均渲染帧率 FPS 与累计 Jank 掉帧次数；
     - 检出性能异常项计数；
   - **ECharts 多维时序曲线区**：
     - CPU 计算负载（App CPU % 平滑面积图 vs 系统总 CPU % 折线图）；
     - 物理内存与堆栈（PSS / Native Heap / Dalvik Heap 三层折线堆叠）；
     - 渲染帧率与卡顿掉帧（FPS 折线图 + Jank 掉帧独立双轴柱状图）；
     - 网络 I/O 速率（上行 TX vs 下行 RX 吞吐图）；
   - **双列明细数据区**：
     - 性能体检与智能归因异常项表格（严重级别、指标实测值 vs 阈值对比、归因与建议）；
     - 时序采样点数据快照分页表格；
   - **交互弹窗**：支持启动新采样会话与按预设场景（内存泄露递增、频繁掉帧、健康基线）注入模拟时序点。
3. **移动工作台挂载集成 (`frontend/src/views/workbench/AppWorkbenchView.vue`)**：
   - 顶部工具栏挂载「原生性能体检」操作按钮；
   - 一键滑出 1060px 性能体检诊断抽屉，对移动端 App 运行时性能进行深度体检与诊断。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/MobilePerfDiagnosticsViewer.spec.ts`：**2 passed in 77ms**；
   - `src/views/workbench/components/HealingAuditTrailPanel.spec.ts`：**2 passed in 72ms**；
   - `src/views/workbench/AppWorkbenchView.spec.ts`：**8 passed in 1.3s**；
   - 核心工作台测试套件：**43 passed in 2.21s**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 13.38s, 0 errors**。
