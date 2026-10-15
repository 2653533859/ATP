# F2.1 页面状态树（FSM）拓扑与状态指纹视图验收（2026-10-16）

## 概述与结论

F2.1（页面状态树拓扑与状态指纹视图）已完成全量前端代码演进、组件封装与自动化测试：
1. **探索会话拓扑 API 客户端与后端链路对齐 (`frontend/src/api/exploration.ts`)**：
   - 后端 `/exploration/sessions/{session_id}` 接口升级返回 `nodes` 与 `links` 状态机结构；
   - 前端创建 `exploration.ts` 客户端，定义 `ExplorationNode`、`ExplorationLink` 与 `ExplorationCoverageMetrics` 数据模式；
   - 开放 `explorationApi.getSession` 与 `explorationApi.step` 状态机查询方法。
2. **页面有限状态机 (FSM) 拓扑关系图组件 (`ExplorationGraphViewer.vue`)**：
   - **核心探索指标看板**：
     - 展示已发现页面状态数（States）、交互动作覆盖率（Actions %，带彩色进度条）、状态转移路径（Transitions）；
     - 高亮展示当前页面置换不变指纹哈希（State Hash，16 位防篡改哈希标签）；
   - **力导向拓扑关系图 (`VChart` / ECharts Graph)**：
     - 节点呈现页面名称、深度（Depth）与当前停留高亮边框；
     - 有向连线（Directed Edges）动态展示操作转移特征（如 `click(productCard)`、`back(systemBack)`）；
     - 鼠标悬停显示状态指纹与详细动作探索进度；
   - **状态指纹与候选动作详情抽屉**：
     - 选中任意节点即时查看该页面拥有的全部候选控件动作槽（Candidate Actions）；
     - 绿色标记已遍历动作与置灰待探索槽位；
   - **会话检索与示例装载**：支持输入真实探索 `session_id` 实时拉取最新状态图，或一键「载入示例状态树」。
3. **主工作台无缝集成 (`AIWorkbenchView.vue`)**：
   - 在 AI 工作台页面主网格下方集成「页面状态树拓扑与状态指纹视图」专属面板，基于 `defineAsyncComponent` 实现按需懒加载。

---

## 质量门禁与验证

1. **前端自动化测试**：
   - `src/views/workbench/components/ExplorationGraphViewer.spec.ts`：**2 passed in 2.88s**；
   - `src/views/workbench/AIWorkbenchView.spec.ts`：**5 passed in 1.38s**；
   - 全量 Vitest 测试套件：**88 个测试文件全部通过，共 410 项单测 100% PASS**。
2. **静态质量与类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean pass**；
   - `npm run build`：生产环境打包成功无警告（2.28s）。
