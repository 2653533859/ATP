# UI1.3 真实流量特征聚类归一与自动化测试用例合成卡片验收 (2026-10-16)

## 概述与结论

UI1.3（真实流量特征聚类归一与自动化测试用例合成卡片）已完成全量交付与验证，至此 **ATP v3.9.0 Phase 1（生产流量网关镜像捕获、智能脱敏与用例聚类合成控制台）100% 达成全量大闭环**：
1. **API 客户端扩展 (`frontend/src/api/trafficGateway.ts` & `frontend/src/api/index.ts`)**：
   - 建立 `TrafficClusterItem`、`SynthesizedCaseItem`、`SynthesisReportItem`、`RunSynthesisRequest` 等强类型接口契约；
   - 封装 `trafficSynthesizerApi` 客户端方法：`runSynthesis`、`previewClusters`、`listReports` 与 `getReport`。
2. **流量用例智能合成卡片组件 (`TrafficToTestCaseSynthesizerCard.vue`)**：
   - **头部 Header 与参数微调栏**：
     - 支持协议筛选（ALL / HTTP / gRPC）、样本上限（默认 100 条）、单用例数据集行数上限（默认 10 行）、用例命名前缀；
     - 勾选「先脱敏清洗 PII (隐私合规)」，整合 T1.2 脱敏防护，保障测试资产安全合规；
     - 「一键聚类合成用例」主操作按钮，带执行中的 loading 交互；
     - 内置「高去重场景 (80%)」与「多端点混杂场景 (50%)」预设快速体验；
   - **聚类去重成效大横幅 (Deduplication Banner)**：
     - 大字徽章呈现聚类去重削峰率百分比（如 80.0%）；
     - 清晰展示数据流向指标：`原始捕获流量 (50)` → `归一聚合簇数 (10)` → `精简标准用例 (10)`；
     - 阐明根据动态路径归一化（如 `{id}`, `{uuid}`）与 Schema 结构指纹提炼大幅杜绝用例膨胀的收益；
   - **合成用例列表与下钻详情模态框 (TestCase Detail Modal)**：
     - 表格展示合成用例名称、协议、方法、归一化路径、聚合流量样本数、数据集行数；
     - 弹窗展示**智能合成断言列表**（状态码、时延 SLA 容差、业务 code 判定）、**请求体模板**与**参数化测试数据集样本表格**；
     - 「一键导入至当前项目」交互。
3. **接口测试工作台集成 (`ApiWorkbenchView.vue`)**：
   - 顶部工具栏挂载「流量用例合成」主要入口；
   - 随时一键滑出 1120px 宽幅控制台抽屉。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/TrafficToTestCaseSynthesizerCard.spec.ts`：**2 passed in 57ms**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed in 1.4s**；
   - 接口工作台核心测试套件：**18 passed in 670ms**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 10.11s, 0 errors**。
