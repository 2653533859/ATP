# UI2.1 测试资产全景引用拓扑图谱与孤儿资产看板验收 (2026-10-16)

## 概述与结论

UI2.1（测试资产全景引用拓扑图谱与孤儿资产看板）已完成全量交付与验证，正式拉开 **Phase 2（全域测试资产依赖拓扑与变更影响面控制台）** 序幕：
1. **API 客户端创建 (`frontend/src/api/assetGraph.ts`)**：
   - 封装 `getProjectGraph`、`getDownstream`、`getUpstream`、`getOrphans` 与 `reindex` 5 大资产图谱核心接口；
   - 建立 `AssetNode`、`AssetType`（plan/suite/case/dataset/api_endpoint/device）、`ProjectAssetGraphResponse` 与 `OrphanAssetsResponse` 强类型定义。
2. **交互图谱与看板组件 (`frontend/src/views/workbench/components/AssetDependencyGraphViewer.vue`)**：
   - 呈现资产总节点数、正向关联边数、孤儿用例数与孤儿数据源数 4 大 KPI；
   - 基于 ECharts 力导向图（Force Graph）呈现 Plan → Suite → Case → API / Dataset 全景资产拓扑；
   - 支持节点类别颜色区分（Plan 蓝、Suite 绿、Case 紫、API 橙、Dataset 青、Orphan 红）；
   - 支持点击图谱节点即时追溯正向被依赖项（Downstream）与上游来源依赖项（Upstream）；
   - 提供孤儿资产治理预警横幅与待治理孤儿用例快捷清单。
3. **接口测试工作台集成 (`frontend/src/views/workbench/ApiWorkbenchView.vue`)**：
   - 顶部工具栏挂载「全景资产图谱」按钮，支持快捷滑出大尺寸抽屉进行全景拓扑图谱查看与资产治理。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/AssetDependencyGraphViewer.spec.ts`：**3 passed in 76ms**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed in 432ms**；
   - 核心工作台测试套件：**30 passed**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 2.45s, 0 errors**。
