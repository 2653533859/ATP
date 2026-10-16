# UI1.2 代码符号与自动化测试用例双向血缘图谱视图验收 (2026-10-16)

## 概述与结论

UI1.2（代码符号与自动化测试用例双向血缘图谱视图）已完成全量交付与验证：
1. **API 客户端扩展 (`frontend/src/api/ciImpact.ts` & `frontend/src/api/index.ts`)**：
   - 增加 `getMappingStats`（图谱总体统计指标）、`queryAffectedCases`（依据代码符号或 API 路由逆向反查受影响测试用例）与 `bindTestCase`（注册测试用例与符号/路由绑定）；
   - 建立 `TestCaseRefItem`、`MappingStats`、`RegisterBindingRequest`、`QueryAffectedCasesRequest` 等强类型接口契约。
2. **代码-用例双向血缘图谱全景视图 (`CodeToTestDependencyGraphView.vue`)**：
   - **核心血缘指标看板 (Metrics Cards)**：展示映射自动化用例数、源码类与函数符号数、覆盖 API 路由端点数与关联代码文件数；
   - **ECharts 关系力导向图 (Force-Directed Graph)**：
     - 4 类节点与配色：代码文件（File 蓝色）、函数/类符号（Symbol 紫色）、API 路由端点（Route 绿色）、自动化测试用例（TestCase 橙色）；
     - 连线可视化展示包含、暴露路由与测试覆盖关系，支持节点点击高亮与拖拽缩放；
   - **双栏交互面板**：
     - 节点属性剖析卡片：点击节点实时显示其标识、所属文件与优先级；
     - 变更影响面逆向快速反查：输入待修改函数符号或路由端点，一键查询受波及用例列表；
   - **用例血缘注册模态框 (Register Binding Modal)**：支持手动录入用例 ID、名称、绑定符号与 API 路由。
3. **路由配置 (`frontend/src/router/index.ts`)**：
   - 注册路由 `/quality/code-to-test-graph`（`code-to-test-dependency-graph`），受工程师与管理员权限管控。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/quality/CodeToTestDependencyGraphView.spec.ts`：**2 passed in 59ms**；
   - `src/router/navigationRoutes.spec.ts`：**2 passed in 3ms**；
   - `src/utils/chartTheme.spec.ts`：**2 passed in 28ms**；
   - 核心质量大盘与分析单测：**24 passed in 1.07s**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 2.57s, 0 errors**。
